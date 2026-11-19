"""The engine inside a worker process: load a scene file, trace it, and draw
any frame (with an ID map for picking). Ported from the Phase 0 spikes
(frame_engine.py, cursor_engine.py, s3_bench.py); the reasoning behind the
clock code is in docs/phase0/S1_frame_at_time.md and S4_timing.md.

This module, identity.py and moves.py are the only places that touch Manim
internals (architecture.md §3): CairoRenderer.play, Mobject.__init__/copy,
Text's SVG cache flag, the __init__ of file-backed mobjects, an audio-length
memo (here and in identity.py), and the Mobject move/scale/rotate methods,
Mobject.add and Transform.begin (moves.py, recording only), and
add_sound / add_subcaption / say / voiceover (narration.py, recording only).
"""

from __future__ import annotations

import functools
import inspect
import os
import queue
import random
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import manim  # noqa: E402
from manim import ImageMobject, Scene, Succession, VMobject, Wait, config, tempconfig  # noqa: E402
from manim.renderer.cairo_renderer import CairoRenderer  # noqa: E402

from .identity import OriginTracker, object_id, parent_map, resolve, site_of  # noqa: E402
from .moves import MoveRecorder, parent_of, placement  # noqa: E402
from . import narration  # noqa: E402

QUALITIES = {"l": "low_quality", "m": "medium_quality", "h": "high_quality"}
SUPPORTED = "0.22."


class EngineError(Exception):
    def __init__(self, message: str, line: int | None = None, tb: str = ""):
        super().__init__(message)
        self.line, self.tb = line, tb


# -- adapter: everything patched in Manim, installed once per process -------
_tracker: OriginTracker | None = None
_recorder: MoveRecorder | None = None
_orig_play = CairoRenderer.play


def install() -> OriginTracker:
    global _tracker
    if _tracker is not None:
        return _tracker
    if not manim.__version__.startswith(SUPPORTED):
        raise EngineError(f"Manim {manim.__version__} is not supported; the studio is pinned to "
                          f"{SUPPORTED}x")
    os.chdir(ROOT)  # scene code and the voiceover cache use relative paths
    _install_thread_rng()

    def dispatch(renderer, scene, *args, **kwargs):
        hook = getattr(renderer, "_studio_hook", None)
        if hook is None:
            return _orig_play(renderer, scene, *args, **kwargs)
        return hook(renderer, scene, *args, **kwargs)
    CairoRenderer.play = dispatch

    # Text, MathTex and SVGMobject read and write files in media/; two cursor
    # threads building the same text read a half-written file (S1).
    from manim import MarkupText, SingleStringMathTex, SVGMobject, Text
    lock = threading.RLock()
    for cls in (SVGMobject, Text, MarkupText, SingleStringMathTex):
        orig = cls.__init__

        def init(self, *a, __orig=orig, **k):
            with lock:
                __orig(self, *a, **k)
        cls.__init__ = init

    # Text: Manim's own SVG cache is off for Text; its file name already
    # hashes the text and every setting, so turning it on is exact.
    orig_text = Text.__init__

    def text_init(self, *a, use_svg_cache=True, **k):
        orig_text(self, *a, use_svg_cache=use_svg_cache, **k)
    Text.__init__ = text_init

    try:  # narration length, decoded from the mp3 on every say()
        import manim_kit
        raw = manim_kit.audio_seconds

        @functools.lru_cache(maxsize=None)
        def cached(path: str, mtime: float) -> float:
            return raw(path)
        manim_kit.audio_seconds = lambda path: cached(str(path), os.path.getmtime(path))
    except Exception:
        pass
    _tracker = OriginTracker()
    global _recorder
    _recorder = MoveRecorder(_tracker)
    narration.install(_tracker)
    return _tracker


def api_names() -> list[str]:
    names = set(dir(manim))
    for mod in ("manim_kit", "style"):
        try:
            names |= set(dir(__import__(mod)))
        except Exception:
            pass
    return sorted(n for n in names if not n.startswith("_"))


# -- helpers ----------------------------------------------------------------
def _has_time_updaters(scene) -> bool:
    return bool(scene.updaters) or any(
        m.has_time_based_updater() for m in scene.get_mobject_family_members())


def _rate_name(f) -> str | None:
    return getattr(f, "__name__", None)


@functools.lru_cache(maxsize=None)
def _default_rate(cls) -> str | None:
    for c in cls.__mro__:
        try:
            p = inspect.signature(c.__init__).parameters.get("rate_func")
        except (TypeError, ValueError):
            continue
        if p is not None and p.default is not inspect.Parameter.empty:
            return _rate_name(p.default)
    return "smooth"


@functools.lru_cache(maxsize=None)
def class_params(cls) -> list[str]:
    """Positional parameter names of the constructor (what `Square(2)`'s 2 is)."""
    try:
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        return []
    out = []
    for p in list(sig.parameters.values())[1:]:
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            out.append(p.name)
        elif p.kind == p.VAR_POSITIONAL:
            out.append(p.name)  # MathTex(*tex_strings)
            break
        else:
            break
    return out


def _hex(c) -> str | None:
    try:
        return manim.ManimColor(c).to_hex().lower()
    except Exception:
        return None


# -- randomness ----------------------------------------------------------------
# `random` and legacy `np.random` are process-wide, but cursors run construct()
# on several threads at once: with shared generators an unseeded scene draws
# different numbers in each cursor and objects jump between spots. Every
# thread gets its own generators instead, seeded like a fresh `manim` run.
_rng_local = threading.local()

_PY_RANDOM = ["betavariate", "binomialvariate", "choice", "choices", "expovariate", "gammavariate",
              "gauss", "getrandbits", "getstate", "lognormvariate", "normalvariate", "paretovariate",
              "randbytes", "randint", "random", "randrange", "sample", "seed", "setstate", "shuffle",
              "triangular", "uniform", "vonmisesvariate", "weibullvariate"]
_NP_RANDOM = ["beta", "binomial", "bytes", "chisquare", "choice", "dirichlet", "exponential", "f",
              "gamma", "geometric", "get_state", "gumbel", "hypergeometric", "laplace", "logistic",
              "lognormal", "logseries", "multinomial", "multivariate_normal", "negative_binomial",
              "noncentral_chisquare", "noncentral_f", "normal", "pareto", "permutation", "poisson",
              "power", "rand", "randint", "randn", "random", "random_integers", "random_sample",
              "ranf", "rayleigh", "sample", "seed", "set_state", "shuffle", "standard_cauchy",
              "standard_exponential", "standard_gamma", "standard_normal", "standard_t",
              "triangular", "uniform", "vonmises", "wald", "weibull", "zipf"]


def _thread_rngs():
    g = getattr(_rng_local, "g", None)
    if g is None:
        g = _rng_local.g = (random.Random(0), np.random.RandomState(0))
    return g


def _install_thread_rng():
    if getattr(random, "_studio_thread_rng", False):
        return

    # Scene.__init__ calls random.seed(config.seed) and config.seed is None by
    # default, which seeds from the OS: a plain `manim` render of an unseeded
    # scene differs every run. The studio must show the same picture in every
    # cursor and after every reload, so an unseeded seed() means seed 0.
    def unseeded(a, k):
        if (not a and k.get("seed", k.get("a")) is None) or (a and a[0] is None):
            return (0,) + tuple(a[1:]), {}
        return a, k

    def py(name):
        def f(*a, **k):
            if name == "seed":
                a, k = unseeded(a, k)
            return getattr(_thread_rngs()[0], name)(*a, **k)
        f.__name__ = name
        return f

    def npf(name):
        def f(*a, **k):
            if name == "seed":
                a, k = unseeded(a, k)
            return getattr(_thread_rngs()[1], name)(*a, **k)
        f.__name__ = name
        return f

    for n in _PY_RANDOM:
        if hasattr(random.Random, n):
            setattr(random, n, py(n))
    for n in _NP_RANDOM:
        if hasattr(np.random.RandomState, n) and hasattr(np.random, n):
            setattr(np.random, n, npf(n))
    random._studio_thread_rng = True


def _seed():
    py, npr = _thread_rngs()
    py.seed(0)
    npr.seed(0)


def _drawn_leaves(scene):
    out = []
    for m in scene.get_mobject_family_members():
        if isinstance(m, ImageMobject):
            out.append(m)
        elif isinstance(m, VMobject) and len(m.points) > 0:
            fill = m.get_fill_opacities()
            stroke = m.get_stroke_opacities()
            vis_fill = len(fill) and float(np.max(fill)) > 0.02
            vis_stroke = m.get_stroke_width() > 0 and len(stroke) and float(np.max(stroke)) > 0.02
            if vis_fill or vis_stroke:
                out.append(m)
    return out


def _id_color(i: int) -> tuple[int, int, int]:
    v = (i * 2654435761) % (1 << 24) or 1
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


class Capture:
    """One drawn frame, and optionally the ID map and the objects in it."""

    def __init__(self, frame: np.ndarray, idmap: np.ndarray | None = None, objects=None):
        self.frame, self.idmap, self.objects = frame, idmap, objects or []


def capture(scene, want_ids: bool) -> Capture:
    r = scene.renderer
    r.static_image = None
    r.update_frame(scene, ignore_skipping=True)
    frame = r.get_frame().copy()
    if not want_ids:
        return Capture(frame)
    idmap, objects = _id_map(scene)
    return Capture(frame, idmap, objects)


_STYLE_ATTRS = ("fill_opacity", "stroke_opacity", "fill_color", "stroke_color", "color",
                "background_stroke_opacity", "background_stroke_color", "background_stroke_width")


def _id_map(scene):
    """Repaint every drawn leaf in a flat colour per selectable object, draw,
    restore the colours exactly. Returns (index image HxW uint32, objects)."""
    parents = parent_map(scene)
    leaves = _drawn_leaves(scene)
    index_of, objects, leaf_index = {}, [], []
    for leaf in leaves:
        sel, origin, how = resolve(leaf, parents)
        if sel is None:
            leaf_index.append(0)
            continue
        k = id(sel)
        if k not in index_of:
            index_of[k] = len(objects) + 1
            objects.append((sel, origin, how))
        leaf_index.append(index_of[k])
    keep = {id(m): i for m, i in zip(leaves, leaf_index)}
    saved = []
    for m in scene.get_mobject_family_members():
        if isinstance(m, VMobject):
            # set_fill / set_stroke also overwrite these plain attributes, which the
            # Inspector reads and later scene code may use: put them back too
            attrs = {a: m.__dict__[a] for a in _STYLE_ATTRS if a in m.__dict__}
            saved.append((m, m.fill_rgbas.copy(), m.stroke_rgbas.copy(), m.background_stroke_rgbas.copy(),
                          m.stroke_width, m.background_stroke_width, getattr(m, "sheen_factor", 0.0), attrs))
        elif isinstance(m, ImageMobject):
            saved.append((m, m.pixel_array.copy()))
    cam = scene.renderer.camera
    bg = cam.background
    shading = getattr(cam, "should_apply_shading", None)
    try:
        for m in scene.get_mobject_family_members():
            i = keep.get(id(m))
            if isinstance(m, ImageMobject):
                if i:
                    m.pixel_array[:, :, :3] = _id_color(i)
                else:
                    m.pixel_array[:, :, 3] = 0
                continue
            if not isinstance(m, VMobject):
                continue
            m.set_stroke(width=0, background=True, family=False)
            if hasattr(m, "sheen_factor"):
                m.sheen_factor = 0.0
            if not i:
                m.set_fill(opacity=0, family=False)
                m.set_stroke(opacity=0, family=False)
                continue
            hexc = "#%02x%02x%02x" % _id_color(i)
            vis_fill = float(np.max(m.get_fill_opacities())) > 0.02
            vis_stroke = m.get_stroke_width() > 0 and float(np.max(m.get_stroke_opacities())) > 0.02
            m.set_fill(hexc, opacity=1 if vis_fill else 0, family=False)
            m.set_stroke(hexc, opacity=1 if vis_stroke else 0, family=False)
        if shading is not None:
            cam.should_apply_shading = False
        black = np.zeros_like(bg)
        black[..., 3] = 255
        cam.background = black
        scene.renderer.static_image = None
        scene.renderer.update_frame(scene, ignore_skipping=True)
        raw = scene.renderer.get_frame()[:, :, :3].astype(np.int64)
    finally:
        cam.background = bg
        if shading is not None:
            cam.should_apply_shading = shading
        for s in saved:
            m = s[0]
            if len(s) == 2:
                m.pixel_array = s[1]
            else:
                m.fill_rgbas, m.stroke_rgbas, m.background_stroke_rgbas = s[1], s[2], s[3]
                m.stroke_width, m.background_stroke_width = s[4], s[5]
                if hasattr(m, "sheen_factor"):
                    m.sheen_factor = s[6]
                m.__dict__.update(s[7])
    code =(raw[:, :, 0] << 16) | (raw[:, :, 1] << 8) | raw[:, :, 2]
    lookup = {(c[0] << 16) | (c[1] << 8) | c[2]: i
              for i, c in ((i, _id_color(i)) for i in range(1, len(objects) + 1))}
    # keep pixels of an exact ID colour with >= 2 same-coloured neighbours:
    # antialiased edges blend with the black background into other codes
    n_same = np.zeros(code.shape, np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                n_same += code == np.roll(np.roll(code, dy, 0), dx, 1)
    out = np.zeros(code.shape, np.uint32)
    valid = (n_same >= 2) & (code != 0)
    if lookup:
        keys = np.array(list(lookup.keys()), np.int64)
        vals = np.array(list(lookup.values()), np.uint32)
        order = np.argsort(keys)
        keys, vals = keys[order], vals[order]
        pos = np.clip(np.searchsorted(keys, code), 0, len(keys) - 1)
        hit = valid & (keys[pos] == code)
        out[hit] = vals[pos[hit]]
    described = [describe_object(m, o, how, parents) for m, o, how in objects]
    # groups the user made (VGroup(a, b)) are selectable too (alt-click, Layers):
    # they have no pixels of their own, so they come after the drawn objects
    index = {id(m): i for i, (m, _, _) in enumerate(objects)}
    for i in range(len(objects)):
        mob = objects[i][0]
        child, p = i, parent_of(mob, parents)
        while p is not None and len(described) < 400:
            po = getattr(p, "_studio_origin", None)
            if po is not None and po.site is not None:
                j = index.get(id(p))
                if j is None:
                    j = index[id(p)] = len(described)
                    d = describe_object(p, po, "group", parents)
                    d["virtual"] = True
                    described.append(d)
                    objects.append((p, po, "group"))
                described[child].setdefault("parent", j)
                child = j
            p = parent_of(p, parents)
    return out, described


def describe_object(mob, origin, how, parents=None) -> dict:
    d = {"id": object_id(mob), "class": type(mob).__name__, "how": how,
         "site": origin.site.span() if origin and origin.site else None,
         "user_site": origin.user_site.span() if origin and origin.user_site else None,
         "chain": [s.func for s in origin.chain] if origin else [],
         "chain_spans": [s.span() for s in origin.chain] if origin else [],
         "func": origin.site.func if origin and origin.site else None,
         "in_helper": bool(origin and origin.site and origin.site.func != "construct"),
         "params": class_params(type(mob)),
         "regenerated": bool(origin and origin.regenerated)}
    try:
        c = mob.get_center()
        d["center"] = [round(float(c[0]), 4), round(float(c[1]), 4)]
        d["size"] = [round(float(mob.width), 4), round(float(mob.height), 4)]
        # a point on the object, to check scales and rotations (the centre alone can't)
        for m in mob.get_family():
            pts = getattr(m, "points", None)
            if pts is not None and len(pts):
                d["p0"] = [round(float(pts[0][0]), 4), round(float(pts[0][1]), 4)]
                break
    except Exception:
        pass
    try:
        d["placement"] = placement(mob, parents or {})
    except Exception:
        pass
    if isinstance(mob, VMobject):
        # A group's own colour is a default nobody sees; report its first drawn part.
        shown = mob if mob.has_points() else next(
            (m for m in mob.family_members_with_points() if isinstance(m, VMobject)), mob)
        d["color"] = _hex(shown.get_color())
    for attr in ("font_size", "radius", "side_length", "text", "stroke_width", "fill_opacity"):
        try:
            v = getattr(mob, attr, None)
        except Exception:  # a property that can't be read mid-animation (Square.side_length during Create)
            continue
        if isinstance(v, (int, float, str)) and not isinstance(v, bool):
            d.setdefault("values", {})[attr] = round(v, 4) if isinstance(v, float) else v
    return d


# -- the engine -----------------------------------------------------------------
class _StopAt(Exception):
    pass


class Engine:
    """One loaded revision of one scene file."""

    _n = 0

    def __init__(self, path: Path, data: bytes, quality: str = "l"):
        self.tracker = install()
        self.path = Path(path).resolve()
        self.config = {
            "dry_run": True, "disable_caching": True, "quality": QUALITIES[quality],
            "verbosity": "ERROR", "progress_bar": "none",
            # own LaTeX folder: never fights the preview server over temp files
            "tex_dir": str(ROOT / "media" / "Tex_studio"),
        }
        self.tracker.set_files([self.path])
        for p in (str(self.path.parent), str(ROOT)):
            if p not in sys.path:
                sys.path.insert(0, p)
        Engine._n += 1
        name = f"_studio_{self.path.stem}_{Engine._n}"
        mod = type(sys)(name)
        mod.__file__ = str(self.path)
        sys.modules[name] = mod
        self.module_name = name
        code = compile(data, str(self.path), "exec")
        try:
            with tempconfig(self.config):
                exec(code, mod.__dict__)
        except Exception as e:
            raise self._error(e) from None
        self.module = mod
        self.pools: dict[str, CursorPool] = {}

    def apply_config(self):
        for k, v in self.config.items():
            config[k] = v

    @property
    def fps(self) -> float:
        with tempconfig(self.config):
            return float(config.frame_rate)

    @property
    def size(self) -> tuple[int, int]:
        with tempconfig(self.config):
            return int(config.pixel_width), int(config.pixel_height)

    @property
    def frame_units(self) -> tuple[float, float]:
        with tempconfig(self.config):
            return float(config.frame_width), float(config.frame_height)

    def scenes(self) -> list[str]:
        """Every Scene subclass defined in the file with a construct() of its
        own or inherited (not Scene's empty one): corpus.md finding."""
        out = []
        for n, obj in vars(self.module).items():
            if inspect.isclass(obj) and issubclass(obj, Scene) and obj.__module__ == self.module.__name__ \
                    and getattr(obj, "construct", None) is not Scene.construct:
                if any("construct" in vars(c) for c in obj.__mro__ if c is not Scene and issubclass(c, Scene)):
                    out.append(n)
        # the file's own render order (a module-level SCENES list) comes first
        order = getattr(self.module, "SCENES", None)
        if isinstance(order, (list, tuple)) and all(isinstance(x, str) for x in order):
            listed = [n for n in order if n in out]
            out = listed + [n for n in out if n not in listed]
        return out

    def _error(self, e: BaseException) -> EngineError:
        line = None
        for fr, ln in traceback.walk_tb(e.__traceback__):
            if str(Path(fr.f_code.co_filename).resolve()).lower() == str(self.path).lower():
                line = ln
        msg = f"{type(e).__name__}: {e}"
        return EngineError(msg, line, "".join(traceback.format_exception(e))[-4000:])

    # -- one run of construct() ------------------------------------------------
    def _event(self, renderer, scene, start, n_frames, step):
        f = sys._getframe(2)
        while f is not None and not self.tracker.is_user(f):
            f = f.f_back
        site = site_of(f) if f is not None else None
        anims = []
        for i, a in enumerate(scene.animations):
            offset = 0.0
            # clip(x, start=s): Succession(Wait(s), x) -- report x and its offset
            parts = getattr(a, "animations", None) if isinstance(a, Succession) else None
            if parts and len(parts) == 2 and isinstance(parts[0], Wait) and not isinstance(parts[1], Wait):
                offset, a = float(a.animations[0].run_time), a.animations[1]
            mob = None if isinstance(a, Wait) else getattr(a, "mobject", None)
            anims.append({"index": i, "class": type(a).__name__, "run_time": round(float(a.run_time), 4),
                          "offset": round(offset, 4),
                          "rate_func": _rate_name(a.rate_func), "default_rate_func": _default_rate(type(a)),
                          "mobject": object_id(mob) if mob is not None else None,
                          "mobject_class": type(mob).__name__ if mob is not None else None,
                          "chain": [c.span() for c in getattr(getattr(mob, "_studio_origin", None), "chain", [])]})
        kind = "wait" if (len(scene.animations) == 1 and isinstance(scene.animations[0], Wait)) else "play"
        return {"kind": kind, "start": round(start, 6), "duration": round(n_frames * step, 6),
                "frames": n_frames,
                # what the code asked for; "duration" is that rounded to whole frames
                "nominal": round(float(getattr(scene, "duration", n_frames * step)), 6),
                "call": site.span() if site else None, "func": site.func if site else None,
                # every scene-file call on the stack, outermost first (which
                # statement of construct() a helper's play() belongs to)
                "chain": [s.span() for s in self.tracker.user_chain(f)] if f is not None else [],
                "call_line": site.line if site else None,
                "in_helper": bool(site and site.func not in ("construct",)),
                "anims": anims}

    def run(self, scene_name: str, t: float | None = None, want_ids: bool = False,
            events: list | None = None, stop: bool = True, audio: dict | None = None):
        """Run construct() with every play skipped to its end; with t, capture
        the frame there and stop (or, with stop=False, run on to the end: one
        run gives both the frame and the whole trace). Returns (Capture,
        scene, end time)."""
        cls = getattr(self.module, scene_name)
        captured: dict = {}
        engine = self

        def hook(renderer, scene, *args, **kwargs):
            renderer.skip_animations = True
            step = 1 / config.frame_rate
            start = renderer.time
            scene.compile_animation_data(*args, **kwargs)
            dur = scene.duration
            frozen = scene.is_current_animation_frozen_frame()
            n_frames = int(dur / step) if frozen else len(np.arange(0, dur, step))
            if events is not None:
                events.append(engine._event(renderer, scene, start, n_frames, step))
            scene.begin_animations()
            hit = t is not None and start <= t < start + n_frames * step
            if hit:
                times = np.arange(0, dur, step) if not frozen else [0.0]
                k = min(int((t - start) / step + 1e-6), n_frames - 1)
                clock = start
                for _ in range(k):
                    clock += step
                if not frozen and not _has_time_updaters(scene):
                    renderer.time = clock
                    scene.update_to_time(times[k])
                elif not frozen:
                    for i, lt in enumerate(times[: k + 1]):
                        renderer.time = start + i * step
                        scene.update_to_time(lt)
                renderer.time = clock
                captured["c"] = capture(scene, want_ids)
                if stop:
                    raise _StopAt
                renderer.time = start
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

        _seed()
        self.tracker.reset_counts()
        scene = None
        try:
            with tempconfig(self.config):
                scene = cls()
                scene.renderer._studio_hook = hook
                scene._studio_audio = audio
                try:
                    scene.render()
                except _StopAt:
                    pass
                if "c" not in captured and t is not None:
                    captured["c"] = capture(scene, want_ids)
        except Exception as e:
            raise self._error(e) from None
        return captured.get("c"), scene, scene.renderer.time

    def trace(self, scene_name: str, t: float | None = None, want_ids: bool = False):
        """The scene's clips; with t, also the frame at t from the same run:
        (trace, Capture or None)."""
        events: list = []
        audio = narration.new_record()
        err = None
        end = 0.0
        cap = None
        try:
            cap, scene, end = self.run(scene_name, t, want_ids, events, stop=False, audio=audio)
        except EngineError as e:
            err = {"message": str(e), "line": e.line, "traceback": e.tb}
            if events:
                last = events[-1]
                end = last["start"] + last["duration"]
        bases = [c.__name__ for c in getattr(self.module, scene_name).__mro__[1:]
                 if c.__module__.startswith("manim") or c.__name__ in ("TimedScene",)][:3]
        cls = getattr(self.module, scene_name)
        out = {"name": scene_name, "events": events, "duration": round(end, 6), "error": err,
               "audio": narration.finish(audio, cls),
               "bases": bases, "target": getattr(getattr(self.module, scene_name), "TARGET", None) or None}
        return out if t is None else (out, cap)

    # -- frames ---------------------------------------------------------------
    def frame(self, scene_name: str, t: float, want_ids: bool) -> Capture:
        pool = self.pools.get(scene_name)
        if pool is not None:
            return pool.frame_at(t, want_ids)
        c, _, _ = self.run(scene_name, t, want_ids)
        return c

    def activate(self, scene_name: str, duration: float, max_cursors: int = 12):
        """Park live cursors along this scene (S1); stop the others."""
        for n in list(self.pools):
            if n != scene_name:
                self.pools.pop(n).close()
        if scene_name not in self.pools and duration > 0:
            self.apply_config()
            self.pools[scene_name] = CursorPool(self, scene_name, duration, max_cursors=max_cursors)

    def close(self):
        for p in self.pools.values():
            p.close()
        self.pools.clear()
        # every load and verify makes a new module; don't keep old revisions alive
        sys.modules.pop(getattr(self, "module_name", ""), None)
        # caches keyed by class or code object would pin the old module through a
        # class the scene file defines; they refill cheaply
        _default_rate.cache_clear()
        class_params.cache_clear()
        from . import identity
        identity._POSITIONS.clear()


# -- live cursors (S1) --------------------------------------------------------
class Cursor:
    def __init__(self, engine: Engine, scene_name: str, park: float = 0.0, start: bool = True):
        self.engine, self.scene_name = engine, scene_name
        self.requests: queue.Queue = queue.Queue()
        self.replies: queue.Queue = queue.Queue()
        self.position = 0.0
        self.park = park
        self.parked = threading.Event()
        self.dead = False
        # set once the cursor is unwinding: a user `finally:` that calls
        # wait() (manim-voiceover does) must not block on the request queue
        self.stopping = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._main, daemon=True)
        self.started = False
        self.requests.put(("park", park, False))
        if start:
            self.start()

    _state = threading.Lock()  # start() and close() race between the warm thread and the pool

    def start(self):
        with self._state:
            if not self.started and not self.dead:
                self.started = True
                self.thread.start()

    def frame_at(self, t: float, want_ids: bool):
        with self.lock:
            if self.dead:
                return None
            self.requests.put(("frame", t, want_ids))
            return self.replies.get()

    def close(self):
        with self._state:
            if not self.started:  # never ran: nothing to unwind, no thread to start
                self.dead = self.stopping = True
                self.parked.set()
                return
        self.requests.put(("stop", 0.0, False))

    def _main(self):
        eng = self.engine
        cls = getattr(eng.module, self.scene_name)
        pending: list = []
        step = 1 / config.frame_rate

        def next_request():
            return pending.pop() if pending else self.requests.get()

        def stop():
            self.stopping = True
            raise SystemExit

        def hook(renderer, scene, *args, **kwargs):
            if self.stopping:
                raise SystemExit
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
            done = -1
            while True:
                kind, t, ids = next_request()
                if kind == "stop":
                    stop()
                if t >= end:
                    pending.append((kind, t, ids))
                    break
                if t < start:
                    self.dead = True
                    self._reply(kind, None)
                    stop()
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
                    if k < done:
                        self.dead = True
                        self._reply(kind, None)
                        stop()
                    for i in range(done + 1, k + 1):
                        renderer.time = start + i * step
                        scene.update_to_time(times[i])
                    done = k
                    self.position = start + k * step
                clock = start
                for _ in range(k):
                    clock += step
                renderer.time = clock
                try:
                    got = capture(scene, ids)
                except Exception as e:  # answer this request with the error; the cursor stays usable
                    got = e
                self._reply(kind, got)
                renderer.time = start
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
            _seed()
            eng.tracker.reset_counts()
            scene = cls()
            scene.renderer._studio_hook = hook
            try:
                scene.render()
            except SystemExit:
                self.dead = True
                self.parked.set()
                return
            self.position = scene.renderer.time
            while True:
                kind, t, ids = next_request()
                if kind == "stop":
                    return
                if kind == "park":
                    self.parked.set()
                    continue
                try:
                    got = capture(scene, ids)
                except Exception as e:
                    got = e
                self._reply(kind, got)
        except BaseException as e:  # report instead of hanging the caller
            self.dead = True
            self.parked.set()
            if not self.stopping:
                self._reply("frame", e)

    def _reply(self, kind, value):
        if kind == "frame":
            self.replies.put(value)
        else:
            self.parked.set()


class CursorPool:
    def __init__(self, engine: Engine, scene_name: str, duration: float,
                 park_every: float = 1.0, max_cursors: int = 12, warm_together: int = 2):
        self.engine, self.scene_name = engine, scene_name
        n = min(max_cursors, max(1, int(duration / park_every) + 1))
        self.spots = [duration * i / n for i in range(n)]
        # Start the first cursor now and the rest a couple at a time: a dozen
        # construct() runs at once fight over the GIL and the LaTeX lock, and the
        # frame someone is waiting for came last (37 s cold in the corpus run).
        self.cursors: list[Cursor] = [Cursor(engine, scene_name, p, start=(i == 0))
                                      for i, p in enumerate(self.spots)]
        self.closed = False
        self.error: tuple[float, EngineError] | None = None
        threading.Thread(target=self._warm, args=(list(self.cursors), warm_together), daemon=True).start()

    def _warm(self, cursors: list, together: int):
        running = [cursors[0]]
        for c in cursors[1:]:
            while not self.closed and sum(1 for r in running if not r.parked.is_set()) >= together:
                time.sleep(0.05)
            if self.closed:
                return
            c.start()
            running.append(c)

    def parked(self) -> int:
        """How many of the spots have a live cursor parked on them (moved-on cursors don't count)."""
        return sum(1 for spot in self.spots
                   if any(c.park == spot and c.parked.is_set() and not c.dead for c in self.cursors))

    MAX_CURSORS = 24  # each holds a whole scene in memory

    def frame_at(self, t: float, want_ids: bool) -> Capture:
        if self.error is not None and t >= self.error[0]:
            raise self.error[1]  # the scene stops here; don't burn another cursor on it
        for _ in range(4):
            # a cursor still warming toward a later spot would run past t
            live = [c for c in self.cursors if c.started and not c.dead and c.position <= t + 1e-9
                    and (c.parked.is_set() or c.park <= t + 1e-9)]
            if live:
                cur = max(live, key=lambda c: c.position)
            else:
                cur = Cursor(self.engine, self.scene_name, 0.0)
                self.cursors.append(cur)
            spot = cur.park
            got = cur.frame_at(t, want_ids)
            if isinstance(got, BaseException):
                err = got if isinstance(got, EngineError) else self.engine._error(got)
                if cur.dead:  # the scene itself failed at this time
                    self._drop(cur, spot)
                    self.error = (t, err)
                raise err
            if got is None:  # it had already moved past t
                self._drop(cur, spot)
                continue
            if spot < cur.position - 1e-9 and spot in self.spots:
                cur.park = cur.position
                self._refill(spot)
            return got
        # cursors keep missing (should not happen): answer from a plain replay
        c, _, _ = self.engine.run(self.scene_name, t, want_ids)
        return c

    def _drop(self, cur: "Cursor", spot: float):
        if cur in self.cursors:
            self.cursors.remove(cur)
        cur.close()
        if spot in self.spots:
            self._refill(spot)

    def _refill(self, spot: float):
        if self.closed or any(c.park == spot and not c.dead and c.position <= spot for c in self.cursors):
            return
        self.cursors.append(Cursor(self.engine, self.scene_name, spot))
        if len(self.cursors) > self.MAX_CURSORS:
            # let go of cursors that moved on from their spot first; parked ones are the pool
            extra = len(self.cursors) - self.MAX_CURSORS
            moved = [c for c in self.cursors if c.park not in self.spots or c.dead]
            for c in moved[:extra]:
                c.close()
                self.cursors.remove(c)

    def close(self):
        self.closed = True
        for c in self.cursors:
            c.close()
