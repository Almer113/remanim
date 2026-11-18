from manim import *


class HelloManim(Scene):
    def construct(self):
        circle = Circle(color=BLUE, fill_opacity=0.5)
        square = Square(color=GREEN)
        self.play(Create(circle))
        self.play(Transform(circle, square))
        self.play(FadeOut(circle))

        eq1 = MathTex(r"e^{i\pi} + 1 = 0")
        eq2 = MathTex(r"e^{i\theta} = \cos\theta + i\sin\theta")
        self.play(Write(eq1))
        self.wait(0.5)
        self.play(TransformMatchingTex(eq1, eq2))
        self.wait()
