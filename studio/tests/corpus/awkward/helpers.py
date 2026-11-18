"""Awkward corpus: objects made in loops, comprehensions and helpers,
including a helper used twice and one that returns a tuple."""
from manim import *


def get_row(n, color=BLUE):
    return VGroup(*[Square(0.6, color=color) for _ in range(n)]).arrange(RIGHT, buff=0.15)


def get_pair():
    a = Circle(radius=0.4, color=RED)
    b = a.copy().set_color(GREEN).next_to(a, RIGHT)
    return a, b


class Helpers(Scene):
    def construct(self):
        top = get_row(5).to_edge(UP)
        bottom = get_row(3, color=ORANGE).to_edge(DOWN)
        a, b = get_pair()
        labels = VGroup()
        for i, sq in enumerate(top):
            lab = Integer(i).scale(0.6).move_to(sq)
            labels.add(lab)
        dots = [Dot(RIGHT * x) for x in (-2, -1, 0, 1, 2)]
        self.add(top, bottom, a, b, labels, *dots)
        self.play(top[2].animate.shift(DOWN * 0.5), run_time=1)
        self.wait(0.5)
