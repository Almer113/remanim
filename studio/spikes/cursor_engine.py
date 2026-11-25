"""Spike S1, part 2: live cursors, so most frames need no replay from zero.

A cursor is one run of the scene's construct() in its own thread, paused
inside a play(). Asked for time t, it moves forward to t (cheap: everything
in between is skipped, as in frame_engine.py) and draws the frame there.
A cursor can't go back, so the pool keeps several of them parked along
the timeline, and a request uses the latest cursor at or before t. A used
cursor stays where it stopped (useful for scrubbing forward); a background
thread puts a fresh one back on the park spot it left.

Timing semantics are exactly frame_engine's (same as an uncached render).

    pool = CursorPool(engine, "Descent3D", park_every=1.0)
    img = pool.frame_at(4.2)
"""

from __future__ import annotations

import queue
import threading

import numpy as np
from manim import Wait, config
from manim.renderer.cairo_renderer import CairoRenderer
from PIL import Image

from frame_engine import FrameEngine, _has_time_updaters

_orig_play = CairoRenderer.play


def _dispatch_play(renderer, scene, *args, **kwargs):
    hook = getattr(renderer, "_studio_hook", None)
    if hook is None:
        return _orig_play(renderer, scene, *args, **kwargs)
    return hook(renderer, scene, *args, **kwargs)


CairoRenderer.play = _dispatch_play


def _serialise_file_backed_mobjects() -> None:
    """Text, MathTex and SVGMobject write and read files in media/ (Text
    rewrites its SVG each time). Two cursor threads building the same text
    at once read a half-written file. One re-entrant lock around them."""
    from manim import MarkupText, SingleStringMathTex, SVGMobject, Text
    lock = threading.RLock()
    for cls in (SVGMobject, Text, MarkupText, SingleStringMathTex):
        orig = cls.__init__
        if getattr(orig, "_studio_locked", False):
            continue

        def init(self, *a, __orig=orig, **k):
            with lock:
                __orig(self, *a, **k)
        init._studio_locked = True
        cls.__init__ = init


_serialise_file_backed_mobjects()


class _Behind(Exception):
    """The cursor is already past the requested time."""


class Cursor:
    def __init__(self, engine: FrameEngine, scene_name: str, park: float = 0.0):
        self.engine, self.scene_name = engine, scene_name
        self.requests: queue.Queue = queue.Queue()
        self.replies: queue.Queue = queue.Queue()
        self.position = 0.0      # how far it has got (start of its current play)
        self.park = park         # where the pool wants it to wait
        self.parked = threading.Event()
        self.dead = False
        self.lock = threading.Lock()  # one request at a time
        self.thread = threading.Thread(target=self._main, daemon=True)
        self.thread.start()
        self.requests.put(("park", park))

    # -- called from the pool ---------------------------------------------
    def frame_at(self, t: float) -> np.ndarray | None:
        """Frame at t, or None if this cursor is already past t."""
        with self.lock:
            if self.dead:
                return None
            self.requests.put(("frame", t))
            return self.replies.get()

    def close(self):
        self.requests.put(("stop", 0.0))

    # -- the thread ---------------------------------------------------------
    def _main(self):
        cls = getattr(self.engine.module, self.scene_name)
        pending: list = []  # a request carried over from one play to the next
        step = 1 / config.frame_rate

        def next_request():
            if pending:
                return pending.pop()
            return self.requests.get()

        def hook(renderer, scene, *args, **kwargs):
            renderer.skip_animations = True
            start = renderer.time
            self.position = start
            scene.compile_animation_data(*args, **kwargs)
            dur = scene.duration
            frozen = scene.is_current_animation_frozen_frame()
            times = np.arange(0, dur, step)
            n_frames = int(dur / step) if frozen else len(times)
            end = start + n_frames * step
            scene.begin_animations()
            stepping = not frozen and _has_time_updaters(scene)
            done = -1  # last local frame applied
            while True:
                kind, t = next_request()
                if kind == "stop":
                    raise SystemExit
                if t >= end:
                    pending.append((kind, t))
                    break
                if t < start:
                    self._reply(kind, None)
                    self.dead = True
                    raise SystemExit
                if kind == "park":
                    self.parked.set()
                    continue
                k = min(int((t - start) / step + 1e-6), n_frames - 1)
                if frozen:
                    pass
                elif not stepping:
                    scene.update_to_time(times[k])
                    done = k
                else:
                    if k < done:  # dt-updaters can't be run backwards
                        self._reply(kind, None)
                        self.dead = True
                        raise SystemExit
                    for i in range(done + 1, k + 1):
                        renderer.time = start + i * step
                        scene.update_to_time(times[i])
                    done = k
                    self.position = start + k * step  # can't serve earlier now
                clock = start
                for _ in range(k):
                    clock += step
                renderer.time = clock
                renderer.static_image = None
                renderer.update_frame(scene, ignore_skipping=True)
                self._reply(kind, renderer.get_frame())
                renderer.time = start
            # finish this play as frame_engine does
            if not frozen and n_frames and done < len(times) - 1:
                scene.update_to_time(times[-1])
            for anim in scene.animations:
                anim.finish()
                anim.clean_up_from_scene(scene)
            renderer.static_image = None
            renderer.time = start
            if frozen:
                renderer.time += n_frames * step
            else:
                for _ in range(n_frames):
                    renderer.time += step
            renderer.num_plays += 1

        try:
            scene = cls()
            scene.renderer._studio_hook = hook
            try:
                scene.render()
            except SystemExit:
                return
            # past the end: every later time shows the final state
            self.position = scene.renderer.time
            while True:
                kind, t = next_request()
                if kind == "stop":
                    return
                if kind == "park":
                    self.parked.set()
                    continue
                scene.renderer.static_image = None
                scene.renderer.update_frame(scene, ignore_skipping=True)
                self._reply(kind, scene.renderer.get_frame())
        except Exception as e:  # report instead of hanging the caller
            self.dead = True
            self.parked.set()
            self._reply("frame", e)

    def _reply(self, kind, value):
        if kind == "frame":
            self.replies.put(value)
        else:
            self.parked.set()


class CursorPool:
    def __init__(self, engine: FrameEngine, scene_name: str, duration: float,
                 park_every: float = 1.0, max_cursors: int = 12):
        self.engine, self.scene_name = engine, scene_name
        engine.apply_config()
        n = min(max_cursors, max(1, int(duration / park_every) + 1))
        self.spots = [duration * i / n for i in range(n)]
        self.cursors: list[Cursor] = [Cursor(engine, scene_name, p) for p in self.spots]
        self._refill_lock = threading.Lock()

    def wait_parked(self, timeout: float = 120):
        for c in self.cursors:
            c.parked.wait(timeout)

    def frame_at(self, t: float) -> Image.Image:
        while True:
            live = [c for c in self.cursors if not c.dead and c.position <= t + 1e-9]
            if live:
                cur = max(live, key=lambda c: c.position)
            else:
                cur = Cursor(self.engine, self.scene_name, 0.0)
                self.cursors.append(cur)
            spot = cur.park
            frame = cur.frame_at(t)
            if isinstance(frame, Exception):
                raise frame
            if frame is None:  # it was already past t; try another
                self.cursors.remove(cur)
                continue
            if spot < cur.position - 1e-9 and spot in self.spots:
                cur.park = cur.position
                self._refill(spot)
            return Image.fromarray(frame).convert("RGB")

    def _refill(self, spot: float):
        """Put a fresh cursor back on a park spot a used cursor has left."""
        if any(c.park == spot and not c.dead and c.position <= spot for c in self.cursors):
            return
        self.cursors.append(Cursor(self.engine, self.scene_name, spot))
        self.cursors = self.cursors[-40:]  # bound memory in a long session

    def close(self):
        for c in self.cursors:
            c.close()
