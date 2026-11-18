"""The Pythagorean theorem — short explainer. Plan: plans/pythagoras.md

Beats: Intro, Squares, Proof, Example, Outro (render in that order).
Narrated with manim-voiceover + Edge TTS; on-screen captions follow the voice.
"""

from contextlib import contextmanager

from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.helper import remove_bookmarks

from edge_tts_service import EdgeTTSService
from style import *

# ── Constants ────────────────────────────────────────────────────────────
VOICE, VOICE_RATE = "en-US-AndrewNeural", "-5%"
READ_CPS = 15      # comfortable caption reading speed, characters per second
READ_PAD = 0.3     # extra seconds on screen per caption
MAX_CAPTION = 70   # characters; longer captions wrap or shrink
A, B = 1.5, 2.0              # legs of the drawn triangle (3-4-5 shape)
C = (A**2 + B**2) ** 0.5     # 2.5
COL_A, COL_B, COL_C = ACCENT, ACCENT_2, GOOD
TRI_FILL = MUTED
SIDE_WIDTH = 6


# ── Builders ─────────────────────────────────────────────────────────────

def pt(x, y):
    return np.array([x, y, 0.0])


def get_caption(text: str) -> Text:
    return place(Text(text, font_size=CAPTION_SIZE, color=FG), "footer")


def get_formula(font_size=72) -> MathTex:
    eq = MathTex("a^2", "+", "b^2", "=", "c^2", font_size=font_size, color=FG)
    eq[0].set_color(COL_A)
    eq[2].set_color(COL_B)
    eq[4].set_color(COL_C)
    return eq


def get_triangle_figure(a=A, b=B, k=1.0, labels=True) -> VGroup:
    """Right angle at the origin; leg b along +x, leg a along +y.

    Returns VGroup(fill, side_a, side_b, side_c, right_angle, [lbl_a, lbl_b, lbl_c]).
    """
    p0, p1, p2 = pt(0, 0), pt(b * k, 0), pt(0, a * k)
    fill = Polygon(p0, p1, p2, stroke_width=0, fill_color=TRI_FILL, fill_opacity=0.35)
    side_a = Line(p0, p2, color=COL_A, stroke_width=SIDE_WIDTH)
    side_b = Line(p0, p1, color=COL_B, stroke_width=SIDE_WIDTH)
    side_c = Line(p1, p2, color=COL_C, stroke_width=SIDE_WIDTH)
    mark = RightAngle(side_b, side_a, length=0.25 * k ** 0.5, color=FG, stroke_width=3)
    fig = VGroup(fill, side_a, side_b, side_c, mark)
    if labels:
        normal = np.array([a, b, 0]) / (a**2 + b**2) ** 0.5
        fs = TITLE_SIZE
        lbl_a = MathTex("a", color=COL_A, font_size=fs).next_to(side_a, LEFT, buff=0.2)
        lbl_b = MathTex("b", color=COL_B, font_size=fs).next_to(side_b, DOWN, buff=0.2)
        lbl_c = MathTex("c", color=COL_C, font_size=fs).move_to(
            side_c.get_center() + normal * 0.45)
        fig.add(lbl_a, lbl_b, lbl_c)
    return fig


def get_side_squares(a=A, b=B, k=1.0, opacity=0.3) -> VGroup:
    """Squares on legs a (left), b (below) and hypotenuse c (outward)."""
    ak, bk = a * k, b * k
    sq_a = Polygon(pt(0, 0), pt(0, ak), pt(-ak, ak), pt(-ak, 0))
    sq_b = Polygon(pt(0, 0), pt(0, -bk), pt(bk, -bk), pt(bk, 0))
    out = pt(ak, bk)  # hypotenuse rotated 90°: same length as c
    sq_c = Polygon(pt(bk, 0), pt(bk, 0) + out, pt(0, ak) + out, pt(0, ak))
    for sq, col in ((sq_a, COL_A), (sq_b, COL_B), (sq_c, COL_C)):
        sq.set_stroke(col, 3).set_fill(col, opacity)
    return VGroup(sq_a, sq_b, sq_c)


def get_square_labels(squares: VGroup, texs=("a^2", "b^2", "c^2"), font_size=BODY_SIZE) -> VGroup:
    cols = (COL_A, COL_B, COL_C)
    return VGroup(*[
        MathTex(t, color=c, font_size=font_size).move_to(sq.get_center())
        for t, c, sq in zip(texs, cols, squares)
    ])


def get_grid(square: Polygon, n: int, color) -> VGroup:
    """n x n grid lines inside a (possibly tilted) square polygon."""
    v = square.get_vertices()
    o, u, w = v[0], v[1] - v[0], v[3] - v[0]
    lines = VGroup()
    for i in range(1, n):
        lines.add(Line(o + u * i / n, o + u * i / n + w, stroke_width=1.5, color=color))
        lines.add(Line(o + w * i / n, o + w * i / n + u, stroke_width=1.5, color=color))
    return lines


# Proof square: side L = a + b, bottom-left corner at the origin.
L = A + B
ARR1 = [  # four triangles around a tilted c-square
    [pt(0, 0), pt(B, 0), pt(0, A)],
    [pt(B, 0), pt(L, 0), pt(L, B)],
    [pt(L, B), pt(L, L), pt(A, L)],
    [pt(A, L), pt(0, L), pt(0, A)],
]
# Arrangement 2 is a pure translation of each triangle (see plan).
ARR2_SHIFTS = [pt(A, 0), pt(-B, A), pt(0, -B), pt(0, 0)]


def get_proof_square(side=3.6) -> tuple[VGroup, Square, VGroup]:
    """(group, outline, triangles), bottom-left corner at the origin, scaled to `side`."""
    k = side / L
    outline = Square(side, color=FG, stroke_width=3).move_to(pt(side / 2, side / 2))
    tris = VGroup(*[
        Polygon(*[p * k for p in pts], color=FG, stroke_width=2,
                fill_color=TRI_FILL, fill_opacity=0.55)
        for pts in ARR1
    ])
    return VGroup(outline, tris), outline, tris


def get_bottom_braces(origin, k, parts) -> VGroup:
    """Braces under the bottom edge. parts = [(length, tex, colour), ...]."""
    group, x = VGroup(), 0.0
    for length, tex, col in parts:
        seg = Line(origin + pt(x * k, 0), origin + pt((x + length) * k, 0))
        brace = Brace(seg, DOWN, buff=0.08, color=col)
        lbl = MathTex(tex, color=col, font_size=CAPTION_SIZE + 4).next_to(brace, DOWN, buff=0.08)
        group.add(VGroup(brace, lbl))
        x += length
    return group


# ── Beats ────────────────────────────────────────────────────────────────

class Beat(VoiceoverScene):
    def setup(self):
        self.camera.background_color = BG
        self.set_speech_service(EdgeTTSService(voice=VOICE, rate=VOICE_RATE))
        self.caption = None

    @contextmanager
    def say(self, spoken: str, caption: str | None = None):
        """Speak `spoken` while showing `caption` (defaults to the spoken text).

        Captions cut in hard (like film subtitles) as the line starts, and stay
        on screen at least len/READ_CPS + READ_PAD seconds.
        """
        text = caption or remove_bookmarks(spoken)
        if len(text) > MAX_CAPTION:
            logger.warning(f"Caption over {MAX_CAPTION} chars: {text!r}")
        if self.caption is not None:
            self.remove(self.caption)
        self.caption = get_caption(text)
        self.add(self.caption)
        start = self.renderer.time
        with self.voiceover(text=spoken, subcaption=text) as tracker:
            yield tracker
        self.safe_wait(start + len(text) / READ_CPS + READ_PAD - self.renderer.time)

    def clear_caption(self):
        if self.caption is not None:
            self.remove(self.caption)
            self.caption = None


def get_intro_triangle() -> VGroup:
    fig = get_triangle_figure(k=1.6)
    return place(fig, "main", fit=False)


def get_title() -> Text:
    return place(Text("The Pythagorean theorem", font_size=TITLE_SIZE, color=FG), "title")


class Intro(Beat):
    def construct(self):
        title = get_title()
        fig = get_intro_triangle()
        fill, side_a, side_b, side_c, mark, lbl_a, lbl_b, lbl_c = fig

        with self.say("Here's one of the most famous facts in all of mathematics."):
            self.play(Write(title), run_time=1.5)
        with self.say("Take any right triangle: a triangle with one "
                      "<bookmark mark='r'/>ninety-degree corner.",
                      caption="Take any right triangle: a triangle with one 90° corner."):
            self.play(FadeIn(fill), Create(side_b), Create(side_a), Create(side_c), run_time=1.6)
            self.wait_until_bookmark("r")
            self.play(Create(mark), run_time=0.6)
        with self.say("Its two shorter sides are called the legs, "
                      "<bookmark mark='a'/>A and <bookmark mark='b'/>B.",
                      caption="Its two shorter sides are called the legs, a and b."):
            self.wait_until_bookmark("a")
            self.play(Write(lbl_a), Indicate(side_a, color=COL_A), run_time=0.7)
            self.wait_until_bookmark("b")
            self.play(Write(lbl_b), Indicate(side_b, color=COL_B), run_time=0.7)
        with self.say("The longest side, across from the right angle, is the "
                      "<bookmark mark='c'/>hypotenuse, C.",
                      caption="The longest side, across from the right angle, is the hypotenuse, c."):
            self.wait_until_bookmark("c")
            self.play(Write(lbl_c), Indicate(side_c, color=COL_C), run_time=0.8)
        self.wait(0.4)


class Squares(Beat):
    def construct(self):
        title = get_title()
        start = get_intro_triangle()
        self.add(title, start)

        # Final layout: triangle + squares on the left, formula on the right.
        tri = get_triangle_figure(k=1.0)
        squares = get_side_squares(k=1.0)
        sq_labels = get_square_labels(squares, font_size=TITLE_SIZE + 6)
        full = VGroup(tri, squares, sq_labels)
        place(full, "left")
        # Split the figure so each side label is its own top-level object;
        # otherwise ReplacementTransform leaves a ghost copy inside `tri`.
        tri_bare = VGroup(*tri[:5])
        side_lbls = list(tri[5:])

        with self.say("Now, build a square on each side of the triangle."):
            self.play(FadeOut(title), ReplacementTransform(start, tri), run_time=1.5)
            self.remove(tri)
            self.add(tri_bare, *side_lbls)
        with self.say("One on <bookmark mark='a'/>A, one on <bookmark mark='b'/>B, "
                      "and one on <bookmark mark='c'/>C.",
                      caption="One on a, one on b, and one on c."):
            for i, mark in enumerate("abc"):
                self.wait_until_bookmark(mark)
                self.play(FadeIn(squares[i], scale=0.6),
                          ReplacementTransform(side_lbls[i], sq_labels[i]), run_time=0.7)
                self.bring_to_front(tri_bare)

        eq = place(get_formula(), "right")
        with self.say("The theorem says the two smaller squares, together,"):
            self.play(TransformFromCopy(sq_labels[0], eq[0]),
                      TransformFromCopy(sq_labels[1], eq[2]),
                      FadeIn(eq[1]), run_time=1.5)
        with self.say("have exactly the same area as the big one."):
            self.play(FadeIn(eq[3]), TransformFromCopy(sq_labels[2], eq[4]), run_time=1.2)
        with self.say("In symbols: A squared plus B squared equals C squared.",
                      caption="In symbols: a² + b² = c²"):
            self.play(Circumscribe(eq, color=FG, buff=0.15), run_time=1.5)
        with self.say("But why should that be true?"):
            pass
        self.wait(0.4)


class Proof(Beat):
    SIDE = 3.6
    LEFT_ORIGIN = pt(-5.0, -1.9)
    RIGHT_ORIGIN = pt(1.4, -1.9)

    def construct(self):
        k = self.SIDE / L
        left, outline_l, tris_l = get_proof_square(self.SIDE)
        left.shift(self.LEFT_ORIGIN)
        braces_l = get_bottom_braces(self.LEFT_ORIGIN, k, [(B, "b", COL_B), (A, "a", COL_A)])
        gap = Polygon(*[self.LEFT_ORIGIN + p * k for p in
                        (pt(B, 0), pt(L, B), pt(A, L), pt(0, A))],
                      stroke_width=0, fill_color=COL_C, fill_opacity=0.45)
        c2 = MathTex("c^2", color=FG, font_size=BODY_SIZE + 6).move_to(gap)

        with self.say("Here's a beautiful way to see it."):
            self.play(Create(outline_l), run_time=1)
        with self.say("Take four copies of our triangle,"):
            self.play(LaggedStart(*[FadeIn(t, scale=0.8) for t in tris_l], lag_ratio=0.25),
                      run_time=1.6)
        with self.say("and fit them inside a square whose side is A plus B.",
                      caption="and fit them inside a square whose side is a + b."):
            self.play(FadeIn(braces_l), run_time=0.8)
        with self.say("The space left in the middle is a square with side C,",
                      caption="The space left in the middle is a square with side c,"):
            self.play(FadeIn(gap), run_time=1)
        with self.say("so its area is C squared.", caption="so its area is c²."):
            self.play(Write(c2), run_time=0.8)

        right, outline_r, tris_r = get_proof_square(self.SIDE)
        right.shift(self.RIGHT_ORIGIN)
        with self.say("Now take the same big square and the same four triangles,"):
            self.play(TransformFromCopy(left, right), run_time=1.5)
        with self.say("and slide the triangles into a new arrangement."):
            self.play(*[t.animate.shift(s * k) for t, s in zip(tris_r, ARR2_SHIFTS)],
                      run_time=2.2, rate_func=smooth)

        sq_a = Square(A * k, stroke_width=0, fill_color=COL_A, fill_opacity=0.45).move_to(
            self.RIGHT_ORIGIN + pt(A / 2, A / 2) * k)
        sq_b = Square(B * k, stroke_width=0, fill_color=COL_B, fill_opacity=0.45).move_to(
            self.RIGHT_ORIGIN + pt(A + B / 2, A + B / 2) * k)
        a2 = MathTex("a^2", color=FG, font_size=BODY_SIZE).move_to(sq_a)
        b2 = MathTex("b^2", color=FG, font_size=BODY_SIZE + 6).move_to(sq_b)
        braces_r = get_bottom_braces(self.RIGHT_ORIGIN, k, [(A, "a", COL_A), (B, "b", COL_B)])
        with self.say("This time, the empty space is two squares: "
                      "<bookmark mark='a'/>A squared, and <bookmark mark='b'/>B squared.",
                      caption="This time, the empty space is two squares: a² and b²."):
            self.wait_until_bookmark("a")
            self.play(FadeIn(sq_a), Write(a2), run_time=0.7)
            self.wait_until_bookmark("b")
            self.play(FadeIn(sq_b), Write(b2), FadeIn(braces_r), run_time=0.7)

        equals = MathTex("=", font_size=72, color=FG).move_to(
            (outline_l.get_right() + outline_r.get_left()) / 2)
        with self.say("Both pictures use the same square and the same four triangles,"):
            self.play(Write(equals), run_time=0.8)
        with self.say("so the empty space must be the same too."):
            pass

        eq = place(MathTex("c^2", "=", "a^2", "+", "b^2", font_size=60, color=FG), "title")
        eq[0].set_color(COL_C)
        eq[2].set_color(COL_A)
        eq[4].set_color(COL_B)
        with self.say("C squared equals A squared plus B squared.", caption="c² = a² + b²"):
            self.play(TransformFromCopy(c2, eq[0]), FadeIn(eq[1]),
                      TransformFromCopy(a2, eq[2]), FadeIn(eq[3]), TransformFromCopy(b2, eq[4]),
                      run_time=1.4)
            self.play(Circumscribe(eq, color=FG, buff=0.12), run_time=1.2)
        self.wait(0.6)


class Example(Beat):
    def construct(self):
        a, b, c = 3, 4, 5
        k = 0.42
        tri = get_triangle_figure(a, b, k, labels=False)
        squares = get_side_squares(a, b, k, opacity=0.2)
        grids = VGroup(*[get_grid(sq, n, sq.get_stroke_color())
                         for sq, n in zip(squares, (a, b, c))])
        fig = VGroup(squares, grids, tri)
        place(fig, "left")
        # Counts go on a dark backing so grid lines don't cut through them.
        counts = VGroup()
        for txt, col, sq in zip(("9", "16", "25"), (COL_A, COL_B, COL_C), squares):
            num = MathTex(txt, color=col, font_size=TITLE_SIZE).move_to(sq)
            counts.add(VGroup(BackgroundRectangle(num, color=BG, fill_opacity=0.85, buff=0.08), num))

        lines = VGroup(
            MathTex("3^2", "+", "4^2", "=", "c^2", font_size=60),
            MathTex("9", "+", "16", "=", "25", font_size=60),
            MathTex("c", "=", "5", font_size=60),
        ).arrange(DOWN, buff=0.6)
        lines[2][0].set_color(COL_C)
        lines[2][2].set_color(COL_C)
        for line in lines[:2]:
            line[0].set_color(COL_A)
            line[2].set_color(COL_B)
            line[4].set_color(COL_C)
        place(lines, "right")

        with self.say("Let's check it with real numbers: legs of three and four.",
                      caption="Let's check it with real numbers: legs of 3 and 4."):
            self.play(FadeIn(tri), run_time=0.8)
            self.play(FadeIn(squares), run_time=0.8)
        with self.say("Count the little squares: <bookmark mark='n'/>nine here, "
                      "<bookmark mark='s'/>sixteen here,",
                      caption="Count the little squares: 9 here, 16 here,"):
            self.play(LaggedStart(*[Create(g) for g in grids], lag_ratio=0.3), run_time=1.4)
            self.wait_until_bookmark("n")
            self.play(FadeIn(counts[0], scale=1.3), run_time=0.5)
            self.wait_until_bookmark("s")
            self.play(FadeIn(counts[1], scale=1.3), run_time=0.5)
        with self.say("and twenty-five on the hypotenuse.", caption="and 25 on the hypotenuse."):
            self.play(FadeIn(counts[2], scale=1.3), run_time=0.5)
        with self.say("Nine plus sixteen is twenty-five,", caption="9 + 16 = 25,"):
            self.play(Write(lines[0]), run_time=0.9)
            self.play(*[TransformFromCopy(cnt[1], lines[1][i]) for cnt, i in zip(counts, (0, 2, 4))],
                      FadeIn(lines[1][1]), FadeIn(lines[1][3]), run_time=1.1)
        with self.say("so the hypotenuse is exactly five.",
                      caption="so the hypotenuse is exactly 5."):
            self.play(Write(lines[2]), Indicate(tri[3], color=COL_C), run_time=1)
        self.wait(0.6)


class Outro(Beat):
    def construct(self):
        eq = place(get_formula(font_size=110), "main")
        tri = get_triangle_figure(k=0.55, labels=False).next_to(eq, UP, buff=0.6)
        with self.say("A squared plus B squared equals C squared.", caption="a² + b² = c²"):
            self.play(FadeIn(tri), Write(eq), run_time=1.4)
        with self.say("It's true for every right triangle, of any size or shape."):
            pass
        self.wait(0.8)
        self.clear_caption()
        self.play(FadeOut(eq), FadeOut(tri), run_time=0.8)


