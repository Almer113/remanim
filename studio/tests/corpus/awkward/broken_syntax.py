"""Awkward corpus: does not parse. The studio must open it read-only
and never write to it."""
from manim import *


class Broken(Scene):
    def construct(self):
        c = Circle(radius=1
        self.play(Create(c))
