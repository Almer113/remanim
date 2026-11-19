"""Phase 5 steps 9 and 10: camera edits."""

import ast

import pytest

from studio.server.code.camera import check, plan_camera_2d, plan_camera_3d
from studio.server.code.source import Source
from studio.server.code.splice import EditError, apply


def make(base, *lines):
    return (f"from manim import *\n\nclass S({base}):\n    def construct(self):\n"
            + "".join("        " + ln + "\n" for ln in lines))


def ev_for(code, needle, start, duration):
    src = Source(code.encode())
    c = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and src.text(n) == needle)
    return {"kind": "play", "call": [c.lineno, c.col_offset, c.end_lineno, c.end_col_offset],
            "call_line": c.lineno, "start": start, "duration": duration, "anims": []}


ZOOM = "self.play(self.camera.frame.animate.scale(0.5).move_to(RIGHT * 2), run_time=1)"


def test_2d_edits_the_last_move():
    code = make("MovingCameraScene", "self.add(Square())", ZOOM, "self.wait(1)")
    evs = [ev_for(code, ZOOM, 0.0, 1.0)]
    plan = plan_camera_2d(Source(code.encode()), "S", evs, 15, False, 1.5, [1.0, 0.5], 14.22, {"width": 7.11})
    out = apply(code.encode(), plan.edits).decode()
    assert "animate.scale(1.0).move_to(RIGHT + 0.5 * UP)" in out


def test_2d_refused_while_moving_and_when_following():
    code = make("MovingCameraScene", ZOOM)
    with pytest.raises(EditError, match="moving here"):
        plan_camera_2d(Source(code.encode()), "S", [ev_for(code, ZOOM, 0.0, 1.0)], 15, False, 0.5, [0, 0], None, {})
    follow = "self.play(self.camera.frame.animate.move_to(dot))"
    code = make("MovingCameraScene", "dot = Dot()", follow)
    with pytest.raises(EditError, match="follows dot"):
        plan_camera_2d(Source(code.encode()), "S", [ev_for(code, follow, 0.0, 1.0)], 15, False, 2, [0, 0], None, {})


def test_2d_inserts_a_move_when_there_is_none():
    code = make("MovingCameraScene", "self.add(Square())", "self.wait(2)")
    # at the first frame: the camera is placed, not moved
    plan = plan_camera_2d(Source(code.encode()), "S", [], 15, False, 0.0, [2.0, 0.0], 8.0, {"width": 14.22})
    out = apply(code.encode(), plan.edits).decode()
    assert "        self.camera.frame.move_to(2 * RIGHT).set(width=8)\n        self.add(Square())" in out
    # later: a one-second move is added there
    wait = {"kind": "wait", "call": None, "call_line": 6, "start": 0.0, "duration": 2.0}
    plan = plan_camera_2d(Source(code.encode()), "S", [wait], 15, False, 1.0, [2.0, 0.0], 8.0, {"width": 14.22})
    out = apply(code.encode(), plan.edits).decode()
    assert "self.play(self.camera.frame.animate.move_to(2 * RIGHT).set(width=8), run_time=1)" in out


def test_3d_edits_degrees_and_adds_missing():
    code = make("ThreeDScene", "self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES)",
                "self.add(Cube())", "self.wait(1)")
    wait = {"kind": "wait", "call_line": 7, "start": 0.0, "duration": 1.0}
    plan = plan_camera_3d(Source(code.encode()), "S", [wait], 0.5, {"phi": 60, "zoom": 1.2})
    out = apply(code.encode(), plan.edits).decode()
    assert "set_camera_orientation(phi=60 * DEGREES, theta=-45 * DEGREES, zoom=1.2)" in out


def test_3d_edits_the_move_camera_under_the_playhead():
    mc = "self.move_camera(theta=0 * DEGREES, run_time=1)"
    code = make("ThreeDScene", "self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES)", mc)
    ev = ev_for(code, mc, 0.0, 1.0)
    out = apply(code.encode(), plan_camera_3d(Source(code.encode()), "S", [ev], 0.5, {"theta": 30}).edits).decode()
    assert "self.move_camera(theta=30 * DEGREES, run_time=1)" in out


def test_3d_computed_angle_refused_and_none_added():
    code = make("ThreeDScene", "self.set_camera_orientation(phi=self.PHI)", "self.wait(1)")
    wait = {"kind": "wait", "call_line": 6, "start": 0.0, "duration": 1.0}
    with pytest.raises(EditError, match="computed"):
        plan_camera_3d(Source(code.encode()), "S", [wait], 0.5, {"phi": 60})
    code = make("ThreeDScene", "self.wait(1)")
    out = apply(code.encode(), plan_camera_3d(Source(code.encode()), "S", [], 0.0, {"phi": 75}).edits).decode()
    assert "        self.set_camera_orientation(phi=75 * DEGREES)\n        self.wait(1)" in out


def test_check():
    assert check("2d", {"center": [1, 0.5], "width": 7}, [1, 0.5], 7) is None
    assert "ended at" in check("2d", {"center": [1.5, 0.5], "width": 7}, [1, 0.5], None)
    assert check("3d", {"phi": 60.1, "theta": -179.9, "zoom": 1}, values={"phi": 60, "theta": 180}) is None


def test_2d_first_frame_edits_the_placement_already_there():
    code = make("MovingCameraScene", "self.camera.frame.move_to(RIGHT)", "self.add(Square())", "self.wait(2)")
    wait = {"kind": "wait", "call": None, "call_line": 7, "start": 0.0, "duration": 2.0}
    plan = plan_camera_2d(Source(code.encode()), "S", [wait], 15, False, 0.0, [2.0, 0.0], 8.0, {"width": 14.22})
    out = apply(code.encode(), plan.edits).decode()
    assert "        self.camera.frame.move_to(2 * RIGHT).set(width=8)\n        self.add(Square())" in out
    assert out.count("camera.frame") == 1
