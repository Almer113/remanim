"""Recreation-specific settings for eola_preview.py (EoLA preview study).

The reusable parts (TimedScene, Blob, bubbles, ClippedGrid, ...) live in
manim_kit.py, which is original code. This file only adds what is specific to
recreating 3Blue1Brown's 2016 look, partly adapted from 3b1b/videos
(_2016/eola/chapter0.py), CC BY-NC-SA 4.0. It is shared under the same
license, for non-commercial use.
"""

from __future__ import annotations

from manim_kit import *

FW, FH = config.frame_width, config.frame_height
GRID_BLUE = BLUE_D
I_COLOR, J_COLOR = GREEN_C, RED_C

# 2016 Manim text was about 1.2x the size of CE's default (48), measured by
# comparing the same formula's width in reference and our frames. This is a
# global default, so it only applies where this module is imported.
Tex.set_default(font_size=58)
MathTex.set_default(font_size=58)

MATMUL_TEX = (r"\begin{bmatrix} a & b \\ c & d \end{bmatrix}"
              r"\begin{bmatrix} e & f \\ g & h \end{bmatrix}"
              r"= \begin{bmatrix} ae+bg & af+bh \\ ce+dg & cf+dh \end{bmatrix}")


class EolaScene(TimedScene):
    """TimedScene on a black background; TARGET = the section's length in the
    reference video."""

    def setup(self):
        super().setup()
        self.camera.background_color = BLACK
