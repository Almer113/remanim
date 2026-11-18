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
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from .code import planner
from .code.census import classify, summary
from .code.source import Source, Span
from .code.splice import Edit, EditError, apply, write_atomic
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


class Document:
    def __init__(self, path: Path, api: list[str], notify):
        self.path = path.resolve()
        self.name = rel(self.path)
        self.api = set(api)
        self.notify = notify  # async callback(dict) to every client
        self.data = self.path.read_bytes()
        self.rev = 0
        self.src = Source(self.data)
        self.worker = WorkerHandle(str(self.path), on_restart=self._restarted)
        self.meta: dict = {}           # scenes, fps, size
        self.traces: dict[str, dict] = {}
        self.error: dict | None = None
        self.undo: list[UndoStep] = []
        self.redo: list[UndoStep] = []
        self.pending: dict[str, Pending] = {}
        self.frames = FrameCache()
        self.active: str | None = None
        self.edit_lock = asyncio.Lock()
        self.load_lock = asyncio.Lock()
        self.last_write: bytes | None = None
        self.prefetch_task: asyncio.Task | None = None

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
        self.rev += 1
        self.pending.clear()  # planned against the old bytes
        self.src = Source(self.data)
        self.traces = {}
        self.error = None
        if not self.src.ok:
            e = self.src.error
            self.error = {"code": "parse", "message": f"SyntaxError: {e.msg}", "line": e.lineno}
            await self.send_model()
            return
        r = await self.worker.request({"op": "load", "data": self.data})
        if "error" in r:
            self.error = {"code": "crash", **r["error"]}
            await self.send_model()
            return
        self.meta = r
        order = list(r["scenes"])
        if self.active in order:
            order.remove(self.active)
            order.insert(0, self.active)
        elif order:
            self.active = order[0]
        for name in order:
            if gen != self._load_gen:
                return  # superseded (another edit, undo or save): stop tracing old bytes
            t = await self.worker.request({"op": "trace", "scene": name})
            if "error" in t and "events" not in t:
                t = {"name": name, "events": [], "duration": 0, "error": t["error"], "bases": []}
            self.traces[name] = t
            if name == self.active:
                await self.send_model()
                await self.activate(name)
        await self.send_model()

    async def activate(self, scene: str):
        self.active = scene
        tr = self.traces.get(scene)
        if tr is None:
            return
        await self.worker.request({"op": "activate", "scene": scene, "duration": tr["duration"]})
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
                todo = [f for f in range(n) if self.frames.get((rev, scene, f, "half", "jpeg")) is None
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
    async def frame(self, scene: str, f: int, size="full", fmt="png", ids=False, background=False):
        if scene not in self.traces:
            return {"error": {"message": f"no scene {scene!r} traced in this revision", "code": "scene"}}
        f = max(0, min(int(f), self.frame_count(scene) - 1))  # Manim never renders outside the scene
        key = (self.rev, scene, f, size, fmt)
        hit = self.frames.get(key)
        if hit is not None and (not ids or "idmap" in hit):
            return hit
        r = await self.worker.request({"op": "frame", "scene": scene, "f": f, "ids": ids,
                                       "size": size, "fmt": fmt}, background=background)
        if "error" in r:
            return r
        if ids:
            for o in r.get("objects", []):
                self._annotate(o)
        self.frames.put(key, r)
        return r

    def _restarted(self):
        """The worker was replaced (crash or deadline): it has nothing loaded.
        Reload, but not forever: code that hangs on every load stays an error
        until the file changes."""
        self._restarts_here = getattr(self, "_restarts_here", {})
        n = self._restarts_here[self.data] = self._restarts_here.get(self.data, 0) + 1
        if n > 2:
            self.error = {"code": "timeout", "message": "the engine had to be restarted 3 times for this "
                                                        "version of the file; fix the code, then save"}
            asyncio.get_running_loop().create_task(self.send_model())
            return
        asyncio.get_running_loop().create_task(self.load())

    def _annotate(self, o: dict):
        """Name, tier and source text for an object, from the code."""
        site = o.get("site") or o.get("user_site")
        o["name"] = self._label(o.get("chain_spans") or []) or             (self.name_at(o.get("site")) if o.get("site") else None)
        o["tier"] = self.tier_at(site[0]) if site else 3
        if o.get("site"):
            call = self.src.find_call(Span(*o["site"]))
            if call is not None:
                o["call_text"] = self.src.text(call)[:300]
                o["kwargs"] = {k.arg: self.src.text(k.value)[:120] for k in call.keywords if k.arg}
                o["args"] = [self.src.text(a)[:120] for a in call.args]

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

    # -- the model sent to the UI ---------------------------------------------
    def model(self) -> dict:
        scenes = []
        census = summary(classify(self.src.tree, self.api)) if self.src.ok else None
        for name in self.meta.get("scenes", []) if self.src.ok else []:
            tr = self.traces.get(name)
            if tr is None:
                scenes.append({"name": name, "pending": True})
                continue
            scenes.append(self._scene_model(tr))
        return {"type": "model", "file": self.name, "rev": self.rev, "session": SESSION, "scenes": scenes,
                "fps": self.meta.get("fps", 15), "width": self.meta.get("width", 854),
                "height": self.meta.get("height", 480), "error": self.error, "census": census,
                "active": self.active, "undo": bool(self.undo), "redo": bool(self.redo),
                "source": self.data.decode("utf-8", "replace")}

    def _scene_model(self, tr: dict) -> dict:
        clips, rows = [], OrderedDict()
        for i, ev in enumerate(tr["events"]):
            call = self.src.find_call(Span(*ev["call"])) if ev.get("call") and self.src.ok else None
            name = Source.call_name(call) if call is not None else None
            lock = None
            if ev.get("in_helper"):
                lock = f"inside {ev.get('func')}() — editing it would change every use"
            elif name not in ("play", "wait", "at"):
                lock = f"timed by {name or 'library code'}() (line {ev.get('call_line')})"
            runtimes = []
            if call is not None and name == "play":
                for a in call.args:
                    runtimes.append(_has_runtime(a))
            # Edits and the Inspector work in the code's own numbers (wait(0.5) is 0.5,
            # not the 7 frames = 0.4667 s it plays for at 15 fps).
            clip = {"index": i, "kind": ev["kind"], "start": ev["start"],
                    "duration": ev.get("nominal", ev["duration"]), "played": ev["duration"],
                    "call": ev.get("call"), "call_name": name, "func": ev.get("func"),
                    "line": ev.get("call_line"), "in_helper": ev.get("in_helper"), "lock": lock,
                    "anims": ev["anims"], "anim_runtimes": runtimes,
                    "tier": self.tier_at(ev["call_line"]) if ev.get("call_line") else 3,
                    "text": self.src.text(call)[:200] if call is not None else None}
            if name == "play" and call is not None and Source.keyword(call, "run_time") is not None:
                clip["play_runtime"] = True
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
        return {"name": tr["name"], "duration": tr["duration"], "error": tr.get("error"),
                "bases": tr.get("bases", []), "target": tr.get("target"), "clips": clips,
                "rows": list(rows.values()), "frames": self.frame_count(tr["name"])}

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
            if msg.get("rev") != self.rev:
                return {"type": "error", "code": "stale", "message": "the file changed; try again"}
            if not self.src.ok:
                return {"type": "edit.refused", "reason": "the file doesn't parse; fix it first"}
            scene = msg.get("scene")
            tr = self.traces.get(scene)
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
                              "field": msg["field"], "value": msg["value"]}
                elif msg["type"] == "edit.prop":
                    obj = msg["object"]
                    plan = planner.plan_property(self.src, obj, msg["prop"], msg["value"])
                    target = {"kind": "prop", "object": obj["id"], "f": msg["f"], "prop": msg["prop"],
                              "value": msg["value"], "before": (obj.get("values") or {}).get(msg["prop"])}
                else:
                    return {"type": "error", "message": f"unknown edit {msg['type']}"}
            except EditError as e:
                return {"type": "edit.refused", "reason": str(e)}
            new = apply(self.data, plan.edits)
            if plan.confirm:
                token = hashlib.sha1(new).hexdigest()[:12]
                self.pending[token] = Pending(token, scene, new, plan.note, plan.edits, plan.checks, target,
                                              base=self.data)
                return {"type": "edit.preview", "token": token, "summary": plan.note,
                        "why": plan.confirm, "diff": self.diff(new)}
            return await self._verify_and_write(scene, new, plan.note, target)

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
            return await self._verify_and_write(p.scene, p.data, p.note, p.target)

    async def _verify_and_write(self, scene: str, new: bytes, note: str, target: dict) -> dict:
        if not Source(new).ok:
            return {"type": "edit.refused", "reason": "the edit would not parse"}
        req = {"op": "verify", "data": new, "scene": scene}
        if target["kind"] == "prop":
            req.update(object=target["object"], f=target["f"])
            if "name" in target["value"]:
                req["eval_name"] = target["value"]["name"]
        r = await self.worker.request(req)
        if "error" in r:
            return {"type": "edit.refused", "reason": f"the edited scene doesn't run: {r['error']['message']}"}
        why = self._check(target, r)
        if why:
            return {"type": "edit.refused", "reason": why}
        before = self.data
        diff = self.diff(new)
        why = self._write(new)
        if why:
            return {"type": "edit.refused", "reason": why}
        self.undo.append(UndoStep(before, new, note))
        self.redo.clear()
        await self._reload_for_reply()
        return {"type": "edit.done", "summary": note, "diff": diff, "rev": self.rev}

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
            return f"the edited scene stops with {tr['error']['message']}"
        fps = self.meta.get("fps", 15)
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
        try:
            write_atomic(self.path, new)
        except OSError as e:
            self.path.with_name(self.path.name + ".studio-tmp").unlink(missing_ok=True)
            return f"can't write the file ({type(e).__name__}: {e}); is it locked by another program?"
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
            except OSError:
                return
            if data == self.data:
                return  # our own write, or a touch
            self.data = data
            await self.notify({"type": "file.changed", "file": self.name, "by": "external"})
            await self.load()

    def close(self):
        if self.prefetch_task:
            self.prefetch_task.cancel()
        self.worker.close()


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
