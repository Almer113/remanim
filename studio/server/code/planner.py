"""GUI intent -> code edits, for the Phase 2 edits: timing (run_time,
wait, at, rate_func) and constructor properties (code_spec.md §4.3, §4.4).

Input is the engine's description of a clip or object (spans of the calls
behind it); output is a Plan with byte edits. The planner never guesses: if
the value isn't a literal it can change, it raises EditError with the
reason, which the UI shows as is.
"""

from __future__ import annotations

import ast
import keyword
import re
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


NAME = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*")


def _name_or_refuse(value, what: str) -> str:
    """A (dotted) Python name and nothing else: values sent by the UI are
    written into the file as code, so anything else is refused."""
    v = str(value).strip()
    if not NAME.fullmatch(v) or any(keyword.iskeyword(p) for p in v.split(".")):
        raise EditError(f"not a {what}: {value!r}")
    return v


def _loop_around(src: Source, node):
    """The loop or comprehension inside the same function that repeats `node`."""
    n = src.parent(node)
    while n is not None and not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                                               ast.ClassDef, ast.Module)):
        if isinstance(n, (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp,
                          ast.DictComp, ast.GeneratorExp)):
            return n
        n = src.parent(n)
    return None


def _confirm_loop(src: Source, call, plan: "Plan") -> "Plan":
    loop = _loop_around(src, call)
    if loop is not None and plan.confirm is None:
        plan.confirm = (f"line {call.lineno} runs inside the loop at line {loop.lineno}: "
                        "this changes it for every pass of the loop")
    return plan


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
    plan = None
    if field_ == "duration":
        try:
            value = round(float(value), 4)
        except (TypeError, ValueError):
            raise EditError(f"not a number: {value!r}") from None
        if not 0 < value < float("inf"):
            raise EditError("a duration must be a number more than 0 (Manim can't render wait(0))")
        if clip["kind"] == "wait":
            plan = _wait_duration(src, clip, name, value)
        elif clip["kind"] == "play":
            plan = _play_runtime(src, clip, value)
        elif clip["kind"] == "anim":
            plan = _anim_runtime(src, clip, value)
    elif field_ == "rate_func":
        plan = _rate_func(src, clip, _name_or_refuse(value, "rate function"))
    if plan is None:
        raise EditError(f"{field_} can't be edited on a {clip['kind']} clip yet")
    if plan.checks.get("one_pass"):
        return plan  # changes this pass of the loop only
    return _confirm_loop(src, _call(src, clip["call"], name or "play"), plan)


# between a call and the loop that binds its time: passes and events stop lining up
BETWEEN = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.Try, ast.IfExp,
           ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension)


def loop_element(src: Source, call, name: ast.Name, k, target: float | None = None):
    """`for t, s in zip((5.5, 7.8), topics): self.at(t)`: on pass k, `t` is the
    k-th number of the literal it comes from. That number, and the loop; or
    None when it isn't a literal or the pass can't be told.

    The pass count `k` counts events, not passes: an `at()` already past its
    time makes no event, and an `if` can skip one. So when `target` (the value
    the name had on this pass) is known, the element is found by its value and
    must be the only one with that value; `k` is used alone only when nothing
    (if/try/inner loop) lies between the call and the loop."""
    if not isinstance(k, int) or k < 0:
        return None
    n = src.parent(call)
    loop = None
    between = False  # a branch, try or inner loop between the call and the loop
    while n is not None and not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        if isinstance(n, (ast.For, ast.AsyncFor)) and loop is None and _binds(n.target, name.id):
            loop = n
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.While, ast.comprehension)) and loop is not None:
            return None  # an outer loop runs this loop several times
        elif loop is None and (isinstance(n, BETWEEN) or type(n).__name__ in ("TryStar", "Match")):
            between = True
        n = src.parent(n)
    if loop is None or between:
        return None  # passes and events no longer line up one to one
    # the name must not be assigned again inside the loop
    for x in ast.walk(loop):
        if x is not loop.target and isinstance(x, ast.Name) and x.id == name.id \
                and isinstance(x.ctx, ast.Store) and not _inside(x, loop.target):
            return None
    it, tgt = loop.iter, loop.target
    seq, pos = None, None
    if isinstance(it, (ast.List, ast.Tuple)):
        seq = it.elts
        pos = None if isinstance(tgt, ast.Name) else _position(tgt, name.id)
        if pos is None and not isinstance(tgt, ast.Name):
            return None
    elif isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and isinstance(tgt, ast.Tuple):
        p = _position(tgt, name.id)
        if p is None:
            return None
        if it.func.id == "zip" and p < len(it.args) and isinstance(it.args[p], (ast.List, ast.Tuple)):
            seq = it.args[p].elts
        elif it.func.id == "enumerate" and p == 1 and it.args and isinstance(it.args[0], (ast.List, ast.Tuple)):
            seq = it.args[0].elts
    if seq is None or any(isinstance(e, ast.Starred) for e in seq):
        return None
    els = []
    for e in seq:
        if pos is not None:
            if not isinstance(e, (ast.Tuple, ast.List)) or pos >= len(e.elts):
                return None
            e = e.elts[pos]
        els.append(e)
    if target is not None:
        hits = [i for i, e in enumerate(els)
                if number_of(e) is not None and abs(number_of(e) - target) < 1e-3]
        if len(hits) != 1:
            return None  # no element, or several, had this value
        k = hits[0]
    if k >= len(els):
        return None
    el = els[k]
    return (el, loop) if number_of(el) is not None else None


def _binds(target, name: str) -> bool:
    return any(isinstance(x, ast.Name) and x.id == name for x in ast.walk(target))


def _inside(node, root) -> bool:
    return any(x is node for x in ast.walk(root))


def _position(tgt, name: str):
    """Index of `name` in a flat tuple target `(t, s)`; None if nested or absent."""
    if not isinstance(tgt, (ast.Tuple, ast.List)):
        return None
    for i, e in enumerate(tgt.elts):
        if isinstance(e, ast.Name) and e.id == name:
            return i
    return None


def _wait_duration(src, clip, name, value) -> Plan:
    call = _call(src, clip["call"], name or "wait")
    if name == "at":
        if not call.args:
            raise EditError("at() without a time")
        new_t = round(clip["start"] + value, 2)  # an absolute time: keep it readable
        arg = call.args[0]
        if number_of(arg) is None and isinstance(arg, ast.Name):
            target = None
            if clip.get("start") is not None and clip.get("duration") is not None:
                target = clip["start"] + clip["duration"]  # the time t had on this pass
            found = loop_element(src, call, arg, clip.get("occurrence"), target)
            if found is not None:
                node, loop = found
                if fmt(new_t, src.text(node)) == src.text(node).lstrip("+"):
                    raise EditError(f"pass {clip['occurrence'] + 1} already waits until "
                                    f"{src.text(node)} s (the change rounds away)")
                return Plan([set_number(src, node, new_t)],
                            f"pass {clip['occurrence'] + 1} of the loop at line {loop.lineno}: "
                            f"{src.text(node)} → {fmt(new_t, src.text(node))}",
                            checks={"duration": value, "one_pass": True})
        off = _offset_literal(arg)
        if off is not None and clip.get("duration") is not None:
            # at(a + 1.2): a time relative to a spoken line (or TARGET). Retiming
            # moves this anchor only, so only the offset changes: a + 1.3.
            node, base, sign = off
            delta = new_t - (clip["start"] + clip["duration"])
            c = round(number_of(node) + sign * delta, 2)
            if c >= 0:
                edit = set_number(src, node, c)
                a, b = src.span(arg)
                n0, n1 = src.span(node)
                text = (src.data[a:n0] + fmt(c, src.text(node)).encode() + src.data[n1:b]).decode("utf-8")
            elif node is arg.right:  # a + 0.1 → a - 0.2, and back
                text = f"{src.text(base)} {'-' if sign > 0 else '+'} {fmt(-c, src.text(node))}"
                edit = Edit(*src.span(arg), text)
            else:
                raise EditError(f"the at() time {src.text(arg)} would need a negative offset; "
                                "change it in the code")
            return Plan([edit], f"self.at({src.text(arg)}) → self.at({text})", checks={"duration": value})
        old = _literal_or_refuse(src, arg, "the at() time")
        return Plan([set_number(src, call.args[0], new_t)],
                    f"self.at({fmt(old)}) → self.at({fmt(new_t)})",
                    checks={"duration": value})
    if name != "wait":
        raise EditError(f"this pause comes from {name}() at line {call.lineno}, not a wait()")
    node = call.args[0] if call.args else None
    kw = Source.keyword(call, "duration")
    node = node if node is not None else (kw.value if kw else None)
    if node is None:
        # self.wait() or self.wait(frozen_frame=...): the default is 1 s
        if call.keywords:
            at, _ = src.span(min(call.keywords, key=lambda k: (k.lineno, k.col_offset)))
            return Plan([Edit(at, at, f"{fmt(value)}, ")], f"wait time {fmt(value)} added",
                        checks={"duration": value})
        end = src.offset(call.end_lineno, call.end_col_offset) - 1
        return Plan([Edit(end, end, fmt(value))], f"self.wait() → self.wait({fmt(value)})",
                    checks={"duration": value})
    _literal_or_refuse(src, node, "the wait time")
    return Plan([set_number(src, node, value)], f"wait {src.text(node)} → {fmt(value, src.text(node))}",
                checks={"duration": value})


def _offset_literal(arg):
    """`a + 1.2`, `1.2 + a`, `self.TARGET - 0.6` → (the number node, the
    other side, +1 when a bigger number means later, else -1). The other
    side must be a plain name or attribute (a time the code already has)."""
    if not (isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Sub))):
        return None
    plain = (ast.Name, ast.Attribute)
    if number_of(arg.right) is not None and isinstance(arg.left, plain):
        return arg.right, arg.left, (1 if isinstance(arg.op, ast.Add) else -1)
    if isinstance(arg.op, ast.Add) and number_of(arg.left) is not None and isinstance(arg.right, plain):
        return arg.left, arg.right, 1
    return None


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
        inner = _anim_call(anims[0]) or _animate_call(anims[0])
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
    from .timeline import _runtime_edits, clip_parts
    call = _call(src, clip["call"], "play")
    anims = _anim_args(call)
    i = clip.get("anim_index", -1)
    if anims is None or not 0 <= i < len(anims):
        raise EditError("can't tell which argument of play() this animation is")
    play_rt = Source.keyword(call, "run_time")
    if play_rt is not None:
        # play(run_time=R) times every animation: give each its own R, this one the new value
        rt = number_of(play_rt.value)
        if rt is None:
            raise EditError(f"play() sets a computed run_time for all its animations (line {call.lineno})")
        if len(anims) == 1:
            return Plan([set_number(src, play_rt.value, value)],
                        f"run_time={src.text(play_rt.value)} → {fmt(value, src.text(play_rt.value))}",
                        checks={"duration": value})
        edits = [set_keyword(src, call, "run_time", None)]
        for j, a in enumerate(anims):
            edits += _runtime_edits(src, a, value if j == i else rt)
        return Plan(edits, f"run_time={fmt(rt)} moved from play() onto each animation; this one {fmt(value)}",
                    checks={"duration": value})
    expr = anims[i]
    inner_, _, length, cc = clip_parts(expr)
    if cc is not None:
        if length is not None:
            _literal_or_refuse(src, length, "the clip's length")
            return Plan([set_number(src, length, value)], f"length={src.text(length)} → {fmt(value, src.text(length))}",
                        checks={"duration": value})
        return Plan([set_keyword(src, cc, "length", fmt(value))], f"length={fmt(value)} added to clip()",
                    checks={"duration": value})
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
    ac = _animate_call(expr)
    if ac is not None:
        # x.animate(rate_func=...).shift(...): run_time belongs in animate(...)
        k = Source.keyword(ac, "run_time")
        if k is not None:
            _literal_or_refuse(src, k.value, "run_time")
            return Plan([set_number(src, k.value, value)],
                        f"run_time={src.text(k.value)} → {fmt(value, src.text(k.value))}",
                        checks={"duration": value})
        return Plan([set_keyword(src, ac, "run_time", fmt(value))],
                    f"run_time={fmt(value)} added to .animate()", checks={"duration": value})
    builder = _animate_attr(expr)
    if builder is not None:
        # x.animate.shift(...) -> x.animate(run_time=v).shift(...)
        _, b = src.span(builder)
        return Plan([Edit(b, b, f"(run_time={fmt(value)})")],
                    f".animate(run_time={fmt(value)})", checks={"duration": value})
    raise EditError(f"can't set run_time on {src.text(expr)[:40]}")


# rate functions that `from manim import *` gives by bare name; the rest
# (ease_in_sine, ease_out_back, ...) are only reachable as rate_functions.<name>
STAR_RATES = {"smooth", "linear", "rush_into", "rush_from", "slow_into", "double_smooth",
              "there_and_back", "there_and_back_with_pause", "wiggle", "running_start",
              "not_quite_there", "squish_rate_func", "lingering", "exponential_decay",
              "smoothererstep", "smootherstep", "smoothstep"}


def _module_names(src) -> set[str]:
    """Names the file binds at module level (imports, defs, assignments)."""
    out = set()
    for node in src.tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            out |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return out


def _rate_expr(src, name: str) -> str:
    """How the file should spell rate function `name`."""
    if "." in name or name in STAR_RATES or name in _module_names(src):
        return name
    return f"rate_functions.{name}"


def _rate_func(src, clip, value) -> Plan:
    call = _call(src, clip["call"], "play")
    default = clip.get("default_rate_func")
    target = call
    if clip["kind"] == "anim":
        anims = _anim_args(call)
        i = clip.get("anim_index", -1)
        from .timeline import clip_parts
        expr = clip_parts(anims[i])[0] if anims is not None and 0 <= i < len(anims) else None
        if expr is None or _anim_call(expr) is None:
            raise EditError("easing for this animation can't be set separately yet")
        if Source.keyword(call, "rate_func") is not None:
            raise EditError("play() sets rate_func for all its animations")
        target = _anim_call(expr)
    kw = Source.keyword(target, "rate_func")
    if value == default:
        if kw is None:
            raise EditError(f"already {value}")
        return Plan([set_keyword(src, target, "rate_func", None)], f"rate_func removed (default {value})",
                    checks={"rate_func": value})
    code = _rate_expr(src, value)
    return Plan([set_keyword(src, target, "rate_func", code)], f"rate_func={code}",
                checks={"rate_func": value.rsplit(".", 1)[-1]})


def _anim_args(call: ast.Call):
    """play()'s positional arguments, or None when they can't be matched to
    the animations one to one (a *starred list)."""
    if any(isinstance(a, ast.Starred) for a in call.args):
        return None
    return list(call.args)


def _anim_call(expr):
    """`FadeIn(x, ...)` -> that Call; `x.animate...` -> None."""
    if isinstance(expr, ast.Call) and _animate_attr(expr) is None and _animate_call(expr) is None:
        return expr
    return None


def _animate_call(expr):
    """The `x.animate(...)` call in a builder chain, if the chain has one."""
    n = expr
    while isinstance(n, (ast.Call, ast.Attribute)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "animate":
            return n
        n = n.func if isinstance(n, ast.Call) else n.value
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
    prop = str(prop)
    if not prop.isidentifier() or keyword.iskeyword(prop):
        raise EditError(f"not a property name: {prop!r}")
    call =_call(src, obj["site"], obj.get("class", "constructor"))
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
        if confirm is None and number_of(node) is None and \
                not isinstance(node, (ast.Constant, ast.Name, ast.Attribute)):
            confirm = f"{prop} is computed here ({src.text(node)[:60]}); this replaces it with {text}"
        a, b = src.span(node)
        plan = Plan([Edit(a, b, text)], f"{prop}: {src.text(node)} → {text}", confirm,
                    checks={"prop": prop, "value": value})
    else:
        plan = Plan([set_keyword(src, call, prop, text)], f"{prop}={text} added", confirm,
                    checks={"prop": prop, "value": value})
    return _confirm_loop(src, call, plan)


# a property set on one object after it is made: the setter a person would write
SETTERS = {"color": "set_color({v})", "fill_color": "set_fill({v})", "fill_opacity": "set_fill(opacity={v})",
           "stroke_color": "set_stroke({v})", "stroke_width": "set_stroke(width={v})",
           "stroke_opacity": "set_stroke(opacity={v})", "opacity": "set_opacity({v})"}


def plan_property_override(src: Source, obj: dict, prop: str, value: dict) -> Plan | None:
    """Tier-2 override (code_spec §5): for one of many objects a loop, a
    comprehension or a helper makes, `dots[2].set_color(RED)` on a new line
    after the group's last placement, instead of changing every one."""
    if "default" in value or not src.ok:
        return None
    from .moves import insert_after, override_target
    target = override_target(src, obj)
    if target is None:
        return None
    expr, after = target
    text = _value_text(src, None, value)
    call = SETTERS.get(prop, "set(" + prop + "={v})").format(v=text)
    try:
        e = insert_after(src, after, f"{expr}.{call}")
    except EditError:
        return None
    return Plan([e], f"only this one: new line {expr}.{call} after line {after.end_lineno}", None,
                checks={"prop": prop, "value": value})


def _value_text(src, node, value: dict) -> str:
    if "number" in value:
        try:
            n = float(value["number"])
        except (TypeError, ValueError):
            raise EditError(f"not a number: {value['number']!r}") from None
        if not -float("inf") < n < float("inf"):
            raise EditError("not a finite number")
        like = src.text(node) if node is not None and number_of(node) is not None else None
        return fmt(n, like)
    if "name" in value:
        return _name_or_refuse(value["name"], "name")
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
    if raw and (q[0] in s or s.endswith("\\") or (len(q) == 1 and ("\n" in s or "\r" in s))):
        prefix = prefix.replace("r", "").replace("R", "")
        raw = False
    body = s if raw else s.replace("\\", "\\\\")
    if not raw:
        body = body.replace(q[0], "\\" + q[0])  # inside triple quotes too
        if len(q) == 1:
            body = body.replace("\n", "\\n").replace("\r", "\\r")
    if len(q) == 3 and getattr(src, "newline", "\n") != "\n":
        body = body.replace("\n", src.newline)  # keep the file's line endings
    return f"{prefix}{q}{body}{q}"
