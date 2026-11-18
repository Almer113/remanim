"""Awkward corpus: morphs and copies."""
from manim import *


class Transforms(Scene):
    def construct(self):
        a = MathTex("a", "^2", "+", "b", "^2")
        b = MathTex("c", "^2").shift(DOWN)
        self.play(Write(a), run_time=1)
        self.play(TransformMatchingTex(a.copy(), b), run_time=1)
        sq = Square()
        circ = Circle().shift(RIGHT * 3)
        self.play(Create(sq), run_time=0.5)
        self.play(Transform(sq, circ), run_time=1)
        tri = Triangle().shift(LEFT * 3)
        self.play(ReplacementTransform(sq, tri), run_time=1)
        self.wait(0.3)
