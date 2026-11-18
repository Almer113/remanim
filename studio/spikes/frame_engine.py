"""Spike S1: show any moment of a scene without rendering the video.

How it works ("replay to t"): run the scene's construct() with every
animation skipped, which only jumps mobjects to their end states and is
cheap. The one play() that spans time t is instead interpolated to the
right point, the frame is drawn, and construct() is stopped there.

The engine stays resident: the scene module is imported once, so later
frames pay only for construct() up to t, not for Python and Manim start-up.
LaTeX is compiled once into its own cache folder and read back from disk.

Usage as a library:
    eng = FrameEngine("order_matters.py")
    img = eng.frame_at("Intro", 3.2)       # PIL image
    eng.trace("Intro")                      # [(start, duration, kind), ...]
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manim import Scene, Wait, config, tempconfig  # noqa: E402
from manim.renderer.cairo_renderer import CairoRenderer  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

QUALITIES = {"l": "low_quality", "m": "medium_quality", "h": "high_quality"}


def _install_caches() -> None:
    """Process-wide memo caches for work replay repeats on every frame.
    Both are exact: the keys cover everything the result depends on."""
    import functools

    import manim_kit
    from manim import Text

    # Narration length: decoded from the mp3 on every say(). Key: path+mtime.
    if not hasattr(manim_kit.audio_seconds, "cache_info"):
        raw = manim_kit.audio_seconds

        @functools.lru_cache(maxsize=None)
        def _cached(path: str, mtime: float) -> float:
            return raw(path)
        manim_kit.audio_seconds = lambda path: _cached(str(path), os.path.getmtime(path))
        manim_kit.audio_seconds.cache_info = _cached.cache_info

    # Text: Manim's own SVG cache is off for Text by default; its SVG file
    # name is already a hash of the text and all its settings.
    if not getattr(Text.__init__, "_studio", False):
        orig = Text.__init__

        def init(self, *a, use_svg_cache=True, **k):
            orig(self, *a, use_svg_cache=use_svg_cache, **k)
        init._studio = True
        Text.__init__ = init


def _flat(anims):
    """Animations, including those inside AnimationGroup/Succession."""
    for a in anims:
        yield a
        yield from _flat(getattr(a, "animations", []) or [])


def _has_time_updaters(scene) -> bool:
    return bool(scene.updaters) or any(
        m.has_time_based_updater() for m in scene.get_mobject_family_members())


class _StopAt(Exception):
    """Raised inside play() once the requested frame is captured."""


class FrameEngine:
    # Tried and dropped: skipping the deep copies that begin() makes for plays
    # that are only jumped to their end. Whether that is safe depends on each
    # animation's internals (FadeIn fades its copy; DrawBorderThenFill reuses
    # its start state), so it broke frames. Exactness wins over speed here.

    def __init__(self, scene_file: str | Path, quality: str = "l"):
        self.path = (ROOT / scene_file).resolve()
        self.quality = QUALITIES[quality]
        os.chdir(ROOT)  # scene code and the voiceover cache use relative paths
        self._config = {
            "dry_run": True, "disable_caching": True, "quality": self.quality,
            "verbosity": "ERROR", "progress_bar": "none",
            # own LaTeX folder: never fights the preview server over temp files
            "tex_dir": str(ROOT / "media" / "Tex_studio"),
        }
        _install_caches()
        with tempconfig(self._config):
            self.module = self._load()

    def apply_config(self) -> None:
        """Set the engine's config for the whole process (cursor threads
        can't each use tempconfig: config is one global object)."""
        for k, v in self._config.items():
            config[k] = v

    # -- loading ---------------------------------------------------------
    def _load(self):
        name = f"_studio_{self.path.stem}"
        spec = importlib.util.spec_from_file_location(name, self.path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    def scenes(self) -> list[str]:
        return [n for n, obj in vars(self.module).items()
                if inspect.isclass(obj) and issubclass(obj, Scene)
                and obj.__module__ == self.module.__name__
                and "construct" in vars(obj)]

    # -- core --------------------------------------------------------------
    def _run(self, scene_name: str, t: float | None, events: list | None):
        """Run construct() skipping everything. With t, stop at t and return
        the frame there; without t, run to the end. Records play spans."""
        cls = getattr(self.module, scene_name)
        orig_play = CairoRenderer.play
        captured: dict = {}

        def play(renderer, scene, *args, **kwargs):
            # Mirrors CairoRenderer.play during a real render, minus drawing,
            # so the clock and time-based updaters match the video exactly:
            # a play of d seconds writes len(arange(0, d, step)) frames, and
            # its updaters see the time of its last frame, not d.
            renderer.skip_animations = True  # no caching, no file output
            step = 1 / config.frame_rate
            start = renderer.time
            scene.compile_animation_data(*args, **kwargs)
            dur = scene.duration
            frozen = scene.is_current_animation_frozen_frame()
            n_frames = int(dur / step) if frozen else len(np.arange(0, dur, step))
            if events is not None:
                kind = "wait" if (len(args) == 1 and isinstance(args[0], Wait)) else "play"
                events.append((round(start, 4), round(n_frames * step, 4), kind))
            hit = t is not None and start <= t < start + n_frames * step
            scene.begin_animations()
            hit = t is not None and start <= t < start + n_frames * step
            # The clock advances exactly as add_frame() does it (one += per
            # frame, or one multiply for a frozen wait): float rounding
            # decides how many frames the next at()/wait() gets.
            if hit:
                times = np.arange(0, dur, step) if not frozen else [0.0]
                k = min(int((t - start) / step + 1e-6), n_frames - 1)
                clock = start
                for i in range(k):
                    clock += step
                if not frozen and not _has_time_updaters(scene):
                    # nothing integrates dt: one jump gives the same state
                    renderer.time = clock
                    scene.update_to_time(times[k])
                elif not frozen:
                    # step frame by frame up to t, like the real render
                    for i, lt in enumerate(times[: k + 1]):
                        renderer.time = start + i * step  # clock-reading updaters
                        scene.update_to_time(lt)
                renderer.time = clock
                renderer.static_image = None
                renderer.update_frame(scene, ignore_skipping=True)
                captured["frame"] = renderer.get_frame()
                raise _StopAt
            if not frozen and n_frames:
                scene.update_to_time(np.arange(0, dur, step)[-1])
            for anim in scene.animations:
                anim.finish()
                anim.clean_up_from_scene(scene)
            renderer.static_image = None
            if frozen:
                renderer.time += n_frames * step
            else:
                for _ in range(n_frames):
                    renderer.time += step
            renderer.num_plays += 1

        CairoRenderer.play = play
        try:
            with tempconfig(self._config):
                scene = cls()
                try:
                    scene.render()
                except _StopAt:
                    pass
                if "frame" not in captured:
                    # t past the end (or no t): show the final state
                    scene.renderer.static_image = None
                    scene.renderer.update_frame(scene, ignore_skipping=True)
                    captured["frame"] = scene.renderer.get_frame()
        finally:
            CairoRenderer.play = orig_play
        return captured["frame"], scene

    def frame_at(self, scene_name: str, t: float) -> Image.Image:
        frame, _ = self._run(scene_name, t, None)
        return Image.fromarray(frame).convert("RGB")

    def trace(self, scene_name: str) -> list[tuple[float, float, str]]:
        events: list = []
        self._run(scene_name, None, events)
        return events
