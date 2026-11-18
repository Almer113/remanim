"""GUI intent -> code edits, for the Phase 2 edits: timing (run_time,
wait, at, rate_func) and constructor properties (code_spec.md §4.3, §4.4).

Input is the engine's description of a clip or object (spans of the calls
behind it); output is a Plan with byte edits. The planner never guesses: if
the value isn't a literal it can change, it raises EditError with the
reason, which the UI shows as is.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from .source import Source, Span
from .splice import Edit, EditError, fmt, number_of, set_keyword, set_number


@dataclass
class Plan:
    edits: list[Edit]
    note: str
    confirm: str | None = None  # a side effect the user must accept first
    checks: dict = field(default_factory=dict)  # what verify-by-replay must see


def _call(src: Source, span: list | Span, what: str) -> ast.Call:
    sp = span if isinstance(span, Span) else Span(*span)
    call = src.find_call(sp)
    if call is None:
        raise EditError(f"can't find the {what} call at line {sp.line}")
    return call


def _literal_or_refuse(src: Source, node, what: str):
    v = number_of(node)
    if v is None:
        raise EditError(f"{what} is computed ({src.text(node)}) at line {node.lineno}; "
                        "change it in the code")
    return v


# -- timing --------------------------------------------------------------------
def plan_timing(src: Source, clip: dict, field_: str, value) -> Plan:
    """clip: {kind: play|wait|anim, call: span of the scene-file call that
    made it (self.play / self.wait / self.at / a helper), call_name, start,
    duration, in_helper, anim_index (anim only), anim_runtimes: [bool]
    (which animations set their own run_time)}."""
    if not src.ok:
        raise EditError("the file doesn't parse")
    if clip.get("in_helper"):
        raise EditError(f"this {clip['kind']} is inside the helper {clip.get('func')}(); "
                        "editing it would change every use")
    name = clip.get("call_name")
    if field_ == "duration":
        value = float(value)
        if value <= 0:
            raise EditError("a duration must be more than 0 (Manim can't render wait(0))")
        if clip["kind"] == "wait":
            return _wait_duration(src, clip, name, value)
        if clip["kind"] == "play":
            return _play_runtime(src, clip, value)
        if clip["kind"] == "anim":
            return _anim_runtime(src, clip, value)
    if field_ == "rate_func":
        return _rate_func(src, clip, str(value))
    raise EditError(f"{field_} can't be edited on a {clip['kind']} clip yet")


def _wait_duration(src, clip, name, value) -> Plan:
    call = _call(src, clip["call"], name or "wait")
    if name == "at":
        if not call.args:
            raise EditError("at() without a time")
        new_t = clip["start"] + value
        old = _literal_or_refuse(src, call.args[0], "the at() time")
        return Plan([set_number(src, call.args[0], new_t)],
                    f"self.at({fmt(old)}) → self.at({fmt(new_t)})",
                    checks={"duration": value})
    if name != "wait":
        raise EditError(f"this pause comes from {name}() at line {call.lineno}, not a wait()")
    node = call.args[0] if call.args else None
    kw = Source.keyword(call, "duration")
    node = node if node is not None else (kw.value if kw else None)
    if node is None:
        # bare self.wait(): its default is 1 s
        end = src.offset(call.end_lineno, call.end_col_offset) - 1
        return Plan([Edit(end, end, fmt(value))], f"self.wait() → self.wait({fmt(value)})",
                    checks={"duration": value})
    _literal_or_refuse(src, node, "the wait time")
    return Plan([set_number(src, node, value)], f"wait {src.text(node)} → {fmt(value, src.text(node))}",
                checks={"duration": value})


def _play_runtime(src, clip, value) -> Plan:
    call = _call(src, clip["call"], "play")
    kw = Source.keyword(call, "run_time")
    if kw is not None:
        _literal_or_refuse(src, kw.value, "run_time")
        return Plan([set_number(src, kw.value, value)],
                    f"run_time={src.text(kw.value)} → {fmt(value, src.text(kw.value))}",
                    checks={"duration": value})
    anims = _anim_args(call)
    if anims is not None and len(anims) == 1:
        inner = _anim_call(anims[0])
        if inner is not None and Source.keyword(inner, "run_time") is not None:
            k = Source.keyword(inner, "run_time")
            _literal_or_refuse(src, k.value, "run_time")
            return Plan([set_number(src, k.value, value)],
                        f"run_time={src.text(k.value)} → {fmt(value, src.text(k.value))}",
                        checks={"duration": value})
    if any(clip.get("anim_runtimes") or []):
        raise EditError("the animations in this play() set their own run_time; adding one to "
                        "play() would stretch them all. Trim each clip instead")
    return Plan([set_keyword(src, call, "run_time", fmt(value))],
                f"run_time={fmt(value)} added to play()", checks={"duration": value})


def _anim_runtime(src, clip, value) -> Plan:
    call = _call(src, clip["call"], "play")
    if Source.keyword(call, "run_time") is not None:
        raise EditError("play() sets run_time for all its animations "
                        f"(line {call.lineno}); per-clip timing inside it comes in Phase 4")
    anims = _anim_args(call)
    i = clip.get("anim_index", -1)
    if anims is None or not 0 <= i < len(anims):
        raise EditError("can't tell which argument of play() this animation is")
    expr = anims[i]
    inner = _anim_call(expr)
    if inner is not None:
        k = Source.keyword(inner, "run_time")
        if k is not None:
            _literal_or_refuse(src, k.value, "run_time")
            return Plan([set_number(src, k.value, value)],
                        f"run_time={src.text(k.value)} → {fmt(value, src.text(k.value))}",
                        checks={"duration": value})
        return Plan([set_keyword(src, inner, "run_time", fmt(value))],
                    f"run_time={fmt(value)} added to {Source.call_name(inner)}()",
                    checks={"duration": value})
    builder = _animate_attr(expr)
    if builder is not None:
        # x.animate.shift(...) -> x.animate(run_time=v).shift(...)
        _, b = src.span(builder)
        return Plan([Edit(b, b, f"(run_time={fmt(value)})")],
                    f".animate(run_time={fmt(value)})", checks={"duration": value})
    raise EditError(f"can't set run_time on {src.text(expr)[:40]}")


def _rate_func(src, clip, value) -> Plan:
    call = _call(src, clip["call"], "play")
    default = clip.get("default_rate_func")
    target = call
    if clip["kind"] == "anim":
        anims = _anim_args(call)
        i = clip.get("anim_index", -1)
        if anims is None or not 0 <= i < len(anims) or _anim_call(anims[i]) is None:
            raise EditError("easing for this animation can't be set separately yet")
        if Source.keyword(call, "rate_func") is not None:
            raise EditError("play() sets rate_func for all its animations")
        target = _anim_call(anims[i])
    kw = Source.keyword(target, "rate_func")
    if value == default:
        if kw is None:
            raise EditError(f"already {value}")
        return Plan([set_keyword(src, target, "rate_func", None)], f"rate_func removed (default {value})",
                    checks={"rate_func": value})
    return Plan([set_keyword(src, target, "rate_func", value)], f"rate_func={value}",
                checks={"rate_func": value})


def _anim_args(call: ast.Call):
    """play()'s positional arguments, or None when they can't be matched to
    the animations one to one (a *starred list)."""
    if any(isinstance(a, ast.Starred) for a in call.args):
        return None
    return list(call.args)


def _anim_call(expr):
    """`FadeIn(x, ...)` -> that Call; `x.animate...` -> None."""
    if isinstance(expr, ast.Call) and _animate_attr(expr) is None:
        return expr
    return None


def _animate_attr(expr):
    """The `x.animate` node (or `x.animate(...)` call) in a builder chain."""
    n = expr
    while isinstance(n, (ast.Call, ast.Attribute)):
        if isinstance(n, ast.Attribute) and n.attr == "animate":
            return n
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "animate":
            return None  # already animate(...): handled as a call
        n = n.func if isinstance(n, ast.Call) else n.value
    return None


# -- properties ----------------------------------------------------------------
def plan_property(src: Source, obj: dict, prop: str, value: dict) -> Plan:
    """obj: {site: span of the creating call, class, params: [positional
    parameter names], func, in_helper}. value: {"number": 2.5} |
    {"name": "ACCENT"} | {"string": "Hello"} | {"default": true}."""
    if not src.ok:
        raise EditError("the file doesn't parse")
    if obj.get("site") is None:
        raise EditError("this object isn't made by a call in the scene file")
    call = _call(src, obj["site"], obj.get("class", "constructor"))
    kw = Source.keyword(call, prop)
    node = kw.value if kw is not None else None
    if node is None and prop in (obj.get("params") or []):
        i = obj["params"].index(prop)
        stars = any(isinstance(a, ast.Starred) for a in call.args[: i + 1])
        if i < len(call.args) and not stars:
            node = call.args[i]
    confirm = None
    if obj.get("in_helper"):
        confirm = (f"{obj.get('class')} is made inside {obj.get('func')}(): this changes "
                   "every object that helper makes")
    if "default" in value:
        if kw is None:
            raise EditError(f"{prop} isn't set here")
        return Plan([set_keyword(src, call, prop, None)], f"{prop}= removed (back to the default)",
                    confirm, checks={"prop": prop})
    text = _value_text(src, node, value)
    if node is not None:
        a, b = src.span(node)
        return Plan([Edit(a, b, text)], f"{prop}: {src.text(node)} → {text}", confirm,
                    checks={"prop": prop, "value": value})
    return Plan([set_keyword(src, call, prop, text)], f"{prop}={text} added", confirm,
                checks={"prop": prop, "value": value})


def _value_text(src, node, value: dict) -> str:
    if "number" in value:
        like = src.text(node) if node is not None and number_of(node) is not None else None
        return fmt(value["number"], like)
    if "name" in value:
        name = str(value["name"])
        if not name.replace("_", "").replace(".", "").isalnum():
            raise EditError(f"not a name: {name!r}")
        return name
    if "string" in value:
        return _string_like(src, node, str(value["string"]))
    raise EditError("unknown value kind")


def _string_like(src, node, s: str) -> str:
    """A string literal in the style of the one it replaces (quote and r prefix)."""
    old = src.text(node) if isinstance(node, ast.Constant) and isinstance(node.value, str) else '""'
    prefix = ""
    while old and old[0] in "rRbBuUfF":
        prefix += old[0]
        old = old[1:]
    q = old[:3] if old[:3] in ('"""', "'''") else old[:1]
    if q not in ('"', "'", '"""', "'''"):
        q = '"'
    raw = "r" in prefix.lower()
    if raw and (q in s or s.endswith("\\")):
        prefix = prefix.replace("r", "").replace("R", "")
        raw = False
    body = s if raw else s.replace("\\", "\\\\")
    if not raw:
        body = body.replace(q, "\\" + q) if len(q) == 1 else body
        body = body.replace("\n", "\\n") if len(q) == 1 else body
    return f"{prefix}{q}{body}{q}"
