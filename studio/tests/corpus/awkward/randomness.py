"""Awkward corpus: non-determinism. Seeded is fine; unseeded must be flagged."""
import random

from manim import *


class Seeded(Scene):
    def construct(self):
        rng = random.Random(7)
        dots = VGroup(*[Dot([rng.uniform(-5, 5), rng.uniform(-3, 3), 0]) for _ in range(20)])
        self.play(FadeIn(dots), run_time=1)


class Unseeded(Scene):
    def construct(self):
        dots = VGroup(*[Dot([random.uniform(-5, 5), random.uniform(-3, 3), 0]) for _ in range(20)])
        self.play(FadeIn(dots), run_time=1)
