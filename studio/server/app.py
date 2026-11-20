"""HTTP routes and the WebSocket hub (protocol.md)."""

from __future__ import annotations

import ast
import asyncio
import hmac
import re
import json
import os
import threading
import warnings
from pathlib import Path

from aiohttp import WSMsgType, web
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .export import Exporter, ExportError
from .claude_panel import ClaudePanel
from .host import WorkerHandle
from .project import ROOT, Document, rel

WEB = ROOT / "studio" / "web" / "dist"
# tests and benches start engines themselves; a spare would only cost memory
NO_SPARE = os.environ.get("STUDIO_NO_SPARE") == "1"
SKIP_DIRS = {".venv", "media", "node_modules", ".git", "studio/server", "studio/spikes", "studio/web",
             "__pycache__", ".claude"}
HIDDEN_DIRS = {"studio/tests/tmp"}  # copies the tests make: openable, but not listed
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
DEV_ORIGINS: set[str] = set()  # `--dev`: the vite dev server (`npm run dev`) on 5173 may call in
VITE_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
TRUSTED_HOSTS: set[str] = set()  # opt-in extra names (`--allow-host`), e.g. a tailnet proxy; empty by default
# a name other than localhost is reached by other machines: they need this token
# (from the link printed at start-up, then a cookie); set by __main__ with --allow-host
ACCESS_TOKEN = ""
# the Claude panel runs an agent on this machine: pages from a trusted (tailnet) name
# may use it only when the server was started with --allow-claude-remote
CLAUDE_REMOTE = False
TOKEN_COOKIE = "studio_token"


def _known_host(name: str) -> bool:
    return name in LOCAL_HOSTS or name in TRUSTED_HOSTS


def _host_name(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host[: host.find("]") + 1]
    return host.rsplit(":", 1)[0] if ":" in host else host


def _same_server(origin: str, host: str) -> bool:
    """http://localhost:8770 and http://127.0.0.1:8770 are both this server;
    a trusted (tailnet) name only matches itself."""
    scheme, _, rest = origin.partition("://")
    port = lambda h: h.rsplit(":", 1)[1] if ":" in h and not h.endswith("]") else ""  # noqa: E731
    o, h = _host_name(rest), _host_name(host)
    same = o == h or (o in LOCAL_HOSTS and h in LOCAL_HOSTS)
    return scheme in ("http", "https") and same and port(rest) == port(host)


@web.middleware
async def local_only(req: web.Request, handler):
    """Opening a file runs it and edits write code, so only this machine's
    own pages may talk to the server: the Host must be local (no DNS
    rebinding) and a browser's Origin must be this server."""
    name = _host_name(req.host or "")
    if not _known_host(name):
        raise web.HTTPForbidden(text="the studio only answers on localhost")
    set_cookie = False
    if name not in LOCAL_HOSTS:
        # another machine (a tailnet name): only with the start-up link's token
        given = req.cookies.get(TOKEN_COOKIE) or ""
        if not (ACCESS_TOKEN and hmac.compare_digest(given, ACCESS_TOKEN)):
            q = req.query.get("token", "")
            if not (ACCESS_TOKEN and q and hmac.compare_digest(q, ACCESS_TOKEN)):
                raise web.HTTPForbidden(text="open the link the studio printed when it started (it carries a token)")
            set_cookie = True
    origin = req.headers.get("Origin")
    if origin is not None and origin not in DEV_ORIGINS and not _same_server(origin, req.host):
        raise web.HTTPForbidden(text="cross-origin requests are not allowed")
    # `<img src="http://127.0.0.1:8770/frame?...">` on another site sends no Origin
    if req.headers.get("Sec-Fetch-Site") == "cross-site" and origin not in DEV_ORIGINS:
        raise web.HTTPForbidden(text="cross-site requests are not allowed")
    if set_cookie:
        # drop the token from the address bar; the cookie carries it from here on
        resp = web.HTTPFound(req.rel_url.with_query({k: v for k, v in req.query.items() if k != "token"}))
        resp.set_cookie(TOKEN_COOKIE, ACCESS_TOKEN, httponly=True, secure=True, samesite="Strict",
                        max_age=7 * 24 * 3600)
        raise resp
    return await handler(req)


def normalise(name: str) -> str:
    """The project-relative name of a scene file the studio may open."""
    path = (ROOT / str(name)).resolve()
    if ROOT not in path.parents or path.suffix != ".py" or not path.is_file():
        raise web.HTTPBadRequest(text="not a scene file in this project")
    r = rel(path)
    parts = r.split("/")[:-1]
    if any(p in SKIP_DIRS or p.startswith(".") or "/".join(parts[: i + 1]) in SKIP_DIRS
           for i, p in enumerate(parts)):
        raise web.HTTPBadRequest(text="that folder holds tools, not scenes")
    return r


def scene_files() -> list[dict]:
    """Python files under the project that define a Scene subclass."""
    import os
    out = []
    paths = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        here = Path(dirpath)
        r_here = "" if here == ROOT else rel(here)
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and (f"{r_here}/{d}" if r_here else d) not in SKIP_DIRS | HIDDEN_DIRS
                             and not d.startswith("."))
        paths += [here / f for f in filenames if f.endswith(".py")]
    for p in sorted(paths, key=lambda x: rel(x)):
        r = rel(p)
        try:
            with warnings.catch_warnings():   # other people's files: `'\i'` escapes and the like
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(p.read_bytes())
        except (SyntaxError, ValueError):
            out.append({"path": r, "scenes": [], "error": "doesn't parse"})
            continue
        scenes = []
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                bases = [ast.unparse(b) for b in n.bases]
                if any("Scene" in b or "Beat" in b for b in bases):
                    scenes.append(n.name)
        if scenes:
            out.append({"path": r, "scenes": scenes})
    return out


class Hub:
    def __init__(self):
        self.clients: set[web.WebSocketResponse] = set()
        self.docs: dict[str, Document] = {}
        self.api: list[str] | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.observer: Observer | None = None
        self._debounce: dict[str, asyncio.TimerHandle] = {}
        self.exporter = Exporter(self.notify)
        self.claude = ClaudePanel(self.notify)
        self.spare: WorkerHandle | None = None  # an engine started ahead: opening a file skips ~5 s

    def take_spare(self) -> WorkerHandle | None:
        """The waiting engine, if there is one; a new one starts for next time."""
        w, self.spare = self.spare, None
        if w is not None and (w.closed or w.proc is None or not w.proc.is_alive()):
            w = None
        if self.loop is not None:
            self.loop.call_later(2.0, self._new_spare)
        return w

    def _new_spare(self):
        if self.spare is None and not NO_SPARE:
            self.spare = WorkerHandle("")

    async def notify(self, msg: dict):
        data = json.dumps(msg)
        for ws in list(self.clients):
            try:
                await ws.send_str(data)
            except Exception:
                self.clients.discard(ws)

    async def open(self, name: str) -> Document:
        name = normalise(name)
        doc = self.docs.get(name)
        if doc is not None:
            await doc.send_model()
            return doc
        doc = Document(ROOT / name, [], self.notify, worker=self.take_spare())
        self.docs[doc.name] = doc
        if self.api is None:
            r = await doc.worker.request({"op": "hello"})
            if r.get("api"):   # a cold first import can time out: never cache "no names"
                self.api = r["api"]
        doc.api = set(self.api or ())
        asyncio.create_task(self._load(doc))
        return doc

    async def _load(self, doc: Document):
        await doc.load()
        if self.api is None:   # hello failed: ask again now the worker is warm
            r = await doc.worker.request({"op": "hello"})
            if r.get("api"):
                self.api = r["api"]
                doc.api = set(self.api)
                doc._census = None   # tiers depend on which names are the library's
                await doc.send_model()

    # -- file watching --------------------------------------------------------
    def start_watching(self):
        hub = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                for p in (getattr(event, "src_path", None), getattr(event, "dest_path", None)):
                    if p and str(p).endswith(".py"):
                        hub.loop.call_soon_threadsafe(hub._changed, str(p))

        self.observer = Observer()
        self.observer.schedule(Handler(), str(ROOT), recursive=True)
        self.observer.daemon = True
        self.observer.start()

    def _changed(self, path: str):
        try:
            name = rel(Path(path))
        except ValueError:
            return
        doc = self.docs.get(name)
        if doc is None:
            # a module that open files import (style.py, manim_kit.py): their engines restart
            for d in list(self.docs.values()):
                if d.depends_on(Path(path)):
                    key = "dep:" + d.name
                    h = self._debounce.pop(key, None)
                    if h:
                        h.cancel()
                    self._debounce[key] = self.loop.call_later(
                        0.3, lambda d=d: asyncio.ensure_future(d.deps_changed()))
            return
        h = self._debounce.pop(name, None)
        if h:
            h.cancel()
        self._debounce[name] = self.loop.call_later(
            0.2, lambda: asyncio.ensure_future(doc.file_changed()))


hub = Hub()


def _doc(req) -> Document:
    doc = hub.docs.get(req.query.get("file", ""))
    if doc is None:
        raise web.HTTPNotFound(text="file not open")
    return doc


def _int(q, key: str, default: int | None = None) -> int:
    """A whole-number query parameter; a missing or malformed one is the
    client's mistake (400), not a server error."""
    v = q.get(key)
    if v is None and default is not None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text=f"{key} must be a whole number")


def _still(doc: Document, rev: int):
    """The code changed (an edit, undo or save) before or while this was
    rendered: the answer belongs to no revision, and must not be cached
    under this one's URL."""
    if rev != doc.rev:
        raise web.HTTPGone(text="old revision")


async def frame(req: web.Request):
    doc = _doc(req)
    q = req.query
    rev = _int(q, "rev", doc.rev)
    if rev != doc.rev:
        raise web.HTTPGone(text="old revision")
    size, fmt = q.get("size", "full"), q.get("fmt", "png")
    r = await doc.frame(q["scene"], _int(q, "f"), size, fmt, ids=q.get("ids") == "1")
    _still(doc, rev)
    if "error" in r:
        return web.json_response(r["error"], status=500)
    return web.Response(body=r["image"], content_type="image/jpeg" if fmt == "jpeg" else "image/png",
                        headers={"Cache-Control": "max-age=3600, immutable"})


async def objects(req: web.Request):
    doc = _doc(req)
    q = req.query
    rev = _int(q, "rev", doc.rev)
    _still(doc, rev)
    r = await doc.frame(q["scene"], _int(q, "f"), "full", "png", ids=True)
    _still(doc, rev)
    if "error" in r:
        return web.json_response({"error": r["error"]}, status=500)
    return web.json_response({"objects": r.get("objects", []), "camera": r.get("camera"),
                              "ghosts": r.get("ghosts"), "rev": doc.rev,
                              "f": _int(q, "f")})


async def glyphs(req: web.Request):
    """One Text / MathTex / Tex's glyph boxes and the source characters
    behind each (Phase 5 step 6). Asked for when the user selects inside a
    formula, since the first probe of a formula costs a LaTeX compile."""
    doc = _doc(req)
    q = req.query
    rev = _int(q, "rev", doc.rev)
    _still(doc, rev)
    r = await doc.glyphs(q["scene"], _int(q, "f"), q.get("id", ""))
    _still(doc, rev)
    if "error" in r:
        return web.json_response({"error": r["error"]}, status=500)
    return web.json_response({"glyphs": r.get("glyphs"), "rev": doc.rev, "f": _int(q, "f"), "id": q.get("id")})


async def idmap(req: web.Request):
    doc = _doc(req)
    q = req.query
    rev = _int(q, "rev", doc.rev)
    _still(doc, rev)
    r = await doc.frame(q["scene"], _int(q, "f"), "full", "png", ids=True)
    _still(doc, rev)
    if "error" in r:
        return web.json_response(r["error"], status=500)
    return web.Response(body=r["idmap"], content_type="image/png",
                        headers={"Cache-Control": "max-age=3600, immutable"})


_sound: dict = {}  # (file, rev, scene) -> (wav bytes, waveforms); last few only
_sound_lock = threading.Lock()   # /audio and /audio/peaks arrive together: mix once


def _scene_sound(doc: Document, scene: str, rev: int):
    from . import audio
    key = (doc.name, rev, scene)
    with _sound_lock:
        if key in _sound:
            return _sound[key]
        tr = doc.traces.get(scene)
        if tr is None or doc.rev != rev:
            raise web.HTTPNotFound(text="scene not traced at this revision")
        problems: list = []
        _sound[key] = (audio.wav_bytes(audio.mix(tr, problems)), audio.waveforms(tr))
        for msg in problems:
            print(f"[audio] {doc.name} {scene}: {msg}", flush=True)
        while len(_sound) > 8:
            _sound.pop(next(iter(_sound)))
        return _sound[key]


async def sound(req: web.Request):
    doc = _doc(req)
    q = req.query
    rev = _int(q, "rev", doc.rev)
    if rev != doc.rev:
        raise web.HTTPGone(text="old revision")
    wav, _ = await asyncio.to_thread(_scene_sound, doc, q["scene"], rev)
    return _ranged(req, wav, "audio/wav", {"Cache-Control": "max-age=3600, immutable"})


def _ranged(req: web.Request, body: bytes, ctype: str, headers: dict) -> web.Response:
    """Answer `Range: bytes=a-b` with a 206, so the browser can seek the
    sound (without it, Chrome plays a WAV from 0 whatever currentTime says)."""
    headers = {**headers, "Accept-Ranges": "bytes"}
    rng = req.headers.get("Range", "")
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return web.Response(body=body, content_type=ctype, headers=headers)
    n = len(body)
    if m.group(1):
        a = int(m.group(1))
        b = min(int(m.group(2)), n - 1) if m.group(2) else n - 1
    else:  # the last k bytes
        a, b = max(0, n - int(m.group(2))), n - 1
    if a >= n or a > b:
        return web.Response(status=416, headers={**headers, "Content-Range": f"bytes */{n}"})
    return web.Response(status=206, body=body[a:b + 1], content_type=ctype,
                        headers={**headers, "Content-Range": f"bytes {a}-{b}/{n}"})


async def sound_peaks(req: web.Request):
    doc = _doc(req)
    q = req.query
    rev = _int(q, "rev", doc.rev)
    if rev != doc.rev:
        raise web.HTTPGone(text="old revision")
    _, waves = await asyncio.to_thread(_scene_sound, doc, q["scene"], rev)
    return web.json_response({"rev": doc.rev, "scene": q["scene"], "sounds": waves})


async def files(req):
    return web.json_response(await asyncio.to_thread(scene_files))


async def status(req):
    doc = hub.docs.get(req.query.get("file", ""))
    if doc is None:  # polled before the file is open: nothing to report yet
        return web.json_response({})
    r = await doc.worker.request({"op": "status", "scene": doc.active}) if doc.active else {}
    cached = sum(1 for k in doc.frames.items if k[0] == doc.rev and k[1] == doc.active and k[3] == "half")
    return web.json_response({**r, "cached": cached, "frames": doc.frame_count(doc.active) if doc.active else 0,
                              "restarts": doc.worker.restarts})


def gate(msg: dict, host: str) -> dict | None:
    """The reply refusing a message this page may not send, or None. Pages
    reached through an --allow-host name (another machine) may not open
    windows here, nor run Claude Code unless --allow-claude-remote."""
    local = _host_name(host) in LOCAL_HOSTS
    t = str(msg.get("type", ""))
    if t == "export.reveal" and not local:
        return {"type": "error", "message": "show in folder works on the studio's own computer only"}
    if t.startswith("claude.") and not (local or CLAUDE_REMOTE):
        return {"type": "claude.status", "available": False, "busy": False,
                "why": "the Claude panel is off for other machines (start the studio with "
                       "--allow-claude-remote to allow it)"}
    return None


async def ws_handler(req):
    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=64 * 1024 * 1024)
    await ws.prepare(req)
    hub.clients.add(ws)
    try:
        async for m in ws:
            if m.type != WSMsgType.TEXT:
                continue
            try:
                msg = json.loads(m.data)
                reply = gate(msg, req.host) or await handle(msg)
            except web.HTTPException as e:
                reply = {"type": "error", "message": e.text}
            except Exception as e:  # never drop the socket over one bad message
                reply = {"type": "error", "message": f"{type(e).__name__}: {e}"}
            if reply:
                if "seq" in msg:
                    reply["seq"] = msg["seq"]
                await ws.send_str(json.dumps(reply))
    finally:
        hub.clients.discard(ws)
    return ws


async def new_file(msg: dict) -> dict:
    """A new scene file from the code_spec §6 template; never overwrites."""
    import re
    from .code.inserts import new_file_text
    from .code.splice import EditError, write_atomic
    name = str(msg.get("name") or "").strip().replace("\\", "/")
    if not re.fullmatch(r"[A-Za-z_][\w-]*(/[A-Za-z_][\w-]*)*\.py", name) or ".." in name:
        return {"type": "error", "message": "a file name like my_scene.py (letters, digits, _ and -)"}
    path = (ROOT / name).resolve()
    if ROOT not in path.parents:
        return {"type": "error", "message": "not inside the project"}
    parts = rel(path).split("/")[:-1]
    if any(p in SKIP_DIRS or p.startswith(".") or "/".join(parts[: i + 1]) in SKIP_DIRS | HIDDEN_DIRS
           for i, p in enumerate(parts)):
        return {"type": "error", "message": "that folder holds tools, not scenes"}
    if path.exists():
        return {"type": "error", "message": f"{name} already exists"}
    scene = str(msg.get("scene") or "") or "".join(w.capitalize() for w in re.split(r"[_\W]+", path.stem) if w) \
        or "NewScene"
    if not scene[0].isalpha():
        scene = "Scene" + scene
    from .code.inserts import SHAPES
    if scene in set(hub.api or ()) | set(SHAPES) | {"Scene", "TimedScene", "VGroup", "Group"}:
        # circle.py must not define `class Circle`: the next Circle dropped in would make the scene
        scene += "Scene"
    try:
        text = new_file_text(scene)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, text.encode("utf-8"))
    except (EditError, OSError) as e:
        return {"type": "error", "message": str(e)}
    return {"type": "file.created", "file": rel(path), "scene": scene}


async def handle(msg: dict) -> dict | None:
    t = msg.get("type")
    if t == "open":
        await hub.open(msg["file"])
        return None
    if t == "file.new":  # needs no open file
        return await new_file(msg)
    if t == "export.cancel":
        return await hub.exporter.cancel(str(msg.get("id", "")))
    if t == "claude.status":
        return hub.claude.status()
    if t == "claude.ask":
        ctx = msg.get("context") if isinstance(msg.get("context"), dict) else {}
        return await hub.claude.ask(str(msg.get("prompt") or ""), ctx, msg.get("session"))
    if t == "claude.stop":
        return await hub.claude.stop()
    if t == "export.reveal":
        p = hub.exporter.file_of(str(msg.get("id", "")), _int(msg, "i", 0))
        if p is None:
            return {"type": "error", "message": "no such export file"}
        reveal(p)
        return {"type": "export.revealed"}
    if t == "export.list":
        return {"type": "export.jobs", "jobs": [j.view() for j in hub.exporter.jobs.values()]}
    doc = hub.docs.get(msg.get("file", ""))
    if doc is None:
        return {"type": "error", "message": "file not open"}
    if t == "scene":
        await doc.activate(msg["scene"])
        await doc.send_model()
        return None
    if t in ("edit.timing", "edit.prop", "edit.move", "edit.scale", "edit.rotate", "edit.insert", "edit.composite",
             "edit.preset", "edit.duplicate", "edit.group", "edit.delete", "edit.delete_clip",
             "edit.voice", "edit.shift", "edit.offset", "edit.merge", "edit.split", "edit.reorder",
             "edit.scene_order", "edit.section", "edit.literal",
             "edit.part_colour", "edit.curve",
             "edit.transform_kind", "edit.match_parts", "edit.camera"):
        return await doc.edit(msg)
    if t == "edit.confirm":
        return await doc.confirm(msg["token"])
    if t == "edit.cancel":
        doc.pending.pop(msg.get("token"), None)
        return {"type": "edit.cancelled"}
    if t == "stop":
        return await doc.stop()
    if t in ("undo", "redo"):
        return await doc.undo_redo(t)
    if t == "export.start":
        if not doc.meta.get("scenes"):
            return {"type": "error", "message": "the file has no scenes that run yet"}
        try:
            return await hub.exporter.start(doc.name, msg.get("spec") or {}, list(doc.meta["scenes"]))
        except ExportError as e:
            return {"type": "error", "message": str(e)}
    return {"type": "error", "message": f"unknown message {t}"}


def reveal(p):
    """Show a file in the system's file manager, selected where it can be."""
    import subprocess
    import sys
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{p}"])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent)])


async def export_file(req: web.Request):
    """A file an export made, by job and index (never a path from the client)."""
    p = hub.exporter.file_of(req.query.get("job", ""), _int(req.query, "i", 0))
    if p is None:
        raise web.HTTPNotFound(text="no such export file")
    return web.FileResponse(p, headers={"Cache-Control": "no-cache"})


async def index(req):
    p = WEB / "index.html"
    if not p.exists():
        return web.Response(text="The web UI isn't built yet: cd studio/web && npm run build",
                            content_type="text/plain")
    return web.FileResponse(p, headers={"Cache-Control": "no-cache"})


async def on_startup(app):
    hub.loop = asyncio.get_running_loop()
    hub.start_watching()
    hub._new_spare()


async def on_cleanup(app):
    if hub.observer:
        hub.observer.stop()
    if hub.spare is not None:
        hub.spare.close()
    hub.claude.close()
    for d in hub.docs.values():
        d.close()


def make_app() -> web.Application:
    app = web.Application(client_max_size=64 * 1024 * 1024, middlewares=[local_only])
    app.router.add_get("/", index)
    app.router.add_get("/api/files", files)
    app.router.add_get("/api/status", status)
    app.router.add_get("/frame", frame)
    app.router.add_get("/objects", objects)
    app.router.add_get("/idmap", idmap)
    app.router.add_get("/glyphs", glyphs)
    app.router.add_get("/audio", sound)
    app.router.add_get("/audio/peaks", sound_peaks)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/export/file", export_file)
    if (WEB / "assets").exists():
        app.router.add_static("/assets", WEB / "assets")
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
