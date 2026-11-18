"""Awkward corpus: every way of writing time. LaggedStart, AnimationGroup,
Succession with Wait, per-animation run_time, play-level override, bare wait(),
rate functions, and a manim_kit TimedScene with at()."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for manim_kit
from manim import *
from manim_kit import TimedScene


class Timing(Scene):
    def construct(self):
        s = VGroup(*[Square(0.5) for _ in range(4)]).arrange(RIGHT)
        self.play(LaggedStart(*[FadeIn(m) for m in s], lag_ratio=0.3), run_time=1.5)
        self.play(s[0].animate(run_time=0.5).shift(UP), s[1].animate(run_time=1.0).shift(UP))
        self.play(Succession(Wait(0.4), s[2].animate.shift(UP)), rate_func=there_and_back)
        self.play(AnimationGroup(s[3].animate.shift(UP), s[3].animate.set_color(RED)), run_time=2)
        self.wait()


class Anchored(TimedScene):
    VOICE = None

    def construct(self):
        c = Circle()
        self.at(0.5)
        self.play(Create(c), run_time=1)
        self.at(2.25)
        self.play(c.animate.shift(RIGHT), run_time=0.5, rate_func=rush_into)
        self.at(4)
