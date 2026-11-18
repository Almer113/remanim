"""HTTP routes and the WebSocket hub (protocol.md)."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

from aiohttp import WSMsgType, web
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .project import ROOT, Document, rel

WEB = ROOT / "studio" / "web" / "dist"
SKIP_DIRS = {".venv", "media", "node_modules", ".git", "studio/server", "studio/spikes", "studio/web",
             "__pycache__", ".claude"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
DEV_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}  # `npm run dev` (vite proxy)


def _host_name(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):
        return host[: host.find("]") + 1]
    return host.rsplit(":", 1)[0] if ":" in host else host


def _same_server(origin: str, host: str) -> bool:
    """http://localhost:8770 and http://127.0.0.1:8770 are both this server."""
    scheme, _, rest = origin.partition("://")
    port = lambda h: h.rsplit(":", 1)[1] if ":" in h and not h.endswith("]") else ""  # noqa: E731
    return scheme in ("http", "https") and _host_name(rest) in LOCAL_HOSTS and port(rest) == port(host)


@web.middleware
async def local_only(req: web.Request, handler):
    """Opening a file runs it and edits write code, so only this machine's
    own pages may talk to the server: the Host must be local (no DNS
    rebinding) and a browser's Origin must be this server."""
    if _host_name(req.host or "") not in LOCAL_HOSTS:
        raise web.HTTPForbidden(text="the studio only answers on localhost")
    origin = req.headers.get("Origin")
    if origin is not None and origin not in DEV_ORIGINS and not _same_server(origin, req.host):
        raise web.HTTPForbidden(text="cross-origin requests are not allowed")
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
                             and (f"{r_here}/{d}" if r_here else d) not in SKIP_DIRS and not d.startswith("."))
        paths += [here / f for f in filenames if f.endswith(".py")]
    for p in sorted(paths, key=lambda x: rel(x)):
        r = rel(p)
        try:
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
        doc = Document(ROOT / name, [], self.notify)
        self.docs[doc.name] = doc
        if self.api is None:
            r = await doc.worker.request({"op": "hello"})
            self.api = r.get("api", [])
        doc.api = set(self.api)
        asyncio.create_task(doc.load())
        return doc

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


async def frame(req: web.Request):
    doc = _doc(req)
    q = req.query
    rev = int(q.get("rev", doc.rev))
    if rev != doc.rev:
        raise web.HTTPGone(text="old revision")
    size, fmt = q.get("size", "full"), q.get("fmt", "png")
    r = await doc.frame(q["scene"], int(q["f"]), size, fmt, ids=q.get("ids") == "1")
    if "error" in r:
        return web.json_response(r["error"], status=500)
    return web.Response(body=r["image"], content_type="image/jpeg" if fmt == "jpeg" else "image/png",
                        headers={"Cache-Control": "max-age=3600, immutable"})


async def objects(req: web.Request):
    doc = _doc(req)
    q = req.query
    if int(q.get("rev", doc.rev)) != doc.rev:
        raise web.HTTPGone(text="old revision")
    r = await doc.frame(q["scene"], int(q["f"]), "full", "png", ids=True)
    if "error" in r:
        return web.json_response({"error": r["error"]}, status=500)
    return web.json_response({"objects": r.get("objects", []), "rev": doc.rev, "f": int(q["f"])})


async def idmap(req: web.Request):
    doc = _doc(req)
    q = req.query
    r = await doc.frame(q["scene"], int(q["f"]), "full", "png", ids=True)
    if "error" in r:
        return web.json_response(r["error"], status=500)
    return web.Response(body=r["idmap"], content_type="image/png",
                        headers={"Cache-Control": "max-age=3600, immutable"})


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
                reply = await handle(msg)
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


async def handle(msg: dict) -> dict | None:
    t = msg.get("type")
    if t == "open":
        await hub.open(msg["file"])
        return None
    doc = hub.docs.get(msg.get("file", ""))
    if doc is None:
        return {"type": "error", "message": "file not open"}
    if t == "scene":
        await doc.activate(msg["scene"])
        await doc.send_model()
        return None
    if t in ("edit.timing", "edit.prop"):
        return await doc.edit(msg)
    if t == "edit.confirm":
        return await doc.confirm(msg["token"])
    if t == "edit.cancel":
        doc.pending.pop(msg.get("token"), None)
        return {"type": "edit.cancelled"}
    if t in ("undo", "redo"):
        return await doc.undo_redo(t)
    return {"type": "error", "message": f"unknown message {t}"}


async def index(req):
    p = WEB / "index.html"
    if not p.exists():
        return web.Response(text="The web UI isn't built yet: cd studio/web && npm run build",
                            content_type="text/plain")
    return web.FileResponse(p, headers={"Cache-Control": "no-cache"})


async def on_startup(app):
    hub.loop = asyncio.get_running_loop()
    hub.start_watching()


async def on_cleanup(app):
    if hub.observer:
        hub.observer.stop()
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
    app.router.add_get("/ws", ws_handler)
    if (WEB / "assets").exists():
        app.router.add_static("/assets", WEB / "assets")
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
