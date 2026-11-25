"""Recreation study of 3Blue1Brown's "Essence of linear algebra preview" (2016).

Plan, shot list and ground rules: plans/eola_preview.md

Visuals adapted from 3Blue1Brown's scene code (github.com/3b1b/videos,
_2016/eola/chapter0.py), licensed CC BY-NC-SA 4.0. This file is shared under the
same license, for non-commercial use. Narration is original; the characters are
an original design (not 3Blue1Brown's Pi creatures); no logo or music.

Every scene has TARGET = its length in the reference, and timestamps inside a
scene (self.at(t)) are seconds from the scene's start, read off the reference.
Render order: S01 ... S23.
"""

from eola_common import *

STUDENT, STUDENT_2, STUDENT_3 = BLUE_D, BLUE_C, BLUE_E
PROF = GREY_BROWN
SAFE_X = 6.5  # same safe area as style.py (not imported: its palette differs from 2016)


def fade_all(scene, run_time=0.5):
    if scene.mobjects:
        scene.play(*[FadeOut(m) for m in scene.mobjects], run_time=run_time)


def get_student(color=STUDENT, **kw):
    return Blob(color, **kw).to_corner(DL)


def get_prof(**kw):
    return Blob(PROF, glasses=True, **kw).to_corner(DR).shift(LEFT * 3)


# ── 1–3: opening ─────────────────────────────────────────────────────────

class S01_TitleCard(EolaScene):
    TARGET = 4.3

    def construct(self):
        title = Tex("Essence of Linear Algebra", font_size=60)
        sub = Tex("preview --- a recreation study", font_size=36, color=GREY_B).next_to(title, DOWN)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=1)
        self.play(FadeIn(sub), run_time=0.6)
        self.at(3.6)
        fade_all(self, 0.6)


class S02_OpeningQuote(EolaScene):
    TARGET = 8.1

    def construct(self):
        words = Tex(r"``There is hardly any theory which is more elementary than ",
                    r"linear algebra", r"\ldots''")
        words[1].set_color(GREEN)
        words.scale_to_fit_width(FW - 2).to_edge(UP)
        author = Tex(r"-Jean Dieudonn\'e", color=YELLOW).next_to(words, DOWN)
        self.play(FadeIn(words), run_time=0.8)
        self.at(3.4)
        self.play(Write(author), run_time=2.4)
        self.at(7.5)
        fade_all(self, 0.5)


class S03_UpcomingSeries(EolaScene):
    TARGET = 4.6

    def construct(self):
        icons = get_icons()
        with self.say("A new series is on its way, and it's all about linear algebra."):
            self.play(LaggedStart(*[FadeIn(i) for i in icons], lag_ratio=0.15), run_time=3.0)
        self.at(4.1)
        fade_all(self, 0.4)


# ── 4–5: linear algebra everywhere; the recipes ─────────────────────────

def get_linalg_label():
    return Tex("Linear Algebra").to_edge(LEFT, buff=0.7)


class S04_AboutLinearAlgebra(EolaScene):
    TARGET = 10.5

    def construct(self):
        linalg = get_linalg_label()
        subjects = VGroup(*[Tex(s) for s in [
            "Computer science", "Physics", "Electrical engineering",
            "Mechanical engineering", "Statistics", r"$\vdots$"]])
        subjects.arrange(DOWN, aligned_edge=LEFT, buff=0.15).next_to(linalg, RIGHT, buff=2)
        arrows = VGroup(*[Arrow(linalg.get_right(), s.get_left(), color=YELLOW, buff=0.15)
                          for s in subjects])
        with self.say("Linear algebra underpins computer science, physics, engineering and "
                      "statistics. Yet many students finish the course without really getting it."):
            self.at(0.6)
            self.play(Write(linalg), run_time=1)
            self.at(3.6)
            self.play(LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.5),
                      FadeIn(subjects), run_time=2)
        self.at(9.8)
        self.play(FadeOut(subjects), FadeOut(arrows), run_time=0.6)


class S05_TopicsBubble(EolaScene):
    TARGET = 25.6

    def construct(self):
        linalg = get_linalg_label()
        self.add(linalg)
        student = get_student()
        cloud = thought_cloud_for(student, width=7, height=3.4)
        q_marks = Tex("???").next_to(student, UP)

        def inside(m):
            return cloud.place_inside(m)

        topics = [
            MathTex(MATMUL_TEX),
            MathTex(r"\text{Det}\begin{pmatrix} a & b \\ c & d \end{pmatrix} = ad - bc"),
            MathTex(r"\vec{\textbf{v}} \times \textbf{w} = \text{Det}"
                    r"\begin{pmatrix} \hat{\imath} & \hat{\jmath} & \hat{k} \\"
                    r" v_1 & v_2 & v_3 \\ w_1 & w_2 & w_3 \end{pmatrix}"),
            MathTex(r"\text{Det}(A - ", r"\lambda", r" I) = 0"),
        ]
        topics[3][1].set_color(YELLOW)
        why = VGroup(Tex("Why?", color=BLUE), MathTex(MATMUL_TEX)).arrange(DOWN)
        arrow = DoubleArrow(LEFT * 0.7, RIGHT * 0.7, color=YELLOW, buff=0, tip_length=0.15)
        cross_q = VGroup(MathTex(r"\vec{v} \times \vec{w}"), arrow, Tex("Det")).arrange(RIGHT)
        cross_q.add(Tex("?").next_to(arrow, UP, buff=0.1))
        eigen_q = Tex(r"What does ``", r"eigen", r"'' \\ even mean?")
        eigen_q[1].set_color(YELLOW)
        for m in topics + [why, cross_q, eigen_q]:
            inside(m)

        with self.say("In a typical class you learn recipes. Multiply these matrices. "
                      "Compute that determinant. Use it to get a cross product. Solve for "
                      "the eigenvalues."):
            self.add(cloud)  # added first so its black fill sits under the label
            self.bring_to_front(linalg)
            self.play(linalg.animate.move_to(cloud.cloud.get_center()), Create(cloud),
                      FadeIn(student), run_time=1.6)
            self.at(5.5)
            current = linalg
            for t, topic in zip((5.5, 7.8, 9.8, 12.5), topics):
                self.at(t)
                self.play(Transform(current, topic), run_time=1)
        with self.say("The procedures work, but the reasons stay hidden. Why is multiplication "
                      "defined like this? What does a cross product have to do with a "
                      "determinant? And what is an eigenvalue, really?"):
            self.at(15.2)
            self.play(FadeOut(current), run_time=0.5)
            self.play(student.animate.set_mode("confused"), Write(q_marks), run_time=0.8)
            last = None
            for t, q in zip((16.5, 19.6, 23.5), (why, cross_q, eigen_q)):
                self.at(t)
                if last:
                    self.play(FadeOut(last), run_time=0.3)
                self.play(FadeIn(q), run_time=0.5)
                last = q
        self.at(25.1)
        fade_all(self, 0.5)


# ── 6–8: numeric vs geometric ───────────────────────────────────────────

NUM_MATRIX = [[1, 0], [1, -1]]    # the numbers the video shows on the left...
GRID_MATRIX = [[0, 1], [-1, 1]]   # ...while its grid plays the code's EXAMPLE_TRANFORM
                                  # (read off the frames: (1,2) lands on (2,1))


def numeric_product():
    m = MathTex(r"\begin{bmatrix} 1 & 0 \\ 1 & -1 \end{bmatrix}"
                r"\begin{bmatrix} 1 \\ 2 \end{bmatrix}"
                r"&= \begin{bmatrix} 1\cdot 1 + 0 \cdot 2 \\ 1 \cdot 1 + (-1)\cdot 2 \end{bmatrix} \\"
                r"&= \begin{bmatrix} 1 \\ -1 \end{bmatrix}")
    return m.scale_to_fit_width(FW / 2 - 0.9)


class S06_NumericVsGeometric(EolaScene):
    TARGET = 17.7

    def construct(self):
        numeric = Tex("Numeric operations").to_corner(UL)
        geometric = Tex("Geometric intuition").to_corner(UL).shift(RIGHT * FW / 2)
        hline = Line(LEFT * FW / 2, RIGHT * FW / 2, color=GREEN).next_to(numeric, DOWN)
        hline.set_x(0)
        vline = Line(UP * FH / 2, DOWN * FH / 2, color=GREEN)
        product = numeric_product().next_to(vline, LEFT).shift(UP * 0.2)
        # box measured from the reference frame at 1:00
        grid = ClippedGrid(("rect", RIGHT * 3.85, 6.0, 3.5), unit=0.55, extent=20,
                           matrix_of=lerp_matrix(GRID_MATRIX), vectors=[((1, 2), YELLOW)])

        with self.say("There are two ways to know this subject. One is numeric: you can carry "
                      "out the operations."):
            self.at(0.8)
            self.play(Create(VGroup(hline, vline)), run_time=1)
            self.play(Write(numeric), FadeIn(product), run_time=1.2)
        with self.say("The other is geometric: you can picture what those operations do to space."):
            self.at(4.9)  # reference: grid in by ~5.9 s, transform ~6.2-8.0 s (checked over 4 frames)
            self.play(Write(geometric), FadeIn(grid.mobject, run_time=0.8), run_time=1.0)
            self.at(6.1)
            self.play(grid.tracker.animate.set_value(1), run_time=2.0)
        self.at(11)
        grid.tracker.set_value(0)
        self.wait(0.6)
        self.play(grid.tracker.animate.set_value(1), run_time=2.8)
        self.at(16.9)
        bottom = Line(LEFT * 4, RIGHT * 4).shift((FH / 2 + 1) * DOWN)
        self.play(Transform(vline, bottom), Transform(hline, bottom),
                  numeric.animate.shift((FH + 1) * DOWN), product.animate.shift((FH + 1) * DOWN),
                  geometric.animate.to_edge(LEFT), FadeOut(grid.mobject), run_time=0.8)


class S07_GeometricHelpful(EolaScene):
    TARGET = 10.5

    def construct(self):
        geometric = Tex("Geometric intuition").to_corner(UL).to_edge(LEFT)
        follow = Tex(r"is helpful for \dots").next_to(geometric, RIGHT)
        follow.align_to(geometric, DOWN)
        self.add(geometric)
        student = Blob(STUDENT, mode="plain").shift(DOWN * 1.2)
        bulb = VGroup(
            Circle(radius=0.32, color=YELLOW, fill_opacity=0.25),
            *[Line(UP * 0.42, UP * 0.6, color=YELLOW).rotate(a, about_point=ORIGIN)
              for a in np.linspace(-1, 1, 5)],
            Rectangle(width=0.22, height=0.18, color=YELLOW, fill_opacity=0.6).shift(DOWN * 0.4),
        )
        thoughts = [bmatrix(NUM_MATRIX), bulb, Tex("So therefore...").scale(0.5)]
        for th in thoughts:
            th.next_to(student, UR, buff=0)
        with self.say("The geometric view tells you which tool fits a problem, why it works, "
                      "and what the answer means."):
            self.play(Write(follow), run_time=1.5)
            self.play(FadeIn(student), Write(thoughts[0]), run_time=1)
            current = thoughts[0]
            for t, mode, th in ((4.6, "happy", thoughts[1]), (7.4, "confused", thoughts[2])):
                self.at(t)
                self.play(student.animate.set_mode(mode), FadeTransform(current, th), run_time=0.8)
                current = th
        self.at(10.0)
        fade_all(self, 0.5)


class S08_NumericToComputations(EolaScene):
    TARGET = 4.3

    def construct(self):
        arrow = Arrow(UP, DOWN, color=YELLOW)
        top = Tex("Numeric understanding").next_to(arrow, UP)
        bottom = Tex("Actual computations").next_to(arrow, DOWN)
        self.add(top)
        with self.say("The numeric view is what gets you the answer."):
            self.play(Create(arrow), run_time=0.8)
            self.play(FadeIn(bottom), run_time=0.8)
        self.at(3.8)
        fade_all(self, 0.5)


# ── 9–10: the pyramid; intimidating experts ─────────────────────────────

class S09_LinAlgPyramid(EolaScene):
    TARGET = 21.7

    def construct(self):
        rects = [Rectangle(height=1, width=w, color=YELLOW) for w in (8, 5, 2)]
        rects[0].shift(2 * DOWN)
        for i in (1, 2):
            rects[i].next_to(rects[i - 1], UP, buff=0)
        words = [Tex(w).move_to(r) for w, r in
                 zip(["Geometric understanding", "Computations", "Uses"], rects)]
        subjects = [Tex(s).to_corner(UR) for s in
                    ["computer science", "engineering", "statistics", "economics", "pure math"]]
        arrow = Arrow(rects[2].get_right(), subjects[0].get_bottom(), color=RED)

        with self.say("Skip the geometric layer, and the cracks might not show for a while."):
            self.at(0.4)
            for w, r in zip(words, rects):
                self.play(Write(w), Create(r), run_time=1)
            self.at(4.5)
            self.play(words[0].animate.set_color(GREY_D), rects[0].animate.set_color(GREY_D))
        with self.say("They show up later, when computer science, engineering, statistics, "
                      "economics or pure maths start building on top of it."):
            self.at(9.0)
            self.play(Create(arrow), run_time=1)
            current = None
            for t, s in zip((11.2, 12.2, 13.2, 14.2, 15.2), subjects):
                self.at(t)
                if current is None:
                    current = s
                    self.play(FadeIn(s), run_time=0.5)
                else:
                    s.move_to(current)
                    self.play(Transform(current, s), run_time=0.5)
        self.at(21.2)
        fade_all(self, 0.5)


class S10_IntimidatingProf(EolaScene):
    TARGET = 17.1

    def construct(self):
        student = get_student()
        prof = get_prof()
        names = [Tex(n).to_edge(RIGHT).shift(2 * UP) for n in ("Professor", "Coworker")]
        arrow = Arrow(names[0].get_bottom(), prof.get_top() + RIGHT * 0.2, color=YELLOW)
        speech = SpeechBubble(7.4, 2.6, center=LEFT * 2.9 + UP * 0.9, tip=prof.get_top() + LEFT * 0.4)
        speech.add(speech.place_inside(Tex(r"Clearly $B^{-1}AB$ inherits \\ those positive eigenvalues\dots",
                                           font_size=34)))
        cloud = ThoughtCloud(4.8, 3.0, tail_to=DOWN * 2.0 + LEFT * 0.9).move_to(RIGHT * 3.9 + UP * 1.85)
        c, a, b = cloud.clip
        rot = rotation(PI / 3)
        A = np.array(NUM_MATRIX, dtype=float) @ np.array([[0, 1], [-1, 1]])  # some generic map

        def M(t):
            # undo a rotation, apply A, redo the rotation (the source's sequence)
            if t < 1 / 3:
                return rotation(-PI / 3 * 3 * t)
            if t < 2 / 3:
                s = 3 * t - 1
                return ((1 - s) * np.eye(2) + s * A) @ np.linalg.inv(rot)
            s = 3 * t - 2
            return rotation(PI / 3 * s) @ A @ np.linalg.inv(rot)

        grid = ClippedGrid(("ellipse", c, a, b), unit=0.42, matrix_of=M, bg_grid=False)
        q_marks = Tex("???").next_to(student, UP)
        student_cloud = thought_cloud_for(student, width=5.2, height=2.6)
        student_cloud.add(student_cloud.place_inside(MathTex(MATMUL_TEX)))
        self.add(student, prof)

        with self.say("Then you watch a professor, or a coworker, glance at a problem and "
                      "know the shape of the answer at once."):
            self.at(0.5)
            self.play(FadeIn(names[0]), Create(arrow), run_time=1)
            self.at(1.8)
            self.play(Transform(names[0], names[1]), run_time=0.8)
            self.at(3.2)
            self.play(FadeOut(names[0]), FadeOut(arrow), run_time=0.6)
            self.at(4.2)
            self.play(FadeIn(speech), prof.animate.set_mode("speaking"), run_time=0.8)
            self.play(FadeIn(cloud), FadeIn(grid.mobject), run_time=0.8)
        with self.say("If you assume they're grinding through numbers in their head, it looks "
                      "like magic, and it's a little discouraging."):
            self.play(grid.tracker.animate.set_value(1 / 3), run_time=2)
            self.play(student.animate.set_mode("confused"), Write(q_marks),
                      grid.tracker.animate.set_value(2 / 3), run_time=2.3)
            self.play(grid.tracker.animate.set_value(1), run_time=2.3)
        self.at(13.2)
        self.play(FadeOut(speech), FadeOut(cloud), FadeOut(grid.mobject), run_time=0.5)
        self.play(FadeIn(student_cloud), run_time=0.6)
        self.at(16.6)
        fade_all(self, 0.5)


# ── 11–13: the sine analogy ─────────────────────────────────────────────

SINE_SERIES = (r"\sin(x) = x - \dfrac{x^3}{3!} + \dfrac{x^5}{5!} + \cdots"
               r" + (-1)^n \dfrac{x^{2n+1}}{(2n+1)!} + \cdots")


def approx_series(val_str, val):
    approx = val - val ** 3 / 6 + val ** 5 / 120
    return MathTex(rf"\sin({val_str}) \approx {val_str} - \dfrac{{({val_str})^3}}{{3!}}"
                   rf" + \dfrac{{({val_str})^5}}{{5!}} \approx {approx:.4f}")


class S11_SineApproximations(EolaScene):
    TARGET = 20.8

    def construct(self):
        series = MathTex(SINE_SERIES).to_edge(UP)
        one = approx_series("1", 1).set_color(YELLOW).next_to(series, DOWN, buff=1.5)
        sixth = approx_series(r"\pi/6", PI / 6).set_color(RED).next_to(one, DOWN, buff=1.5)
        words = Tex("(How calculators compute sine)", color=GREEN)
        with self.say("Here's an analogy. Suppose sine had only ever been shown to you as this "
                      "infinite sum."):
            self.at(0.6)
            self.play(Write(series), run_time=1.6)
        with self.say("It is how calculators get their values, so it isn't wrong."):
            self.at(6.0)
            self.play(FadeIn(words), run_time=2)
        self.at(11.8)
        self.play(FadeOut(words), run_time=1)
        with self.say("You'd practise plugging in numbers and adding up terms."):
            self.at(13.4)
            self.play(Write(one), run_time=1.3)
            self.at(16.4)
            self.play(Write(sixth), run_time=1.3)
        self.at(20.3)
        fade_all(self, 0.5)


class S12_LooseConnectionToTriangles(EolaScene):
    TARGET = 9.5

    def construct(self):
        arrow = DoubleArrow(LEFT, RIGHT, color=YELLOW, buff=0)
        sine = MathTex(r"\sin(x)").next_to(arrow, LEFT)
        tri = Polygon(ORIGIN, 2 * RIGHT, 2 * RIGHT + UP, color=GREEN).next_to(arrow, RIGHT)
        q = Tex("?").scale(1.5).next_to(arrow, UP)
        self.add(sine)
        with self.say("Somewhere in the back of your mind, you'd know it relates to triangles, "
                      "but no one ever showed you how."):
            self.play(Create(arrow), run_time=0.8)
            self.play(Create(tri), run_time=1)
            self.play(Write(q), run_time=0.8)
        self.at(9.0)
        fade_all(self, 0.5)


class S13_PhysicsExample(EolaScene):
    TARGET = 22.6

    def construct(self):
        title = Tex("Physics").to_corner(UL)
        parabola = FunctionGraph(lambda x: (3 - x) * (3 + x) / 4, x_range=[-4, 4], color=BLUE_D)
        dot = Dot(radius=0.15, color=WHITE)
        alpha, vlen = 0.7, 3
        p1 = parabola.point_from_proportion(alpha)
        p2 = parabola.point_from_proportion(alpha + 0.01)
        vec = vlen * (p2 - p1) / np.linalg.norm(p2 - p1)
        v = Arrow(p1, p1 + vec, buff=0, color=YELLOW)
        vx = Arrow(p1, p1 + vec[0] * RIGHT, buff=0, color=GREEN_B)
        vy = Arrow(p1 + vec[0] * RIGHT, p1 + vec, buff=0, color=RED)
        arc = Arc(radius=vlen / 4, angle=angle_of_vector(vec), arc_center=p1)
        theta = MathTex(r"\theta").scale(0.75).next_to(arc, RIGHT, buff=0.1)
        v_lbl = MathTex(r"\vec{v}", color=YELLOW).move_to(p1 + RIGHT * vec[0] / 4 + UP * vec[1] / 2)
        vx_lbl = MathTex(r"||\vec{v}|| \cos(\theta)", color=GREEN_B).next_to(vx, UP)
        vy_lbl = MathTex(r"||\vec{v}|| \sin(\theta)", color=RED).next_to(vy, RIGHT)
        prof = Blob(PROF, glasses=True, mode="speaking").to_corner(DL)
        bubble = SpeechBubble(4.4, 2.2, center=prof.get_top() + UP * 1.7 + RIGHT * 2.8,
                              tip=prof.get_top() + RIGHT * 0.7)
        bubble.add(bubble.place_inside(MathTex(r"\sin(\theta) \approx 0.7\text{-ish}")))

        with self.say("Then physics comes along. Velocities split into sine and cosine parts,"):
            self.play(Write(title), run_time=0.6)
            self.play(MoveAlongPath(dot, parabola.copy()), Create(parabola),
                      run_time=3, rate_func=linear)
            self.at(4.0)
            for m in (v, vx, vy):
                self.play(GrowArrow(m), run_time=0.6)
            self.play(Create(arc), Write(theta), run_time=0.8)
            for lbl in (v_lbl, vx_lbl, vy_lbl):
                self.play(Write(lbl), run_time=0.6)
        with self.say("and your classmates estimate these values instantly. You'd decide they "
                      "must be human calculators, and feel slow for needing to add up a "
                      "series every time."):
            self.at(9.1)
            self.play(FadeIn(prof), Create(bubble), run_time=1.5)
        self.at(22.1)
        fade_all(self, 0.5)


# ── 14–16: the core intuitions ──────────────────────────────────────────

INTUITION_BOX = ("rect", RIGHT * 1.6 + DOWN * 0.8, 8.2, 4.7)  # top clears the 2-line caption


def big_arrow():
    return Arrow(LEFT, RIGHT, color=YELLOW, stroke_width=8, buff=0).scale(0.6)


class S14_LinearAlgebraIntuitions(EolaScene):
    TARGET = 28.5

    def construct(self):
        title = Tex("Preview of core visual intuitions").to_edge(UP)
        hline = Line(LEFT * FW / 2, RIGHT * FW / 2, color=BLUE_E).next_to(title, DOWN)
        lines = [
            "A matrix is a transformation of space (more in chapter 3)",
            "Multiplying matrices means doing one transformation, \\\\ then another (more in chapter 4)",
            "The determinant tells you how much areas get scaled \\\\ (more in chapter 5)",
        ]
        texts = [Tex(s).scale(0.7).next_to(hline, DOWN) for s in lines]
        box_left = INTUITION_BOX[1][0] - INTUITION_BOX[2] / 2

        def left_of_box(m):
            arr = big_arrow().next_to(box_left * RIGHT + INTUITION_BOX[1][1] * UP, LEFT, buff=0.15)
            room = arr.get_left()[0] - 0.15 - (-SAFE_X)
            if m.width > room:
                m.scale_to_fit_width(room)
            m.next_to(arr, LEFT, buff=0.15)
            return arr

        with self.say("Linear algebra is a lot like that, except the fix is easy. A handful "
                      "of visual ideas sit under the whole subject."):
            self.at(0.7)
            self.play(Write(title), Create(hline), run_time=2)

        # 1. matrices transform space
        m1 = bmatrix([[1, -1], [1, 2]]).scale(1.3)
        a1 = left_of_box(m1)
        g1 = ClippedGrid(INTUITION_BOX, unit=0.6, matrix_of=lerp_matrix([[1, -1], [1, 2]]))
        with self.say("A matrix moves space around."):
            self.at(3.9)  # reference starts this transform at ~5.4 s (checked over 3 frames)
            self.play(FadeIn(texts[0]), Write(m1), run_time=0.8)
            self.play(GrowArrow(a1), FadeIn(g1.mobject), run_time=0.6)
            self.play(g1.tracker.animate.set_value(1), run_time=2)
        self.at(10.5)
        self.play(FadeOut(VGroup(texts[0], m1, a1, g1.mobject)), run_time=0.6)

        # 2. multiplication = composition
        m_first = bmatrix([[1, -1], [1, 2]], color=BLUE).scale(1.1)
        m_second = bmatrix([[1, 2], [2, 1]], color=GREEN).scale(1.1)
        pair = VGroup(m_second, m_first).arrange(RIGHT, buff=0.1)
        a2 = left_of_box(pair)
        b1 = Brace(m_first, UP)
        b2 = Brace(m_second, DOWN)
        l1 = Tex("Apply first").scale(0.6).next_to(b1, UP, buff=0.1)
        l2 = Tex("Apply second").scale(0.6).next_to(b2, DOWN, buff=0.1)
        g2 = ClippedGrid(INTUITION_BOX, unit=0.6, matrix_of=chain_matrices([[1, -1], [1, 2]],
                                                                          [[1, 2], [2, 1]]))
        with self.say("Multiplying matrices means doing one move after another."):
            self.at(11.7)
            self.play(FadeIn(texts[1]), Write(m_first), GrowArrow(a2),
                      GrowFromCenter(b1), Write(l1), FadeIn(g2.mobject), run_time=1)
            self.play(g2.tracker.animate.set_value(0.5), run_time=2)
            self.play(Write(m_second), GrowFromCenter(b2), Write(l2), run_time=1)
            self.play(g2.tracker.animate.set_value(1), run_time=2)
        self.at(18.4)
        self.play(FadeOut(VGroup(texts[1], pair, a2, b1, b2, l1, l2, g2.mobject)), run_time=0.6)

        # 3. determinant = area scaling
        det = MathTex(r"\text{Det}\left(\begin{bmatrix} 1 & -1 \\ 1 & 2 \end{bmatrix}\right)").scale(1.2)
        a3 = left_of_box(det)
        g3 = ClippedGrid(INTUITION_BOX, unit=0.6, matrix_of=lerp_matrix([[1, -1], [1, 2]]),
                         square=True, show_basis=False)
        with self.say("The determinant measures how much areas stretch. Once these click, the "
                      "formulas start explaining themselves."):
            self.at(19.2)
            self.play(FadeIn(texts[2]), Write(det), GrowArrow(a3), FadeIn(g3.mobject), run_time=1)
            self.play(g3.tracker.animate.set_value(1), run_time=2)
        self.at(27.2)
        self.play(FadeOut(VGroup(texts[2], det, a3, g3.mobject)), run_time=0.7)
        self.at(28.0)
        fade_all(self, 0.5)


class S15_ProfessorsTry(EolaScene):
    TARGET = 6.8

    def construct(self):
        prof = get_prof(mode="speaking")
        student = get_student().scale(0.8).to_corner(DL)
        speech = SpeechBubble(7.4, 2.6, center=LEFT * 2.8 + UP * 2.0, tip=prof.get_top() + LEFT * 0.4)
        speech.add(speech.place_inside(Tex(r"Isn't it gorgeous? Let me show \\ you how I picture it\dots")))
        cloud = ThoughtCloud(4.0, 2.8, tail_to=DOWN * 1.7 + LEFT * 0.6).move_to(RIGHT * 4.3 + UP * 1.9)
        c, a, b = cloud.clip
        grid = ClippedGrid(("ellipse", c, a, b), unit=0.4, matrix_of=lerp_matrix([[1, -1], [1, 2]]),
                           square=True, show_basis=False, bg_grid=False)
        self.add(student, prof)
        with self.say("To be fair, good teachers do try to share this picture."):
            self.play(FadeIn(speech), run_time=1)
            self.play(blink(student))
            self.play(FadeIn(cloud), FadeIn(grid.mobject), run_time=0.6)
            self.play(grid.tracker.animate.set_value(1), blink(prof), run_time=1.5)
        self.at(6.3)
        fade_all(self, 0.5)


class S16_ExampleMatrixMultiplication(EolaScene):
    TARGET = 14.1

    def construct(self):
        L = Matrix([[-3, 1], [2, 5]])
        R = Matrix([[5, 3], [7, -3]])
        eq = MathTex("=")
        result_full = Matrix([["(-3)(5)+(1)(7)", "(-3)(3)+(1)(-3)"],
                              ["(2)(5)+(5)(7)", "(2)(3)+(5)(-3)"]], h_buff=5.6)
        row = VGroup(L, R, eq, result_full).arrange(RIGHT, buff=0.2).scale_to_fit_width(FW - 1)
        row.center().shift(UP * 0.6)
        brackets = result_full.get_brackets()
        Le, Re = L.get_entries(), R.get_entries()
        self.add(L, R, eq, brackets)

        def terms(i, j):
            a, b = [[-3, 1], [2, 5]][i], [[5, 3], [7, -3]]
            parts = [f"({a[0]})({b[0][j]})", f"+({a[1]})({b[1][j]})"]
            m = MathTex(*parts).match_height(result_full.get_entries()[0])
            m.move_to(result_full.get_entries()[2 * i + j])
            return m

        with self.say("Yet courses spend most of their time on hand calculation, which "
                      "computers now do for us. Our job is the concepts."):
            t = 0.6
            for i in range(2):
                for j in range(2):
                    m = terms(i, j)
                    for k in range(2):
                        self.at(t)
                        l_ent, r_ent = Le[2 * i + k], Re[2 * k + j]
                        circles = VGroup(*[Circle(color=YELLOW).surround(e, buffer_factor=1.4)
                                           for e in (l_ent, r_ent)])
                        self.play(Create(circles), l_ent.animate.set_color(YELLOW),
                                  r_ent.animate.set_color(YELLOW), run_time=0.35)
                        self.play(Write(m[k].set_color(YELLOW)), run_time=0.5)
                        self.play(FadeOut(circles), l_ent.animate.set_color(WHITE),
                                  r_ent.animate.set_color(WHITE), m[k].animate.set_color(WHITE),
                                  run_time=0.35)
                        t += 1.55
        self.at(13.6)
        fade_all(self, 0.5)


# ── 17–18: the series ───────────────────────────────────────────────────

CHAPTERS = [
    "Chapter 1: Vectors, what even are they?",
    "Chapter 2: Linear combinations, span and bases",
    "Chapter 3: Matrices as linear transformations",
    "Chapter 4: Matrix multiplication as composition",
    "Chapter 5: The determinant",
    "Chapter 6: Inverse matrices, column space and null space",
    "Chapter 7: Dot products and cross products",
    "Chapter 8: Change of basis",
    "Chapter 9: Eigenvectors and eigenvalues",
    "Chapter 10: Abstract vector spaces",
]


def get_chapters():
    title = Tex("Essence of Linear Algebra", color=BLUE).to_corner(UL)
    hline = Line(LEFT * FW / 2, RIGHT * FW / 2).next_to(title, DOWN).set_x(0)
    chapters = VGroup(*[Tex(c) for c in CHAPTERS]).arrange(DOWN).scale(0.7).next_to(hline, DOWN)
    for c in chapters:
        c.to_edge(LEFT, buff=1)
    return title, hline, chapters


def get_icons():
    colors = color_gradient([BLUE_A, BLUE_D], 10)
    # 10 icons must fit inside the safe area (|x| <= 6.5)
    return VGroup(*[video_icon(c, width=FW / 13) for c in colors]).arrange(RIGHT, buff=0.15).shift(UP)


class S17_TableOfContents(EolaScene):
    TARGET = 20.4

    def construct(self):
        title, hline, chapters = get_chapters()
        note = Tex(r"(The one I'm most \\ looking forward to)", color=YELLOW).scale(0.5)
        note.next_to(hline, DOWN).to_edge(RIGHT)
        arrow = Arrow(note.get_bottom(), chapters[2].get_right(), color=YELLOW)
        with self.say("So here's the plan: a short series you can watch in one sitting, from "
                      "vectors all the way to eigenvalues and abstract vector spaces."):
            self.at(0.6)
            self.play(Write(title), Create(hline), run_time=1.2)
            self.at(2.8)
            for ch in chapters:
                self.play(FadeIn(ch), run_time=1)
        with self.say("Chapter three is the one to look forward to."):
            self.at(12.6)  # reference: note fully in by ~13.4 s (checked over 3 frames)
            self.play(chapters[2].animate.set_color(YELLOW), Create(arrow), Write(note), run_time=0.8)
        self.at(19.4)
        self.play(FadeOut(VGroup(note, arrow, hline, title)), run_time=0.8)


class S18_SeriesIntoBubble(EolaScene):
    TARGET = 14.6

    def construct(self):
        _, _, chapters = get_chapters()
        chapters[2].set_color(YELLOW)
        self.add(chapters)
        icons = get_icons()
        student = get_student()
        cloud = thought_cloud_for(student, width=6.2, height=3.2)
        small = icons.copy().scale(0.2)
        cloud.place_inside(small)
        c, a, b = cloud.clip
        angle = ValueTracker(0.4)
        grid3d = always_redraw(lambda: lattice_3d(c, a, b, angle.get_value()))

        with self.say("Videos alone won't teach you the subject. What they can do is give you "
                      "the right pictures, so the practice you do afterwards actually sticks."):
            self.play(Transform(chapters, icons, path_arc=PI / 2), run_time=1)
            self.remove(chapters)
            self.add(icons)
            self.play(FadeIn(student), run_time=0.8)
            self.play(blink(student))
            self.at(3.2)
            self.add(cloud)
            self.bring_to_front(icons)
            self.play(Create(cloud), Transform(icons, small), run_time=1)
            self.play(FadeOut(icons), FadeIn(grid3d), run_time=0.6)
            self.play(angle.animate.set_value(0.4 + 1.6), run_time=8.5, rate_func=linear)
        self.at(14.1)
        fade_all(self, 0.5)


def lattice_3d(c, a, b, theta, n=3, unit=0.5):
    """Colourful 3D cube lattice, rotated about y by theta, projected, clipped."""
    rot = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
    tilt = np.array([[1, 0, 0], [0, np.cos(0.45), -np.sin(0.45)], [0, np.sin(0.45), np.cos(0.45)]])
    R = tilt @ rot
    g = VGroup()
    rng = range(-n, n + 1)
    for axis in range(3):
        for i in rng:
            for j in rng:
                p = np.zeros(3)
                q = np.zeros(3)
                others = [k for k in range(3) if k != axis]
                p[others[0]] = q[others[0]] = i
                p[others[1]] = q[others[1]] = j
                p[axis], q[axis] = -n, n
                P = c + unit * (R @ p) * np.array([1, 1, 0])
                Q = c + unit * (R @ q) * np.array([1, 1, 0])
                seg = clip_ellipse(P, Q, c, a, b)
                if seg is None:
                    continue
                hue = (i + j + 2 * n) / (4 * n)
                col = interpolate_color(ManimColor("#3fd7c5"), ManimColor("#d65fdc"), hue)
                if axis == 1:
                    col = interpolate_color(col, YELLOW, 0.4)
                g.add(Line(*seg, stroke_width=1.5, color=col, stroke_opacity=0.8))
    for vec, col in (((1, 0, 0), RED), ((0, 1, 0), GREEN), ((0, 0, 1), BLUE)):
        end = c + unit * (R @ np.array(vec, dtype=float)) * np.array([1, 1, 0])
        g.add(Arrow(c, end, buff=0, color=col, stroke_width=3, tip_length=0.12))
    return g


# ── 19–23: who it's for; pacing; next video ─────────────────────────────

def get_three_students():
    s = VGroup(*[Blob(col) for col in (STUDENT, STUDENT_2, STUDENT_3)])
    return s.arrange(RIGHT).scale(0.8)


class S19_ResourceForTeachers(EolaScene):
    TARGET = 8.6

    def construct(self):
        prof = Blob(PROF, glasses=True, mode="speaking").to_corner(DR)
        students = get_three_students().to_corner(DL)
        speech = SpeechBubble(6.2, 2.4, center=UP * 1.5 + LEFT * 0.6, tip=prof.get_top() + LEFT * 0.5)
        words = Tex(r"I'll assume you've all \\ seen this before\dots")
        speech.place_inside(words)
        self.add(students, prof)
        with self.say("Teachers can point students here for a quick visual refresher."):
            self.play(FadeIn(speech), Write(words), run_time=3)
            for k in (2, 0, 1):
                self.play(blink(students[k]))
        self.at(8.1)
        fade_all(self, 0.5)


class S20_AboutPacing(EolaScene):
    TARGET = 2.5

    def construct(self):
        words = Tex("About pacing", r"\dots")
        with self.say("A word on pacing."):
            self.play(FadeIn(words[0]), run_time=0.6)
            self.play(Write(words[1]), run_time=0.6)
        self.at(2.1)
        fade_all(self, 0.4)


class S21_DifferingBackgrounds(EolaScene):
    TARGET = 10.0

    def construct(self):
        students = get_three_students().center().to_edge(DOWN)
        labels = [Tex(s).shift(2 * UP) for s in
                  ("Reviewing", "Hasn't taken it yet", "Taking the course right now")]
        modes = ["happy", "speaking", "confused"]
        self.add(students)
        word = arrow = None
        with self.say("Some of you are reviewing, some haven't started, and some are taking "
                      "the course right now. One speed won't suit everyone."):
            for k, (lbl, st, mode) in enumerate(zip(labels, students, modes)):
                self.at(0.3 + 3.2 * k)
                new_arrow = Arrow(lbl.get_bottom(), st.get_top(), color=YELLOW)
                if word is None:
                    word, arrow = lbl, new_arrow
                    self.play(Write(word), Create(arrow), st.animate.set_mode(mode), run_time=1)
                else:
                    self.play(Transform(word, lbl), Transform(arrow, new_arrow),
                              st.animate.set_mode(mode), run_time=1)
                self.play(blink(st))
        self.at(9.6)
        fade_all(self, 0.4)


class S22_PauseAndPonder(EolaScene):
    TARGET = 9.7

    def construct(self):
        bars = VGroup(*[Rectangle(width=0.18, height=1.5, stroke_width=0, fill_color=WHITE,
                                  fill_opacity=1) for _ in range(2)]).arrange(RIGHT, buff=0.35)
        bars.shift(LEFT)
        cloud = ThoughtCloud(2.6, 1.4, tail_to=DOWN * 0.9 + LEFT * 1.0)
        cloud.next_to(bars, RIGHT, buff=0.6)
        with self.say("So pause whenever you need to. Thinking it through on your own is where "
                      "the learning happens."):
            self.at(0.4)
            self.play(FadeIn(bars), run_time=1)
            self.play(Create(cloud), run_time=1)
        self.at(9.3)
        fade_all(self, 0.4)


class S23_NextVideo(EolaScene):
    TARGET = 16.8

    def construct(self):
        title = Tex("Next video: Vectors, what even are they?").to_edge(UP)
        rect = Rectangle(width=16, height=9, color=BLUE).scale_to_fit_height(6).next_to(title, DOWN)
        grid = ClippedGrid(("rect", rect.get_center(), rect.width, rect.height), unit=0.5,
                           extent=14, show_basis=False, bg_grid=False, stroke=1.5)
        o = grid.center
        v_end = grid.to_screen(np.eye(2), (1, 3))
        w_end = grid.to_screen(np.eye(2), (4, -1.5))
        v = Arrow(o, v_end, buff=0, color=YELLOW)
        w = Arrow(o, w_end, buff=0, color=PINK)
        w_moved = Arrow(v_end, v_end + (w_end - o), buff=0, color=PINK)
        s = Arrow(o, v_end + (w_end - o), buff=0, color=PURPLE_A)
        lv = MathTex(r"\vec{v}", color=YELLOW).scale(0.6).next_to(v.get_center(), LEFT, buff=0.1)
        lw = MathTex(r"\vec{w}", color=PINK).scale(0.6).next_to(w.get_center(), UP, buff=0.1)
        ls = MathTex(r"\vec{v}+\vec{w}").scale(0.6).next_to(s.get_center(), DOWN, buff=0.1)
        walker = Blob(PINK, height=0.8).move_to(o + UP * 0.4)

        self.add(title)
        with self.say("Next up: vectors, and what they really are. See you there."):
            self.play(Create(rect), run_time=1)
            self.play(FadeIn(grid.mobject), run_time=0.5)
            self.play(GrowArrow(v), Write(lv), run_time=0.8)
            self.play(GrowArrow(w), Write(lw), run_time=0.8)
        self.at(6.3)
        self.play(FadeIn(walker), run_time=0.5)
        self.play(walker.animate.move_to(v_end + UP * 0.4), run_time=1.5)
        self.play(Transform(w, w_moved), lw.animate.next_to(w_moved.get_center(), UP, buff=0.1),
                  run_time=1)
        self.play(walker.animate.move_to(w_moved.get_end() + UP * 0.4), run_time=1.5)
        self.play(GrowArrow(s), Write(ls), run_time=1)
        self.at(16.3)
        fade_all(self, 0.5)


SCENES = [
    "S01_TitleCard", "S02_OpeningQuote", "S03_UpcomingSeries", "S04_AboutLinearAlgebra",
    "S05_TopicsBubble", "S06_NumericVsGeometric", "S07_GeometricHelpful",
    "S08_NumericToComputations", "S09_LinAlgPyramid", "S10_IntimidatingProf",
    "S11_SineApproximations", "S12_LooseConnectionToTriangles", "S13_PhysicsExample",
    "S14_LinearAlgebraIntuitions", "S15_ProfessorsTry", "S16_ExampleMatrixMultiplication",
    "S17_TableOfContents", "S18_SeriesIntoBubble", "S19_ResourceForTeachers",
    "S20_AboutPacing", "S21_DifferingBackgrounds", "S22_PauseAndPonder", "S23_NextVideo",
]
