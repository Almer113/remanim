"""Why e^(i pi) = -1. Plan: plans/euler_identity.md.

Render order: Hook, TimesI, Velocity, Walk, Steps, Takeaway.
"""

import cmath

from manim import *
from manim_kit import *
from style import *

POINT, VEL, ARC = ACCENT, ACCENT_2, GOOD  # colour ledger
PLANE_AT = RIGHT * 1.2 + DOWN * 0.15
UNIT = 1.6  # frame units per 1 on the complex plane


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


# -- helpers -----------------------------------------------------------------

def get_title():
    return place(MathTex(r"e^{i\pi} = -1", font_size=TITLE_SIZE, color=FG), "title")


def get_plane(center=PLANE_AT, unit=UNIT, xr=2.5, yr=1.5):
    plane = ComplexPlane(
        x_range=[-xr, xr, 1], y_range=[-yr, yr, 1],
        x_length=2 * xr * unit, y_length=2 * yr * unit,
        background_line_style={"stroke_color": MUTED, "stroke_opacity": 0.35, "stroke_width": 1},
        axis_config={"stroke_color": FG, "stroke_width": 2},
    )
    return plane.move_to(center)


def get_label(plane, z, tex, direction, color=FG):
    return MathTex(tex, font_size=BODY_SIZE, color=color).next_to(plane.n2p(z), direction, buff=0.15)


def get_spiral(plane, n):
    pts = [plane.n2p((1 + 1j * PI / n) ** k) for k in range(n + 1)]
    return VMobject(stroke_color=VEL, stroke_width=3).set_points_as_corners(pts)


# -- beats -------------------------------------------------------------------

class Hook(Beat):
    TARGET = 7.6

    def construct(self):
        eq = MathTex(r"e^{i\pi} = -1", font_size=96, color=FG)
        place(eq, "main")
        question = Text("Why?", font_size=BODY_SIZE, color=MUTED)
        question.next_to(eq, DOWN, buff=0.6)

        self.at(0.2)
        with self.say("E to the I pi equals minus one. Why on earth would that be true?",
                      caption="e^(iπ) = −1. Why on earth would that be true?"):
            self.play(Write(eq), run_time=1.5)
            self.at(3.0)
            self.play(FadeIn(question, shift=UP * 0.2), run_time=0.6)
        self.at(6.4)
        self.play(FadeOut(question), Transform(eq, get_title()), run_time=1.0)


class TimesI(Beat):
    TARGET = 9.5

    def construct(self):
        self.add(get_title())
        plane = get_plane()
        dot = Dot(plane.n2p(1), radius=0.1, color=POINT)
        labels = [get_label(plane, 1, "1", DR), get_label(plane, 1j, "i", UR),
                  get_label(plane, -1, "-1", DL), get_label(plane, -1j, "-i", DR)]

        self.at(0.2)
        self.play(FadeIn(plane), FadeIn(dot), FadeIn(labels[0]), run_time=0.8)
        with self.say("Multiplying by I turns a point a quarter turn around zero.",
                      caption="Multiplying by i turns a point a quarter turn."):
            for k, z in enumerate((1, 1j, -1, -1j)[:3]):
                self.at(1.4 + 2.4 * k)
                turn_arrow = CurvedArrow(plane.n2p(z * 1.25), plane.n2p(z * 1j * 1.25),
                                         angle=PI / 2, color=VEL)
                times = MathTex(r"\times i", font_size=BODY_SIZE, color=VEL)
                times.move_to(plane.n2p(z * (1 + 1j) * 1.05))
                self.play(Create(turn_arrow), FadeIn(times),
                          Rotate(dot, PI / 2, about_point=plane.n2p(0)), run_time=1.2)
                self.play(FadeOut(turn_arrow), FadeOut(times), run_time=0.3)
                self.play(FadeIn(labels[k + 1]), run_time=0.3)
        self.at(8.93)
        self.fade_all()


class Velocity(Beat):
    TARGET = 8.1

    def construct(self):
        self.add(get_title())
        line = NumberLine(x_range=[0, 4, 1], length=5.2, color=FG, include_numbers=True,
                          font_size=28)
        place(line, "left")
        t = ValueTracker(0)
        dot = always_redraw(lambda: Dot(line.n2p(np.exp(t.get_value())), radius=0.1, color=POINT))
        vel = always_redraw(lambda: Arrow(
            dot.get_center(), dot.get_center() + RIGHT * 0.4 * np.exp(t.get_value()),
            buff=0, color=VEL, stroke_width=5, max_tip_length_to_length_ratio=0.3))
        left_rule = Tex(r"velocity $=$ position", font_size=BODY_SIZE, color=FG)
        left_rule.next_to(line, UP, buff=1.2)

        plane = get_plane(RIGHT * 3.6 + DOWN * 0.4, unit=1.1, xr=2, yr=1.5).scale(1.3)
        z_dot = Dot(plane.n2p(1), radius=0.1, color=POINT)
        radius = Line(plane.n2p(0), plane.n2p(1), color=POINT, stroke_width=4)
        z_vel = Arrow(plane.n2p(1), plane.n2p(1 + 1j), buff=0, color=VEL, stroke_width=5)
        right_rule = Tex(r"velocity $= i \times$ position", font_size=BODY_SIZE, color=FG)
        right_rule.next_to(plane, UP, buff=0.3)

        with self.say("E to the T grows at its own size. "
                      "E to the I T moves at its own size, turned a quarter turn.",
                      caption="e^t moves at its own size; e^(it), turned a quarter turn."):
            self.at(0.2)
            self.play(FadeIn(line), FadeIn(left_rule), FadeIn(dot), FadeIn(vel), run_time=0.8)
            self.play(t.animate.set_value(1.3), run_time=3.0, rate_func=linear)
            self.at(4.2)
            self.play(FadeIn(plane), FadeIn(radius), FadeIn(z_dot), FadeIn(right_rule),
                      run_time=0.8)
            self.play(GrowArrow(z_vel), run_time=1.0)
        self.at(7.5)
        self.fade_all()


class Walk(Beat):
    TARGET = 11.8

    def construct(self):
        self.add(get_title())
        plane = get_plane()
        circle = Circle(radius=UNIT, color=MUTED, stroke_width=2).move_to(plane.n2p(0))
        t = ValueTracker(0)

        def z():
            return cmath.exp(1j * t.get_value())

        arc = always_redraw(lambda: Arc(radius=UNIT, angle=max(t.get_value(), 1e-3),
                                        arc_center=plane.n2p(0), color=ARC, stroke_width=6))
        radius = always_redraw(lambda: Line(plane.n2p(0), plane.n2p(z()), color=POINT, stroke_width=4))
        vel = always_redraw(lambda: Arrow(plane.n2p(z()), plane.n2p(z() + 1j * z()), buff=0,
                                          color=VEL, stroke_width=5))
        dot = always_redraw(lambda: Dot(plane.n2p(z()), radius=0.1, color=POINT))
        clock = VGroup(MathTex("t =", font_size=BODY_SIZE, color=FG),
                       DecimalNumber(0, num_decimal_places=2, font_size=BODY_SIZE, color=FG))
        clock.arrange(RIGHT, buff=0.2).move_to(LEFT * 4.8 + DOWN * 2.2)
        clock[1].add_updater(lambda m: m.set_value(t.get_value()))
        minus_one = get_label(plane, -1, "-1", DL).shift(0.2419 * LEFT)
        pi_label = MathTex(r"\pi", font_size=48, color=ARC).next_to(plane.n2p(1.12j), UP, buff=0.1)

        self.at(0.2)
        self.play(FadeIn(plane), FadeIn(circle), FadeIn(minus_one), FadeIn(clock), run_time=0.8)
        self.add(arc, radius, dot)
        self.play(GrowArrow(vel), run_time=0.6)
        self.line("Always sideways, always speed one, so it walks around the circle.",
                  caption="Always sideways, speed 1: it walks the circle.")
        self.at(2.0)
        self.play(t.animate.set_value(PI), run_time=5.0, rate_func=linear)
        with self.say("After time pi, it has walked half way: to minus one.",
                      caption="After π, it's halfway: at −1."):
            self.play(Write(pi_label), minus_one.animate.set_color(ARC), run_time=1.0)
        self.at(11.17)
        self.fade_all()


class Steps(Beat):
    TARGET = 9.5

    def construct(self):
        self.add(get_title())
        plane = get_plane()
        circle = Circle(radius=UNIT, color=MUTED, stroke_width=2).move_to(plane.n2p(0))
        target = Dot(plane.n2p(-1), radius=0.1, color=ARC)
        spirals = [get_spiral(plane, n) for n in (8, 16, 64)]
        labels = [MathTex(f"n = {n}", font_size=BODY_SIZE, color=VEL).move_to(RIGHT * 5.2 + UP * 1.8)
                  for n in (8, 16, 64)]

        self.at(0.2)
        self.play(FadeIn(plane), FadeIn(circle), FadeIn(target), run_time=0.8)
        with self.say("Take the walk in small straight steps, and the steps close in on minus one.",
                      caption="Small straight steps close in on −1 too."):
            self.at(1.2)
            self.play(Create(spirals[0]), FadeIn(labels[0]), run_time=2.0)
            for k in (1, 2):
                self.at(1.2 + 2.6 * k)
                self.play(Transform(spirals[0], spirals[k]), Transform(labels[0], labels[k]),
                          run_time=1.5)
        self.at(8.93)
        self.fade_all()


class Takeaway(Beat):
    TARGET = 10.0

    def construct(self):
        general = MathTex(r"e^{i\theta} = \cos\theta + i\sin\theta", font_size=60, color=FG)
        place(general, "main").shift(UP * 0.8)
        at_pi = MathTex(r"e^{i\pi}", "=", r"\cos\pi + i\sin\pi", "=", "-1", font_size=60, color=FG)
        at_pi.next_to(general, DOWN, buff=0.8)
        at_pi[4].set_color(ARC)

        self.at(0.2)
        with self.say("In general, E to the I theta is cos theta plus I sin theta. "
                      "Put in pi, and you land on minus one.",
                      caption="e^(iθ) = cos θ + i sin θ. Put in π: −1."):
            self.play(Write(general), run_time=1.8)
            self.at(4.8)
            self.play(Write(at_pi[:4]), run_time=1.5)
            self.play(Write(at_pi[4]), run_time=0.8)
        self.at(9.4)
        self.play(FadeOut(general), run_time=0.5)
