"""Order matters: AB ≠ BA — a short test video for manim_kit.py.

Plan: plans/order_matters.md. Render order: Question, RotateThenShear,
ShearThenRotate, CompareMatrices, Takeaway.
"""

from manim_kit import *
from style import *

R_COLOR, S_COLOR = ACCENT, ACCENT_2
I_COL, J_COL = GOOD, BAD
BLOB_COLOR = PURPLE_B

SHEAR = [[1, 1], [0, 1]]
ROT = [[0, -1], [1, 0]]
SR = [[1, -1], [1, 0]]  # S·R: rotate first, then shear
RS = [[0, -1], [1, 1]]  # R·S: shear first, then rotate

BOX_W, BOX_H, UNIT = 5.6, 3.4, 0.7
LEFT_BOX = LEFT * 3.4 + UP * 0.05
RIGHT_BOX = RIGHT * 3.4 + UP * 0.05


class Beat(TimedScene):
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


# ── helpers ──────────────────────────────────────────────────────────────

def get_title():
    return place(Text("Order matters", font_size=TITLE_SIZE, color=FG), "title")


def get_grid(center, *steps):
    return ClippedGrid(("rect", center, BOX_W, BOX_H), unit=UNIT, extent=20,
                       matrix_of=chain_matrices(*steps), line_color=MUTED,
                       i_color=I_COL, j_color=J_COL)


def get_heading(text, center):
    return Text(text, font_size=BODY_SIZE, color=FG).next_to(center + UP * BOX_H / 2, UP, buff=0.25)


def get_steps(first, second, center):
    """'1. R  2. S' under a box, each in its ledger colour."""
    def step(n, letter):
        col = R_COLOR if letter == "R" else S_COLOR
        return Text(f"{n}. {letter}", font_size=BODY_SIZE, color=col)
    g = VGroup(step(1, first), step(2, second)).arrange(RIGHT, buff=0.8)
    return g.next_to(center + DOWN * BOX_H / 2, DOWN, buff=0.2)


def get_landing(grid, matrix, label):
    tip = grid.to_screen(matrix, (1, 0))
    lbl = MathTex(label, color=I_COL, font_size=BODY_SIZE).next_to(tip, UR, buff=0.08)
    return lbl.add_background_rectangle(color=BG, opacity=0.85, buff=0.06)


def get_panel(center, heading, first, second, matrix, label):
    """A finished panel (static), for carrying into a later scene."""
    steps = (turn(PI / 2), SHEAR) if first == "R" else (SHEAR, turn(PI / 2))
    grid = get_grid(center, *steps)
    grid.tracker.set_value(1)
    return VGroup(grid.snapshot(), get_heading(heading, center),
                  get_steps(first, second, center), get_landing(grid, matrix, label))


# ── beats ────────────────────────────────────────────────────────────────

class Question(Beat):
    TARGET = 7.5

    def construct(self):
        title = get_title()
        blob = Blob(BLOB_COLOR, height=2.0).to_corner(DL, buff=0.7).shift(UP * 0.5)
        bubble = SpeechBubble(6.6, 2.2, center=blob.get_top() + UP * 1.4 + RIGHT * 3.9,
                              tip=blob.get_top() + RIGHT * 0.5, stroke_color=FG, fill_color=BG)
        words = bubble.place_inside(Text("Does the order matter?", font_size=BODY_SIZE, color=FG))
        eq = MathTex("S", "R", r"\overset{?}{=}", "R", "S", font_size=72, color=FG)
        for i in (0, 4):
            eq[i].set_color(S_COLOR)
        for i in (1, 3):
            eq[i].set_color(R_COLOR)
        eq.move_to(RIGHT * 3.6 + DOWN * 1.0)

        self.at(0.2)
        self.play(FadeIn(title), FadeIn(blob, shift=UP * 0.2), run_time=0.8)
        with self.say("Rotate, then shear. Or shear, then rotate. Same result?"):
            self.at(1.2)
            self.add(bubble)
            self.bring_to_front(words)
            self.play(FadeIn(bubble), Write(words), blob.animate.set_mode("speaking"), run_time=1.0)
            self.at(3.4)
            self.play(Write(eq), blob.animate.set_mode("confused").look_at(eq.get_center()),
                      run_time=1.2)
            self.at(5.2)
            self.play(blink(blob))
        self.at(6.9)
        self.fade_all()


class RotateThenShear(Beat):
    TARGET = 10.0

    def construct(self):
        self.add(get_title())
        heading = get_heading("Rotate, then shear", LEFT_BOX)
        grid = get_grid(LEFT_BOX, turn(PI / 2), SHEAR)
        steps = get_steps("R", "S", LEFT_BOX)
        landing = get_landing(grid, SR, "(1,\\,1)")

        with self.say("First rotate a quarter turn, then shear. The green arrow lands here."):
            self.at(0.3)
            self.play(FadeIn(heading), FadeIn(grid.mobject), run_time=0.8)
            self.at(1.4)
            self.play(FadeIn(steps[0]), run_time=0.4)
            self.play(grid.tracker.animate.set_value(0.5), run_time=1.8)
            self.at(4.0)
            self.play(FadeIn(steps[1]), run_time=0.4)
            self.play(grid.tracker.animate.set_value(1), run_time=1.8)
            self.at(6.6)
            self.play(Write(landing), run_time=0.6)
        self.at(9.5)  # hold the result; the next beat continues from here


class ShearThenRotate(Beat):
    TARGET = 11.5

    def construct(self):
        self.add(get_title())
        left = get_panel(LEFT_BOX, "Rotate, then shear", "R", "S", SR, "(1,\\,1)")
        self.add(left)
        heading = get_heading("Shear, then rotate", RIGHT_BOX)
        grid = get_grid(RIGHT_BOX, SHEAR, turn(PI / 2))
        steps = get_steps("S", "R", RIGHT_BOX)
        landing = get_landing(grid, RS, "(0,\\,1)")

        # Not set_opacity(): it sets fill AND stroke absolutely, so the
        # outline-only border would fill grey (then solid white on "undo").
        # fade() scales what's there; Restore() undoes it exactly.
        left.save_state()
        self.at(0.2)
        self.play(left.animate.fade(0.7), run_time=0.6)
        with self.say("Now the other way: shear first, then rotate. It lands somewhere else."):
            self.play(FadeIn(heading), FadeIn(grid.mobject), run_time=0.8)
            self.at(1.8)
            self.play(FadeIn(steps[0]), run_time=0.4)
            self.play(grid.tracker.animate.set_value(0.5), run_time=1.8)
            self.at(4.4)
            self.play(FadeIn(steps[1]), run_time=0.4)
            self.play(grid.tracker.animate.set_value(1), run_time=1.8)
            self.at(7.0)
            self.play(Write(landing), run_time=0.6)
        self.at(8.6)
        self.play(Restore(left), run_time=0.6)  # both results side by side
        self.at(11.0)
        self.fade_all()


def get_product(left, right, values):
    lhs = MathTex(left, right, "=", font_size=60)
    for part, letter in ((lhs[0], left), (lhs[1], right)):
        part.set_color(R_COLOR if letter == "R" else S_COLOR)
    m = Matrix(values, element_to_mobject_config={"font_size": 60}).set_color(FG)
    return VGroup(lhs, m).arrange(RIGHT, buff=0.25), m


class CompareMatrices(Beat):
    TARGET = 9.0

    def construct(self):
        title = get_title()
        self.add(title)
        sr, m_sr = get_product("S", "R", SR)
        rs, m_rs = get_product("R", "S", RS)
        neq = MathTex(r"\neq", font_size=72, color=FG)
        row = place(VGroup(sr, neq, rs).arrange(RIGHT, buff=0.6), "main")
        note = Text("first column = where the green arrow lands", font_size=CAPTION_SIZE,
                    color=I_COL).next_to(row, DOWN, buff=0.6)

        with self.say("As matrices, S R and R S really are different.",
                      caption="As matrices, SR and RS really are different."):
            self.at(0.4)
            self.play(Write(sr), run_time=1.2)
            self.at(1.9)
            self.play(Write(rs), run_time=1.2)
            self.at(3.4)
            self.play(Write(neq), run_time=0.6)
        self.at(4.8)
        self.play(m_sr.get_columns()[0].animate.set_color(I_COL),
                  m_rs.get_columns()[0].animate.set_color(I_COL), FadeIn(note), run_time=0.8)
        self.at(8.5)
        self.fade_all()


class Takeaway(Beat):
    TARGET = 7.5

    def construct(self):
        blob = Blob(BLOB_COLOR, height=2.0, mode="happy").to_corner(DL, buff=0.7).shift(UP * 0.5)
        cloud = thought_cloud_for(blob, width=4.4, height=2.6, stroke_color=FG, fill_color=BG)
        c, a, b = cloud.clip
        spin = ClippedGrid(("ellipse", c, a, b), unit=0.35, bg_grid=False, line_color=MUTED,
                           i_color=I_COL, j_color=J_COL,
                           matrix_of=lambda t: rotation(TAU * t) @ np.array(SHEAR, dtype=float))
        rule = VGroup(
            MathTex("S", "R", font_size=72),
            Text("means", font_size=TITLE_SIZE, color=FG),
            Text("R first", font_size=TITLE_SIZE, color=R_COLOR),
        ).arrange(RIGHT, buff=0.35)
        rule[0][0].set_color(S_COLOR)
        rule[0][1].set_color(R_COLOR)
        rule.move_to(RIGHT * 3.6 + DOWN * 1.2)

        self.at(0.2)
        self.add(cloud)
        self.play(FadeIn(blob), Create(cloud), run_time=0.8)
        # Fade in while still; only then start turning (a grid that turns while
        # it fades in is hard to read).
        self.play(FadeIn(spin.mobject), run_time=0.4)
        spin.tracker.add_updater(lambda m, dt: m.increment_value(dt / 5))
        self.add(spin.tracker)
        with self.say("Read a product right to left: S R means R happens first.",
                      caption="Read right to left: SR means R happens first."):
            self.at(1.8)
            self.play(Write(rule), run_time=1.2)
            self.at(4.4)
            self.play(blink(blob))
        self.at(7.0)
        self.fade_all()


SCENES = ["Question", "RotateThenShear", "ShearThenRotate", "CompareMatrices", "Takeaway"]
