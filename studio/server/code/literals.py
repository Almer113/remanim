"""Tier-2 literal editing (census S5, implication 1; code_spec §2).

In a tier-1 or tier-2 statement every number, string and constant name can
be changed in place, while the structure around it stays as written:
`blob.get_top() + UP * 1.4` → `... * 1.6`, `0.7 if k < 3 else 0.45` →
`... else 0.5`, `for level in [0.5, 1, 2]` → `[0.5, 1, 3]`. The code peek
shows these values and lets the user type a new one; the replay checks
that the scene still runs.

Module- and class-level constants (`LEVELS = [...]`, `TARGET = 6.0`) count
too: a loop over a named constant is edited where the constant is made.
"""

from __future__ import annotations

import ast

from .census import Census
from .source import Source
from .splice import Edit, EditError, fmt, number_of

# Names that are code, not values: editing them would change what the code does.
NOT_VALUES = {"self", "True", "False", "None", "DEGREES", "PI", "TAU"}  # units, not choices


def number_text(src: Source, node, text: str) -> str:
    """`text` as it can replace `node`: a negative number that is the base
    of `**` needs brackets (`-3 ** 2` is -(3 ** 2)), as it does after
    `.` (`(-3).real`)."""
    if not text.lstrip().startswith("-"):
        return text
    par = src.parent(node)
    if isinstance(par, ast.BinOp) and isinstance(par.op, ast.Pow) and par.left is node:
        return f"({text})"
    if isinstance(par, ast.Attribute) and par.value is node:
        return f"({text})"
    return text


def _is_docstring(body: list, s) -> bool:
    return (body and s is body[0] and isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
            and isinstance(s.value.value, str))


def _value_nodes(src: Source, root) -> list:
    """Numbers (with their sign), strings and CONSTANT names inside `root`,
    outermost first; never inside an f-string, a lambda's parameters or a
    nested def."""
    out = []

    def walk(n):
        if isinstance(n, (ast.JoinedStr, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(n, ast.UnaryOp) and number_of(n) is not None:
            out.append(n)
            return
        if isinstance(n, ast.Constant):
            v = n.value
            if (isinstance(v, (int, float)) and not isinstance(v, bool)) or isinstance(v, str):
                out.append(n)
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in NOT_VALUES \
                and n.id.isupper() and len(n.id) > 1:
            out.append(n)
            return
        if isinstance(n, ast.Attribute):
            walk(n.value)  # `np.pi` and `self.X` are code; their receiver may hold values
            return
        if isinstance(n, ast.keyword):
            walk(n.value)
            return
        if isinstance(n, ast.Lambda):
            walk(n.body)
            return
        for c in ast.iter_child_nodes(n):
            walk(c)

    walk(root)
    return out


def _parts(s) -> list:
    """The parts of a statement that belong to its own line(s): a compound
    statement's header, or the whole of a simple one."""
    if isinstance(s, (ast.For, ast.AsyncFor)):
        return [s.iter]
    if isinstance(s, (ast.With, ast.AsyncWith)):
        return [i.context_expr for i in s.items]
    if isinstance(s, (ast.If, ast.While)):
        return [s.test]
    if isinstance(s, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return [s.value] if s.value is not None else []
    if isinstance(s, (ast.Expr, ast.Return)):
        return [s.value] if s.value is not None else []
    return []


def _bodies(s) -> list:
    if isinstance(s, (ast.For, ast.AsyncFor, ast.While, ast.If)):
        return s.body + s.orelse
    if isinstance(s, (ast.With, ast.AsyncWith)):
        return s.body
    return []


def find_literals(src: Source, census: Census) -> list[dict]:
    """Every editable value in the file: {span, text, kind, where, line}.
    `span` is in the AST's own units (UTF-8 columns), as edits use them."""
    if not src.ok:
        return []
    out: list[dict] = []
    tiers = census.lines

    def take(node, stmt, where: str, scope: str):
        a = getattr(node, "lineno", None)
        if a is None:
            return
        kind = ("number" if number_of(node) is not None
                else "string" if isinstance(node, ast.Constant) else "name")
        if kind == "string" and node.end_lineno != node.lineno:
            return  # multi-line strings: edited as text in the Inspector, not inline
        out.append({"span": [node.lineno, node.col_offset, node.end_lineno, node.end_col_offset],
                    "text": src.text(node), "kind": kind, "line": stmt.lineno, "where": where,
                    "scope": scope})

    def stmts(body, where: str, scope: str):
        for s in body:
            if _is_docstring(body, s):
                continue
            tier = tiers.get(s.lineno, 3)
            if tier <= 2:
                for p in _parts(s):
                    for n in _value_nodes(src, p):
                        take(n, s, where, scope)
            stmts(_bodies(s), where, scope)

    calc = Census(set(), set())
    for node in src.tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None \
                and calc.expr_tier(node.value) <= 2:
            for n in _value_nodes(src, node.value):
                take(n, node, "<module>", "constant")
        elif isinstance(node, ast.FunctionDef):
            stmts(node.body, node.name, "helper")
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.Assign, ast.AnnAssign)) and m.value is not None \
                        and calc.expr_tier(m.value) <= 2:
                    for n in _value_nodes(src, m.value):
                        take(n, m, node.name, "constant")
                elif isinstance(m, ast.FunctionDef):
                    stmts(m.body, f"{node.name}.{m.name}", "method")
    return out


def plan_literal(src: Source, census: Census, span, value: dict):
    """Replace the value at `span` (as find_literals gave it)."""
    from .planner import Plan, _name_or_refuse, _string_like
    if not src.ok:
        raise EditError("the file doesn't parse")
    try:
        span = [int(x) for x in span]
    except (TypeError, ValueError):
        raise EditError("not a position in the file") from None
    lit = next((x for x in find_literals(src, census) if x["span"] == span), None)
    if lit is None:
        raise EditError("that value isn't there any more, or it is in code the studio can't edit")
    node = _node_at(src, span)
    old = lit["text"]
    if "number" in value:
        if lit["kind"] != "number":
            raise EditError(f"{old} isn't a number")
        try:
            n = float(value["number"])
        except (TypeError, ValueError):
            raise EditError(f"not a number: {value['number']!r}") from None
        if not -float("inf") < n < float("inf"):
            raise EditError("not a finite number")
        text = number_text(src, node, fmt(n, old))
    elif "string" in value:
        if lit["kind"] != "string":
            raise EditError(f"{old} isn't a string")
        s = str(value["string"])
        if "\x00" in s or any(0xD800 <= ord(c) <= 0xDFFF for c in s):
            raise EditError("that text can't be written to a Python file")
        text = _string_like(src, node, s.replace("\r\n", "\n").replace("\r", "\n"))
    elif "name" in value:
        if lit["kind"] != "name":
            raise EditError(f"{old} isn't a name")
        text = _name_or_refuse(value["name"], "name")
    else:
        raise EditError("unknown value kind")
    if text == old:
        raise EditError("that's the value already")
    a, b = src.span(node)
    confirm = None
    if lit["scope"] == "helper" or lit["scope"] == "method" and not lit["where"].endswith(".construct"):
        # a scene method other than construct() is a helper too: it may run many times
        confirm = f"line {lit['line']} is inside the helper {lit['where']}(): this changes every use of it"
    elif lit["scope"] == "constant":
        users = _uses(src, node)
        if users:
            confirm = (f"this value is part of a constant read on line{'s' if len(users) > 1 else ''} "
                       f"{', '.join(map(str, users))}: they all change")
    where = "" if lit["scope"] != "constant" else " (a constant)"
    return Plan([Edit(a, b, text)], f"line {span[0]}: {old} → {text}{where}", confirm,
                checks={"literal": text})


def _node_at(src: Source, span: list[int]):
    for n in ast.walk(src.tree):
        if [getattr(n, "lineno", None), getattr(n, "col_offset", None),
                getattr(n, "end_lineno", None), getattr(n, "end_col_offset", None)] == span \
                and isinstance(n, (ast.Constant, ast.UnaryOp, ast.Name)):
            return n
    raise EditError("that value isn't there any more")


def _uses(src: Source, node) -> list[int]:
    """Lines that read the constant `node` is part of (module or class level)."""
    stmt = node
    while stmt is not None and not isinstance(src.parent(stmt), (ast.Module, ast.ClassDef)):
        stmt = src.parent(stmt)
    if stmt is None:
        return []
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
    names = {t.id for t in targets if isinstance(t, ast.Name)}
    lines = set()
    for n in ast.walk(src.tree):
        if isinstance(n, ast.Name) and n.id in names and isinstance(n.ctx, ast.Load):
            lines.add(n.lineno)
        elif isinstance(n, ast.Attribute) and n.attr in names and isinstance(n.ctx, ast.Load) \
                and isinstance(n.value, ast.Name) and n.value.id in ("self", "cls"):
            lines.add(n.lineno)
    return sorted(lines)


def plan_literals(src: Source, census: Census, changes: list):
    """Several values at once (the parts of one MathTex): one edit, one undo step."""
    from .planner import Plan
    if not isinstance(changes, list) or not changes:
        raise EditError("nothing to change")
    if len(changes) > 50:
        raise EditError("too many changes at once")
    plans = []
    for c in changes:
        if not isinstance(c, dict):
            raise EditError("bad change")
        try:
            plans.append(plan_literal(src, census, c.get("span"), c.get("value") or {}))
        except EditError as e:
            if "already" in str(e) and len(changes) > 1:
                continue  # a part left as it was
            raise
    if not plans:
        raise EditError("that's the value already")
    spans = sorted((e.start, e.end) for p in plans for e in p.edits)
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise EditError("two of the changes overlap")
    confirm = next((p.confirm for p in plans if p.confirm), None)
    return Plan([e for p in plans for e in p.edits], "; ".join(p.note for p in plans), confirm,
                checks={"literal": True})
