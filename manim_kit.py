"""Reusable Manim CE building blocks (original code; no third-party scene code).

    from manim_kit import *

Contents
  TimedScene      VoiceoverScene with an absolute timeline: `at(t)`, non-blocking
                  narration `say()`, and an optional TARGET length lock.
  clip            an animation placed on its play()'s own timeline (a delay
                  and/or a length), so clips in one play() can overlap.
  Blob, blink     a simple original character with moods, and a blink animation.
  ThoughtCloud    cloud bubble with trailing puffs; `thought_cloud_for(blob)`.
  SpeechBubble    ellipse + tail as one clean outline.
  ClippedGrid     linear-transformation grid clipped to a rectangle or ellipse,
                  driven by a ValueTracker (no masks needed).
  clip_rect / clip_ellipse, lerp_matrix, chain_matrices, turn, rotation, bmatrix,
  video_icon, audio_seconds.

Nothing here changes global config (fonts, colours, background); scenes and
style.py decide that. Lessons behind the design are in
docs/recreation_learnings.md.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import numpy as np
from manim import *
from manim_voiceover import VoiceoverScene

from edge_tts_service import EdgeTTSService


# ── Timeline scene: absolute timing + non-blocking narration ────────────

def audio_seconds(path: str) -> float:
    import av
    with av.open(str(path)) as c:
        return float(c.duration) / av.time_base


class TimedScene(VoiceoverScene):
    """A scene driven by an absolute clock, like a video editor's timeline.

    - `self.at(t)`: wait until `t` seconds into the scene (no-op if past).
    - `with self.say(text, caption=None):` puts a narration line on the
      timeline and returns at once. A line starts now, or when the previous
      line ends if that is later, so lines never overlap. Visuals keep their
      own `at()` timing instead of waiting for the voice.
      (manim-voiceover's `voiceover()` waits for the audio at the end of each
      block, which makes later absolute marks drift late. Bookmarks are not
      supported by `say()`; use `voiceover()` when you need them.)
    - `TARGET`: if set, the scene is padded to exactly this many seconds and
      warns when it overruns. It never ends before the last line finishes.

    - CAPTIONS = True burns captions into the frame, scheduled on the same
      timeline: hard cuts, each on screen at least len/READ_CPS + READ_PAD s,
      and the next line waits until the caption has been read. Override
      `caption_mobject(text)` for your own look (position, font, colour).

    Set VOICE = None to skip narration setup (e.g. silent scenes).
    """

    TARGET: float = 0.0
    VOICE: str | None = "en-US-AndrewNeural"
    VOICE_RATE: str = "-5%"
    VOICE_GAP: float = 0.3  # silence kept between two lines
    CAPTIONS: bool = False
    READ_CPS, READ_PAD, MAX_CAPTION = 15, 0.3, 70

    def setup(self):
        super().setup()
        if self.VOICE:
            self.set_speech_service(EdgeTTSService(voice=self.VOICE, rate=self.VOICE_RATE))

    @contextmanager
    def say(self, text: str, caption: str | None = None):
        if not self.VOICE:
            raise ValueError(f"{type(self).__name__}.VOICE is None; set a voice "
                             "(e.g. VOICE = \"en-US-AndrewNeural\") to narrate")
        now = self.renderer.time
        start = max(now, getattr(self, "_voice_free", 0.0))
        data = self.speech_service._wrap_generate_from_text(text)
        audio = Path(self.speech_service.cache_dir) / data["final_audio"]
        duration = audio_seconds(audio)
        shown = caption or text
        hold = max(duration, len(shown) / self.READ_CPS + self.READ_PAD)
        # A cached play() leaves renderer.skip_animations on until the next
        # play, and add_sound() silently drops audio while it is on. So a line
        # starting right after a cached animation vanished on re-renders.
        # manim-voiceover resets the flag the same way.
        self.renderer.skip_animations = self.renderer._original_skipping_status
        self.add_sound(str(audio), time_offset=start - now)
        self.add_subcaption(shown, duration=hold, offset=start - now)
        if self.CAPTIONS:
            self._schedule_caption(shown, start, start + hold)
        # the next line starts after the voice AND after this caption was read
        self._voice_free = start + max(duration + self.VOICE_GAP, hold)
        self._timeline_end = max(getattr(self, "_timeline_end", 0.0), start + hold)
        yield duration

    def line(self, spoken: str, caption: str | None = None) -> tuple[float, float]:
        """Schedule a narration line (like `say`) and return its (start, end)
        on the timeline, so visuals can land on the words:
        `a, b = self.line(...); self.at(a + 0.5)`. The start can be later
        than now if the previous line or caption is still running."""
        start = max(self.renderer.time, getattr(self, "_voice_free", 0.0))
        with self.say(spoken, caption=caption) as d:
            pass
        return start, start + d

    # on-screen captions --------------------------------------------------
    def caption_mobject(self, text: str) -> Mobject:
        mob = Text(text, font_size=28, color=WHITE)
        if mob.width > 13:
            mob.scale_to_fit_width(13)
        return mob.to_edge(DOWN, buff=0.35)

    def _schedule_caption(self, text, start, end):
        if len(text) > self.MAX_CAPTION:
            logger.warning(f"Caption over {self.MAX_CAPTION} chars: {text!r}")
        if not hasattr(self, "_caption_track"):
            self._captions = []
            self._caption_track = VGroup()
            # dt in the signature makes it a time-based updater. Without one,
            # Manim renders a wait() as a single frozen frame, so a caption
            # due to change during a wait stayed up until the next play().
            self._caption_track.add_updater(lambda m, dt: self._show_current_caption())
            self.add(self._caption_track)
        mob = self.caption_mobject(text)
        self._captions.append((start, end, mob))
        self._caption_track.add(mob)
        # In a 3D scene, pin captions to the screen or the camera moves them.
        # (camera call, not scene.add_fixed_in_frame_mobjects: that also
        # adds the caption as a second top-level copy.)
        if hasattr(self.camera, "add_fixed_in_frame_mobjects"):
            self.camera.add_fixed_in_frame_mobjects(mob)
        self._show_current_caption()
        self.bring_to_front(self._caption_track)

    def _show_current_caption(self):
        t = self.renderer.time + 1e-6
        current = None
        for start, end, mob in self._captions:
            if start <= t:
                current = (end, mob)
        for _, _, mob in self._captions:
            mob.set_opacity(1 if current and mob is current[1] and t < current[0] else 0)

    def at(self, t: float):
        dt = t - self.renderer.time
        if dt > 1 / config.frame_rate:
            self.wait(dt)

    def lock_to_target(self):
        end = getattr(self, "_timeline_end", 0.0)  # last voice / caption
        if end > self.renderer.time:
            self.wait(end - self.renderer.time)
        if not self.TARGET:
            return
        dt = self.TARGET - self.renderer.time
        if dt > 1 / config.frame_rate:
            self.wait(dt)
        elif dt < -0.1:
            logger.warning(f"{type(self).__name__} overran its {self.TARGET:.2f}s target by {-dt:.2f}s")

    def tear_down(self):
        self.lock_to_target()
        super().tear_down()


def clip(anim: Animation, start: float = 0.0, length: float | None = None) -> Animation:
    """An animation placed on its play()'s local timeline: it starts `start`
    seconds into the play and lasts `length` (else its own run_time).
    Don't give that play() a run_time=: it would stretch every clip in it."""
    if length is not None:
        anim.run_time = length
    return Succession(Wait(start), anim) if start else anim


# ── Character ────────────────────────────────────────────────────────────

class Blob(VGroup):
    """A simple character: rounded body, two eyes, a mouth.

    modes: "plain", "confused" (eyes up, tilted mouth), "speaking" (open
    mouth), "happy". Change with `.set_mode()` (works with `.animate`).
    """

    def __init__(self, color=BLUE_D, height=2.2, mode="plain", glasses=False, **kwargs):
        super().__init__(**kwargs)
        w = height * 0.62
        self.body = RoundedRectangle(width=w, height=height, corner_radius=w * 0.48,
                                     stroke_width=0, fill_color=color, fill_opacity=1)
        eye_r = w * 0.17
        self.eyes = VGroup()
        for dx in (-0.22, 0.22):
            white = Circle(radius=eye_r, stroke_width=0, fill_color=WHITE, fill_opacity=1)
            pupil = Circle(radius=eye_r * 0.5, stroke_width=0, fill_color=BLACK, fill_opacity=1)
            eye = VGroup(white, pupil).move_to(self.body.get_top() + DOWN * height * 0.24 + RIGHT * w * dx)
            self.eyes.add(eye)
        self.mouth = VMobject()
        self.add(self.body, self.eyes, self.mouth)
        if glasses:
            frames = VGroup(*[Circle(radius=eye_r * 1.35, color=GREY_A, stroke_width=3).move_to(e)
                              for e in self.eyes])
            bridge = Line(frames[0].get_right(), frames[1].get_left(), color=GREY_A, stroke_width=3)
            self.add(frames, bridge)
        self.set_mode(mode)

    def _mouth_for(self, mode):
        c = self.body.get_center() + UP * self.body.height * 0.05
        w = self.body.width * 0.36
        if mode == "speaking":
            m = Ellipse(width=w * 0.7, height=w * 0.45, stroke_width=0, fill_color=BLACK, fill_opacity=1)
        elif mode == "confused":
            m = Line(LEFT * w / 2, RIGHT * w / 2, stroke_width=4, color=BLACK).rotate(-0.2)
        elif mode == "happy":
            m = Arc(radius=w / 2, start_angle=PI + 0.3, angle=PI - 0.6, stroke_width=4, color=BLACK)
        else:
            m = Arc(radius=w, start_angle=PI * 1.5 - 0.35, angle=0.7, stroke_width=4, color=BLACK)
        return m.move_to(c)

    def set_mode(self, mode):
        self.mode = mode
        self.mouth.become(self._mouth_for(mode))
        self.look({"confused": UP + LEFT * 0.4}.get(mode, ORIGIN))
        return self

    def look(self, direction):
        for white, pupil in self.eyes:
            d = np.array(direction, dtype=float)
            n = np.linalg.norm(d)
            offset = d / n * white.width * 0.22 if n > 0 else ORIGIN
            pupil.move_to(white.get_center() + offset)
        return self

    def look_at(self, point):
        return self.look(np.array(point) - self.eyes.get_center())


def blink(blob: Blob, run_time=0.3) -> Animation:
    """Close and reopen the eyes.

    One alpha-driven animation on purpose: a Succession of two `.animate`
    steps builds both targets up front from the open eyes, so the "reopen"
    step would stretch them 10x.
    """
    start = blob.eyes.copy()

    def update(eyes, alpha):
        eyes.become(start)
        factor = 1 - 0.9 * there_and_back(alpha)
        for eye in eyes:
            eye.stretch(factor, 1, about_point=eye.get_center())

    return UpdateFromAlphaFunc(blob.eyes, update, run_time=run_time, rate_func=linear)


# ── Bubbles ──────────────────────────────────────────────────────────────
# Both have an opaque fill: add the bubble first, then bring_to_front() its
# contents, or the fill hides them.

class ThoughtCloud(VGroup):
    """Cloud outline from a ring of circles, plus trailing puffs to `tail_to`
    (a point relative to the cloud's centre).

    `.clip` = (center, a, b): an ellipse safely inside the cloud, for
    ClippedGrid(("ellipse", *cloud.clip)).
    """

    def __init__(self, width=6, height=3, tail_to=None, n_bumps=14,
                 stroke_color=WHITE, fill_color=BLACK, fill_opacity=1, **kwargs):
        super().__init__(**kwargs)
        a, b = width / 2, height / 2
        circles = []
        for k in range(n_bumps):
            th = TAU * k / n_bumps
            r = 0.23 * (a + b) / 2 * (1 + 0.25 * np.sin(3 * th))
            p = np.array([(a - r * 0.7) * np.cos(th), (b - r * 0.7) * np.sin(th), 0])
            circles.append(Circle(radius=r).move_to(p))
        core = Ellipse(width=2 * a * 0.85, height=2 * b * 0.8)
        self.cloud = Union(core, *circles).set_stroke(stroke_color, 2).set_fill(fill_color, fill_opacity)
        self.add(self.cloud)
        self.puffs = VGroup()
        if tail_to is not None:
            start = np.array([-a * 0.55, -b * 0.85, 0])
            end = np.array(tail_to, dtype=float)
            for i, s in enumerate((0.42, 0.28, 0.17)):
                p = interpolate(start, end, 0.18 + 0.27 * i)
                self.puffs.add(Ellipse(width=s * 1.6, height=s).move_to(p)
                               .set_stroke(stroke_color, 2).set_fill(fill_color, fill_opacity))
            self.add(self.puffs)
        self._a, self._b = a * 0.86, b * 0.8

    @property
    def clip(self):
        c = self.cloud.get_center()
        sx = self.cloud.width / (2 * self._a / 0.86) if self._a else 1
        return c, self._a * sx, self._b * self.cloud.height / (2 * self._b / 0.8)

    def place_inside(self, mob, buff=0.9):
        """Centre `mob` in the cloud, shrinking it to fit. Returns `mob`."""
        mob.move_to(self.cloud.get_center())
        if mob.width > self.cloud.width * buff * 0.8:
            mob.scale_to_fit_width(self.cloud.width * buff * 0.8)
        if mob.height > self.cloud.height * buff * 0.65:
            mob.scale_to_fit_height(self.cloud.height * buff * 0.65)
        return mob


def thought_cloud_for(blob: Blob, width=6, height=3, side=RIGHT, **kwargs) -> ThoughtCloud:
    """A cloud up and to `side` of the character, puffs trailing to its head."""
    head = blob.get_top() + side * blob.width * 0.5
    center = head + UP * (height / 2 + 1.1) + side * (width / 2 + 0.4)
    cloud = ThoughtCloud(width, height, tail_to=head - center + UP * 0.1, **kwargs)
    return cloud.shift(center)


class SpeechBubble(VGroup):
    """Ellipse with a pointed tail ending at `tip` (absolute point), drawn as
    one outline (boolean union)."""

    def __init__(self, width=5, height=2.2, center=ORIGIN, tip=DOWN * 3,
                 stroke_color=WHITE, fill_color=BLACK, **kwargs):
        super().__init__(**kwargs)
        center = np.array(center, dtype=float)
        tip = np.array(tip, dtype=float)
        ell = Ellipse(width=width, height=height).move_to(center)
        d = tip - center
        d /= np.linalg.norm(d)
        perp = np.array([-d[1], d[0], 0])
        # The tail's base sits well inside the ellipse so the union is one shape.
        base = center + d * np.array([width / 2, height / 2, 0]) * 0.55
        pts = [base + perp * 0.45, tip, base + perp * 0.05]
        # Match the ellipse's counter-clockwise winding, or the union cancels
        # the overlap and the tail shows as a separate sliver.
        u, v = pts[1] - pts[0], pts[2] - pts[0]
        if u[0] * v[1] - u[1] * v[0] < 0:  # 2-D cross; np.cross rejects 2-D in NumPy 2
            pts.reverse()
        self.shape = Union(ell, Polygon(*pts)).set_stroke(stroke_color, 2).set_fill(fill_color, 1)
        self.ellipse = ell
        self.add(self.shape)

    def place_inside(self, mob, buff=0.75):
        """Centre `mob` on the ellipse (not the whole shape: the tail pulls the
        bounding box off-centre), shrinking it to fit. Returns `mob`."""
        e = self.ellipse
        mob.move_to(e.get_center())
        if mob.width > e.width * buff * 0.8:
            mob.scale_to_fit_width(e.width * buff * 0.8)
        if mob.height > e.height * 0.62:
            mob.scale_to_fit_height(e.height * 0.62)
        return mob


# ── Clipping ─────────────────────────────────────────────────────────────

def clip_rect(p, q, xmin, xmax, ymin, ymax):
    """Liang–Barsky: clip segment pq to an axis-aligned box. None if outside."""
    d = q - p
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-d[0], p[0] - xmin), (d[0], xmax - p[0]),
                   (-d[1], p[1] - ymin), (d[1], ymax - p[1])):
        if abs(pk) < 1e-12:
            if qk < 0:
                return None
        else:
            t = qk / pk
            if pk < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    if t0 > t1:
        return None
    return p + t0 * d, p + t1 * d


def clip_ellipse(p, q, c, a, b):
    """Clip segment pq to the ellipse centred c with semi-axes a, b. None if outside."""
    P = np.array([(p[0] - c[0]) / a, (p[1] - c[1]) / b])
    Q = np.array([(q[0] - c[0]) / a, (q[1] - c[1]) / b])
    d = Q - P
    A = d @ d
    if A < 1e-12:
        return None
    B = 2 * P @ d
    C = P @ P - 1
    disc = B * B - 4 * A * C
    if disc <= 0:
        return None
    s = np.sqrt(disc)
    t0, t1 = max((-B - s) / (2 * A), 0.0), min((-B + s) / (2 * A), 1.0)
    if t0 >= t1:
        return None
    return p + t0 * (q - p), p + t1 * (q - p)


# ── Linear-transformation grid inside a frame ───────────────────────────

class ClippedGrid:
    """A 2-D linear-transformation picture, clipped to a rectangle or ellipse.

    frame: ("rect", center, width, height) or ("ellipse", center, a, b).
    matrix_of(t): the 2×2 matrix at progress t in [0, 1] (see lerp_matrix,
    chain_matrices). Add `grid.mobject` to the scene and animate with
    `grid.tracker.animate.set_value(1)`.

    Notes: the grid always has the same number of parts (lines clipped out
    of the frame and squashed arrows become invisible stand-ins), so it can
    be faded in or out while the tracker moves. Shears and
    stretches pull the grid's edge into view, so use
    extent ≈ 20 for those. Linear interpolation towards a matrix with
    negative determinant passes through det = 0 (the grid flattens).
    """

    def __init__(self, frame, unit=0.5, matrix_of=None, extent=12, vectors=(),
                 square=False, show_basis=True, bg_grid=True, border=True,
                 line_color=BLUE_D, i_color=GREEN_C, j_color=RED_C,
                 square_color=YELLOW_A, stroke=2.0):
        self.frame = frame
        self.unit = unit
        self.extent = extent
        self.matrix_of = matrix_of or (lambda t: np.eye(2))
        self.vectors = vectors  # list of (xy, color)
        self.square = square
        self.show_basis = show_basis
        self.bg_grid = bg_grid
        self.border = border
        self.line_color, self.i_color, self.j_color = line_color, i_color, j_color
        self.square_color = square_color
        self.stroke = stroke
        self.tracker = ValueTracker(0)
        self.mobject = always_redraw(self._draw)

    @property
    def center(self):
        return np.array(self.frame[1], dtype=float)

    def shift(self, *vectors):
        """Move the frame (and the grid inside it) like a mobject's shift, so
        `ClippedGrid(...).shift(RIGHT)` reads and works as it would on any
        Manim object. Returns self."""
        d = np.zeros(3)
        for v in vectors:
            v = np.array(v, dtype=float)
            d[: len(v)] += v
        kind, c, *rest = self.frame
        c3 = np.zeros(3)
        c = np.array(c, dtype=float)
        c3[: len(c)] = c
        self.frame = (kind, c3 + d, *rest)
        self.mobject.become(self._draw())  # now, not at the next redraw
        return self

    def move_to(self, point):
        """Put the frame's centre at `point`. Returns self."""
        p = np.zeros(3)
        q = np.array(point, dtype=float)
        p[: len(q)] = q
        c = np.zeros(3)
        c[: len(self.center)] = self.center
        return self.shift(p - c)

    def _clip(self, p, q):
        if self.frame[0] == "rect":
            _, c, w, h = self.frame
            return clip_rect(p, q, c[0] - w / 2, c[0] + w / 2, c[1] - h / 2, c[1] + h / 2)
        _, c, a, b = self.frame
        return clip_ellipse(p, q, c, a, b)

    def snapshot(self) -> VGroup:
        """A static copy of the grid at the tracker's current value (e.g. to
        dim it or carry the end state into the next scene)."""
        return self._draw()

    def to_screen(self, M, xy):
        v = np.array(M, dtype=float) @ np.array(xy, dtype=float)
        return self.center + self.unit * np.array([v[0], v[1], 0.0])

    def _lines(self, M, color, width, opacity, axes_color=None):
        g = VGroup()
        E = self.extent
        for k in range(-E, E + 1):
            for p, q in (((k, -E), (k, E)), ((-E, k), (E, k))):
                seg = self._clip(self.to_screen(M, p), self.to_screen(M, q))
                if seg is None:
                    # outside the frame: an invisible stand-in keeps the part
                    # count the same at every tracker value (fades can't crash)
                    g.add(Line(self.center, self.center + RIGHT * 1e-3, stroke_width=width,
                               color=color, stroke_opacity=0))
                    continue
                axis = k == 0 and axes_color is not None
                g.add(Line(*seg, stroke_width=width * (1.5 if axis else 1),
                           color=axes_color if axis else color, stroke_opacity=opacity))
        return g

    def _draw(self):
        M = np.array(self.matrix_of(self.tracker.get_value()), dtype=float)
        out = VGroup()
        if self.bg_grid:
            out.add(self._lines(np.eye(2), GREY, 1, 0.35))
        out.add(self._lines(M, self.line_color, self.stroke, 1, axes_color=WHITE))
        if self.square:
            corners = [self.to_screen(M, xy) for xy in ((0, 0), (1, 0), (1, 1), (0, 1))]
            out.add(Polygon(*corners, stroke_width=0, fill_color=self.square_color, fill_opacity=0.5))
        vecs = list(self.vectors)
        if self.show_basis:
            vecs = [((1, 0), self.i_color), ((0, 1), self.j_color)] + vecs
        for xy, col in vecs:
            end = self.to_screen(M, xy)
            if np.linalg.norm(end - self.center) > 1e-3:
                out.add(Arrow(self.center, end, buff=0, color=col, stroke_width=4,
                              max_tip_length_to_length_ratio=0.25, tip_length=0.18))
            else:
                # squashed to nothing: an invisible arrow keeps the part count
                out.add(Arrow(self.center, self.center + RIGHT * 0.01, buff=0, color=col,
                              stroke_width=4, max_tip_length_to_length_ratio=0.25,
                              tip_length=0.18).set_opacity(0))
        if self.border and self.frame[0] == "rect":
            _, c, w, h = self.frame
            out.add(Rectangle(width=w, height=h, color=WHITE, stroke_width=2).move_to(c))
        return out


def lerp_matrix(A):
    """t ↦ (1−t)·I + t·A."""
    A = np.array(A, dtype=float)
    return lambda t: (1 - t) * np.eye(2) + t * A


def turn(theta):
    """A rotation step for chain_matrices that really turns (s ↦ rotation(θ·s)).
    A plain rotation matrix would be blended linearly and shrink the grid
    halfway (by 1/√2 for 90°)."""
    return lambda s: rotation(theta * s)


def chain_matrices(*steps):
    """Apply steps one after another: over t in [i/n, (i+1)/n], step i is
    applied on top of the ones before. A step is a 2×2 matrix (blended in
    linearly) or a function s ↦ matrix with s in [0, 1] (e.g. `turn(PI/2)`)."""
    fns = [st if callable(st) else lerp_matrix(st) for st in steps]
    n = len(fns)

    def f(t):
        acc = np.eye(2)
        k = min(int(t * n), n - 1)
        for g in fns[:k]:
            acc = np.array(g(1), dtype=float) @ acc
        return np.array(fns[k](t * n - k), dtype=float) @ acc
    return f


def rotation(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]])


def bmatrix(rows, **kwargs) -> MathTex:
    """MathTex bracket matrix from a list of rows."""
    body = r" \\ ".join(" & ".join(str(x) for x in r) for r in rows)
    return MathTex(r"\begin{bmatrix}" + body + r"\end{bmatrix}", **kwargs)


def video_icon(color=BLUE_C, width=1.2) -> VGroup:
    """Rounded play-button frame."""
    frame = RoundedRectangle(width=1, height=0.7, corner_radius=0.12, stroke_width=3, color=color)
    tri = Triangle(fill_color=WHITE, fill_opacity=1, stroke_width=0).rotate(-PI / 2).scale(0.16)
    tri.move_to(frame.get_center() + RIGHT * 0.02)
    return VGroup(frame, tri).scale_to_fit_width(width)
