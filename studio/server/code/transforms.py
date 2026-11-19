"""Transform pairs (Phase 5, step 8): switching a Transform-family
animation's kind, keeping its arguments.

The kinds differ in what is on screen afterwards:

| kind                  | after `K(a, b)`                      |
|-----------------------|--------------------------------------|
| Transform             | `a` (now shaped like `b`)            |
| ReplacementTransform  | `b`                                  |
| FadeTransform         | `b`                                  |
| TransformFromCopy     | `a` and `b`                          |

A switch is refused when code after the animation uses a name that the
new kind takes off screen (`self.play(a.animate.shift(UP))` after a switch
from `Transform(a, b)` to `ReplacementTransform(a, b)` would move an object
that is no longer shown). The replay then checks the scene still runs.
"""

from __future__ import annotations

import ast

from .source import Source
from .splice import Edit, EditError

KINDS = ("Transform", "ReplacementTransform", "FadeTransform", "TransformFromCopy")
ON_SCREEN = {"Transform": {0}, "ReplacementTransform": {1}, "FadeTransform": {1}, "TransformFromCopy": {0, 1}}


def _transform_call(src: Source, play_span, index: int) -> ast.Call:
    from .planner import _anim_args, _call
    play = _call(src, play_span, "play")
    anims = _anim_args(play)
    if anims is None or not 0 <= index < len(anims):
        raise EditError("can't tell which argument of play() this animation is")
    a = anims[index]
    if not (isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in KINDS):
        raise EditError("this animation isn't a Transform, ReplacementTransform, FadeTransform "
                        "or TransformFromCopy written in the scene")
    if len(a.args) < 2:
        raise EditError("this transform doesn't name its source and target")
    return a


def _later_uses(src: Source, call: ast.Call, name: str) -> list[int]:
    """Lines after `call`, in the same function, that read `name` (until it is
    bound again)."""
    from .moves import function_of, statement_of
    fn = function_of(src, call)
    stmt = statement_of(src, call)
    if fn is None or stmt is None:
        return []
    names = sorted((n.lineno, n.col_offset, isinstance(n.ctx, ast.Store)) for n in ast.walk(fn)
                   if isinstance(n, ast.Name) and n.id == name and n.lineno > stmt.end_lineno)
    lines = []
    for line, _, store in names:
        if store:
            break  # bound again: later uses are another object
        lines.append(line)
    return sorted(set(lines))


def plan_kind(src: Source, play_span, index: int, kind: str):
    from .planner import Plan
    if kind not in KINDS:
        raise EditError(f"not a transform kind: {kind}")
    call = _transform_call(src, play_span, index)
    old = call.func.id
    if old == kind:
        raise EditError(f"it is a {kind} already")
    gone = ON_SCREEN[old] - ON_SCREEN[kind]
    for i in sorted(gone):
        arg = call.args[i]
        if not isinstance(arg, ast.Name):
            continue
        uses = _later_uses(src, call, arg.id)
        if uses:
            raise EditError(f"after {kind}({src.text(call.args[0])}, {src.text(call.args[1])}), "
                            f"{arg.id} is no longer on screen, but line {uses[0]} uses it")
    a, b = src.span(call.func)
    return Plan([Edit(a, b, kind)], f"{old} → {kind} (line {call.lineno})", None, checks={"kind": kind})


def pair(src: Source, play_span, index: int) -> dict | None:
    """{kind, source, target, kinds} for the Inspector, or None."""
    try:
        call = _transform_call(src, play_span, index)
    except EditError:
        return None
    return {"kind": call.func.id, "source": src.text(call.args[0]), "target": src.text(call.args[1]),
            "kinds": list(KINDS)}



MATCHING = ("TransformMatchingTex", "TransformMatchingShapes")


def plan_key_map(src: Source, play_span, index: int, source_key: str, target_key: str):
    """"Match these" (step 8): pair a part of the source formula with a part of
    the target that `TransformMatchingTex` didn't match, by adding
    `key_map={source_key: target_key}` to the call (or one more entry in it)."""
    from .planner import Plan, _anim_args, _call
    from .tex import _add_to_map, _str_code
    play = _call(src, play_span, "play")
    anims = _anim_args(play)
    if anims is None or not 0 <= index < len(anims):
        raise EditError("can't tell which argument of play() this animation is")
    a = anims[index]
    if not (isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id in MATCHING):
        raise EditError("only TransformMatchingTex written in the scene can be told which parts match")
    if a.func.id != "TransformMatchingTex":
        raise EditError("TransformMatchingShapes matches parts by their shape; there is no key to write")
    if not (isinstance(source_key, str) and isinstance(target_key, str) and source_key and target_key):
        raise EditError("pick one part on each side")
    e = _add_to_map(src, a, "key_map", source_key, _str_code(src, target_key))
    if e is None:
        k = Source.keyword(a, "key_map")
        raise EditError(f"key_map is computed ({src.text(k.value)}) at line {a.lineno}; change it in the code")
    return Plan([e], f"{a.func.id} at line {a.lineno}: {source_key} → {target_key}", None)
