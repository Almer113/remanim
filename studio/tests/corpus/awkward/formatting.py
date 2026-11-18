# Awkward corpus: formatting the studio must never disturb.
# Comments everywhere, multi-line calls, trailing commas, odd spacing,
# backslash continuations, semicolons, unicode, raw strings.
from manim import *  # star import, as usual


class Formatting(Scene):
    def construct(self):
        # a comment before the object
        title = Text( "Ünïcödé — ✓" ,font_size = 40 )   # odd spacing kept
        title.to_edge(UP)  ;  title.shift(0.1*DOWN)   # two statements, one line
        eq = MathTex(
            r"e^{i\pi} + 1 = 0",   # raw string
            color=YELLOW,          # trailing comment
        )
        box = Square(side_length=2) \
            .shift(LEFT * 3)       # backslash continuation
        dot = Dot(point=np.array([2., -1.0, 0]))  # numpy vector literal
        self.play(Write(title), run_time=1)
        self.play(FadeIn(eq, shift=UP * .5), Create(box),)   # trailing comma
        self.add(dot)
        self.wait(0.5)
        # a comment at the end
