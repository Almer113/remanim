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
  above;
- calls are maths only: `np.`/`math.` functions from an allow-list (or
  numpy ufuncs), plain names the file binds (`func(x)`), never `eval`,
  `open`, `getattr` and the like, and no attribute of another module;
- one line, no comments (a `#` would comment out the rest of the call).

The replay then runs it (the worker runs the file, as for every edit):
the curve must still render, with no exception.
"""

from __future__ import annotations

import ast
import builtins
import io
import math
import tokenize

from .census import PLOTTERS
from .source import Source, Span
from .splice import Edit, EditError

MATHS_BUILTINS = {"abs", "min", "max", "round", "pow", "sum", "int", "float", "len", "range"}
NOT_ALLOWED = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.NamedExpr,
               ast.Await, ast.Yield, ast.YieldFrom, ast.Starred)
CURVE_KW = ("function", "func")
NUMERIC_MODULES = {"np", "numpy", "math"}
NUMERIC_ATTRS = {
    "sqrt", "exp", "log", "log10", "log2", "sin", "cos", "tan", "arcsin", "arccos", "arctan",
    "arctan2", "sinh", "cosh", "tanh", "abs", "absolute", "sign", "floor", "ceil", "round", "clip",
    "where", "maximum", "minimum", "power", "mod", "hypot", "degrees", "radians", "pi", "e", "tau",
    "inf", "heaviside", "sinc", "exp2", "expm1", "log1p", "cbrt", "square", "fmod", "real", "imag",
    "array",
    # the same functions under math's names
    "asin", "acos", "atan", "atan2", "fabs", "pow", "factorial", "comb", "perm", "gamma", "erf",
}
# never callable from a formula, whatever the file binds
FORBIDDEN_CALLS = {"eval", "exec", "open", "compile", "__import__", "getattr", "setattr", "delattr",
                   "globals", "locals", "vars", "input", "breakpoint", "exit", "quit", "help",
                   "memoryview", "type", "object", "super", "classmethod", "staticmethod", "property"}
SAFE_IMPORTS = {"manim", "numpy", "math", "style", "manim_kit"}


def _numeric_attr(module: str, attr: str) -> bool:
    if attr.startswith("_"):
        return False
    if attr in NUMERIC_ATTRS:
        return True
    if module == "math":
        return callable(getattr(math, attr, None)) or isinstance(getattr(math, attr, None), float)
    try:
        import numpy
    except ImportError:  # pragma: no cover
        return False
    return isinstance(getattr(numpy, attr, None), numpy.ufunc)


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


def _scope_walk(node):
    """The nodes of one scope: nested functions, lambdas, classes and
    comprehensions are not entered (their names are their own)."""
    todo = list(ast.iter_child_nodes(node))
    while todo:
        n = todo.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                          ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        todo.extend(ast.iter_child_nodes(n))


def _bound_names(src: Source, lam: ast.Lambda) -> set[str]:
    """Names readable where the lambda is: module-level bindings and
    imports, the enclosing functions' (and lambdas') parameters, and what
    those functions bind before the lambda."""
    out: set[str] = set()
    at = src.span(lam)[0]

    def params(a: ast.arguments):
        for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
            if x is not None:
                out.add(x.arg)

    def binds(scope, before: int | None):
        for n in _scope_walk(scope):
            if before is not None and hasattr(n, "lineno") and src.span(n)[0] >= before:
                continue
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                out.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)
            elif isinstance(n, ast.alias):
                if n.name != "*":
                    out.add((n.asname or n.name).split(".")[0])
            elif isinstance(n, ast.ExceptHandler) and n.name:
                out.add(n.name)

    binds(src.tree, None)  # the module runs before construct() does
    p = src.parent(lam)
    while p is not None:
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params(p.args)
            binds(p, at)
        elif isinstance(p, ast.Lambda):
            params(p.args)
        p = src.parent(p)
    return out


def _imported(src: Source) -> dict[str, str]:
    """Name -> the module it was imported from (`import os` → os: os,
    `from pathlib import Path` → Path: pathlib), for every import in the file."""
    out = {}
    for n in ast.walk(src.tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out[(a.asname or a.name).split(".")[0]] = a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                if a.name != "*":
                    out[a.asname or a.name] = n.module.split(".")[0]
    return out


def _check_calls(src: Source, tree, params: set[str]) -> None:
    imported = _imported(src)
    originals = {(a.asname or a.name): a.name for n in ast.walk(src.tree) if isinstance(n, ast.ImportFrom)
                 for a in n.names}  # `from numpy import savetxt as sin` → savetxt
    # `import numpy as xp`: module names, as opposed to `from numpy import sin`
    aliases = {(a.asname or a.name): a.name for n in ast.walk(src.tree) if isinstance(n, ast.Import)
               for a in n.names if a.name in ("numpy", "math")}

    def module_of(name: str) -> str | None:
        if name in params:
            return None
        m = aliases.get(name) or ({"np": "numpy", "numpy": "numpy", "math": "math"}.get(name)
                                  if name not in imported else None)
        return m

    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            root = n.value
            if not isinstance(root, ast.Name):
                raise EditError(f"{src_text(n)} isn't something a formula may use; edit it in the code")
            mod = module_of(root.id)
            if mod is not None:
                if not _numeric_attr(mod, n.attr):
                    raise EditError(f"{root.id}.{n.attr} isn't a maths function the studio allows in a formula")
            elif root.id in imported and imported[root.id] not in SAFE_IMPORTS:
                raise EditError(f"{root.id}.{n.attr} isn't a maths function the studio allows in a formula")
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                if f.id in FORBIDDEN_CALLS or f.id.startswith("__"):
                    raise EditError(f"{f.id}() isn't a maths function the studio allows in a formula")
                if f.id in imported and imported[f.id] not in SAFE_IMPORTS:
                    raise EditError(f"{f.id}() comes from {imported[f.id]}, which isn't maths "
                                    "the studio allows in a formula")
                if f.id in imported and imported[f.id] in ("numpy", "math") \
                        and not _numeric_attr(imported[f.id], originals.get(f.id, f.id)):
                    raise EditError(f"{f.id} isn't a maths function the studio allows in a formula")
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and module_of(f.value.id) is not None and f.value.id not in params:
                pass  # checked as an attribute above
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                raise EditError(f"{f.value.id}.{f.attr} isn't a maths function the studio allows in a formula")
            else:
                what = f.attr if isinstance(f, ast.Attribute) else type(f).__name__.lower()
                raise EditError(f"calling {what}() isn't something the studio allows in a formula; "
                                "edit it in the code")


def src_text(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover
        return type(node).__name__


def _one_line(text: str) -> None:
    """No newline and no comment: the formula is spliced into one line of a call."""
    if "\n" in text or "\r" in text:
        raise EditError("a formula must be on one line")
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                raise EditError("a formula can't contain a # comment (it would hide the rest of the line)")
    except (tokenize.TokenError, SyntaxError):
        pass  # ast.parse says what is wrong


def _wrapped(text: str) -> bool:
    """Is the whole text one bracketed group `( ... )`?"""
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    try:
        toks = [t for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type == tokenize.OP and t.string in "()[]{}"]
    except (tokenize.TokenError, SyntaxError):
        return False
    for i, t in enumerate(toks):
        depth += 1 if t.string in "([{" else -1
        if depth == 0 and i != len(toks) - 1:
            return False
    return depth == 0


def check_expression(src: Source, lam: ast.Lambda, text: str, api: set[str]) -> ast.expr:
    text = text.strip()
    if not text:
        raise EditError("type a formula")
    _one_line(text)
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
    _check_calls(src, tree.body, params)
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
    if isinstance(body, (ast.Tuple, ast.IfExp)) and not _wrapped(new):
        new = f"({new})"  # keeps `lambda t: (a, b)` one argument of the call
    old = src.text(lam.body)
    if new == old:
        raise EditError("that's the formula already")
    a, b = src.span(lam.body)
    confirm = None
    if obj.get("in_helper"):
        confirm = f"this curve is made inside {obj.get('func')}(): every curve that helper makes changes"
    return Plan([Edit(a, b, new)], f"curve: {old} → {new}", confirm, checks={"curve": True})
