"""Graphs (Phase 5, step 7): a curve's formula, edited as an expression.

`axes.plot(lambda x: 0.5 * x**2, x_range=[-2, 2])` shows in the Inspector
as `0.5 * x**2` of `x`. A new formula typed by the user is code, so it is
checked before anything is written:

- it parses as one Python expression;
- every name it reads is the lambda's own parameter, a name the file
  already binds where the lambda is (module level, the enclosing function,
  a `from ... import *` the file has), `np`/`math` when the file imports
  them, or one of a few maths builtins;
- no attribute starts with an underscore, no lambdas, comprehensions,
  walrus, `await` or `yield`, and no calls to anything outside the names
  above.

The replay then runs it (the worker runs the file, as for every edit):
the curve must still render, with no exception.
"""

from __future__ import annotations

import ast
import builtins

from .census import PLOTTERS
from .source import Source, Span
from .splice import Edit, EditError

MATHS_BUILTINS = {"abs", "min", "max", "round", "pow", "sum", "int", "float", "len", "range"}
NOT_ALLOWED = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.NamedExpr,
               ast.Await, ast.Yield, ast.YieldFrom, ast.Starred)
CURVE_KW = ("function", "func")


def curve_lambda(src: Source, site) -> ast.Lambda | None:
    """The lambda that a plotting call at `site` draws (first positional
    argument, or `function=`)."""
    call = src.find_call(Span(*site)) if site else None
    if call is None:
        return None
    f = call.func
    name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
    if name not in PLOTTERS:
        return None
    cand = call.args[:1] + [k.value for k in call.keywords if k.arg in CURVE_KW]
    return next((c for c in cand if isinstance(c, ast.Lambda)), None)


def describe_curve(src: Source, site) -> dict | None:
    """{params, expr, span} for the Inspector, or None."""
    lam = curve_lambda(src, site)
    if lam is None or lam.args.vararg or lam.args.kwarg:
        return None
    b = lam.body
    return {"params": [a.arg for a in lam.args.args], "expr": src.text(b),
            "span": [b.lineno, b.col_offset, b.end_lineno, b.end_col_offset]}


def _bound_names(src: Source, lam: ast.Lambda) -> set[str]:
    """Names readable where the lambda is: module-level bindings, the
    enclosing functions' parameters and assignments, imports."""
    out: set[str] = set()

    def binds(node):
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                out.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)
            elif isinstance(n, ast.arg):
                out.add(n.arg)
            elif isinstance(n, ast.alias):
                out.add((n.asname or n.name).split(".")[0])

    for st in src.tree.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(st.name)
        else:
            binds(st)
    p = src.parent(lam)
    while p is not None:
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
            binds(p)
        p = src.parent(p)
    return out


def check_expression(src: Source, lam: ast.Lambda, text: str, api: set[str]) -> ast.expr:
    text = text.strip()
    if not text:
        raise EditError("type a formula")
    if len(text) > 500:
        raise EditError("that formula is too long for the Inspector; edit it in the code")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        raise EditError(f"not a formula Python can read: {e.msg}") from None
    params = {a.arg for a in lam.args.args}
    known = params | _bound_names(src, lam) | (MATHS_BUILTINS & set(dir(builtins)))
    stars = {n.module for n in src.tree.body if isinstance(n, ast.ImportFrom) and n.module
             and any(a.name == "*" for a in n.names)}
    if stars:
        known |= api  # `from manim import *` (and the style/kit names it re-exports)
    for n in ast.walk(tree.body):
        if isinstance(n, NOT_ALLOWED):
            raise EditError(f"a formula can't contain {type(n).__name__.lower()} here; edit it in the code")
        if isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            raise EditError(f"{n.attr} isn't something a formula may use")
        if isinstance(n, ast.Name) and n.id not in known:
            raise EditError(f"{n.id} isn't defined here (the curve's variable is "
                            f"{', '.join(sorted(params)) or 'none'})")
    return tree.body  # a constant curve (y = 2) is allowed


def plan_curve(src: Source, obj: dict, text: str, api: set[str]):
    """Replace the formula of the curve made at obj["site"]."""
    from .planner import Plan
    if not src.ok:
        raise EditError("the file doesn't parse")
    lam = curve_lambda(src, obj.get("site") or obj.get("user_site"))
    if lam is None:
        raise EditError("this object isn't drawn from a lambda the studio can edit")
    body = check_expression(src, lam, text, api)
    new = text.strip()
    if isinstance(body, (ast.Tuple, ast.IfExp)) and not new.startswith("("):
        new = f"({new})"  # keeps `lambda t: (a, b)` one argument of the call
    old = src.text(lam.body)
    if new == old:
        raise EditError("that's the formula already")
    a, b = src.span(lam.body)
    confirm = None
    if obj.get("in_helper"):
        confirm = f"this curve is made inside {obj.get('func')}(): every curve that helper makes changes"
    return Plan([Edit(a, b, new)], f"curve: {old} → {new}", confirm, checks={"curve": True})
