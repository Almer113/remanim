"""Awkward corpus: an updater that fails partway through a play, a style
value the ID map must not overwrite, and copies made by library code
(TransformFromCopy) from one user call."""
from manim import *


class LateError(Scene):
    def construct(self):
        d = Dot()
        self.add(d)
        self.play(d.animate.shift(RIGHT), run_time=1)
        t = ValueTracker(0)

        def bad(m):
            if t.get_value() > 0.5:
                raise ZeroDivisionError("boom")
        d.add_updater(bad)
        self.play(t.animate.set_value(1), run_time=1)


class Opacity(Scene):
    def construct(self):
        sq = Square(fill_opacity=0.4, color=BLUE)
        self.add(sq)
        self.play(sq.animate.shift(RIGHT), run_time=1)


class Copies(Scene):
    def construct(self):
        a = VGroup(*[Dot(LEFT * 2 + UP * i) for i in range(3)])
        b = VGroup(*[Square(0.4).shift(RIGHT * 2 + UP * i) for i in range(3)])
        self.add(a)
        self.play(*[TransformFromCopy(x, y) for x, y in zip(a, b)], run_time=1)
