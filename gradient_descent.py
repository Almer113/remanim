"""Rolling downhill: gradient descent. Plan: plans/gradient_descent.md.

Render order: SCENES at the bottom. 2D beats use `Beat`, 3D beats `Beat3D`.
"""

from manim_kit import *
from style import *

# ── colour ledger ────────────────────────────────────────────────────────
WALKER = ACCENT_2          # ball / dot and its path
GRAD_COLOR = BAD           # ∇f, uphill
STEP_COLOR = GOOD          # −η∇f, downhill
ETA_COLOR = ACCENT         # step size η
LAND_SCALE = [(BLUE_E, -0.15), (TEAL, 0.6), (YELLOW, 2.0)]  # by height f
BLOB_COLOR = PURPLE_B

# ── the landscape (checked in the plan) ──────────────────────────────────
DOMAIN = 1.8  # -DOMAIN <= x, y <= DOMAIN
# Starts on the near side (y < 0) so the 3D camera sees them; f is even in y,
# so these are the plan's checked paths mirrored.
START = (-1.6, -1.5)
START_LOCAL = (1.6, -1.5)
DEEP_MIN = (-1.04, 0.0)
SHALLOW_MIN = (0.954, 0.0)


def f(x, y):
    return 0.35 * (x * x - 1) ** 2 + 0.25 * y * y + 0.12 * x


def grad(x, y):
    return np.array([1.4 * x * (x * x - 1) + 0.12, 0.5 * y])


def descend(start, eta, n):
    """Points visited by gradient descent: start, then n steps."""
    p = np.array(start, dtype=float)
    out = [p.copy()]
    for _ in range(n):
        p = p - eta * grad(*p)
        out.append(p.copy())
    return out


def land_color(z):
    """Colour for height z, same scale on the 3D surface and the 2D map."""
    (c0, z0), (c1, z1), (c2, z2) = LAND_SCALE
    if z <= z1:
        return interpolate_color(c0, c1, np.clip((z - z0) / (z1 - z0), 0, 1))
    return interpolate_color(c1, c2, np.clip((z - z1) / (z2 - z1), 0, 1))


def contour_segments(F, xs, ys, level):
    """Marching squares: line segments where the grid F (F[i, j] = f(xs[i], ys[j]))
    crosses `level`. Returns [((x0, y0), (x1, y1)), ...] in data coordinates."""
    segs = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            corners = ((xs[i], ys[j], F[i, j]), (xs[i + 1], ys[j], F[i + 1, j]),
                       (xs[i + 1], ys[j + 1], F[i + 1, j + 1]), (xs[i], ys[j + 1], F[i, j + 1]))
            pts = []
            for k in range(4):
                a, b = corners[k], corners[(k + 1) % 4]
                if (a[2] - level) * (b[2] - level) < 0:
                    t = (level - a[2]) / (b[2] - a[2])
                    pts.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            if len(pts) == 2:
                segs.append(tuple(pts))
            elif len(pts) == 4:  # saddle cell: either pairing is a fine picture
                segs += [tuple(pts[:2]), tuple(pts[2:])]
    return segs


# ── scene bases ──────────────────────────────────────────────────────────

class Beat(TimedScene):
    CAPTIONS = True

    def setup(self):
        super().setup()
        self.camera.background_color = BG

    def caption_mobject(self, text):
        return place(Text(text, font_size=CAPTION_SIZE, color=FG), "footer")

    def fade_all(self, run_time=0.5):
        mobs = [m for m in self.mobjects if m is not getattr(self, "_caption_track", None)]
        if mobs:
            self.play(*[FadeOut(m) for m in mobs], run_time=run_time)


class Beat3D(Beat, ThreeDScene):
    """3D beat: captions and `pin()`ned text stay fixed on screen."""

    PHI, THETA, ZOOM = 62 * DEGREES, -58 * DEGREES, 1.4

    def setup(self):
        super().setup()
        self.set_camera_orientation(phi=self.PHI, theta=self.THETA, zoom=self.ZOOM)

    def pin(self, *mobs):
        self.camera.add_fixed_in_frame_mobjects(*mobs)
        return mobs[0] if len(mobs) == 1 else mobs


# ── 2D helpers ───────────────────────────────────────────────────────────

HILL_Y = -0.85  # vertical offset of the foggy hill


def hill(x):
    return HILL_Y - 0.4 + 0.8 * np.sin(0.6 * x + 1.0) + 0.025 * x * x


def hill_slope(x):
    return 0.48 * np.cos(0.6 * x + 1.0) + 0.05 * x


def hill_point(x):
    return np.array([x, hill(x), 0])


def get_hill():
    return FunctionGraph(hill, x_range=[-config.frame_width / 2, config.frame_width / 2], color=FG, stroke_width=4)


def get_fog(window=1.5, ramp=1.2, n=10):
    """Opaque background-coloured fog with a clear window around x = 0."""
    top, bottom = 2.7, -2.7
    h = top - bottom
    fog = VGroup()
    for side in (LEFT, RIGHT):
        for k in range(n):
            w = ramp / n
            r = Rectangle(width=w + 0.01, height=h, stroke_width=0, fill_color=BG,
                          fill_opacity=(k + 1) / n)
            r.move_to(side * (window + (k + 0.5) * w) + UP * (top + bottom) / 2)
            fog.add(r)
        wall = Rectangle(width=12, height=h, stroke_width=0, fill_color=BG, fill_opacity=1)
        wall.move_to(side * (window + ramp + 6) + UP * (top + bottom) / 2)
        fog.add(wall)
    return fog


def get_tangent(x, length=2.2, color=FG):
    s = hill_slope(x)
    d = np.array([1, s, 0]) / np.hypot(1, s)
    return Line(hill_point(x) - d * length / 2, hill_point(x) + d * length / 2,
                color=color, stroke_width=3)


def get_eta_label(value):
    lbl = MathTex(r"\eta", "=", f"{value}", font_size=TITLE_SIZE, color=FG)
    lbl[0].set_color(ETA_COLOR)
    lbl[2].set_color(ETA_COLOR)
    return lbl


def get_rule_1d():
    rule = MathTex("x", r"\leftarrow", "x", "-", r"\eta", r"\,f'(x)", font_size=TITLE_SIZE, color=FG)
    rule[4].set_color(ETA_COLOR)
    return rule


def parabola_steps(x0, eta, n):
    xs = [x0]
    for _ in range(n):
        xs.append(xs[-1] - eta * 2 * xs[-1])
    return xs


# ── beats 1–4 (2D) ───────────────────────────────────────────────────────

BLOB_X = 2.2  # where Blob stands on the hill


class Foggy(Beat):
    TARGET = 12.0

    def construct(self):
        ground = get_hill()
        fog = get_fog().move_to(RIGHT * BLOB_X, coor_mask=[1, 0, 0])
        blob = Blob(BLOB_COLOR, height=1.1, mode="plain")
        blob.move_to(hill_point(BLOB_X) + UP * blob.height / 2)

        self.at(0.3)
        self.play(Create(ground), run_time=1.6)
        a, b = self.line("You're on a hillside in thick fog, trying to reach the bottom.")
        self.play(FadeIn(blob, shift=DOWN * 0.3), run_time=0.6)
        self.at(a + 2.0)
        self.play(FadeIn(fog), run_time=1.4)
        c, d = self.line("You can't see the valley. You only feel the ground under your feet.")
        self.at(c + 0.3)
        self.play(blob.animate.set_mode("confused"), run_time=0.5)
        self.at(c + 2.0)
        self.play(blob.animate.look(LEFT), run_time=0.4)
        self.wait(0.6)
        self.play(blob.animate.look(RIGHT), run_time=0.4)
        self.at(d + 0.2)
        self.play(blob.animate.look(DOWN), run_time=0.4)


class FeelTheSlope(Beat):
    TARGET = 10.0

    def construct(self):
        x = ValueTracker(BLOB_X)
        ground = get_hill()
        fog = get_fog()
        fog.add_updater(lambda m: m.move_to(RIGHT * x.get_value(), coor_mask=[1, 0, 0]))
        blob = Blob(BLOB_COLOR, height=1.1, mode="confused").look(DOWN)
        blob.add_updater(lambda m: m.move_to(hill_point(x.get_value()) + UP * m.height / 2))
        self.add(ground, fog, blob)

        tangent = always_redraw(lambda: get_tangent(x.get_value(), color=WALKER))
        # Both parts in LaTeX: at the same font_size, LaTeX digits are far
        # smaller than Pango Text (here "slope" was ~1.9x the number's height).
        word = place(Tex("slope", font_size=TITLE_SIZE, color=FG), "title").shift(LEFT * 0.8)
        value = always_redraw(lambda: DecimalNumber(
            hill_slope(x.get_value()), num_decimal_places=2, include_sign=True,
            font_size=TITLE_SIZE, color=WALKER).next_to(word, RIGHT, buff=0.3))
        readout = VGroup(word, value)

        a, b = self.line("But that's enough. Feel which way the ground tilts,")
        self.at(a + 0.5)
        self.play(Create(tangent), FadeIn(readout), run_time=0.8)
        self.play(x.animate.set_value(BLOB_X - 0.35), run_time=1.0)
        self.play(x.animate.set_value(BLOB_X + 0.25), run_time=1.0)
        self.play(x.animate.set_value(BLOB_X), run_time=0.6)
        c, d = self.line("and take a small step downhill. Then do it again.")
        self.at(c + 0.6)
        self.play(blob.animate.set_mode("happy"), run_time=0.3)
        self.play(x.animate.set_value(BLOB_X + 0.8), run_time=1.0)
        self.at(c + 2.6)
        self.play(x.animate.set_value(BLOB_X + 1.5), run_time=1.0)
        self.play(x.animate.set_value(BLOB_X + 2.1), run_time=1.0)
        self.at(self.TARGET - 0.7)
        for m in (fog, blob):
            m.clear_updaters()
        self.fade_all()


class OneDimension(Beat):
    TARGET = 16.0
    ETA, X0, N = 0.2, 1.6, 6

    def construct(self):
        axes = Axes(x_range=[-2, 2, 1], y_range=[0, 4, 1], x_length=7.5, y_length=4.2,
                    axis_config={"color": MUTED, "include_tip": False})
        place(axes, "main").shift(DOWN * 0.2)
        curve = axes.plot(lambda t: t * t, x_range=[-2, 2], color=FG, stroke_width=4)
        rule = place(get_rule_1d(), "title")
        x = ValueTracker(self.X0)
        dot = always_redraw(lambda: Dot(axes.c2p(x.get_value(), x.get_value() ** 2),
                                        radius=0.11, color=WALKER))

        def tangent_at(t, length=2.6):
            s = 2 * t  # slope in data units; convert to a screen direction
            p0, p1 = axes.c2p(t, t * t), axes.c2p(t + 0.1, t * t + 0.1 * s)
            d = (p1 - p0) / np.linalg.norm(p1 - p0)
            return Line(p0 - d * length / 2, p0 + d * length / 2, color=WALKER, stroke_width=5)

        self.at(0.2)
        self.play(Create(axes), Create(curve), run_time=1.2)
        self.play(FadeIn(dot), run_time=0.3)
        a, b = self.line("In maths, the tilt is the slope: the derivative, f prime.",
                         caption="In maths, the tilt is the slope: the derivative, f′.")
        self.at(a + 1.2)
        tan = tangent_at(self.X0)
        self.play(Create(tan), run_time=0.6)
        c, d = self.line("Step against it, scaled by a small number, eta: the step size.",
                         caption="Step against it, scaled by a small number η: the step size.")
        self.at(c + 0.2)
        self.play(Write(rule), run_time=1.4)
        e, _ = self.line("Repeat, and you close in on the bottom.")
        self.at(c + 2.6)
        for nxt in parabola_steps(self.X0, self.ETA, self.N)[1:]:
            self.play(x.animate.set_value(nxt), FadeOut(tan), run_time=0.55)
            tan = tangent_at(nxt)
            self.play(FadeIn(tan), run_time=0.25)
        self.play(FadeOut(tan), run_time=0.3)
        self.at(self.TARGET - 0.6)
        self.fade_all()


STEP_CASES = [(0.1, "crawls"), (0.9, "bounces"), (1.05, "flies off")]


def get_step_panel(eta, verdict):
    """(frame, axes): small axes with y = x², η label above, verdict below."""
    axes = Axes(x_range=[-3, 3, 1], y_range=[0, 9, 3], x_length=3.7, y_length=3.0,
                axis_config={"color": MUTED, "include_tip": False, "stroke_width": 2})
    curve = axes.plot(lambda t: t * t, x_range=[-3, 3], color=FG, stroke_width=3)
    label = get_eta_label(eta).next_to(axes, UP, buff=0.3)
    word = Text(verdict, font_size=CAPTION_SIZE, color=MUTED).next_to(axes, DOWN, buff=0.3)
    return VGroup(axes, curve, label, word)


def get_hops(axes, eta, n=6, x0=1.6):
    """Dots for each visited point and the lines between them (build after placing)."""
    pts = [axes.c2p(t, t * t) for t in parabola_steps(x0, eta, n)]
    dots = VGroup(*[Dot(p, radius=0.07, color=WALKER) for p in pts])
    hops = VGroup(*[Line(p, q, color=WALKER, stroke_width=3) for p, q in zip(pts, pts[1:])])
    return dots, hops


class StepSize(Beat):
    TARGET = 13.5

    def construct(self):
        frames = VGroup(*[get_step_panel(eta, word) for eta, word in STEP_CASES])
        place(frames.arrange(RIGHT, buff=0.7), "main")
        built = [(fr, *get_hops(fr[0], eta)) for fr, (eta, _) in zip(frames, STEP_CASES)]

        self.at(0.2)
        self.play(*[FadeIn(VGroup(fr[0], fr[1], fr[2])) for fr, _, _ in built], run_time=0.8)

        def walk(dots, hops, step_time):
            self.play(FadeIn(dots[0]), run_time=0.2)
            for hop, dot in zip(hops, dots[1:]):
                self.play(Create(hop), run_time=step_time)
                self.add(dot)

        lines = [("The step size matters. Too small, and you crawl.", 1.6),
                 ("Too big, and you bounce from side to side.", 0.6),
                 ("Bigger still, and you fly off completely.", 0.6)]
        for (fr, dots, hops), (text, lead) in zip(built, lines):
            a, b = self.line(text)
            self.at(a + lead)
            walk(dots, hops, 0.3)
            self.play(FadeIn(fr[3]), run_time=0.3)
        self.at(self.TARGET - 0.6)
        self.fade_all()


# ── 3D helpers ───────────────────────────────────────────────────────────

U, ZS, ZMID = 1.5, 0.55, 0.7  # screen units per x/y unit, per f unit; f at screen z=0
SURF_RES = 32
BALL_R = 0.11
LIFT = 0.04  # trails float a little above the surface so faces don't hide them


def p3(x, y, z=None, lift=0.0):
    """Screen point for landscape coordinates (x, y), on the surface by default."""
    z = f(x, y) if z is None else z
    return np.array([x * U, y * U, (z - ZMID) * ZS + lift])


def get_landscape(height=1.0, res=SURF_RES):
    """Opaque surface coloured by f; height=0 gives the flat map (same faces,
    same colours), so Transform(flat, full) raises it."""
    surf = Surface(lambda u, v: p3(u, v, ZMID + height * (f(u, v) - ZMID)),
                   u_range=[-DOMAIN, DOMAIN], v_range=[-DOMAIN, DOMAIN],
                   resolution=(res, res), checkerboard_colors=False,
                   stroke_width=0.4, stroke_color=BG, fill_opacity=1)
    for face in surf:
        u, v = (face.u1 + face.u2) / 2, (face.v1 + face.v2) / 2
        face.set_fill(land_color(f(u, v)), opacity=1)
    return surf


def ball_at(x, y):
    return p3(x, y, lift=BALL_R)


def get_ball(x, y):
    return Dot3D(ball_at(x, y), radius=BALL_R, color=WALKER, resolution=(10, 10))


def slope_vector(x, y, length, downhill=False):
    """Screen vector along the surface, straight up (or down) the slope."""
    g = grad(x, y)
    n = np.linalg.norm(g)
    sgn = -1 if downhill else 1
    v = np.array([sgn * g[0] / n * U, sgn * g[1] / n * U, sgn * n * ZS])
    return v / np.linalg.norm(v) * length


def get_arrow3d(start, vec, color, lift=0.12):
    start = start + OUT * lift  # clear of the surface, or its faces hide the arrow
    arrow = Arrow3D(start, start + vec, color=color, thickness=0.025, height=0.25,
                    base_radius=0.08, resolution=12)
    # The 3D camera depth-sorts shade_in_3d parts face by face, so nearer
    # surface faces covered the arrow. Unshaded parts are drawn last: on top.
    for part in arrow.get_family():
        part.shade_in_3d = False
    return arrow


def hop(ball, a, b, height=0.3, run_time=0.5):
    """Ball jumps from landscape point a to b in a small arc."""
    pa, pb = ball_at(*a), ball_at(*b)

    def update(m, alpha):
        m.move_to(interpolate(pa, pb, alpha) + OUT * height * np.sin(PI * alpha))

    return UpdateFromAlphaFunc(ball, update, run_time=run_time, rate_func=smooth)


def get_trail_piece(a, b):
    return Line(p3(*a, lift=LIFT), p3(*b, lift=LIFT), color=WALKER, stroke_width=5)


def get_heading(text):
    return place(Text(text, font_size=TITLE_SIZE, color=FG), "title")


# ── beats 5–7 (3D) ───────────────────────────────────────────────────────

class Landscape(Beat3D):
    TARGET = 10.0
    ORBIT = 0.06  # radians per second

    def construct(self):
        self.set_camera_orientation(theta=self.THETA - self.ORBIT * self.TARGET)
        flat = get_landscape(height=0)
        full = get_landscape()
        self.begin_ambient_camera_rotation(rate=self.ORBIT)
        a, b = self.line("Real problems have more than one direction to walk in.")
        self.at(0.3)
        self.play(FadeIn(flat), run_time=1.2)
        c, d = self.line("The ground is a whole landscape, with hills and valleys.")
        self.at(c + 0.2)
        self.play(Transform(flat, full), run_time=2.5)
        # No heading: once zoomed in, the orbiting landscape's corner rises
        # into the title area. The narration names it anyway.


class Gradient(Beat3D):
    TARGET = 11.0

    def construct(self):
        land = get_landscape()
        self.add(land)
        x0, y0 = START
        ball = get_ball(x0, y0)
        up = get_arrow3d(ball_at(x0, y0), slope_vector(x0, y0, 1.4), GRAD_COLOR)
        down = get_arrow3d(ball_at(x0, y0), slope_vector(x0, y0, 1.1, downhill=True), STEP_COLOR)
        formula = MathTex(r"\nabla f", "=", r"\left(\frac{\partial f}{\partial x},\ "
                          r"\frac{\partial f}{\partial y}\right)", font_size=TITLE_SIZE, color=FG)
        formula[0].set_color(GRAD_COLOR)
        formula.to_corner(UR, buff=0.7)
        self.pin(formula)
        self.remove(formula)  # pinned, but not shown yet

        self.at(0.3)
        self.play(FadeIn(ball, scale=0.5), run_time=0.5)
        a, b = self.line("The slope in every direction at once is called the gradient.")
        self.at(a + 1.0)
        self.play(Write(formula), run_time=1.4)
        self.at(b - 0.6)
        self.play(Create(up), run_time=0.8)
        c, d = self.line("It points straight uphill, so we step the opposite way.")
        self.at(c + 2.0)
        self.play(Create(down), run_time=0.8)
        self.at(self.TARGET - 0.6)
        self.play(FadeOut(up), FadeOut(down), FadeOut(formula), run_time=0.5)


class Descent3D(Beat3D):
    TARGET = 10.0
    ETA, N = 0.3, 9
    ORBIT = 0.03

    def construct(self):
        land = get_landscape()
        path = descend(START, self.ETA, self.N)
        ball = get_ball(*path[0])
        self.add(land, ball)
        eta = self.pin(get_eta_label(self.ETA).to_corner(UR, buff=0.7))
        self.remove(eta)
        self.begin_ambient_camera_rotation(rate=self.ORBIT)
        a, b = self.line("Step, recompute the gradient, step again.")
        self.at(0.4)
        self.play(FadeIn(eta), run_time=0.5)
        self.at(a + 0.6)
        for k, (p, q) in enumerate(zip(path, path[1:])):
            rt = 0.7 if k < 3 else 0.45
            self.play(hop(ball, p, q, height=0.3 if k < 3 else 0.12, run_time=rt))
            self.add(get_trail_piece(p, q))
            self.bring_to_front(ball)
            if k == 2:
                self.line("The ball works its way down into the valley.")
        self.at(self.TARGET - 0.6)
        self.play(FadeOut(eta), run_time=0.5)


# ── contour map helpers (2D) ─────────────────────────────────────────────

MAP_SIZE = 5.0
MAP_CENTER = DOWN * 0.15
LEVELS = [-0.08, 0.0, 0.1, 0.2, 0.35, 0.5, 0.7, 0.95, 1.25, 1.6, 2.0, 2.5]


def m2s(x, y):
    """Screen point for landscape coordinates on the flat map."""
    k = MAP_SIZE / (2 * DOMAIN)
    return MAP_CENTER + RIGHT * x * k + UP * y * k


def get_heightmap(px=200, brightness=0.8):
    """Image of the landscape coloured like the 3D surface (dimmed a little so
    lines and paths drawn over it stand out)."""
    t = np.linspace(-DOMAIN, DOMAIN, px)
    img = np.zeros((px, px, 3), dtype=np.uint8)
    for r, y in enumerate(t[::-1]):  # row 0 is the top: largest y
        for c, x in enumerate(t):
            img[r, c] = (np.array(land_color(f(x, y)).to_rgb()) * 255 * brightness).astype(np.uint8)
    im = ImageMobject(img)
    im.set_resampling_algorithm(RESAMPLING_ALGORITHMS["bilinear"])
    return im.stretch_to_fit_width(MAP_SIZE).stretch_to_fit_height(MAP_SIZE).move_to(MAP_CENTER)


def get_contours(n=90):
    xs = np.linspace(-DOMAIN, DOMAIN, n)
    F = f(xs[:, None], xs[None, :])
    lines = VMobject(stroke_color=BG, stroke_width=2, stroke_opacity=0.6)
    for level in LEVELS:
        for a, b in contour_segments(F, xs, xs, level):
            lines.start_new_path(m2s(*a))
            lines.add_line_to(m2s(*b))
    return lines


def get_map():
    border = Square(MAP_SIZE, stroke_color=MUTED, stroke_width=2).move_to(MAP_CENTER)
    return Group(get_heightmap(), get_contours(), border)


def get_map_path(points, color=WALKER):
    dots = VGroup(*[Dot(m2s(*p), radius=0.06, color=color) for p in points])
    hops = VGroup(*[Line(m2s(*p), m2s(*q), color=color, stroke_width=4)
                    for p, q in zip(points, points[1:])])
    return dots, hops


def draw_path(scene, dots, hops, step_time=0.3):
    scene.play(FadeIn(dots[0]), run_time=0.2)
    for hop_line, dot in zip(hops, dots[1:]):
        scene.play(Create(hop_line), run_time=step_time)
        scene.add(dot)


def get_valley_marks():
    marks = VGroup()
    for (x, y), word in ((DEEP_MIN, "deepest"), (SHALLOW_MIN, "shallow dip")):
        cross = Cross(scale_factor=0.09, stroke_color=FG, stroke_width=4).move_to(m2s(x, y))
        lbl = Text(word, font_size=CAPTION_SIZE, color=FG).next_to(cross, UP, buff=0.15)  # paths arrive from below
        lbl.add_background_rectangle(color=BG, opacity=0.75, buff=0.06)
        marks.add(VGroup(cross, lbl))
    return marks


# ── beats 8–9 (2D map) ───────────────────────────────────────────────────

class ContourMap(Beat):
    TARGET = 13.0
    ETA, N = 0.3, 9
    # Where the gradient is shown against a contour: an empty part of the map.
    # (On the path, uphill points straight back along the path: cluttered.)
    DEMO_POINT = (0.9, 0.55)

    def construct(self):
        board = get_map()
        path = descend(START, self.ETA, self.N)
        dots, hops = get_map_path(path)
        eta = get_eta_label(self.ETA).next_to(board, RIGHT, buff=0.6, aligned_edge=UP)

        x, y = self.DEMO_POINT
        g = grad(x, y)
        u = g / np.linalg.norm(g)
        at = m2s(x, y)
        up = Arrow(at, at + np.array([u[0], u[1], 0]) * 1.1, buff=0, color=GRAD_COLOR,
                   stroke_width=6, max_tip_length_to_length_ratio=0.25)
        tangent = DashedLine(at - np.array([-u[1], u[0], 0]) * 0.8,
                             at + np.array([-u[1], u[0], 0]) * 0.8, color=FG, stroke_width=3)
        corner = RightAngle(Line(at, tangent.get_end()), Line(at, up.get_end()),
                            length=0.25, color=FG, stroke_width=2)
        grad_label = MathTex(r"\nabla f", color=GRAD_COLOR, font_size=BODY_SIZE)
        grad_label.next_to(up.get_end(), LEFT, buff=0.15)
        grad_label.add_background_rectangle(color=BG, opacity=0.75, buff=0.05)

        a, b = self.line("From above, the landscape becomes a contour map.")
        self.at(a + 0.2)
        self.play(FadeIn(board), run_time=1.2)
        self.play(FadeIn(eta), run_time=0.4)
        self.at(a + 2.0)
        draw_path(self, dots, hops, step_time=0.25)
        c, d = self.line("The gradient always crosses the contour lines at right angles.")
        self.at(c + 1.0)
        self.play(Create(tangent), run_time=0.6)
        self.play(GrowArrow(up), FadeIn(grad_label), run_time=0.7)
        self.play(Create(corner), run_time=0.4)
        self.line("It's the steepest way up.")
        self.at(self.TARGET - 0.6)
        self.play(*[FadeOut(m) for m in (up, tangent, corner, grad_label, eta)], run_time=0.5)


class TooBig(Beat):
    TARGET = 10.5
    ETA, N = 0.55, 8

    def construct(self):
        board = get_map()
        old_dots, old_hops = get_map_path(descend(START, ContourMap.ETA, ContourMap.N))
        old = VGroup(old_dots, old_hops)
        self.add(board, old)
        dots, hops = get_map_path(descend(START, self.ETA, self.N))
        eta = get_eta_label(self.ETA).next_to(board, RIGHT, buff=0.6, aligned_edge=UP)
        marks = get_valley_marks()

        a, b = self.line("Now take bigger steps from the same start.")
        self.at(0.3)
        self.play(old.animate.fade(0.75), FadeIn(eta), run_time=0.6)
        self.at(a + 1.8)
        self.play(FadeIn(dots[0]), run_time=0.2)
        self.play(Create(hops[0]), run_time=1.0)  # the big jump, slowly
        self.add(dots[1])
        c, d = self.line("The first jump clears the ridge, and we settle in the wrong valley.")
        self.at(c + 0.5)
        for hop_line, dot in zip(hops[1:], dots[2:]):
            self.play(Create(hop_line), run_time=0.3)
            self.add(dot)
        self.at(d - 1.2)
        self.play(FadeIn(marks), run_time=0.6)
        self.at(self.TARGET - 0.6)
        self.fade_all()


# ── beat 10 (3D) ─────────────────────────────────────────────────────────

class LocalMinimum(Beat3D):
    TARGET = 13.5
    ETA, N = 0.3, 10

    def construct(self):
        land = get_landscape()
        path = descend(START_LOCAL, self.ETA, self.N)
        ball = get_ball(*path[0])
        self.add(land)
        a, b = self.line("Start somewhere else, and you can get stuck in a shallow dip.")
        self.at(0.3)
        self.play(FadeIn(ball, scale=0.5), run_time=0.4)
        self.at(a + 0.8)
        for k, (p, q) in enumerate(zip(path, path[1:])):
            self.play(hop(ball, p, q, height=0.25 if k < 2 else 0.1,
                          run_time=0.6 if k < 2 else 0.35))
            self.add(get_trail_piece(p, q))
            self.bring_to_front(ball)

        base = p3(*DEEP_MIN, lift=0.02)
        pole = Line(base, base + OUT * 1.4, color=FG, stroke_width=5)
        flag = Polygon(base + OUT * 1.4, base + OUT * 1.0, base + OUT * 1.2 + RIGHT * 0.6,
                       stroke_width=0, fill_color=GOOD, fill_opacity=1)
        c, d = self.line("The real lowest point is right next door.")
        self.at(c + 0.2)
        self.move_camera(zoom=self.ZOOM * 0.8, run_time=1.8,
                         added_anims=[Create(pole)])
        self.play(FadeIn(flag), run_time=0.4)
        self.line("Gradient descent only knows what's under its feet.")
        self.at(self.TARGET - 0.6)
        self.play(*[FadeOut(m) for m in self.mobjects if m is not self._caption_track], run_time=0.5)


# ── beat 11 (2D) ─────────────────────────────────────────────────────────

class Takeaway(Beat):
    TARGET = 10.5

    def construct(self):
        rule = MathTex(r"\mathbf{p}", r"\leftarrow", r"\mathbf{p}", "-", r"\eta", r"\nabla f",
                       font_size=84, color=FG)
        rule[4].set_color(ETA_COLOR)
        rule[5].set_color(GRAD_COLOR)
        rule.move_to(UP * 0.9)
        sub = Text("This is how neural networks learn.", font_size=BODY_SIZE, color=MUTED)
        sub.next_to(rule, DOWN, buff=0.7)
        blob = Blob(BLOB_COLOR, height=1.6, mode="happy").to_corner(DL, buff=0.7).shift(UP * 0.4)

        a, b = self.line("Feel the slope, step downhill, repeat.")
        self.at(0.3)
        self.play(Write(rule), FadeIn(blob, shift=UP * 0.2), run_time=1.4)
        c, d = self.line("That one rule is how most of machine learning learns.")
        self.at(c + 0.6)
        self.play(FadeIn(sub, shift=UP * 0.15), blob.animate.look_at(rule.get_center()), run_time=0.8)
        self.at(d + 0.4)
        self.play(blink(blob))
        self.at(self.TARGET - 0.8)
        self.fade_all(run_time=0.7)


SCENES = ["Foggy", "FeelTheSlope", "OneDimension", "StepSize", "Landscape", "Gradient",
          "Descent3D", "ContourMap", "TooBig", "LocalMinimum", "Takeaway"]
