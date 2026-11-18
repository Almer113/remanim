"""Awkward corpus: scenes built from a base class and a mixin."""
from manim import *


class TitleMixin:
    TITLE = "Base"

    def add_title(self):
        self.title = Text(self.TITLE, font_size=40).to_edge(UP)
        self.play(FadeIn(self.title), run_time=0.5)


class BaseScene(TitleMixin, Scene):
    def construct(self):
        self.add_title()
        self.body()
        self.wait(0.5)

    def body(self):
        self.play(Create(Circle()), run_time=1)


class Child(BaseScene):
    TITLE = "Child"

    def body(self):
        sq = Square(color=GREEN)
        self.play(Create(sq), run_time=1)
        super().body()
