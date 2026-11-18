"""Awkward corpus: a wait() inside `finally:`, as manim-voiceover's
voiceover() block does. Closing a cursor unwinds through it."""
from manim import *


class FinallyWait(Scene):
    def construct(self):
        for i in range(4):
            try:
                self.play(FadeIn(Dot(LEFT * 3 + RIGHT * 2 * i)), run_time=1)
            finally:
                self.wait(0.5)
