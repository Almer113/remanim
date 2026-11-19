"""Phase 5 step 7: a point placed in graph coordinates is dragged in graph units."""

import ast

from studio.server.code import moves
from studio.server.code.source import Source
from studio.server.code.splice import apply

AXES = {"ax": {"o": [-3.0, -2.0], "ex": [0.5, 0.0], "ey": [0.0, 1.0]}}


def drag(code, needle, dx, dy, coords=AXES):
    src = Source(code.encode())
    expr = next(n for n in ast.walk(src.tree) if isinstance(n, ast.Call) and src.text(n) == needle)
    tok = moves.COORDS.set(coords)
    try:
        e = moves.edit_vector(src, expr, dx, dy)
    finally:
        moves.COORDS.reset(tok)
    return None if e is None else apply(code.encode(), e).decode()


def test_c2p_numbers_move_in_axis_units():
    code = "d = Dot(ax.c2p(1, 2))\n"
    assert drag(code, "ax.c2p(1, 2)", 0.25, 0.5) == "d = Dot(ax.c2p(1.5, 2.5))\n"
    # only the number that changes is touched
    assert drag(code, "ax.c2p(1, 2)", 1.0, 0.0) == "d = Dot(ax.c2p(3, 2))\n"


def test_skewed_axes_solve_both():
    c = {"ax": {"o": [0, 0], "ex": [1.0, 0.0], "ey": [1.0, 1.0]}}
    assert drag("p = ax.coords_to_point(0, 0)\n", "ax.coords_to_point(0, 0)", 1.0, 1.0, c) \
        == "p = ax.coords_to_point(0, 1)\n"


def test_number_line_along_and_off():
    c = {"nl": {"o": [0, 0], "ex": [2.0, 0.0]}}
    assert drag("d = Dot(nl.n2p(1))\n", "nl.n2p(1)", 1.0, 0.0, c) == "d = Dot(nl.n2p(1.5))\n"
    assert drag("d = Dot(nl.n2p(1))\n", "nl.n2p(1)", 0.0, 1.0, c) is None


def test_not_on_screen_or_computed_is_left_alone():
    assert drag("d = Dot(ax.c2p(1, 2))\n", "ax.c2p(1, 2)", 1, 0, {}) is None
    assert drag("d = Dot(ax.c2p(x, 2))\n", "ax.c2p(x, 2)", 1, 0) is None
