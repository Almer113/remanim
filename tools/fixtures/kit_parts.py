"""Smoke test for manim_kit building blocks (not content).

Parts: every component in one frame. KitTiming: a narrated TimedScene with
at() marks and a TARGET, to check that narration doesn't delay visuals.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from manim_kit import *  # noqa: E402


class Parts(Scene):
    def construct(self):
        student = Blob(BLUE_D).to_corner(DL)
        prof = Blob(GREY_BROWN, glasses=True, mode="speaking").to_corner(DR).shift(LEFT * 2)
        confused = Blob(BLUE_C, mode="confused", height=1.6).next_to(student, RIGHT)
        cloud = thought_cloud_for(student, width=5, height=2.6)
        grid = ClippedGrid(("ellipse",) + tuple(cloud.clip), unit=0.35,
                           matrix_of=lerp_matrix([[0, 1], [-1, 1]]), vectors=[((1, 2), YELLOW)])
        grid.tracker.set_value(0.6)
        box = ClippedGrid(("rect", RIGHT * 3.5 + UP * 2.3, 6, 3), unit=0.45,
                          matrix_of=chain_matrices([[1, -1], [1, 2]], [[1, 2], [2, 1]]), square=True)
        box.tracker.set_value(1)
        sb = SpeechBubble(4.5, 1.8, center=prof.get_center() + UP * 2.6 + LEFT * 1.5,
                          tip=prof.get_top() + LEFT * 0.2)
        sb.add(sb.place_inside(Tex("Speech text")))
        self.add(cloud, grid.mobject, box.mobject, student, prof, confused, sb,
                 video_icon().to_edge(LEFT).shift(UP * 3))
        self.wait(0.1)


class KitTiming(TimedScene):
    TARGET = 7.5

    def construct(self):
        blob = Blob(BLUE_D).shift(LEFT * 3)
        dot = Dot(RIGHT * 2)
        with self.say("Testing the timeline: this line is long enough to run past two seconds."):
            self.play(FadeIn(blob), run_time=0.5)
        self.at(2.0)  # must land at 2.0 s even though the voice is still speaking
        self.play(FadeIn(dot), blink(blob), run_time=0.5)
        with self.say("Second line."):  # waits for the first line on the audio track only
            self.play(dot.animate.shift(UP), run_time=0.5)


class GridFade(Scene):
    """A ClippedGrid faded in and out while it turns and shears (it keeps
    the same part count, so the fades don't crash)."""

    def construct(self):
        spin = ClippedGrid(("ellipse", ORIGIN, 3, 2), unit=0.35, bg_grid=False,
                           matrix_of=lambda t: rotation(TAU * t) @ np.array([[1, 1], [0, 1]], dtype=float))
        squash = ClippedGrid(("rect", RIGHT * 4, 3, 3), unit=0.4,
                             matrix_of=lerp_matrix([[1, 0], [0, 0]]))
        for g in (spin, squash):
            seen = set()
            for v in np.linspace(0, 1, 61):
                g.tracker.set_value(v)
                seen.add(len(g._draw().family_members_with_points()))
            g.tracker.set_value(0)
            assert len(seen) == 1, f"part count changes with the tracker: {sorted(seen)}"
        # shift / move_to move the frame and the drawn grid together, at once
        c0 = squash.mobject.get_center()
        squash.shift(0.5 * UP)
        assert np.allclose(squash.mobject.get_center(), c0 + 0.5 * UP), "shift didn't move the grid"
        squash.move_to(RIGHT * 4)
        assert np.allclose(squash.mobject.get_center(), c0), "move_to didn't put it back"
        spin.tracker.add_updater(lambda m, dt: m.increment_value(dt / 3))
        self.add(spin.tracker)
        self.play(FadeIn(spin.mobject), FadeIn(squash.mobject), run_time=1)
        self.play(squash.tracker.animate.set_value(1), run_time=1)
        self.play(FadeOut(spin.mobject), FadeOut(squash.mobject), run_time=1)
