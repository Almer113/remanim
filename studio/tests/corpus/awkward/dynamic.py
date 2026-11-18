"""Awkward corpus: tier 3. Updaters, always_redraw, ValueTracker, lambdas."""
from manim import *


class Dynamic(Scene):
    def construct(self):
        x = ValueTracker(-3)
        dot = always_redraw(lambda: Dot(RIGHT * x.get_value(), color=YELLOW))
        label = DecimalNumber(0, num_decimal_places=1).to_edge(UP)
        label.add_updater(lambda m: m.set_value(x.get_value()))
        spinner = Square().shift(DOWN * 2)
        spinner.add_updater(lambda m, dt: m.rotate(dt))
        self.add(dot, label, spinner)
        self.play(x.animate.set_value(3), run_time=2, rate_func=linear)
        self.wait(1)
