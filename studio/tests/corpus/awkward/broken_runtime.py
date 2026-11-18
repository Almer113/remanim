"""Awkward corpus: parses, crashes at t = 1. The studio must show the trace
up to the crash and the failing line."""
from manim import *


class CrashLater(Scene):
    def construct(self):
        c = Circle()
        self.play(Create(c), run_time=1)
        self.play(Write(undefined_name), run_time=1)  # noqa: F821
