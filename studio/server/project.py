"""Open files: exact bytes, revisions, the scene model, edits and undo.

The .py file is the only state (architecture.md §1). A Document holds the
bytes it last read or wrote; every edit is planned, verified by replay in
the worker, written atomically, and then reloaded like any other change.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import math
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from .code import inserts
from .code import literals as literalplan
from .code import moves as moveplan
from .code import planner
from .code import tex as texplan
from .code import graphs as graphplan
from .code import transforms as transformplan
from .code import camera as cameraplan
from .code import scenes
from .code import timeline
from .code.census import classify, summary
from .code.source import Source, Span
from .code.splice import Edit, EditError, apply, number_of, write_atomic
from .code.splice import fmt as fmt_num
from . import tracecache
from .host import WorkerHandle

ROOT = Path(__file__).resolve().parents[2]
# Revisions restart at 1 with every server run; frame URLs carry this too,
# so the browser never shows a cached frame from an earlier run.
SESSION = secrets.token_hex(4)


@dataclass
class UndoStep:
    before: bytes
    after: bytes
    note: str


@dataclass
class Pending:
    """An edit waiting for the user to accept its side effect."""
    token: str
    scene: str
    data: bytes
    note: str
    edits: list
    checks: dict
    target: dict
    base: bytes = b""  # the bytes `data` was planned from
    verified: bool = False  # already replayed and measured (canvas edits)


class FrameCache:
    def __init__(self, limit_bytes: int = 400 * 1024 * 1024):
        self.items: OrderedDict = OrderedDict()
        self.size = 0
        self.limit = limit_bytes

    def get(self, key):
        v = self.items.get(key)
        if v is not None:
            self.items.move_to_end(key)
        return v

    def put(self, key, value: dict):
        n = sum(len(v) for v in value.values() if isinstance(v, (bytes, bytearray)))
        if key in self.items:
            return
        self.items[key] = value
        self.size += n
        while self.size > self.limit and self.items:
            _, old = self.items.popitem(last=False)
            self.size -= sum(len(v) for v in old.values() if isinstance(v, (bytes, bytearray)))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()



def _timings(trace: dict) -> list:
    """Every event's kind, start and length, to compare two replays."""
    return [(e.get("kind"), round(e.get("start", 0), 3), round(e.get("duration", 0), 3))
            for e in trace.get("events") or []]


def content_end(tr: dict) -> float:
    """When the scene's own content ends: its last play() / wait() made from
    the scene file, or the last narration line (spoken, or its caption held),
    whichever is later. Padding to TARGET is not content."""
    end = 0.0
    for e in tr.get("events") or []:
        if e.get("call") is not None:
            end = max(end, e["start"] + e["duration"])
    for ln in (tr.get("audio") or {}).get("lines", []):
        end = max(end, ln["start"] + max(ln.get("duration") or 0.0, ln.get("hold") or 0.0))
    return round(end, 4)


# animations that take things off the screen (Phase 7 step 6)
REMOVERS = {"FadeOut", "Uncreate", "Unwrite", "ShrinkToCenter", "FadeOutAndShift"}
SPEECH_GRACE = 0.5  # s into a line before a fade counts as mid-sentence


def speech_warnings(tr: dict | None) -> dict[int, str]:
    """Event index → a warning, for animations that take things away while a
    narration line is still being spoken: they start during the line and end
    before it does. Warnings only: some fades over speech are deliberate."""
    out: dict[int, str] = {}
    if not tr:
        return out
    lines = [(ln["start"], ln["start"] + (ln.get("duration") or 0.0), ln.get("text") or "")
             for ln in (tr.get("audio") or {}).get("lines", []) if ln.get("duration")]
    events = tr.get("events") or []
    # when each object was first brought on by an animation; objects never animated
    # in (self.add) count as there from the start
    first: dict[str, float] = {}
    for ev in events:
        for a in ev.get("anims") or []:
            if a.get("mobject") and a.get("class") not in REMOVERS:
                first.setdefault(a["mobject"], ev["start"])
    for i, ev in enumerate(events):
        if ev.get("kind") != "play":
            continue
        rm = [a for a in ev.get("anims") or [] if a.get("class") in REMOVERS]
        if not rm:
            continue
        s, e = ev["start"], ev["start"] + ev["duration"]
        for ls, le, text in lines:
            # something brought in during this line and taken away again is a
            # pointer for the words (an arrow, a label): only older things count
            # and a fade in the line's first half second clears the stage for what it
            # says (a title going as the next part starts): only fades later in it count
            gone = sorted({a["class"] for a in rm if first.get(a.get("mobject"), -1.0) < ls - 1e-3})
            if gone and ls + SPEECH_GRACE <= s < le and e < le - 0.05:
                words = text if len(text) <= 32 else text[:30].rstrip() + "…"
                out[i] = (f"{'/'.join(gone)} ends {le - e:.1f} s before the line \u201c{words}\u201d does "
                          f"(at {le:.2f} s): things leave mid-sentence")
                break
    return out


def _stop_reason(err: dict) -> str:
    """Why an edited scene was refused, with a hint for errors whose cause
    is in the scene rather than in the edit."""
    m = err.get("message", "")
    tex = latex_error(m)
    if tex:
        return f"LaTeX can't compile the new text: {tex}" + (f" (line {err['line']})" if err.get("line") else "")
    why = f"the edited scene stops with {m}" + (f" (line {err['line']})" if err.get("line") else "")
    if "zip()" in m and "families_zipped" in (err.get("traceback") or ""):
        why += (". An object changed its number of parts while an animation ran, most often a "
                "FadeIn/FadeOut of an always_redraw object (a ClippedGrid) that is still moving; "
                "the edit only changed the timing it happens at. Fade it while it is still")
    return why


def latex_error(message: str) -> str | None:
    """LaTeX's own words, which the engine adds to a TeX error as "[LaTeX:
    ...]" (it reads the log at once: Manim deletes it after the next
    compile); "see the LaTeX log" when it couldn't; None if this isn't one."""
    if "error converting to" not in message:
        return None
    m = re.search(r"\[LaTeX: (.*)\]\s*$", message)
    return m.group(1) if m else "see the LaTeX log"


_BOOKMARK = re.compile(r"<bookmark\s+mark\s*=\s*['\"][^'\"]*['\"]\s*/>")


def _tts_failed(err: dict) -> bool:
    """Text-to-speech, not the scene, failed (offline, service down)."""
    m = err.get("message", "")
    tb = err.get("traceback") or ""
    return "Edge TTS failed" in m or "edge_tts_service" in tb or "edge_tts" in tb


class Document:
    def __init__(self, path: Path, api: list[str], notify, worker: WorkerHandle | None = None):
        self.path = path.resolve()
        self.name = rel(self.path)
        self.api = set(api)
        self.notify = notify  # async callback(dict) to every client
        self.data = self.path.read_bytes()
        self.rev = 0
        self.src = Source(self.data)
        if worker is not None:  # a spare engine, already started (Hub.take_spare)
            worker.path, worker.on_restart = str(self.path), self._restarted
            self.worker = worker
        else:
            self.worker = WorkerHandle(str(self.path), on_restart=self._restarted)
        self.meta: dict = {}           # scenes, fps, size
        self.traces: dict[str, dict] = {}
        self.error: dict | None = None
        self.undo: list[UndoStep] = []
        self.redo: list[UndoStep] = []
        self.pending: dict[str, Pending] = {}
        self.frames = FrameCache()
        # revisions with the same content (bytes, imported modules, quality) draw the
        # same frames: an undo finds the earlier revision's frames (Phase 7 step 13)
        self._content_rev: dict[tuple, int] = {}
        self._same_as: dict[int, int] = {}
        self.active: str | None = None
        self.edit_lock = asyncio.Lock()
        self.load_lock = asyncio.Lock()
        self.last_write: bytes | None = None
        self.prefetch_task: asyncio.Task | None = None
        self.tracing: tuple[str, float, bytes] | None = None   # (scene, or "" for the module; start; bytes)
        self._stopped: dict[bytes, set] = {}               # bytes → what the user stopped in them

    # -- loading -------------------------------------------------------------
    async def load(self):
        """(Re)load the current bytes into the worker and trace the scenes.
        Loads never overlap: a second one waits, then traces the newest bytes."""
        self._load_gen = gen = getattr(self, "_load_gen", 0) + 1
        async with self.load_lock:
            if gen != self._load_gen:
                return  # a newer load is queued behind us and will trace newer bytes
            await self._load(gen)

    async def _load(self, gen: int):
        # the bytes this load is for: self.data can change while it awaits (a
        # save), and an old trace must never be filed under the new bytes
        data = self.data
        self.rev += 1
        self.pending.clear()  # planned against the old bytes
        self.src = Source(data)
        self.error = None
        # cleared first: a reply waiting on this reload (_reload_for_reply) must not
        # take the old revision's traces for the new one
        self.traces = {}
        # While the file doesn't run, the studio keeps showing the last version
        # that did (self.good: its bytes, source, meta and traces; the worker
        # keeps that engine loaded), read-only, beside the error.
        good = getattr(self, "good", None)
        if not self.src.ok:
            e = self.src.error
            self.error = {"code": "parse", "message": f"SyntaxError: {e.msg}", "line": e.lineno}
            self._show_good(good)
            await self.send_model()
            return
        # the modules it imports, and their bytes, as they were before the engine
        # read them: a module saved during the load must not be cached as read
        deps_before = sorted(set(getattr(self, "deps", [])) | set(self._static_deps()))
        seen_before = tracecache.deps_digest(self.path, deps_before)
        if data in self._stopped and "" in self._stopped[data]:
            r = {"error": {"code": "stopped", "line": None, "message": "stopped: the file ran too long while "
                                                                       "loading (an endless loop?); fix it and save"}}
        else:
            self.tracing = ("", time.monotonic(), data)
            await self.send_status()
            r = await self._engine({"op": "load", "data": data, "path": str(self.path)})
            self.tracing = None
            await self.send_status()  # the UI's "loading…" pill ends here, whatever the outcome
        if "error" in r:
            self.error = {"code": "crash", **r["error"]}
            # fixing a module it imports must reload it, even if it never ran here
            self.deps = sorted(set(deps_before) | set(r.get("deps") or []))
            self._deps_seen = seen_before
            if data in self._stopped and "" in self._stopped[data]:
                self.error.update(code="stopped", message="stopped: the file ran too long while loading "
                                                          "(an endless loop?); fix it and save")
            if good is not None and (r["error"].get("restarted") or self.error["code"] == "stopped"
                                     or r.get("loaded") is False):
                # the engine is new (a crash, a Stop, a changed module) and holds
                # nothing: load the version that ran, so it can still be shown
                self._cant_draw = None
                back = await self._engine({"op": "load", "data": good["data"]})
                if "error" in back:  # it imports what broke (a module): it can't run either
                    self._cant_draw = ("the last version that ran can't be drawn now either: "
                                       + (back["error"].get("message") or "it doesn't load"))
            self._show_good(good)
            await self.send_model()
            return
        self.traces = {}
        self._cant_draw = None
        self.good = {"data": data, "src": self.src, "meta": r, "traces": self.traces}
        self.meta = r
        self.deps = sorted(set(r.get("deps") or []) | set(self._static_deps()))
        self._deps_digest = self._deps_seen = tracecache.deps_digest(self.path, self.deps)
        if tracecache.deps_digest(self.path, deps_before) != seen_before:
            # a module changed while the engine imported it: which version it has is
            # unknown, so nothing is cached, and the engine restarts with the new one
            self._deps_digest = self._deps_seen = None
            asyncio.get_running_loop().create_task(self.deps_changed())
        self._file_content(data)
        order = list(r["scenes"])
        if self.active in order:
            order.remove(self.active)
            order.insert(0, self.active)
        elif order:
            self.active = order[0]
        # what needs no run first (cached traces, scenes the user stopped), all at once:
        # one slow or endless scene must not hide the scenes that are ready
        known = {}
        for name in order:
            t = tracecache.CACHE.get(self._trace_key(data, name))
            if t is None and name in self._stopped.get(data, ()):
                t = {"name": name, "events": [], "duration": 0, "bases": [], "error": {
                    "code": "stopped", "line": None, "message": "stopped: this scene ran too long (an endless "
                                                                "loop?); fix it and save to try again"}}
            if t is not None:
                known[name] = t
        if known:
            self.traces.update(known)
            await self.send_model()
            if self.active in known:
                await self.activate(self.active)
        for name in order:
            if gen != self._load_gen:
                return  # superseded (another edit, undo or save): stop tracing old bytes
            if name in known:
                continue
            self.tracing = (name, time.monotonic(), data)
            await self.send_status()
            t = await self._engine({"op": "trace", "scene": name})
            self.tracing = None
            if gen != self._load_gen:
                return  # superseded while tracing (a Stop, or new bytes): the newer load decides
            if "error" in t and "events" not in t:
                t = {"name": name, "events": [], "duration": 0, "error": t["error"], "bases": []}
            else:
                tracecache.CACHE.put(self._trace_key(data, name), t)
            self.traces[name] = t
            if name == self.active:
                await self.send_model()
                await self.activate(name)
        await self.send_model()
        await self.send_status()

    def _show_good(self, good: dict | None):
        if good is None:
            self.traces = {}
            return
        self.meta = good["meta"]
        # scenes the last good version never got to (the file changed while it was
        # tracing) would wait for a trace that never comes: say so instead
        self.traces = {n: good["traces"].get(n) or {
            "name": n, "events": [], "duration": 0, "bases": [], "error": {
                "code": "untraced", "line": None,
                "message": "not traced: the file changed before this scene was; fix the file to see it"}}
            for n in good["meta"].get("scenes", [])}

    @property
    def stale(self) -> bool:
        """Showing the last version that ran, not the file as it is."""
        good = getattr(self, "good", None)
        return bool(self.error) and good is not None and good["data"] != self.data

    def _trace_key(self, data: bytes, scene: str) -> str | None:
        """Per scene: the code it can depend on (tracecache.scene_text), the
        modules it imports, the engine. None when there's nothing safe to key on."""
        d = getattr(self, "_deps_digest", None)
        if not d or getattr(self, "_no_cache", False):
            return None
        src = self.src if data == self.data else Source(data)
        if not src.ok:
            return None
        text = tracecache.scene_text(src.tree, data, scene, self.meta.get("scenes", []))
        return tracecache.key(text, d, scene, self.worker.quality)

    async def _engine(self, msg: dict, **kw) -> dict:
        """Every engine request goes through here. A verify run traces the
        edited bytes: kept, so the reload after the write needn't trace the
        same scene again."""
        at = getattr(self, "_edit_at", None)
        if msg.get("op") == "verify" and at and msg.get("scene") == at[0] and msg.get("f", at[1]) == at[1]:
            # the edit's own run draws the frame at the playhead too: after the write
            # that is the frame the UI asks for first, so it needn't run the scene again
            msg = {**msg, "f": at[1], "objects": True, "frame": True}
        r = await self.worker.request(msg, **kw)
        if msg.get("op") == "verify" and isinstance(r.get("trace"), dict) and msg.get("scene"):
            k = self._trace_key(msg["data"], msg["scene"])
            if k:
                tracecache.CACHE.put(k, r["trace"])
            fr = r.pop("frame", None)
            if fr is not None:
                self._verified_frame = (msg["data"], msg["scene"], msg["f"], fr)
        return r

    async def activate(self, scene: str):
        self.active = scene
        tr = self.traces.get(scene)
        if tr is None:
            return
        await self._engine({"op": "activate", "scene": scene, "duration": tr["duration"]})
        if self.prefetch_task is None or self.prefetch_task.done():
            self.prefetch_task = asyncio.create_task(self.prefetch())

    async def prefetch(self):
        """Fill the frame cache for the active scene (half-size JPEG for
        playback) while nobody else needs the worker."""
        failed: set = set()
        try:
            while True:
                scene, rev = self.active, self.rev
                tr = self.traces.get(scene)
                if tr is None:
                    return
                n = self.frame_count(scene)
                todo = [f for f in range(n) if self._cached((rev, scene, f, "half", "jpeg")) is None
                        and (rev, scene, f) not in failed]
                if not todo:
                    return
                for f in todo:
                    while self.worker.waiting:
                        await asyncio.sleep(0.05)
                    if self.rev != rev or self.active != scene:
                        break
                    r = await self.frame(scene, f, "half", "jpeg", background=True)
                    if "error" in r:  # don't retry it forever; the UI asks again when it's shown
                        failed.add((rev, scene, f))
                await asyncio.sleep(0)
        except Exception:
            return

    def frame_count(self, scene: str) -> int:
        tr = self.traces.get(scene)
        fps = self.meta.get("fps", 15)
        if not tr:
            return 1
        return max(1, int(round(tr["duration"] * fps)))

    # -- frames ---------------------------------------------------------------
    def _never_ends(self, scene: str) -> dict | None:
        """A scene that was stopped, or ran past the engine's deadline, would
        do it again for every frame: those are refused, not run."""
        err = (self.traces.get(scene) or {}).get("error") or {}
        if err.get("code") in ("stopped", "timeout", "untraced"):
            return {"error": {"message": err.get("message") or "this scene doesn't finish", "code": err["code"]}}
        return None

    async def frame(self, scene: str, f: int, size="full", fmt="png", ids=False, background=False):
        if scene not in self.traces:
            return {"error": {"message": f"no scene {scene!r} traced in this revision", "code": "scene"}}
        never = self._never_ends(scene)
        if never:
            return never
        if self.error and getattr(self, "_cant_draw", None):
            return {"error": {"message": self._cant_draw, "code": "not_loaded"}}
        f = max(0, min(int(f), self.frame_count(scene) - 1))  # Manim never renders outside the scene
        key = (self.rev, scene, f, size, fmt)
        hit = self._cached(key, want=(lambda v: "idmap" in v) if ids else None)
        if hit is not None and (not ids or "idmap" in hit):
            return hit
        r = await self._engine({"op": "frame", "scene": scene, "f": f, "ids": ids,
                                       "size": size, "fmt": fmt}, background=background)
        if "error" in r:
            return r
        if ids:
            for o in r.get("objects", []):
                self._annotate(o)
        self.frames.put(key, r)
        return r

    async def glyphs(self, scene: str, f: int, oid: str) -> dict:
        """The glyph map of object `oid` at frame f ({"glyphs": None} when
        the object isn't text, or the probe doesn't match what it draws)."""
        if scene not in self.traces:
            return {"error": {"message": f"no scene {scene!r} traced in this revision", "code": "scene"}}
        if not oid:
            return {"glyphs": None}
        never = self._never_ends(scene)
        if never:
            return never
        f = max(0, min(int(f), self.frame_count(scene) - 1))
        key = (self.rev, scene, f, "glyphs", oid)
        hit = self._cached(key)
        if hit is not None:
            return hit
        r = await self._engine({"op": "frame", "scene": scene, "f": f, "ids": oid,
                                       "size": "half", "fmt": "jpeg"})
        if "error" in r:
            return r
        o = next((o for o in r.get("objects", []) if o.get("id") == oid), None)
        out = {"glyphs": (o or {}).get("glyphs")}
        self.frames.put(key, out)
        return out

    async def stop(self) -> dict:
        """Stop a load or trace that runs too long (an endless loop): end the
        engine process. The reload that follows skips what was stopped, for
        these bytes; saving the file tries again."""
        if self.tracing is None:
            return {"type": "error", "message": "nothing is running"}
        name, _, data = self.tracing
        self._stopped.setdefault(data, set()).add(name)  # the bytes being traced, not newer ones
        self._stop_asked = True
        await asyncio.to_thread(self.worker.kill)
        return {"type": "stopped", "scene": name or None}

    async def send_status(self):
        """Pushed while something runs, so the UI can offer Stop."""
        t = self.tracing
        await self.notify({"type": "engine.busy", "file": self.name,
                           "what": None if t is None else (t[0] or "(loading the file)"),
                           "since": None if t is None else round(time.monotonic() - t[1], 1)})

    def _restarted(self):
        """The worker was replaced (crash or deadline): it has nothing loaded.
        Reload, but not forever: code that hangs on every load stays an error
        until the file changes."""
        self.tracing = None
        if getattr(self, "_stop_asked", False):
            # stopped by the user: reload, skipping what was stopped; it doesn't count.
            # The load that was running is superseded now, so its "restarted" reply
            # for the stopped scene is never shown, not even until the reload starts
            self._stop_asked = False
            self._load_gen = getattr(self, "_load_gen", 0) + 1
            asyncio.get_running_loop().create_task(self.load())
            return
        self._restarts_here = getattr(self, "_restarts_here", {})
        n = self._restarts_here[self.data] = self._restarts_here.get(self.data, 0) + 1
        if n > 2:
            self.error = {"code": "timeout", "message": "the engine had to be restarted 3 times for this "
                                                        "version of the file; fix the code, then save"}
            asyncio.get_running_loop().create_task(self.send_model())
            return
        asyncio.get_running_loop().create_task(self.load())

    def _annotate(self, o: dict):
        """Name, tier and source text for an object, from the code. While the
        file doesn't run, the frames are the last version that ran, so their
        objects are named from that version's source (edits are refused then)."""
        good = getattr(self, "good", None)
        if self.stale and good is not None:
            src = self.src
            self.src = good["src"]  # no await in here: nothing else sees the swap
            try:
                return self._annotate_from_src(o)
            finally:
                self.src = src
        return self._annotate_from_src(o)

    def _annotate_from_src(self, o: dict):
        site = o.get("site") or o.get("user_site")
        o["name"] = self._label(o.get("chain_spans") or []) or             (self.name_at(o.get("site")) if o.get("site") else None)
        o["tier"] = self.tier_at(site[0]) if site else 3
        if site:
            # a curve: made by the user's plot call even when Manim builds it (user_site)
            curve = graphplan.describe_curve(self.src, site)
            if curve is not None and self.tier_at(site[0]) <= 2:
                o["curve"] = curve
        # the scale and turn chained on the call that makes it (or on this call of
        # the helper that makes it): what the Inspector shows (Phase 7 step 9)
        # an object made by a helper: the helper's own call, and this call of the
        # helper (where the studio chains its edits) both count
        # and a later statement that places, scales or turns it (`eq.shift(UP).scale(0.9)`),
        # since a scale edit chains onto the last of those
        P = o.get("placement") or {}
        later = [m["site"] for m in (P.get("move"), P.get("scale"), P.get("rotate"))
                 if m and m.get("kind") == "static" and m.get("site")]
        spans = []
        for sp in [o.get("site"), o.get("user_site")] + list(o.get("chain_spans") or []) + later:
            if sp and list(sp) not in spans:
                spans.append(list(sp))
        calls, seen = [], set()
        for sp in spans:
            c = self.src.find_call(Span(*sp))
            if c is None:
                continue
            for t in moveplan.transform_calls(self.src, c, own=sp in [list(s) for s in later]):
                if id(t) not in seen:  # one .scale() reached from two sites counts once
                    seen.add(id(t))
                    calls.append(t)
        st = moveplan.transform_value(calls) if spans else None
        if st is not None:
            o["scale_now"], o["turn_now"] = st
        if o.get("site"):
            call = self.src.find_call(Span(*o["site"]))
            if call is not None:
                o["call_text"] = self.src.text(call)[:300]
                o["kwargs"] = {k.arg: self.src.text(k.value)[:120] for k in call.keywords if k.arg}
                o["args"] = [self.src.text(a)[:120] for a in call.args]
                if o.get("class") in TEXT_CLASSES:
                    o["texts"] = self._texts(call)
                if o.get("class") in AXES_CLASSES:
                    o["ranges"] = self._ranges(call)
                elif Source.call_name(call) in AREA_CALLS:
                    o["ranges"] = self._ranges(call, AREA_KW)  # an area or Riemann sum (step 7)
        elif o.get("user_site") and self.tier_at(o["user_site"][0]) <= 2:
            # made inside Manim by the user's axes.get_area(...) call: its numbers are still the user's
            call = self.src.find_call(Span(*o["user_site"]))
            if call is not None and Source.call_name(call) in AREA_CALLS:
                o["ranges"] = self._ranges(call, AREA_KW)

    def _texts(self, call) -> list[dict]:
        """The string arguments of a Text / MathTex call, for editing in place
        (edit.literal): span, value, and whether the code can be edited."""
        ok = self._literal_spans()
        out = []
        for a in call.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                span = [a.lineno, a.col_offset, a.end_lineno, a.end_col_offset]
                out.append({"span": span, "value": a.value, "editable": tuple(span) in ok,
                            "raw": self.src.text(a)[:1].lower() == "r"})
            else:
                out.append({"span": None, "value": None, "editable": False, "code": self.src.text(a)[:80]})
        return out

    def _ranges(self, call, kws=None) -> list[dict]:
        """Axes / NumberPlane / NumberLine sizes and ranges (step 7): each
        number of `x_range=[-3, 3, 1]`, `x_length=6` that the literal edit can
        change, as {kw, parts: [{span, value, label}]}."""
        ok = self._literal_spans()
        names = ("min", "max", "step")
        out = []
        for k in call.keywords:
            if k.arg not in (kws or RANGE_KW):
                continue
            v = k.value
            items = v.elts if isinstance(v, (ast.List, ast.Tuple)) else [v]
            parts = []
            for j, e in enumerate(items):
                n = number_of(e)
                span = [e.lineno, e.col_offset, e.end_lineno, e.end_col_offset]
                parts.append({"span": span if n is not None and tuple(span) in ok else None,
                              "value": n, "text": self.src.text(e)[:40],
                              "label": names[j] if len(items) > 1 and j < 3 else k.arg})
            out.append({"kw": k.arg, "parts": parts})
        return out

    def _literal_spans(self) -> set:
        c = getattr(self, "_lit_cache", None)
        if c is None or c[0] is not self.src:
            spans = {tuple(x["span"]) for x in literalplan.find_literals(self.src, self.census())}                 if self.src.ok else set()
            self._lit_cache = c = (self.src, spans)
        return c[1]

    def name_at(self, span) -> str | None:
        if not self.src.ok or span is None:
            return None
        stmt = self.src.statement_at(span[0])
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return None
        want = tuple(span)
        v = stmt.value
        while isinstance(v, ast.Call):
            if (v.lineno, v.col_offset, v.end_lineno, v.end_col_offset) == want:
                return stmt.targets[0].id
            f = v.func
            if isinstance(f, ast.Attribute) and f.end_lineno == want[0] and \
                    f.end_col_offset - len(f.attr.encode("utf-8")) == want[1] and (v.end_lineno, v.end_col_offset) == want[2:]:
                return stmt.targets[0].id
            v = f.value if isinstance(f, ast.Attribute) else None
        return None

    _census = None

    def tier_at(self, line: int) -> int:
        if not self.src.ok:
            return 3
        if self._census is None or self._census[0] is not self.src:
            self._census = (self.src, classify(self.src.tree, self.api))
        return self._census[1].lines.get(line, 1)

    def census(self):
        self.tier_at(0)  # builds and caches the classification for this source
        return self._census[1]

    def literal_list(self) -> list[dict]:
        """Editable values for the code peek, with columns in characters."""
        if not self.src.ok:
            return []
        out = []
        for x in literalplan.find_literals(self.src, self.census()):
            l1, c1, l2, c2 = x["span"]
            a = self.src.offset(l1, 0)
            cols = [len(self.data[a:self.src.offset(l1, c1)].decode("utf-8", "replace")),
                    len(self.data[a:self.src.offset(l2, c2)].decode("utf-8", "replace"))]
            item = {"span": x["span"], "line": l1, "cols": cols, "kind": x["kind"], "text": x["text"],
                    "scope": x["scope"]}
            if x["kind"] == "string":
                try:
                    item["value"] = ast.literal_eval(x["text"])  # what the user edits, without quotes
                except (ValueError, SyntaxError):
                    continue
            out.append(item)
        return out

    # -- the model sent to the UI ---------------------------------------------
    def _scenes(self) -> list[dict]:
        scenes = []
        for name in self.meta.get("scenes", []) if self.src.ok else []:
            tr = self.traces.get(name)
            if tr is None:
                scenes.append({"name": name, "pending": True})
                continue
            scenes.append(self._scene_model(tr))
        return scenes

    def model(self) -> dict:
        stale = self.stale
        if stale:
            # the scenes of the last version that ran, read against its own source
            # (no await in here, so nothing sees the swap)
            now = (self.src, self._census, getattr(self, "_lit_cache", None), self.data)
            self.src, self.data = self.good["src"], self.good["data"]
            try:
                scenes = self._scenes()
            finally:
                self.src, self._census, self._lit_cache, self.data = now
        else:
            scenes = self._scenes()
        census = summary(classify(self.src.tree, self.api)) if self.src.ok else None
        return {"type": "model", "file": self.name, "rev": self.rev, "session": SESSION, "scenes": scenes,
                "stale": stale,
                "fps": self.meta.get("fps", 15), "width": self.meta.get("width", 854),
                "height": self.meta.get("height", 480), "frame_width": self.meta.get("frame_width", 14.2222),
                "frame_height": self.meta.get("frame_height", 8.0), "error": self.error, "census": census,
                "active": self.active, "undo": bool(self.undo), "redo": bool(self.redo),
                "source": self.data.decode("utf-8", "replace"), "literals": [] if stale else self.literal_list()}

    def _scene_model(self, tr: dict) -> dict:
        clips, rows = [], OrderedDict()
        speech = speech_warnings(tr)
        n_play = 0
        seen_calls: dict = {}  # pass of a loop: how many earlier events the same call made
        for i, ev in enumerate(tr["events"]):
            call = self.src.find_call(Span(*ev["call"])) if ev.get("call") and self.src.ok else None
            name = Source.call_name(call) if call is not None else None
            lock = None
            padding = ev.get("call") is None and ev["kind"] == "wait" and i == len(tr["events"]) - 1 \
                and bool(tr.get("target"))
            if padding:
                tl = self._target_line(tr)
                lock = "padding to TARGET" + (f" (line {tl})" if tl else "") + ": change the scene's length instead"
            elif ev.get("in_helper"):
                lock = f"inside {ev.get('func')}() — editing it would change every use"
            elif name not in ("play", "wait", "at"):
                lock = f"timed by {name or 'library code'}() (line {ev.get('call_line')})"
            runtimes = []
            if call is not None and name == "play":
                for a in call.args:
                    runtimes.append(_has_runtime(a))
            # Edits and the Inspector work in the code's own numbers (wait(0.5) is 0.5,
            # not the 7 frames = 0.4667 s it plays for at 15 fps).
            key = tuple(ev["call"]) if ev.get("call") else None
            occurrence = seen_calls.get(key, 0)
            if key is not None:
                seen_calls[key] = occurrence + 1
            clip = {"index": i, "kind": ev["kind"], "start": ev["start"], "occurrence": occurrence,
                    "duration": ev.get("nominal", ev["duration"]), "played": ev["duration"],
                    "call": ev.get("call"), "call_name": name, "func": ev.get("func"),
                    "line": ev.get("call_line"), "in_helper": ev.get("in_helper"), "lock": lock,
                    "anims": ev["anims"], "anim_runtimes": runtimes,
                    "tier": self.tier_at(ev["call_line"]) if ev.get("call_line") else 3,
                    "text": self.src.text(call)[:200] if call is not None else None}
            if padding:
                clip["padding"] = True
            if not lock and call is not None and ev["kind"] in ("play", "wait"):
                # a length the code computes (at(1.2 + 2.4 * k), run_time=t): say so up
                # front, so the field shows read-only instead of refusing after Enter
                clip.update(self._timing_locks(clip))
            if i in speech:
                clip["speech"] = speech[i]
            if name == "play" and call is not None and Source.keyword(call, "run_time") is not None:
                clip["play_runtime"] = True
            if name == "play" and call is not None and not lock:
                pairs = [transformplan.pair(self.src, ev["call"], k) for k in range(len(call.args))]
                if any(pairs):
                    clip["transforms"] = pairs  # per play() argument (step 8)
            if ev["kind"] == "play":
                clip["play_index"] = n_play
                n_play += 1
            clips.append(clip)
            if ev["kind"] == "play":
                for a in ev["anims"]:
                    if a.get("mobject_class") == "Mobject":
                        continue  # the empty placeholder Manim's Wait adds to the scene
                    key = a.get("mobject") or f"({a['class']})"
                    rows.setdefault(key, {"id": a.get("mobject"), "class": a.get("mobject_class"),
                                          "label": None, "chain": a.get("chain") or [], "clips": []})
                    rows[key]["clips"].append({"clip": i, "anim": a["index"]})
        for key, row in rows.items():
            row["label"] = self._label(row["chain"]) or self._object_label(row["id"], row["class"])
        timed = tr.get("timed", "TimedScene" in (tr.get("bases") or []))
        return {"name": tr["name"], "duration": tr["duration"], "error": tr.get("error"),
                "bases": tr.get("bases", []), "target": tr.get("target"), "clips": clips,
                "target_info": self._target_info(tr, timed),
                "voice_state": self._voice_state(tr["name"]) if timed else None,
                "rows": list(rows.values()), "frames": self.frame_count(tr["name"]), "timed": timed,
                "ambient": self._ambient(tr["name"]),
                **self._audio_model(tr, timed)}

    def _timing_locks(self, clip: dict) -> dict:
        """Why a clip's length (and each animation's run_time) can't be edited,
        found by planning a retime without writing it (Phase 7 step 8)."""
        out: dict = {}

        def why(c: dict) -> str | None:
            try:
                planner.plan_timing(self.src, c, "duration", round(c["duration"] + 0.5, 4))
            except EditError as e:
                return str(e)
            except Exception:  # noqa: BLE001 - a planner bug must not break the model
                return None
            return None
        w = why(clip)
        if w:
            out["duration_lock"] = w
        if clip["kind"] == "play" and len(clip["anims"]) > 1:
            locks = [why(dict(clip, kind="anim", anim_index=k, duration=a.get("run_time") or clip["duration"]))
                     for k, a in enumerate(clip["anims"])]
            if any(locks):
                out["anim_locks"] = locks
        return out

    def _voice_state(self, scene: str) -> dict | None:
        """Is the scene silent (VOICE = None), and who says so (Phase 7 step 5)."""
        if not self.src.ok:
            return None
        try:
            vs = timeline.voice_state(self.src, scene)
        except EditError:
            return None
        if vs["silent"] and vs["owner"] != scene:
            # the scenes in this file that the base's VOICE = None also silences
            vs["shared"] = sorted(n for n in self.meta.get("scenes", [])
                                  if timeline.voice_state(self.src, n).get("owner") == vs["owner"])
        return vs

    def _target_line(self, tr: dict) -> int | None:
        """The line that sets the scene's TARGET: its own, or a base class's in this file."""
        if not self.src.ok:
            return None
        for cls in timeline.class_chain(self.src, tr["name"]):
            st = timeline._setting(cls, "TARGET")
            if st is not None:
                return st.lineno
        return None

    def _target_info(self, tr: dict, timed: bool) -> dict:
        """The scene's length as the TARGET field shows it (Phase 7 step 4)."""
        own = None
        if self.src.ok:
            try:
                own = timeline.target_stmt(self.src, tr["name"])
            except EditError:
                pass
        computed = None
        if own is not None and number_of(own.value) is None:
            computed = f"TARGET is computed ({self.src.text(own.value)}); change it in the code"
        return {"value": tr.get("target"), "own": own is not None, "line": self._target_line(tr),
                "computed": computed, "content_end": content_end(tr), "editable": timed and not computed}

    async def _target_edit(self, scene: str, tr: dict, msg: dict) -> dict:
        """Set TARGET to a length, or "fit": the content's end + 0.1 s."""
        if not tr.get("timed", "TimedScene" in (tr.get("bases") or [])):
            return {"type": "edit.refused", "reason": "only a TimedScene pads itself to a TARGET length"}
        fps = self.meta.get("fps", 15)
        end = content_end(tr)
        v = msg.get("value")
        try:
            if v == "fit":
                value = math.ceil((end + 0.1) * 100 - 1e-6) / 100
            else:
                value = float(v)
                if not math.isfinite(value):
                    raise ValueError
            if value < end - 0.5 / fps:
                raise EditError(f"the scene's content runs to {end:.2f} s; a TARGET shorter than that "
                                "doesn't cut it (shorten the content first)")
            plan = timeline.plan_target(self.src, scene, value)
        except (TypeError, ValueError):
            return {"type": "edit.refused", "reason": f"not a length: {v!r}"}
        except EditError as e:
            return {"type": "edit.refused", "reason": str(e)}
        new = apply(self.data, plan.edits)
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        r = await self._engine({"op": "verify", "data": new, "scene": scene})
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited scene doesn't run: {r['error']['message']}"}
        after = r["trace"]
        if after.get("error"):
            return {"type": "edit.refused", "reason": _stop_reason(after["error"])}
        if abs(after["duration"] - value) > 1.5 / fps:
            return {"type": "edit.refused", "reason": f"the scene lasts {after['duration']:.2f} s after the edit, "
                                                      f"not {value:g} s"}
        note = plan.note + (" (fit: content ends at %.2f s)" % end if v == "fit" else "")
        return await self._write_verified(new, note)

    async def _ripple_target(self, scene: str, new: bytes, after: dict, note: str) -> tuple[bytes, str]:
        """After a retime with ripple on: a literal TARGET follows the content's
        end, so the padding after it stays as it was. Verified by replay; left
        alone when that fails."""
        before = self.traces.get(scene) or {}
        if not before.get("target") or after.get("error"):
            return new, note
        fps = self.meta.get("fps", 15)
        d = content_end(after) - content_end(before)
        if abs(d) < 0.5 / fps:
            return new, note
        src = Source(new)
        try:
            st = timeline.target_stmt(src, scene)
        except EditError:
            return new, note
        old = number_of(st.value) if st is not None else None
        if old is None:
            return new, note
        value = round(old + d, 2)
        if value < content_end(after) - 0.5 / fps:
            return new, note
        try:
            plan = timeline.plan_target(src, scene, value)
        except EditError:
            return new, note
        new2 = apply(new, plan.edits)
        r = await self._engine({"op": "verify", "data": new2, "scene": scene})
        tr2 = r.get("trace") if "error" not in r else None
        if tr2 is None or tr2.get("error") or abs(tr2["duration"] - value) > 1.5 / fps:
            return new, note
        return new2, note + f" · ripple: TARGET {fmt_num(old)} → {fmt_num(value)}"

    def _ambient(self, scene: str) -> list[dict]:
        """`self.begin_ambient_camera_rotation(rate=0.1)` in the scene (step 10):
        each rate as a field the literal edit can change (span None when computed)."""
        if not self.src.ok:
            return []
        try:
            fn = inserts.scene_construct(self.src, scene)
        except EditError:
            return []
        ok = self._literal_spans()
        out = []
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "begin_ambient_camera_rotation"):
                continue
            kw = Source.keyword(n, "rate")
            e = kw.value if kw is not None else (n.args[0] if n.args else None)
            if e is None:
                out.append({"line": n.lineno, "span": None, "value": 0.02, "text": "(default 0.02)"})
                continue
            v = number_of(e)
            span = [e.lineno, e.col_offset, e.end_lineno, e.end_col_offset]
            out.append({"line": n.lineno, "span": span if v is not None and tuple(span) in ok else None,
                        "value": v, "text": self.src.text(e)[:40]})
        return sorted(out, key=lambda x: x["line"])

    def _audio_model(self, tr: dict, timed: bool) -> dict:
        """Narration lines, captions and other sounds, with what can be edited."""
        a = tr.get("audio") or {}
        voice = []
        for ln in a.get("lines", []):
            lock = None
            call = None
            if self.src.ok:
                try:
                    call, _ = timeline._line_call(self.src, tr["name"], ln)
                except EditError as e:
                    lock = str(e)
            shown = _BOOKMARK.sub("", ln.get("caption") or ln["text"]).strip()
            # a voiceover's caption is up exactly as long as its speech, so only
            # its length can be a problem; say() holds captions itself
            hold = ln.get("hold") if ln["kind"] == "say" else None
            voice.append({"index": ln["index"], "kind": ln["kind"], "text": ln["text"], "caption": ln.get("caption"),
                          "start": ln["start"], "requested": ln["requested"], "duration": ln.get("duration", 0.0),
                          "hold": ln.get("hold", 0.0), "block_end": ln.get("block_end"),
                          "bookmarks": ln.get("bookmarks") or [],
                          "line": call.lineno if call is not None else (ln["call"][0] if ln.get("call") else None),
                          "lock": lock, "movable": lock is None and timed and ln["kind"] == "say",
                          "warnings": timeline.caption_warnings(shown, hold)})
        line_files = {ln.get("audio") for ln in a.get("lines", [])}
        sounds = []
        for snd in a.get("sounds", []):
            if snd.get("line") is not None or snd["file"] in line_files:
                continue
            f = Path(snd["file"])
            try:
                name = rel(f)
            except ValueError:
                name = f.name
            sounds.append({"file": name, "start": snd["start"], "line": snd["call"][0] if snd.get("call") else None})
        sections = [{"index": i, "name": x["name"], "start": x["start"],
                     "line": x["call"][0] if x.get("call") else None} for i, x in enumerate(a.get("sections", []))]
        return {"voice": voice, "captions": a.get("captions", []), "burned_captions": a.get("burned", False),
                "sounds": sounds, "sections": sections}

    def _label(self, chain: list) -> str | None:
        """The variable an object ends up in: `title = get_title()` names
        the Text made inside get_title()."""
        for span in chain:
            n = self.name_at(span)
            if n:
                return n
        return None

    def _object_label(self, oid: str | None, cls: str | None) -> str:
        if not oid:
            return cls or "?"
        try:
            cls_, rest = oid.lstrip("~").split("@")
            line, col = rest.split("#")[0].split(":")
            line, col = int(line), int(col)
        except ValueError:
            return oid
        if self.src.ok and not oid.startswith("~"):
            stmt = self.src.statement_at(line)
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and \
                    isinstance(stmt.targets[0], ast.Name) and stmt.lineno == line:
                return stmt.targets[0].id
        return f"{cls_} · line {line}"

    async def send_model(self):
        await self.notify(self.model())

    # -- edits ------------------------------------------------------------------
    async def edit(self, msg: dict) -> dict:
        async with self.edit_lock:
            at = msg.get("at")
            self._edit_at = (msg.get("scene"), at) if isinstance(at, int) and not isinstance(at, bool) and at >= 0 else None
            self._verified_frame = None
            try:
                return await self._edit(msg)
            finally:
                self._edit_at = None

    async def _edit(self, msg: dict) -> dict:
        if msg.get("rev") != self.rev:
            return {"type": "error", "code": "stale", "message": "the file changed; try again"}
        if not self.src.ok:
            return {"type": "edit.refused", "reason": "the file doesn't parse; fix it first"}
        if self.error:
            return {"type": "edit.refused", "reason": "the file doesn't run; fix it first (the studio is showing "
                                                      "the last version that ran)"}
        if msg["type"] in SCENE_EDITS:
            return await self._scene_edit(msg)
        if msg["type"] == "edit.target":
            tr0 = self.traces.get(msg.get("scene"))
            if tr0 is None or tr0.get("error"):
                return {"type": "edit.refused", "reason": "that scene isn't traced (or stops with an error)"}
            return await self._target_edit(msg["scene"], tr0, msg)
        scene = msg.get("scene")
        tr = self.traces.get(scene)
        if tr is None and msg["type"] == "edit.scene_order":
            # the SCENES list belongs to no scene: verify against any traced one
            scene = next((n for n, t in self.traces.items() if not t.get("error")), None)
            tr = self.traces.get(scene) if scene else None
        if tr is None:
            return {"type": "edit.refused", "reason": "that scene is still being traced; try again in a moment"}
        if tr.get("error"):
            return {"type": "edit.refused", "reason": "the scene stops with an error; fix it first"}
        try:
            if msg["type"] == "edit.timing":
                clips = self._scene_model(tr)["clips"]
                i = msg.get("clip")
                if not isinstance(i, int) or not 0 <= i < len(clips):
                    return {"type": "edit.refused", "reason": "that clip no longer exists"}
                clip = clips[i]
                if msg.get("anim") is not None and not (
                        isinstance(msg["anim"], int) and 0 <= msg["anim"] < len(clip["anims"])):
                    return {"type": "edit.refused", "reason": "that animation no longer exists"}
                c = dict(clip)
                if msg.get("anim") is not None:
                    c.update(kind="anim", anim_index=msg["anim"],
                             default_rate_func=clip["anims"][msg["anim"]]["default_rate_func"])
                elif clip["anims"]:
                    c["default_rate_func"] = clip["anims"][0]["default_rate_func"]
                plan = planner.plan_timing(self.src, c, msg["field"], msg["value"])
                target = {"kind": "timing", "clip": msg["clip"], "anim": msg.get("anim"),
                          "field": msg["field"], "value": msg["value"],
                          "ripple": bool(msg.get("ripple")) and msg["field"] == "duration"}
            elif msg["type"] in ("edit.move", "edit.scale", "edit.rotate"):
                return await self._transform(scene, tr, msg)
            elif msg["type"] in STRUCTURAL:
                return await self._structural(scene, tr, msg)
            elif msg["type"] in TIMELINE:
                return await self._timeline(scene, tr, msg)
            elif msg["type"] == "edit.camera":
                return await self._camera(scene, tr, msg)
            elif msg["type"] == "edit.part_colour":
                return await self._part_colour(scene, tr, msg)
            elif msg["type"] == "edit.match_parts":
                clips = self._scene_model(tr)["clips"]
                i, arg = msg.get("clip"), msg.get("arg")
                if not isinstance(i, int) or not 0 <= i < len(clips) or clips[i].get("lock"):
                    return {"type": "edit.refused", "reason": "that clip can't be edited here"}
                if not isinstance(arg, int):
                    return {"type": "edit.refused", "reason": "which animation of the play()?"}
                plan = transformplan.plan_key_map(self.src, clips[i]["call"], arg,
                                                  msg.get("source_key"), msg.get("target_key"))
                target = {"kind": "literal"}  # the scene must still run; Manim pairs the keys
            elif msg["type"] == "edit.transform_kind":
                clips = self._scene_model(tr)["clips"]
                i = msg.get("clip")
                if not isinstance(i, int) or not 0 <= i < len(clips) or clips[i].get("lock"):
                    return {"type": "edit.refused", "reason": "that clip can't be edited here"}
                arg = msg.get("arg")
                if not isinstance(arg, int):
                    return {"type": "edit.refused", "reason": "which animation of the play()?"}
                plan = transformplan.plan_kind(self.src, clips[i]["call"], arg, str(msg.get("kind")))
                target = {"kind": "literal"}  # the scene must still run
            elif msg["type"] == "edit.curve":
                plan = graphplan.plan_curve(self.src, msg.get("object") or {}, str(msg.get("expr", "")), self.api)
                target = {"kind": "literal"}  # the replay must run; the curve is what was typed
            elif msg["type"] == "edit.literal":
                if "changes" in msg:
                    plan = literalplan.plan_literals(self.src, self.census(), msg.get("changes"))
                else:
                    plan = literalplan.plan_literal(self.src, self.census(), msg.get("span"), msg.get("value") or {})
                target = {"kind": "literal"}
            elif msg["type"] == "edit.prop":
                obj = msg["object"]
                plan = planner.plan_property(self.src, obj, msg["prop"], msg["value"])
                target = {"kind": "prop", "object": obj["id"], "f": msg["f"], "prop": msg["prop"],
                          "value": msg["value"], "before": (obj.get("values") or {}).get(msg["prop"])}
            else:
                return {"type": "error", "message": f"unknown edit {msg['type']}"}
        except EditError as e:
            return {"type": "edit.refused", "reason": str(e)}
        try:
            new = apply(self.data, plan.edits)
        except EditError as e:  # overlapping edits from a planner: refuse, don't crash the request
            return {"type": "edit.refused", "reason": str(e)}
        if plan.confirm:
            token = hashlib.sha1(new).hexdigest()[:12]
            self.pending[token] = Pending(token, scene, new, plan.note, plan.edits, plan.checks, target,
                                          base=self.data)
            reply = {"type": "edit.preview", "token": token, "summary": plan.note,
                     "why": plan.confirm, "diff": self.diff(new)}
            if msg["type"] == "edit.prop":
                try:
                    alt = planner.plan_property_override(self.src, msg["object"], msg["prop"], msg["value"])
                except EditError:
                    alt = None
                if alt is not None:
                    new2 = apply(self.data, alt.edits)
                    if Source(new2).ok:
                        t2 = hashlib.sha1(new2).hexdigest()[:12]
                        self.pending[t2] = Pending(t2, scene, new2, alt.note, alt.edits, alt.checks, target,
                                                   base=self.data)
                        reply["alternatives"] = [{"token": t2, "summary": alt.note, "diff": self.diff(new2),
                                                  "label": "Only this one"}]
            return reply
        return await self._verify_and_write(scene, new, plan.note, target)

    async def _part_colour(self, scene: str, tr: dict, msg: dict) -> dict:
        """Colour some glyphs of a Text / MathTex / Tex (step 6). Each
        candidate edit is replayed; the first where exactly the picked glyphs
        change colour is written."""
        obj = msg.get("object") or {}
        try:
            f = int(msg.get("f", 0))
        except (TypeError, ValueError):
            return {"type": "edit.refused", "reason": "no frame given"}
        g = await self.glyphs(scene, f, obj.get("id") or "")
        if "error" in g:
            return {"type": "edit.refused", "reason": _stop_reason(g["error"])}
        g = g.get("glyphs")
        if not g:
            return {"type": "edit.refused",
                    "reason": "the studio can't match this text's glyphs to its source"}
        value = msg.get("value") or {}
        try:
            sel = texplan.selection(g, msg.get("glyphs") or [])
            colour = planner._value_text(self.src, None, value)
            plans = texplan.candidates(self.src, self._annotated(obj), g, sel, colour)
        except EditError as e:
            return {"type": "edit.refused", "reason": str(e)}
        want = value.get("string") if "string" in value else None
        reasons = []
        asked = None  # the first checked candidate that needs a yes; one that doesn't wins
        for plan in plans:
            new = apply(self.data, plan.edits)
            if not Source(new).ok:
                continue
            # every candidate is replayed and glyph-checked first, the ones that ask too
            req = {"op": "verify", "data": new, "scene": scene, "f": f, "glyphs": True,
                   "object": remap_id(obj.get("id"), self.data, plan.edits)}
            if "name" in value:
                req["eval_name"] = value["name"]
            r = await self._engine(req)
            if "error" in r:
                reasons.append(f"{plan.note}: the scene doesn't run ({_stop_reason(r['error'])})")
                continue
            if (r.get("trace") or {}).get("error"):
                reasons.append(f"{plan.note}: the scene stops with an error")
                continue
            got = (r.get("object") or {}).get("glyphs")
            hexes = r.get("eval") if "name" in value else want
            why = texplan.check(g.get("colors") or [], got, sel, hexes if isinstance(hexes, str) else None,
                                _same_colour)
            if why is None:
                if not plan.confirm:
                    return await self._write_verified(new, plan.note)
                asked = asked or (plan, new)
                continue
            reasons.append(f"{plan.note}: {why}")
        if asked:
            plan, new = asked
            token = hashlib.sha1(new).hexdigest()[:12]
            self.pending[token] = Pending(token, scene, new, plan.note, plan.edits, plan.checks,
                                          {"kind": "part_colour"}, base=self.data, verified=True)
            return {"type": "edit.preview", "token": token, "summary": plan.note,
                    "why": plan.confirm, "diff": self.diff(new)}
        return {"type": "edit.refused",
                "reason": "no edit coloured exactly those glyphs: " + "; ".join(reasons[:2] or ["nothing to try"])}

    async def _camera(self, scene: str, tr: dict, msg: dict) -> dict:
        """Move / zoom a 2D camera frame, or turn a 3D camera, at frame f
        (steps 9, 10). Verified by the camera's state at f after the replay."""
        try:
            f = max(0, int(msg.get("f", 0)))
        except (TypeError, ValueError):
            return {"type": "edit.refused", "reason": "no frame given"}
        fps = self.meta.get("fps", 15)
        t = round(f / fps, 4)
        cur = (await self.frame(scene, f, "half", "jpeg")).get("camera")
        if not cur:
            return {"type": "edit.refused", "reason": "this scene's camera can't be moved here"}

        def num(v):
            if v is None:
                return None
            x = float(v)
            if not math.isfinite(x):
                raise EditError("not a number")
            return x
        try:
            if cur["kind"] == "2d":
                c = msg.get("center")
                center = [num(c[0]), num(c[1])] if isinstance(c, (list, tuple)) and len(c) == 2 else None
                width = num(msg.get("width"))
                timed = tr.get("timed", "TimedScene" in (tr.get("bases") or []))
                plan = cameraplan.plan_camera_2d(self.src, scene, tr["events"], fps, timed, t, center, width, cur)
                want = {"center": center, "width": width}
            else:
                values = {k: num(msg.get(k)) for k in ("phi", "theta", "gamma", "zoom")}
                plan = cameraplan.plan_camera_3d(self.src, scene, tr["events"], t, values)
                want = {"values": values}
            new = apply(self.data, plan.edits)
        except (EditError, TypeError, ValueError) as e:
            return {"type": "edit.refused", "reason": str(e) if isinstance(e, EditError) else "bad request"}
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        fv = f
        if "start" in plan.checks:  # an inserted move: look where it has finished
            fv = int(round((plan.checks["start"] + plan.checks["run_time"]) * fps))
        elif "verify_at" in plan.checks:  # a camera move running at f: look at its end
            fv = max(0, int(round(plan.checks["verify_at"] * fps)) - 1)
        r = await self._engine({"op": "verify", "data": new, "scene": scene, "f": fv, "objects": True})
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited scene doesn't run: {r['error']['message']}"}
        if r["trace"].get("error"):
            return {"type": "edit.refused", "reason": _stop_reason(r["trace"]["error"])}
        why = cameraplan.check(cur["kind"], r.get("camera"), **want)
        if why:
            return {"type": "edit.refused", "reason": f"{plan.note}, but {why}"}
        if getattr(plan, "confirm", None):  # e.g. a camera move in a loop: every pass changes
            token = hashlib.sha1(new).hexdigest()[:12]
            self.pending[token] = Pending(token, scene, new, plan.note, plan.edits, plan.checks,
                                          {"kind": "camera"}, base=self.data, verified=True)
            return {"type": "edit.preview", "token": token, "summary": plan.note,
                    "why": plan.confirm, "diff": self.diff(new)}
        return await self._write_verified(new, plan.note)

    def _annotated(self, obj: dict) -> dict:
        o = dict(obj)
        self._annotate(o)
        return o

    async def confirm(self, token: str) -> dict:
        async with self.edit_lock:
            p = self.pending.pop(token, None)
            if p is None:
                return {"type": "error", "message": "that edit is no longer pending"}
            if p.data is None:
                return {"type": "error", "message": "nothing to confirm"}
            if p.base != self.data:
                return {"type": "edit.refused",
                        "reason": "the file changed since this edit was planned; make the edit again"}
            if p.verified:
                return await self._write_verified(p.data, p.note)
            return await self._verify_and_write(p.scene, p.data, p.note, p.target)

    async def _verify_and_write(self, scene: str, new: bytes, note: str, target: dict) -> dict:
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        req = {"op": "verify", "data": new, "scene": scene}
        if target["kind"] == "prop":
            req.update(object=target["object"], f=target["f"])
            if "name" in target["value"]:
                req["eval_name"] = target["value"]["name"]
        r = await self._engine(req)
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited scene doesn't run: {r['error']['message']}"}
        why = self._check(target, r)
        if why:
            return {"type": "edit.refused", "reason": why}
        if target.get("ripple") and isinstance(r.get("trace"), dict):
            new, note = await self._ripple_target(scene, new, r["trace"], note)
        return await self._write_verified(new, note)

    async def _scene_edit(self, msg: dict) -> dict:
        """Add, delete or rename a scene class (Phase 7 step 3). Verified by
        tracing: the new scene runs; the renamed one times out as before;
        after a delete, another scene still runs."""
        kind, scene = msg["type"], msg.get("scene")
        defined = list(self.meta.get("scenes", []))
        tr = self.traces.get(scene)
        if tr is None:
            return {"type": "edit.refused", "reason": "that scene is still being traced; try again in a moment"}
        try:
            if kind == "edit.scene_add":
                plan = scenes.plan_scene_add(self.src, scene, msg.get("name"), msg.get("where", "after"),
                                             defined, self.api)
                check = plan.checks["new_scene"]
            elif kind == "edit.scene_rename":
                plan = scenes.plan_scene_rename(self.src, scene, msg.get("name"), defined, self.api)
                check = plan.checks["renamed"][1]
            else:
                plan = scenes.plan_scene_delete(self.src, scene, defined)
                check = next((n for n in defined if n != scene and not (self.traces.get(n) or {}).get("error")),
                             None)
                if check is None:
                    raise EditError("no other scene runs, so the delete can't be checked")
        except EditError as e:
            return {"type": "edit.refused", "reason": str(e)}
        new = apply(self.data, plan.edits)
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        r = await self._engine({"op": "verify", "data": new, "scene": check})
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited file doesn't run: {r['error']['message']}"}
        after = r["trace"]
        if after.get("error"):
            return {"type": "edit.refused", "reason": _stop_reason(after["error"])}
        if kind == "edit.scene_rename" and not tr.get("error") and _timings(after) != _timings(tr):
            return {"type": "edit.refused", "reason": "the renamed scene doesn't time out as before"}
        out = await self._write_verified(new, plan.note)
        if out.get("type") == "edit.done":
            out["scene"] = None if kind == "edit.scene_delete" else check
        return out

    async def _write_verified(self, new: bytes, note: str) -> dict:
        warned = set(speech_warnings(self.traces.get(self.active)).values())
        before = self.data
        diff = self.diff(new)
        why = self._write(new)
        if why:
            return {"type": "edit.refused", "reason": why}
        self.undo.append(UndoStep(before, new, note))
        self.redo.clear()
        await self._reload_for_reply()
        self._seed_frame(new)
        out = {"type": "edit.done", "summary": note, "diff": diff, "rev": self.rev}
        fresh = [w for w in speech_warnings(self.traces.get(self.active)).values() if w not in warned]
        if fresh:
            out["warning"] = fresh[0] + (f" (and {len(fresh) - 1} more)" if len(fresh) > 1 else "")
        return out

    # -- canvas edits: move, scale, rotate (code_spec §4.1, §4.2) ------------------------
    async def _transform(self, scene: str, tr: dict, msg: dict) -> dict:
        kind = msg["type"].split(".")[1]
        obj = msg.get("object") or {}
        try:
            f = int(msg.get("f", 0))
        except (TypeError, ValueError):
            return {"type": "edit.refused", "reason": "no frame given"}
        why = self._animating(tr, obj, f)
        if why:
            return {"type": "edit.refused", "reason": why}
        try:
            if kind == "move":
                # drags and nudges are written to 2 decimals (0.01 units ≈ 1.4 px at
                # 1080p); a value typed in the Inspector keeps what was typed (step 9)
                nd = 4 if msg.get("exact") else 2
                dx, dy = round(float(msg["dx"]), nd), round(float(msg["dy"]), nd)
                if not (math.isfinite(dx) and math.isfinite(dy)):
                    raise EditError("not a distance")
                if abs(dx) < 1e-4 and abs(dy) < 1e-4:
                    return {"type": "edit.refused", "reason": "no movement"}
                plan = lambda k=1.0: moveplan.move_candidates(self.src, obj, dx / k, dy / k)  # noqa: E731
                amount = (dx, dy)
            elif kind == "scale":
                k = round(float(msg["k"]), 4)
                about = msg.get("about") or None
                if not math.isfinite(k) or abs(k - 1) < 1e-4:
                    return {"type": "edit.refused", "reason": "no change in size"}
                plan = lambda _k=1.0: moveplan.scale_candidates(self.src, obj, k, about)  # noqa: E731
                amount = (k, about)
            else:
                deg = round(float(msg["deg"]), 2)
                if not math.isfinite(deg) or abs(deg) < 0.01:
                    return {"type": "edit.refused", "reason": "no rotation"}
                plan = lambda _k=1.0: moveplan.rotate_candidates(self.src, obj, deg)  # noqa: E731
                amount = (deg,)
            cands = plan()
        except (EditError, KeyError, TypeError, ValueError) as e:
            return {"type": "edit.refused", "reason": str(e) if isinstance(e, EditError) else f"bad request: {e}"}
        if not cands:
            why = _why_stuck(obj, None, self.path.name) if kind == "move" else None
            return {"type": "edit.refused", "reason": "no code places this object in a way the studio can edit yet"
                    + (f": {why}" if why else "")}
        expect = _expected(kind, obj, amount)
        if expect is None:
            return {"type": "edit.refused", "reason": "the object's position isn't known at this frame"}
        r0 = await self.frame(scene, f, ids=True)
        before_objs = r0.get("objects", []) if "error" not in r0 else []
        if kind == "move":
            # axes on screen, by name: a point placed with axes.c2p(x, y) moves in graph units
            coords = {o["name"]: o["coords"] for o in before_objs if o.get("coords") and o.get("name")}
            if coords:
                tok = moveplan.COORDS.set(coords)
                try:
                    cands = plan()
                except EditError:
                    pass
                finally:
                    moveplan.COORDS.reset(tok)
                plan0 = plan
                plan = lambda k=1.0: _with_coords(coords, plan0, k)  # noqa: E731
        tried, calibrated = [], False
        last_got = None
        i = 0
        while i < len(cands) and i < 5:
            c = cands[i]
            try:
                new = apply(self.data, c.edits)
            except EditError as e:   # one bad candidate must not stop the next ones
                tried.append(f"{c.note}: {e}")
                i += 1
                continue
            if not Source(new).ok:
                tried.append(f"{c.note}: would not parse")
                i += 1
                continue
            oid = remap_id(obj.get("id"), self.data, c.edits)
            r = await self._engine({"op": "verify", "data": new, "scene": scene, "object": oid, "f": f})
            if "error" in r:
                tried.append(f"{c.note}: the scene doesn't run ({r['error']['message'][:80]})")
                i += 1
                continue
            if r["trace"].get("error"):
                tried.append(f"{c.note}: the scene stops with {r['trace']['error']['message'][:80]}")
                i += 1
                continue
            got = r.get("object")
            last_got = got or last_got
            miss = _miss(kind, expect, got)
            if miss and kind == "move" and not calibrated and got and got.get("center"):
                # a parent scaled the shift (object moved by k * drag): correct once
                k = _ratio(obj["center"], got["center"], amount)
                if k is not None:
                    calibrated = True
                    try:
                        recal = plan(k)
                    except EditError:
                        recal = []
                    if i < len(recal):
                        cands[i] = recal[i]
                        continue
            if miss:
                tried.append(f"{c.note}: {miss}")
                i += 1
                continue
            also = _also_moved(obj, before_objs, r.get("objects") or [], self.data, c.edits)
            note = c.note + (f"; also moves {', '.join(also[:4])}" if also else "")
            if c.confirm:
                token = hashlib.sha1(new).hexdigest()[:12]
                self.pending[token] = Pending(token, scene, new, note, c.edits, {}, {"kind": kind},
                                              base=self.data, verified=True)
                return {"type": "edit.preview", "token": token, "summary": note, "why": c.confirm,
                        "diff": self.diff(new), "also_moves": also}
            return await self._write_verified(new, note)
        why = _why_stuck(obj, last_got, self.path.name) if kind == "move" else None
        return {"type": "edit.refused", "reason": "no edit put the object where you dragged it"
                + (f": {why}" if why else f" (tried: {tried[0]})" if tried else ""), "tried": tried}

    # -- library drops, presets, duplicate, group, delete (code_spec §4.5, §4.6) -------------
    async def _structural(self, scene: str, tr: dict, msg: dict) -> dict:
        kind = msg["type"]
        fps = self.meta.get("fps", 15)
        try:
            f = max(0, int(msg.get("f", 0)))
        except (TypeError, ValueError):
            return {"type": "edit.refused", "reason": "no frame given"}
        t = round(f / fps, 4)
        timed = tr.get("timed", "TimedScene" in (tr.get("bases") or []))
        events = tr["events"]
        src = self.src
        fv = f  # the frame verification looks at
        try:
            if kind == "edit.insert":
                x, y = float(msg.get("x", 0)), float(msg.get("y", 0))
                if not (math.isfinite(x) and math.isfinite(y)):
                    raise EditError("not a position")
                plan = inserts.plan_insert(src, scene, events, fps, timed, str(msg.get("class")), x, y, t,
                                           msg.get("entrance"), msg.get("region") or None)
            elif kind == "edit.composite":
                x, y = float(msg.get("x", 0)), float(msg.get("y", 0))
                if not (math.isfinite(x) and math.isfinite(y)):
                    raise EditError("not a position")
                plan = inserts.plan_composite(src, scene, events, fps, timed, str(msg.get("preset")), x, y, t,
                                              msg.get("object"), tr.get("bases"))
            elif kind == "edit.preset":
                plan = inserts.plan_preset(src, scene, events, fps, timed, msg["object"], str(msg.get("preset")), t)
            elif kind == "edit.duplicate":
                plan = inserts.plan_duplicate(src, scene, events, fps, timed, msg["object"], t)
            elif kind == "edit.group":
                plan = inserts.plan_group(src, scene, list(msg.get("objects") or []))
            elif kind == "edit.delete":
                plan = inserts.plan_delete(src, scene, msg["object"], self.api)
            else:  # edit.delete_clip
                clips = self._scene_model(tr)["clips"]
                i = msg.get("clip")
                if not isinstance(i, int) or not 0 <= i < len(clips):
                    return {"type": "edit.refused", "reason": "that clip no longer exists"}
                anim = msg.get("anim")
                if anim is not None and not (isinstance(anim, int) and 0 <= anim < len(clips[i]["anims"])):
                    return {"type": "edit.refused", "reason": "that animation no longer exists"}
                plan = inserts.plan_delete_clip(src, scene, clips[i], anim)
        except (EditError, KeyError, TypeError, ValueError) as e:
            return {"type": "edit.refused", "reason": str(e) if isinstance(e, EditError) else f"bad request: {e}"}
        new = apply(self.data, plan.edits)
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        ch = plan.checks
        line = None
        if ch.get("name") and kind in ("edit.insert", "edit.duplicate", "edit.group", "edit.composite"):
            line = _line_of_assignment(new, ch["name"], plan.edits)
            if "seen" in ch:
                fv = max(0, int(round((ch["start"] + ch["seen"]) * fps)))
            elif "start" in ch:
                fv = max(0, int(round((ch["start"] + ch.get("run_time", 0)) * fps)) - 1)
        if kind == "edit.preset":
            fv = max(0, int(round(ch["start"] * fps)) + 1)
        req = {"op": "verify", "data": new, "scene": scene, "f": fv, "objects": True}
        r = await self._engine(req)
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited scene doesn't run: {r['error']['message']}"}
        if r["trace"].get("error"):
            return {"type": "edit.refused", "reason": _stop_reason(r['trace']['error'])}
        objs = r.get("objects") or []
        why = None
        if kind in ("edit.insert", "edit.duplicate", "edit.group", "edit.composite"):
            hit = [o for o in objs if (o.get("site") or [None])[0] == line]
            if not hit:
                why = "the new object isn't on screen after the edit"
            elif kind == "edit.insert" and ch.get("center"):
                c = hit[0].get("center") or [1e9, 1e9]
                if abs(c[0] - ch["center"][0]) > 0.05 or abs(c[1] - ch["center"][1]) > 0.05:
                    why = f"the new object is at ({c[0]:.2f}, {c[1]:.2f}), not where it was dropped"
        elif kind == "edit.preset":
            want = msg.get("preset")
            if not any(a["class"] == want for ev in r["trace"]["events"] for a in ev["anims"]):
                why = f"no {want} clip in the scene after the edit"
        elif kind == "edit.delete":
            gone = remap_id(ch.get("gone"), self.data, plan.edits)
            if any(o["id"] == gone for o in objs):
                why = "the object is still on screen after the edit"
        elif kind == "edit.delete_clip":
            if len(r["trace"]["events"]) >= len(events) and msg.get("anim") is None:
                why = "the clip is still there after the edit"
        if why:
            return {"type": "edit.refused", "reason": why}
        return await self._write_verified(new, plan.note)

    # -- timeline edits: narration, moving groups and clips (Phase 4) ----------------------
    async def _timeline(self, scene: str, tr: dict, msg: dict) -> dict:
        fps = self.meta.get("fps", 15)
        timed = tr.get("timed", "TimedScene" in (tr.get("bases") or []))
        events = tr["events"]
        lines = (tr.get("audio") or {}).get("lines", [])
        src = self.src
        kind = msg["type"]

        def num(v, what):
            try:
                x = float(v)
            except (TypeError, ValueError):
                raise EditError(f"not a {what}: {v!r}") from None
            if not math.isfinite(x):
                raise EditError(f"not a {what}")
            return x

        def line_at(i):
            if not isinstance(i, int) or not 0 <= i < len(lines):
                raise EditError("that narration line no longer exists")
            return lines[i]
        try:
            if kind == "edit.voice":
                act = msg.get("action")
                if act == "text":
                    plan = timeline.plan_voice_text(src, scene, line_at(msg.get("line")), msg.get("value"))
                elif act == "caption":
                    plan = timeline.plan_voice_caption(src, scene, line_at(msg.get("line")), msg.get("value"))
                elif act == "move":
                    plan = timeline.plan_voice_move(src, scene, line_at(msg.get("line")), events, lines,
                                                    num(msg.get("t"), "time"), fps, timed)
                elif act == "add":
                    plan = timeline.plan_voice_add(src, scene, events, fps, timed, num(msg.get("t"), "time"),
                                                   msg.get("value"))
                    if msg.get("voice") in ("class", "base"):
                        # a silent scene: the voice and the line in one edit, one undo step
                        pv = timeline.plan_set_voice(src, scene, msg["voice"])
                        plan = timeline.Plan(pv.edits + plan.edits, pv.note + "; " + plan.note, checks=plan.checks)
                    elif timeline.voice_state(src, scene)["silent"]:
                        raise EditError("this scene has no voice (VOICE = None); choose one first")
                elif act == "delete":
                    plan = timeline.plan_voice_delete(src, scene, line_at(msg.get("line")))
                else:
                    raise EditError(f"unknown narration edit {act!r}")
            elif kind == "edit.shift":
                plays = list(msg.get("plays") or [])
                voices = list(msg.get("lines") or [])
                plan = timeline.plan_shift(src, scene, events, lines, plays, voices, num(msg.get("dt"), "time"),
                                           fps, timed, bool(msg.get("ripple", True)))
            elif kind == "edit.offset":
                clips = self._scene_model(tr)["clips"]
                i = msg.get("clip")
                if not isinstance(i, int) or not 0 <= i < len(clips) or clips[i]["kind"] != "play":
                    raise EditError("that clip no longer exists")
                anim = msg.get("anim")
                if not isinstance(anim, int):
                    raise EditError("no animation given")
                plan = timeline.plan_anim_offset(src, clips[i], anim, num(msg.get("start"), "time"), fps)
            elif kind == "edit.section":
                secs = (tr.get("audio") or {}).get("sections", [])
                act = msg.get("action")
                if act == "add":
                    plan = timeline.plan_section_add(src, scene, events, fps, timed, num(msg.get("t"), "time"),
                                                     msg.get("name"))
                else:
                    i = msg.get("section")
                    if not isinstance(i, int) or not 0 <= i < len(secs):
                        raise EditError("that section no longer exists")
                    if act == "rename":
                        plan = timeline.plan_section_rename(src, scene, secs[i], msg.get("name"))
                    elif act == "delete":
                        plan = timeline.plan_section_delete(src, scene, secs[i])
                    else:
                        raise EditError(f"unknown section edit {act!r}")
            elif kind == "edit.reorder":
                plan = timeline.plan_reorder(src, scene, events, msg.get("play"), msg.get("target"),
                                             bool(msg.get("after")), timed)
            elif kind == "edit.scene_order":
                plan = timeline.plan_scene_order(src, msg.get("order"), list(self.meta.get("scenes", [])))
            elif kind in ("edit.merge", "edit.split"):
                clips = self._scene_model(tr)["clips"]

                def play_clip(i):
                    if not isinstance(i, int) or not 0 <= i < len(clips) or clips[i]["kind"] != "play":
                        raise EditError("that clip no longer exists")
                    return clips[i]
                anim = msg.get("anim")
                if anim is not None and not isinstance(anim, int):
                    raise EditError("bad animation index")
                if kind == "edit.merge":
                    plan = timeline.plan_merge(src, scene, play_clip(msg.get("clip")), anim,
                                               play_clip(msg.get("into")), num(msg.get("start"), "time"), fps)
                else:
                    if anim is None:
                        raise EditError("no animation given")
                    plan = timeline.plan_split(src, scene, play_clip(msg.get("clip")), anim,
                                               num(msg.get("t"), "time"), events, fps, timed)
            else:
                raise EditError(f"unknown edit {kind}")
        except EditError as e:
            return {"type": "edit.refused", "reason": str(e)}
        new = apply(self.data, plan.edits)
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        r = await self._engine({"op": "verify", "data": new, "scene": scene})
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited scene doesn't run: {r['error']['message']}"}
        after = r["trace"]
        if after.get("error"):
            m = after["error"]["message"]
            if _tts_failed(after["error"]):
                return {"type": "edit.refused", "reason": f"text-to-speech failed (no network?): {m}"}
            return {"type": "edit.refused", "reason": _stop_reason(after["error"])}
        why = timeline.check(plan.checks, tr, after, fps)
        if why:
            return {"type": "edit.refused", "reason": why}
        # a reorder, merge or split changes which play is which: index-by-index
        # "what else moved" would be noise there
        same_plays = not ({"order", "merged", "split"} & set(plan.checks))
        note = plan.note + (timeline.knock_on(tr, after, fps, set(plan.checks.get("starts", {}).get("plays", {})))
                            if same_plays else "")
        if kind in ("edit.shift", "edit.voice", "edit.offset"):
            # at() calls the edit left waiting for nothing read as if something
            # happened then; they go too (no timing changes: they don't wait)
            try:
                cleanup, extra = timeline.dead_anchors(src, tr, Source(new), after, scene)
                if cleanup:
                    tidy = apply(new, cleanup)
                    if Source(tidy).ok:
                        # the tidied file is replayed too: it must time out exactly as the edit did
                        r2 = await self._engine({"op": "verify", "data": tidy, "scene": scene})
                        after2 = r2.get("trace") if "error" not in r2 else None
                        same = after2 is not None and not after2.get("error") \
                            and _timings(after2) == _timings(after) \
                            and not timeline.check(plan.checks, tr, after2, fps)
                        if same:
                            new, note = tidy, note + extra
            except EditError:
                pass
        return await self._write_verified(new, note)

    def _animating(self, tr: dict, obj: dict, f: int) -> str | None:
        """Canvas edits are offered at still moments only (S2 gap 5)."""
        fps = self.meta.get("fps", 15)
        t = f / fps
        ids = {obj.get("id")} | {a.get("id") for a in (obj.get("placement") or {}).get("ancestors") or []}
        for ev in tr["events"]:
            # the last frame of a play shows its end state, near enough: editable
            if ev["kind"] != "play" or not (ev["start"] + 1e-6 < t < ev["start"] + ev["duration"] - 1.5 / fps):
                continue
            if any(a.get("mobject") in ids for a in ev["anims"]):
                return (f"it is animating here (the play() at line {ev.get('call_line')}); "
                        "move the playhead to a still moment or the end of the animation")
        return None

    def _file_content(self, data: bytes):
        """File this revision under its content; remember the last earlier
        revision with the same content, whose frames are this one's too."""
        if not self._deps_digest or getattr(self, "_no_cache", False):
            return
        c = (hashlib.sha256(data).digest(), self._deps_digest, self.worker.quality)
        prev = self._content_rev.get(c)
        if prev is not None and prev != self.rev:
            self._same_as[self.rev] = prev
        self._content_rev[c] = self.rev

    def _cached(self, key: tuple, want=None):
        """A cached frame for key, or for the same frame of an earlier revision
        with the same content (copied under this revision's key)."""
        hit = self.frames.get(key)
        if hit is not None and (want is None or want(hit)):
            return hit
        rev, seen = key[0], set()
        while (rev := self._same_as.get(rev)) is not None and rev not in seen:
            seen.add(rev)
            old = self.frames.get((rev, *key[1:]))
            if old is not None and (want is None or want(old)):
                self.frames.put(key, old)  # no-op when a lesser frame holds the key
                return old
        return hit

    def _seed_frame(self, new: bytes):
        """The frame the edit's verify run drew at the playhead, cached for the
        revision now loaded, when that revision is exactly those bytes."""
        v, self._verified_frame = getattr(self, "_verified_frame", None), None
        if v is None or v[0] != new or self.data != new or self.error:
            return
        _, scene, f, fr = v
        if scene not in self.traces or not 0 <= f < self.frame_count(scene):
            return
        for o in fr.get("objects", []):
            self._annotate(o)
        self.frames.put((self.rev, scene, f, "full", "png"), fr)

    async def _reload_for_reply(self):
        """Reload after our own write; return as soon as the active scene is
        traced (the UI shows it), while the other scenes keep tracing."""
        rev0 = self.rev
        self._load_task = task = asyncio.create_task(self.load())
        while not task.done():
            if self.rev > rev0 and (self.error or self.active in self.traces or not self.meta.get("scenes")):
                return
            await asyncio.sleep(0.05)
        task.result()

    def _check(self, target: dict, r: dict) -> str | None:
        tr = r["trace"]
        if tr.get("error"):
            return _stop_reason(tr['error'])
        fps = self.meta.get("fps", 15)
        if target["kind"] == "literal":
            return None  # the value is what the user typed; the scene must still run
        if target["kind"] == "timing":
            evs = tr["events"]
            i = target["clip"]
            if i >= len(evs):
                return "the edited scene has fewer clips than before"
            ev = evs[i]
            if target["field"] == "duration":
                want = float(target["value"])
                got = ev["duration"] if target.get("anim") is None else ev["anims"][target["anim"]]["run_time"]
                if target.get("anim") is None and ev["kind"] == "play" and not math.isclose(got, want, abs_tol=1.5 / fps):
                    return f"the clip lasts {got:.3f} s after the edit, not {want:.3f} s"
                if target.get("anim") is not None and not math.isclose(got, want, abs_tol=1e-6):
                    return f"the animation lasts {got:.3f} s after the edit, not {want:.3f} s"
                if ev["kind"] == "wait" and not math.isclose(got, want, abs_tol=1.5 / fps):
                    return f"the pause lasts {got:.3f} s after the edit, not {want:.3f} s"
            if target["field"] == "rate_func":
                a = ev["anims"][target["anim"] or 0]
                if a["rate_func"] != target["value"]:
                    return f"easing is {a['rate_func']} after the edit, not {target['value']}"
            return None
        if target["kind"] == "prop":
            o = r.get("object")
            if o is None:
                return "the object isn't on screen at this moment after the edit"
            v = target["value"]
            prop = target["prop"]
            if prop == "color" and "eval" in r:
                if not _same_colour(o.get("color"), r["eval"]):
                    return (f"the colour is {o.get('color')} after the edit, not {r['eval']}: "
                            "something later sets it again")
            if "number" in v and prop in (o.get("values") or {}):
                got = o["values"][prop]
                before = target.get("before")
                close = lambda a, b: math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)  # noqa: E731
                # Mid-animation the value read back is the animated one, so a
                # mismatch alone proves nothing; the edit failed only if it had
                # no effect at all (something later sets the value again).
                if isinstance(got, (int, float)) and not close(got, v["number"]) and \
                        isinstance(before, (int, float)) and close(got, before) and not close(before, v["number"]):
                    return f"{prop} is still {got} after the edit, not {v['number']}: something later sets it again"
        return None

    def _write(self, new: bytes) -> str | None:
        """Write `new`, unless the file on disk is no longer what we planned
        from (saved in an editor while the edit was verifying). Returns why
        nothing was written, or None."""
        try:
            on_disk = self.path.read_bytes()
        except OSError as e:
            return f"can't read the file: {e}"
        if on_disk != self.data:
            return "the file changed on disk while the edit was checked; nothing was written"
        import os
        if not os.access(self.path, os.W_OK):
            # (an atomic replace would go round the read-only flag on POSIX systems)
            return "the file is read-only; make it writable (file properties, or git), then try again"
        try:
            write_atomic(self.path, new)
        except OSError as e:
            self.path.with_name(self.path.name + ".studio-tmp").unlink(missing_ok=True)
            if getattr(e, "errno", None) == 28:
                return "the disk is full; nothing was written"
            return f"can't write the file ({type(e).__name__}: {e}); is it open and locked in another program?"
        self.last_write = new
        self.data = new
        return None

    def diff(self, new: bytes) -> list[dict]:
        import difflib
        a = self.data.decode("utf-8", "replace").splitlines()
        b = new.decode("utf-8", "replace").splitlines()
        out = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            out.append({"line": i1 + 1, "before": a[i1:i2], "after": b[j1:j2]})
        return out

    async def undo_redo(self, which: str) -> dict:
        async with self.edit_lock:
            stack, other = (self.undo, self.redo) if which == "undo" else (self.redo, self.undo)
            if not stack:
                return {"type": "error", "message": f"nothing to {which}"}
            step = stack[-1]
            want_now, target = (step.after, step.before) if which == "undo" else (step.before, step.after)
            if self.data != want_now:
                return {"type": "edit.refused",
                        "reason": f"the file changed since that edit; {which} would overwrite the change"}
            diff = self.diff(target)
            why = self._write(target)
            if why:
                return {"type": "edit.refused", "reason": why}
            stack.pop()
            other.append(step)
            await self._reload_for_reply()
            return {"type": "edit.done", "summary": f"{which}: {step.note}", "diff": diff, "rev": self.rev}

    # -- external changes ---------------------------------------------------------
    async def file_changed(self):
        # after any edit in flight, so its write and the reload stay in order
        async with self.edit_lock:
            try:
                data = self.path.read_bytes()
            except OSError as e:
                if not self.path.exists() and (self.error or {}).get("code") != "missing":
                    # deleted or renamed: keep showing what we have, read-only, until it's back
                    self.error = {"code": "missing", "line": None,
                                  "message": "the file was deleted or renamed outside the studio; "
                                             "nothing can be written until it's back"}
                    self.rev += 1
                    self.pending.clear()
                    await self.notify({"type": "file.changed", "file": self.name, "by": "deleted"})
                    await self.send_model()
                elif self.path.exists():
                    self.error = {"code": "unreadable", "line": None, "message": f"can't read the file: {e}"}
                    await self.send_model()
                return
            if data == self.data and (self.error or {}).get("code") not in ("missing", "unreadable"):
                return  # our own write, or a touch
            self.data = data
            await self.notify({"type": "file.changed", "file": self.name, "by": "external"})
            await self.load()

    def _static_deps(self) -> list[str]:
        """Project modules the file imports by name, anywhere in it (`from style
        import *`, an import inside construct()): known even when the file
        doesn't load, so fixing the module reloads it."""
        if not self.src.ok:
            return []
        names = []
        for n in ast.walk(self.src.tree):
            if isinstance(n, ast.Import):
                names += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                names.append(n.module)
        out = set()
        for m in names:
            for base in {self.path.parent, ROOT}:
                f = base / (m.replace(".", "/") + ".py")
                if f.is_file() and f.resolve() != self.path.resolve():
                    out.add(str(f.resolve()))
        return sorted(out)

    def depends_on(self, path: Path) -> bool:
        try:
            p = str(Path(path).resolve())
        except (OSError, ValueError):
            return False
        return p in {str(Path(d).resolve()) for d in getattr(self, "deps", [])}

    async def deps_changed(self):
        """A local module the scene imports (style.py, manim_kit.py) changed:
        a new engine process imports it afresh, then everything is traced
        again (the cache key covers the module's bytes)."""
        async with self.edit_lock:
            # Windows reports a "modified" event when a module is only read (another
            # engine importing manim_kit.py): restart only if the bytes really changed
            if tracecache.deps_digest(self.path, getattr(self, "deps", [])) == getattr(self, "_deps_seen", None):
                return
            self._verified_frame = None  # drawn with the old module
            await self.notify({"type": "file.changed", "file": self.name, "by": "dependency"})
            await self.worker.fresh()
            await self.load()

    def close(self):
        if self.prefetch_task:
            self.prefetch_task.cancel()
        self.worker.close()


# objects whose positional string arguments are the text on screen (Phase 5 step 5)
TEXT_CLASSES = {"Text", "MarkupText", "MathTex", "Tex", "SingleStringMathTex", "Paragraph", "Title",
                "Variable", "BulletedList"}

STRUCTURAL = ("edit.insert", "edit.composite", "edit.preset", "edit.duplicate", "edit.group", "edit.delete", "edit.delete_clip")
SCENE_EDITS = ("edit.scene_add", "edit.scene_delete", "edit.scene_rename")
TIMELINE = ("edit.voice", "edit.shift", "edit.offset", "edit.merge", "edit.split", "edit.reorder",
            "edit.scene_order", "edit.section")


def _line_of_assignment(new: bytes, name: str, edits: list) -> int | None:
    """The line where the edit assigns `name` (in the edited bytes)."""
    import re
    text = new.decode("utf-8", "replace")
    m = re.search(rf"^[ \t]*{re.escape(name)} = ", text, re.M)
    return text.count("\n", 0, m.start()) + 1 if m else None


AXES_CLASSES = {"Axes", "NumberPlane", "NumberLine", "ThreeDAxes", "ComplexPlane", "PolarPlane"}
RANGE_KW = ("x_range", "y_range", "z_range", "x_length", "y_length", "z_length", "length")
AREA_CALLS = {"get_area", "get_riemann_rectangles"}
AREA_KW = ("x_range", "dx", "fill_opacity", "opacity", "stroke_width")


def _with_coords(coords: dict, plan, k: float):
    tok = moveplan.COORDS.set(coords)
    try:
        return plan(k)
    finally:
        moveplan.COORDS.reset(tok)


def remap_id(oid: str | None, data: bytes, edits: list) -> str | None:
    """The id an object gets after `edits`: ids carry the creating call's
    line and column, which move when lines are added or removed before it."""
    if not oid:
        return oid
    try:
        head, rest = oid.split("@", 1)
        pos, occ = rest.split("#", 1)
        line, col = (int(x) for x in pos.split(":"))
    except ValueError:
        return oid
    src = Source(data)
    if line > len(src.line_starts):
        return oid
    start = src.line_starts[line - 1]
    at = start + col
    dl = dc = 0
    for e in edits:
        if e.end <= start:
            dl += e.text.count("\n") - data[e.start:e.end].count(b"\n")
        elif start <= e.start and e.end <= at and "\n" not in e.text and b"\n" not in data[e.start:e.end]:
            dc += len(e.text.encode("utf-8")) - (e.end - e.start)
    return f"{head}@{line + dl}:{col + dc}#{occ}"


def _expected(kind: str, obj: dict, amount) -> dict | None:
    c, p0, size = obj.get("center"), obj.get("p0"), obj.get("size")
    if not c:
        return None
    if kind == "move":
        dx, dy = amount
        return {"center": [c[0] + dx, c[1] + dy], "p0": [p0[0] + dx, p0[1] + dy] if p0 else None}
    if kind == "scale":
        k, about = amount
        ax, ay = c
        if about and size:
            sx = 1 if "R" in about else -1 if "L" in about else 0
            sy = 1 if about.startswith("U") else -1 if about.startswith("D") else 0
            ax, ay = c[0] + sx * size[0] / 2, c[1] + sy * size[1] / 2

        def f(p):
            return [ax + k * (p[0] - ax), ay + k * (p[1] - ay)]
        return {"center": f(c), "p0": f(p0) if p0 else None,
                "size": [size[0] * k, size[1] * k] if size else None}
    (deg,) = amount
    a = math.radians(deg)
    if not p0:
        return {"center": list(c), "p0": None}
    vx, vy = p0[0] - c[0], p0[1] - c[1]
    return {"center": list(c), "p0": [c[0] + vx * math.cos(a) - vy * math.sin(a),
                                      c[1] + vx * math.sin(a) + vy * math.cos(a)]}


def _why_stuck(obj: dict, got: dict | None, fname: str) -> str | None:
    """Why every candidate missed, when the object says so: something that
    runs after the edited line puts it back (Phase 5, step 3)."""
    if obj.get("updaters"):
        at = obj.get("updater_at")
        where = f" (line {at[1]})" if at and at[0] == fname else ""
        return f"an updater{where} redraws it every frame and puts it back; change it in the code"
    mv = ((got or {}).get("placement") or {}).get("move") or (obj.get("placement") or {}).get("move")
    if mv and mv.get("kind") == "animation":
        return (f"the animation on line {mv['site'][0]} carries it afterwards (it follows a path or "
                "turns about a point); move what it follows, or edit that line")
    if mv and mv.get("kind") == "animate":
        return (f"line {mv['site'][0]} moves it afterwards with .animate.{mv.get('method')}() to a place "
                "worked out from other objects (or a later .animate on it wins); edit that line")
    return None


def _miss(kind: str, expect: dict, got: dict | None, tol: float = 0.011) -> str | None:
    """Why the object after the edit isn't where the drag put it, or None."""
    if got is None or not got.get("center"):
        return "the object isn't on screen at this moment after the edit"
    gc, ec = got["center"], expect["center"]
    if abs(gc[0] - ec[0]) > tol or abs(gc[1] - ec[1]) > tol:
        return f"its centre is at ({gc[0]:.2f}, {gc[1]:.2f}), not ({ec[0]:.2f}, {ec[1]:.2f})"
    if expect.get("p0") and got.get("p0"):
        gp, ep = got["p0"], expect["p0"]
        if abs(gp[0] - ep[0]) > 2 * tol or abs(gp[1] - ep[1]) > 2 * tol:
            return "its shape didn't turn or grow as dragged" if kind != "move" else "only part of it moved"
    if expect.get("size") and got.get("size"):
        if any(abs(g - e) > 2 * tol for g, e in zip(got["size"], expect["size"])):
            return (f"its size is {got['size'][0]:.2f} x {got['size'][1]:.2f}, not "
                    f"{expect['size'][0]:.2f} x {expect['size'][1]:.2f}")
    return None


def _ratio(c0, c1, amount) -> float | None:
    """k when the object moved by k * (dx, dy) instead of (dx, dy)."""
    dx, dy = amount
    mx, my = c1[0] - c0[0], c1[1] - c0[1]
    ks = [m / d for m, d in ((mx, dx), (my, dy)) if abs(d) > 1e-3]
    if not ks or any(k <= 0.05 for k in ks) or max(ks) - min(ks) > 0.02 or abs(ks[0] - 1) < 0.01:
        return None
    return ks[0]


def _related(objs: list, oid) -> set:
    """An object's own id, the groups it is in and its parts."""
    idx = {o["id"]: i for i, o in enumerate(objs)}
    if oid not in idx:
        return {oid}
    out = {oid}
    i = objs[idx[oid]].get("parent")
    while i is not None and i < len(objs):
        out.add(objs[i]["id"])
        i = objs[i].get("parent")
    for o in objs:
        j = o.get("parent")
        while j is not None and j < len(objs):
            if objs[j]["id"] == oid:
                out.add(o["id"])
                break
            j = objs[j].get("parent")
    return out


def _also_moved(obj: dict, before: list, after: list, data: bytes, edits: list) -> list[str]:
    """Other objects that moved with the edit (not the object's own parts or groups)."""
    mine = _related(before, obj.get("id"))
    after_by_id = {o["id"]: o for o in after}
    names = []
    for o in before:
        if o["id"] in mine or o.get("virtual") or not o.get("center"):
            continue
        a = after_by_id.get(remap_id(o["id"], data, edits))
        if a is None or not a.get("center"):
            continue
        if abs(a["center"][0] - o["center"][0]) > 0.01 or abs(a["center"][1] - o["center"][1]) > 0.01:
            names.append(o.get("name") or o["class"])
    return sorted(set(names))


def _same_colour(a: str | None, b: str | None, tol: int = 2) -> bool:
    """Hex colours equal up to float rounding (#fb6254 vs #fc6255)."""
    try:
        return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tol for i in (1, 3, 5))
    except (TypeError, ValueError, IndexError):
        return a == b


def _has_runtime(expr) -> bool:
    for n in ast.walk(expr):
        if isinstance(n, ast.Call) and any(k.arg == "run_time" for k in n.keywords):
            return True
    return False
