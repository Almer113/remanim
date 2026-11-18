"""Awkward corpus: camera moves (2D frame and 3D)."""
from manim import *


class Zoom(MovingCameraScene):
    def construct(self):
        sq = Square()
        self.add(sq, Dot(RIGHT * 2))
        self.play(self.camera.frame.animate.scale(0.5).move_to(RIGHT * 2), run_time=1)
        self.wait(0.3)


class Orbit(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES)
        axes = ThreeDAxes(x_range=[-2, 2], y_range=[-2, 2], z_range=[-1, 1])
        title = Text("3D", font_size=36).to_corner(UL)
        self.add_fixed_in_frame_mobjects(title)
        self.add(axes, Cube(side_length=1, fill_opacity=0.6))
        self.move_camera(theta=0 * DEGREES, run_time=1)
