"""Odd numbers make squares: 1 + 3 + 5 + ... + (2n - 1) = n^2.
Plan: plans/odd_squares.md. Made in reManim (Phase 7 exit check).
"""

from manim import *
from manim_kit import *
from style import *

OLD, NEW, CORNER, TOTAL = ACCENT, ACCENT_2, GOOD, GOOD  # colour ledger
DOT_R = 0.12
SPACING = 0.75
MATH = 56  # LaTeX reads small: maths one size up from text


class Beat(TimedScene):
    VOICE = "en-US-AndrewNeural"  # set a voice to narrate
    CAPTIONS = True

    def setup(self):
        super().setup()
        self.camera.background_color = BG

    def caption_mobject(self, text):
        return place(Text(text, font_size=CAPTION_SIZE, color=FG), "footer")

    def fade_all(self, run_time=0.5):
        mobs = [m for m in self.mobjects if m is not getattr(self, "_caption_track", None)]
        if mobs:
            self.play(*[FadeOut(m) for m in mobs], run_time=run_time)


# -- helpers -----------------------------------------------------------------

def get_layer(k, corner=ORIGIN, spacing=SPACING, color=NEW):
    """The k-th L-shaped layer (k = 1 is the single dot): 2k - 1 dots, the
    top row then the right column, the corner dot last-but-one in the row."""
    cells = [(i, k - 1) for i in range(k)] + [(k - 1, j) for j in range(k - 2, -1, -1)]
    return VGroup(*[Dot(corner + spacing * (i * RIGHT + j * UP), radius=DOT_R, color=color)
                    for i, j in cells])


def get_square(n, corner=ORIGIN, spacing=SPACING, color=OLD):
    """An n x n square of dots as its n layers, bottom-left dot at `corner`."""
    return VGroup(*[get_layer(k, corner, spacing, color) for k in range(1, n + 1)])


def get_sum(n, font_size=MATH):
    """1 + 3 + ... + (2n - 1) = n^2 as separate parts: odd terms orange, total green."""
    parts = []
    for k in range(1, n + 1):
        if k > 1:
            parts.append("+")
        parts.append(str(2 * k - 1))
    tex = MathTex(*parts, "=", str(n * n), font_size=font_size, color=FG)
    for part in tex[:-2]:
        if part.tex_string != "+":
            part.set_color(NEW)
    tex[-1].set_color(TOTAL)
    return tex


def get_sum_column():
    """The four sums 1 = 1 ... 1 + 3 + 5 + 7 = 16, their = signs lined up."""
    rows = VGroup(*[get_sum(n) for n in range(1, 5)]).arrange(DOWN, buff=0.45)
    for row in rows:
        row.shift((rows[0][-2].get_x() - row[-2].get_x()) * RIGHT)
    return rows


def get_general_eq(font_size=MATH):
    """1 + 3 + 5 + ... + (2n - 1) = n^2, odd terms orange, n^2 green."""
    eq = MathTex("1", "+", "3", "+", "5", "+", r"\cdots", "+", "(2n-1)", "=", "n^2",
                 font_size=font_size, color=FG)
    for i in (0, 2, 4, 6, 8):
        eq[i].set_color(NEW)
    eq[-1].set_color(TOTAL)
    return eq


class Sums(Beat):
    TARGET = 10.0  # seconds; the scene is padded to this length

    def construct(self):
        rows = get_sum_column()
        place(rows, "main")
        rows.shift(LEFT * 1.0)
        squares = VGroup(*[MathTex("=", f"{n}^2", font_size=MATH, color=TOTAL)
                           .next_to(row, RIGHT, buff=0.25) for n, row in enumerate(rows, 1)])
        right = max(row.get_right()[0] for row in rows) + 0.3
        for sq, row in zip(squares, rows):
            sq[0].set_color(FG)
            sq.shift((right - sq.get_left()[0]) * RIGHT + (row[-2].get_y() - sq[0].get_y()) * UP)

        self.at(0.3)
        self.line("Add up the odd numbers: one, then one plus three, then one plus three plus five.",
                  caption="Add up the odd numbers: 1, then 1 + 3, then 1 + 3 + 5.")
        self.play(Write(rows[0]), run_time=0.8)
        self.at(2.2)
        self.play(Write(rows[1]), run_time=0.8)
        self.at(3.6)
        self.play(Write(rows[2]), run_time=1.0)
        self.at(5.4)
        self.play(Write(rows[3]), run_time=1.0)
        self.at(6.6)
        self.line("Every total is a square. Why?")
        self.play(LaggedStart(*[FadeIn(sq, shift=LEFT * 0.2) for sq in squares], lag_ratio=0.3),
                  run_time=1.6)
        self.at(9.4)
        self.fade_all()


class Layers(Beat):
    TARGET = 12.97

    def construct(self):
        corner = REGIONS["left"][0] + (LEFT + DOWN) * 0.9
        layers = get_square(4, corner, color=NEW)
        sums = [get_sum(n) for n in range(1, 5)]
        for s in sums:
            place(s, "right")

        self.at(0.3)
        self.line("Start with one dot. Wrap three around it, and you have a two by two square.",
                  caption="One dot. Wrap 3 around it: a 2 × 2 square.")
        self.play(GrowFromCenter(layers[0]), FadeIn(sums[0]), run_time=0.8)
        self.at(1.6)
        self.play(layers[0].animate.set_color(OLD), run_time=0.4)
        for k in range(1, 4):
            if k == 2:
                self.at(6.0)
                self.line("Five more make three by three. Seven more make four by four.",
                          caption="5 more: 3 × 3. 7 more: 4 × 4.")
            self.at((2.4, 6.4, 9.4)[k - 1])
            self.play(LaggedStart(*[GrowFromCenter(d) for d in layers[k]], lag_ratio=0.15),
                      TransformMatchingShapes(sums[k - 1], sums[k]), run_time=1.4)
            self.play(layers[k].animate.set_color(OLD), run_time=0.4)
        self.at(12.27)
        self.fade_all()


class WhyOdd(Beat):
    TARGET = 12.27

    def construct(self):
        n = 4
        corner = LEFT * 5.4 + DOWN * 2.2
        square = get_square(n, corner)
        layer = get_layer(n + 1, corner)
        top, corner_dot, side = layer[:n], layer[n], layer[n + 1:]
        top_brace = Brace(top, UP, buff=0.15, color=FG)
        top_label = MathTex("n", font_size=MATH, color=FG).next_to(top_brace, UP, buff=0.1)
        side_brace = Brace(side, RIGHT, buff=0.15, color=FG)
        side_label = MathTex("n", font_size=MATH, color=FG).next_to(side_brace, RIGHT, buff=0.1)
        plus_one = MathTex("+1", font_size=MATH, color=CORNER).next_to(corner_dot, UR, buff=0.15)
        eq = MathTex("n", "+", "n", "+", "1", "=", "2n+1", font_size=72, color=FG)
        eq[4].set_color(CORNER)
        eq[6].set_color(NEW)
        place(eq, "right")
        eq.shift(UP * 0.5).scale(0.9)
        odd = Tex("the next odd number", font_size=44, color=NEW).next_to(eq, DOWN, buff=0.5)

        self.at(0.3)
        self.play(FadeIn(square), run_time=0.8)
        self.play(square.animate.fade(0.5), run_time=0.5)
        self.line("Each new layer covers one side, then the other, then the corner.",
                  caption="Each layer: one side, the other side, the corner.")
        self.at(2.0)
        self.play(LaggedStart(*[GrowFromCenter(d) for d in top], lag_ratio=0.1),
                  GrowFromCenter(top_brace), FadeIn(top_label), run_time=1.0)
        self.at(3.4)
        self.play(LaggedStart(*[GrowFromCenter(d) for d in side], lag_ratio=0.1),
                  GrowFromCenter(side_brace), FadeIn(side_label), run_time=1.0)
        self.at(4.8)
        corner_dot.set_color(CORNER)
        self.play(GrowFromCenter(corner_dot), FadeIn(plus_one), run_time=0.6)
        self.at(6.6)
        self.line("That's N plus N plus one: always the next odd number.",
                  caption="n + n + 1: always the next odd number.")
        self.play(Write(eq), run_time=1.4)
        self.at(9.6)
        self.play(FadeIn(odd, shift=UP * 0.2), run_time=0.6)
        self.at(11.67)
        self.fade_all()


class General(Beat):
    TARGET = 9.27

    def construct(self):
        n = 6
        corner = DOWN * 1.9 + LEFT * 1.4
        layers = get_square(n, corner, spacing=0.56)
        for k, layer in enumerate(layers):
            layer.set_color(OLD if k % 2 == 0 else NEW)
        eq = get_general_eq()
        place(eq, "title")
        terms = [eq[0], eq[2], eq[4], eq[6], eq[6], eq[8]]  # the term each layer lights

        self.at(0.3)
        self.play(FadeIn(eq), run_time=0.8)
        self.play(eq.animate.fade(0.6), run_time=0.4)
        self.line("Keep going, and the first N odd numbers always fill an N by N square.",
                  caption="The first n odd numbers always fill an n × n square.")
        for k, layer in enumerate(layers):
            self.play(LaggedStart(*[GrowFromCenter(d) for d in layer], lag_ratio=0.08),
                      terms[k].animate.set_opacity(1), run_time=0.7)
        self.play(eq[1::2].animate.set_opacity(1), eq[-1].animate.set_opacity(1),
                  run_time=0.8)
        self.at(7.87)
        self.play(FadeOut(layers), run_time=0.6)


class Takeaway(Beat):
    TARGET = 8.0

    def construct(self):
        eq = get_general_eq()
        place(eq, "title")
        self.add(eq)
        check = MathTex(r"1 + 3 + \cdots + 19", "=", "100", "=", "10^2", font_size=MATH, color=FG)
        check[-1].set_color(TOTAL)

        self.at(0.2)
        self.play(eq.animate.scale(1.25).move_to(REGIONS["main"][0] + UP * 0.6), run_time=1.0)
        check.next_to(eq, DOWN, buff=0.8)
        self.line("One plus three, all the way to nineteen, is a hundred: ten squared.",
                  caption="All the way to 19: 100, which is 10².")
        self.at(1.6)
        self.play(FadeIn(check, shift=UP * 0.2), run_time=0.8)
        self.at(7.4)
        self.fade_all()
