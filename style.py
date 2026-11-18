"""Shared look and layout for every scene in this project.

Import with:  from style import *

Keep colours, fonts and screen regions here so all videos match, and so the
layout checker (tools/check_layout.py) knows the safe area.
"""

from manim import (
    DOWN, LEFT, ORIGIN, RIGHT, UP, Mobject, ManimColor, config,
)

# ── Palette ──────────────────────────────────────────────────────────────
BG = ManimColor("#0f1115")
FG = ManimColor("#e8eaed")      # main text
MUTED = ManimColor("#8b929b")   # secondary text, de-emphasised items
ACCENT = ManimColor("#58c4dd")  # the thing the viewer should look at
ACCENT_2 = ManimColor("#f0ac5f")
GOOD = ManimColor("#83c167")
BAD = ManimColor("#fc6255")

# ── Text sizes (Manim font_size units) ───────────────────────────────────
TITLE_SIZE = 48
BODY_SIZE = 36
CAPTION_SIZE = 28
MIN_FONT_SIZE = 20  # anything smaller is unreadable at 480p/phone size

# ── Frame and safe area ──────────────────────────────────────────────────
# Default frame is 14.22 x 8 units. Keep content inside the safe area.
SAFE_X = 6.5   # |x| <= SAFE_X
SAFE_Y = 3.5   # |y| <= SAFE_Y
EDGE_BUFF = 0.5

# Named screen regions: (center, width, height). Place things *into* a
# region instead of using raw coordinates.
REGIONS = {
    "title":  (UP * 3.0,               13.0, 1.0),
    # main/left/right end at y=-2.65, leaving a gap above the footer caption
    "main":   (DOWN * 0.15,             13.0, 5.0),
    "left":   (LEFT * 3.4 + DOWN * 0.15, 6.2, 5.0),
    "right":  (RIGHT * 3.4 + DOWN * 0.15, 6.2, 5.0),
    "footer": (DOWN * 3.2,             13.0, 0.7),
}


def place(mob: Mobject, region: str = "main", fit: bool = True) -> Mobject:
    """Centre `mob` in a named region, shrinking it (never growing) to fit."""
    center, w, h = REGIONS[region]
    if fit:
        if mob.width > w:
            mob.scale_to_fit_width(w)
        if mob.height > h:
            mob.scale_to_fit_height(h)
    return mob.move_to(center)


def grid_point(col: int, row: int, cols: int = 6, rows: int = 6):
    """Centre of cell (col, row) on a cols x rows grid over the safe area.

    (0, 0) is top-left. Useful for laying out several items without
    hand-picking coordinates.
    """
    cell_w = 2 * SAFE_X / cols
    cell_h = 2 * SAFE_Y / rows
    x = -SAFE_X + cell_w * (col + 0.5)
    y = SAFE_Y - cell_h * (row + 0.5)
    return RIGHT * x + UP * y


def apply_background() -> None:
    config.background_color = BG


__all__ = [
    "BG", "FG", "MUTED", "ACCENT", "ACCENT_2", "GOOD", "BAD",
    "TITLE_SIZE", "BODY_SIZE", "CAPTION_SIZE", "MIN_FONT_SIZE",
    "SAFE_X", "SAFE_Y", "EDGE_BUFF", "REGIONS",
    "place", "grid_point", "apply_background", "ORIGIN",
]
