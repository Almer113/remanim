"""Deliberately broken scene used to test tools/check_layout.py."""
from manim import *


class BadLayout(Scene):
    def construct(self):
        title = Text("A title that is far too long to fit on the screen at all", font_size=48)
        title.to_edge(UP)
        eq = MathTex(r"a^2 + b^2 = c^2").move_to(UP * 0.1)
        note = Text("overlapping note", font_size=36).move_to(DOWN * 0.1)
        tiny = Text("tiny footnote", font_size=12).to_corner(DR)
        box = Square(2).shift(RIGHT * 1.6)
        self.play(Write(title))
        self.play(Write(eq), FadeIn(note))
        self.play(Create(box), FadeIn(tiny))
        self.play(eq.animate.shift(LEFT * 9))
