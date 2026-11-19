"""Phase 5 step 6: the probe parser and the similarity check (no LaTeX run)."""

import numpy as np

from studio.server.engine.texmap import Probe, probe_parts, similar


def pieces(tex, text_mode=False):
    pr = Probe(tex, text_mode, "p")
    body = pr.seq(0, len(tex))
    return body, [tex[o0:o1] for (_, _, o0, o1) in pr.pieces]


def test_each_symbol_is_its_own_piece():
    _, own = pieces("a^2 + b^2 = c^2")
    assert sorted(own) == sorted(["a", "2", "+", "b", "2", "=", "c", "2"])


def test_a_command_with_arguments_owns_only_its_name():
    _, own = pieces(r"\frac{1}{n}")
    assert r"\frac" in own and "1" in own and "n" in own


def test_scripts_stay_with_their_base():
    body, own = pieces(r"\sum_{n=1}^\infty x")
    assert r"\sum" in own and r"\infty" in own
    # the base wraps its scripts, so the limits don't move
    assert body.index(r"\sum") < body.index(r"\infty")


def test_spacing_and_alignment_are_left_alone():
    body, own = pieces(r"a &= b \quad c")
    assert "&" not in own and r"\quad" not in own
    assert "&" in body and r"\quad" in body


def test_text_mode_words_and_ligatures():
    _, own = pieces("Jean--Paul ``hi''", text_mode=True)
    assert "Jean" in own and "--" in own and "``" in own and "''" in own


def test_environment_owns_begin():
    _, own = pieces(r"\begin{bmatrix} 1 & 2 \end{bmatrix}")
    assert r"\begin" in own and "1" in own and "2" in own


def test_parts_get_their_own_prefix():
    body, probes = probe_parts(["a", "+", "b"], False, " ")
    assert "sp00x" in body and "sp02x" in body and len(probes) == 3


def test_similar_allows_move_scale_turn():
    a = np.array([[0, 0], [1, 0], [1, 2], [3, 1]], float)
    th = 0.7
    rot = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    b = (a @ rot.T) * 1.8 + [4, -2]
    assert similar(a, b)
    c = b.copy()
    c[2] += [0.5, 0]
    assert not similar(a, c)
    assert not similar(a, b[:3])
