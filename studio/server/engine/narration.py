"""What a scene says and plays, recorded while it runs (Phase 4).

Patched while the studio's play hook is on (its own runs, never a real
render):
- `Scene.add_sound` / `Scene.add_subcaption`: recorded, not mixed. The
  studio never writes video, and Manim's add_sound converts the file to WAV
  on every call.
- `TimedScene.say` (and so `line()`): the line's text, caption, requested
  and real start, length and the scene-file call behind it.
- `VoiceoverScene.voiceover`: the same, plus bookmarks (read-only on the
  timeline: voiceover() blocks, so its timing can't be edited).
- `Scene.next_section`: recorded (name, time), not split into files.
- the speech service's synthesis is serialised: cursor threads replaying a
  new line must not synthesise it twice at once.

Records go to `scene._studio_audio` when the run asks for them (a trace);
cursors get none.
"""

from __future__ import annotations

import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from manim import Scene

_tracker = None
_installed = False
_tts_lock = threading.RLock()


def _site(depth: int = 2):
    """The innermost scene-file frame on the stack: (span, func, chain)."""
    f = sys._getframe(depth)
    while f is not None and not _tracker.is_user(f):
        f = f.f_back
    if f is None:
        return None, None, []
    from .identity import site_of
    s = site_of(f)
    return s.span(), s.func, [c.span() for c in _tracker.user_chain(f)]


def _rec(scene):
    """The record lists, or None when this run doesn't record."""
    if getattr(scene.renderer, "_studio_hook", None) is None:
        return None
    return getattr(scene, "_studio_audio", None)


def _studio(scene) -> bool:
    return getattr(scene.renderer, "_studio_hook", None) is not None


def install(tracker):
    global _tracker, _installed
    _tracker = tracker
    if _installed:
        return
    _installed = True

    orig_sound, orig_sub = Scene.add_sound, Scene.add_subcaption

    def add_sound(self, sound_file, time_offset=0, gain=None, **kwargs):
        if not _studio(self):
            return orig_sound(self, sound_file, time_offset, gain, **kwargs)
        rec = _rec(self)
        if rec is not None:
            span, func, chain = _site()
            rec["sounds"].append({"file": str(Path(sound_file).resolve()),
                                  "start": round(self.renderer.time + float(time_offset), 6),
                                  "gain": gain, "call": span, "func": func, "chain": chain,
                                  "line": rec["_open"][-1] if rec["_open"] else None})

    def add_subcaption(self, content, duration=1, offset=0):
        if not _studio(self):
            return orig_sub(self, content, duration, offset)
        rec = _rec(self)
        if rec is not None:
            start = self.renderer.time + float(offset)
            rec["captions"].append({"text": str(content), "start": round(start, 6),
                                    "end": round(start + float(duration), 6),
                                    "line": rec["_open"][-1] if rec["_open"] else None})

    Scene.add_sound, Scene.add_subcaption = add_sound, add_subcaption

    orig_section = Scene.next_section

    def next_section(self, name="unnamed", *args, **kwargs):
        if not _studio(self):
            return orig_section(self, name, *args, **kwargs)
        rec = _rec(self)
        if rec is not None:
            span, func, chain = _site()
            rec["sections"].append({"name": str(name), "start": round(self.renderer.time, 6), "call": span,
                                    "func": func, "chain": chain,
                                    "skip": bool(kwargs.get("skip_animations", args[1] if len(args) > 1 else False))})
    Scene.next_section = next_section

    try:
        import manim_kit
    except Exception:
        manim_kit = None
    if manim_kit is not None and hasattr(manim_kit, "TimedScene"):
        TS = manim_kit.TimedScene
        orig_say = TS.say

        @contextmanager
        def say(self, text, caption=None):
            rec = _rec(self)
            if rec is None:
                with orig_say(self, text, caption=caption) as d:
                    yield d
                return
            span, func, chain = _site(3)
            now = self.renderer.time
            free = getattr(self, "_voice_free", 0.0)
            i = len(rec["lines"])
            entry = {"index": i, "kind": "say", "text": str(text), "caption": caption,
                     "requested": round(now, 6), "start": round(max(now, free), 6),
                     "call": span, "func": func, "chain": chain}
            rec["lines"].append(entry)
            rec["_open"].append(i)
            try:
                with orig_say(self, text, caption=caption) as d:
                    entry["duration"] = round(float(d), 6)
                    shown = caption or text
                    entry["hold"] = round(max(float(d), len(shown) / self.READ_CPS + self.READ_PAD), 6)
                    yield d
            finally:
                rec["_open"].pop()
                entry["block_end"] = round(self.renderer.time, 6)
        TS.say = say

    try:
        from manim_voiceover import VoiceoverScene
    except Exception:
        VoiceoverScene = None
    if VoiceoverScene is not None:
        orig_vo = VoiceoverScene.voiceover

        @contextmanager
        def voiceover(self, text=None, ssml=None, **kwargs):
            rec = _rec(self)
            if rec is None:
                with orig_vo(self, text=text, ssml=ssml, **kwargs) as tr:
                    yield tr
                return
            span, func, chain = _site(3)
            i = len(rec["lines"])
            entry = {"index": i, "kind": "voiceover", "text": str(text if text is not None else ssml),
                     "caption": kwargs.get("subcaption"), "requested": round(self.renderer.time, 6),
                     "start": round(self.renderer.time, 6), "call": span, "func": func, "chain": chain}
            rec["lines"].append(entry)
            rec["_open"].append(i)
            try:
                with orig_vo(self, text=text, ssml=ssml, **kwargs) as tr:
                    entry["start"] = round(float(getattr(tr, "start_t", entry["start"])), 6)
                    entry["duration"] = round(float(getattr(tr, "duration", 0.0)), 6)
                    entry["hold"] = entry["duration"]
                    marks = getattr(tr, "bookmark_times", None) or {}
                    entry["bookmarks"] = [{"name": str(k), "t": round(float(v), 6)} for k, v in marks.items()]
                    yield tr
            finally:
                rec["_open"].pop()
                entry["block_end"] = round(self.renderer.time, 6)
        VoiceoverScene.voiceover = voiceover

    # one synthesis at a time per process
    try:
        import edge_tts_service
        svc = edge_tts_service.EdgeTTSService
        orig_gen = svc._wrap_generate_from_text

        def gen(self, text, **kwargs):
            with _tts_lock:
                return orig_gen(self, text, **kwargs)
        svc._wrap_generate_from_text = gen
    except Exception:
        pass


def new_record() -> dict:
    return {"lines": [], "captions": [], "sounds": [], "sections": [], "_open": []}


def finish(rec: dict | None, cls) -> dict:
    """The record as sent in a trace (cls: the scene class)."""
    if rec is None:
        return {"lines": [], "captions": [], "sounds": [], "sections": [], "burned": False}
    out = {k: v for k, v in rec.items() if not k.startswith("_")}
    out["burned"] = bool(getattr(cls, "CAPTIONS", False))
    for ln in out["lines"]:
        ln.setdefault("duration", 0.0)
        ln.setdefault("hold", ln["duration"])
        ln.setdefault("block_end", ln["start"])
        snd = next((s for s in out["sounds"] if s["line"] == ln["index"]), None)
        ln["audio"] = snd["file"] if snd else None
    return out
