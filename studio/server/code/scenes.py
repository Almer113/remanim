"""Scene classes as a whole: add, delete, rename (Phase 7 step 3).

Each is one byte-splice plan, verified by tracing (the project does that):
an added scene must trace, a renamed one must time out as before, and after a
delete the file must still run. The file's `SCENES` list and a docstring
"Render order: A, B, C" line follow the change when they list the scenes.
"""

from __future__ import annotations

import ast
import keyword
import re

from .planner import Plan, _string_like
from .source import Source
from .splice import Edit, EditError


def _class(src: Source, name: str) -> ast.ClassDef:
    for node in src.tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise EditError(f"no class {name} in the file")


def _module_names(src: Source) -> set[str]:
    out = set()
    for node in src.tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for t in node.targets if isinstance(node, ast.Assign) else [node.target]:
                out.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in node.names if a.name != "*")
    return out


def _check_new_name(src: Source, name, taken: set[str]) -> str:
    name = str(name or "").strip()
    if keyword.iskeyword(name):
        raise EditError(f"{name} is a word Python reserves; pick another name")
    if not name.isidentifier() or not name.isascii():
        raise EditError(f"not a class name: {name!r} (letters, digits and _, not starting with a digit)")
    if name in _module_names(src):
        raise EditError(f"the file already defines {name}")
    if name in taken:
        raise EditError(f"{name} is a Manim or project name; pick another")
    return name


def _refs(src: Source, name: str, skip: ast.AST | None) -> list[int]:
    """Lines where code names `name` (outside `skip`'s own subtree)."""
    inside = {id(n) for n in ast.walk(skip)} if skip is not None else set()
    return sorted({n.lineno for n in ast.walk(src.tree)
                   if isinstance(n, ast.Name) and n.id == name and id(n) not in inside})


def _scenes_list(src: Source):
    for node in src.tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "SCENES" and isinstance(node.value, (ast.List, ast.Tuple)):
            return node
    return None


def _list_edits(src: Source, op: str, name: str, new: str | None, after: str | None) -> tuple[list[Edit], list[str]]:
    """Edits to SCENES; also the names it listed before (for the docstring)."""
    node = _scenes_list(src)
    if node is None:
        return [], []
    elts = node.value.elts
    if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts):
        raise EditError(f"SCENES (line {node.lineno}) isn't a plain list of names; change it in the code")
    names = [e.value for e in elts]
    spans = [src.span(e) for e in elts]
    tup = isinstance(node.value, ast.Tuple)
    # one name per line (each with its own comment, perhaps): edit whole lines, so
    # every comment stays with its name
    def tail(e) -> str:
        return src.after(e.end_lineno, e.end_col_offset).strip()

    def alone(e) -> bool:  # nothing else on its line but a comma and a comment
        t = tail(e)
        t = t[1:].lstrip() if t.startswith(",") else t
        return e.lineno == e.end_lineno and not src.before(e.lineno, e.col_offset).strip() \
            and (t == "" or t.startswith("#"))
    per_line = len({e.lineno for e in elts}) == len(elts) and all(alone(e) for e in elts)

    def comma_after(i: int) -> bool:
        return tail(elts[i]).startswith(",")
    if op == "add":
        if not elts:
            a = src.span(node.value)[0] + 1
            # ("C") would be a string, not a tuple
            return [Edit(a, a, _string_like(src, None, new) + ("," if tup else ""))], names
        i = names.index(after) if after in names else len(names) - 1
        q = _string_like(src, elts[i], new)
        if per_line:
            e = elts[i]
            line = src.indent_of(e.lineno) + q + ("," if comma_after(i) else "") + src.newline
            fix = [] if comma_after(i) else [Edit(spans[i][1], spans[i][1], ",")]
            at = src.line_end(e.lineno)
            return fix + [Edit(at, at, line)], names
        return [Edit(spans[i][1], spans[i][1], ", " + q)], names
    if name not in names:
        return [], names
    i = names.index(name)
    if op == "rename":
        return [Edit(*spans[i], _string_like(src, elts[i], new))], names
    if len(names) == 1:  # the list empties: () or [] (a lone name's comma can't stay behind)
        return [Edit(*src.span(node.value), "()" if tup else "[]")], names
    if per_line:  # the whole line, comment and all
        e = elts[i]
        return [Edit(src.line_starts[e.lineno - 1], src.line_end(e.lineno), "")], names
    # delete: the name and one comma
    if i < len(names) - 1:
        return [Edit(spans[i][0], spans[i + 1][0], "")], names
    return [Edit(spans[i - 1][1], spans[i][1], "")], names


def _doc_edits(src: Source, order: list[str], op: str, name: str, new: str | None, after: str | None) -> list[Edit]:
    """The docstring's "Render order: A, B, C" (perhaps wrapped), when it lists `order`."""
    doc = ast.get_docstring(src.tree, clean=False)
    if not doc or not order or not isinstance(src.tree.body[0], ast.Expr):
        return []
    d0, d1 = src.span(src.tree.body[0])
    text = src.data[d0:d1].decode("utf-8")
    pat = re.compile(r",\s+".join(r"\b(" + re.escape(n) + r")\b" for n in order))
    # only a list that follows a label ("Render order: A, B", "Beats: A, B"), never
    # prose that happens to name a scene ("Intro scene for the Euler video")
    label = re.compile(r"(?i)\b(?:render\s+order|order|beats|scenes)\s*:\s*$")
    found = [m for m in pat.finditer(text) if label.search(text[:m.start()])]
    if len(found) != 1:
        return []
    m = found[0]

    def at(i: int) -> int:
        return d0 + len(text[:i].encode("utf-8"))
    g = {n: k + 1 for k, n in enumerate(order)}
    if op == "add":
        k = g.get(after, len(order))
        return [Edit(at(m.end(k)), at(m.end(k)), ", " + new)]
    if name not in g:
        return []
    k = g[name]
    if op == "rename":
        return [Edit(at(m.start(k)), at(m.end(k)), new)]
    if k < len(order):
        return [Edit(at(m.start(k)), at(m.start(k + 1)), "")]
    if k > 1:
        return [Edit(at(m.end(k - 1)), at(m.end(k)), "")]
    return []


def _order_edits(src: Source, defined: list[str], op: str, name: str = "", new: str | None = None,
                 after: str | None = None) -> tuple[list[Edit], str]:
    edits, listed = _list_edits(src, op, name, new, after)
    doc = _doc_edits(src, listed or defined, op, name, new, after)
    also = [w for w, e in (("SCENES", edits), ("the docstring's render order", doc)) if e]
    return edits + doc, (" (and " + " and ".join(also) + ")") if also else ""


# -- add ----------------------------------------------------------------------------------
def _class_attr(cls: ast.ClassDef, attr: str):
    for st in cls.body:
        if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == attr for t in st.targets):
            return st
        if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.target.id == attr:
            return st
    return None


def _first_call(fn: ast.FunctionDef | None, name: str) -> bool:
    if fn is None or not fn.body:
        return False
    st = fn.body[0]
    return isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name) \
        and st.value.func.id == name and not st.value.args and not st.value.keywords


def _class_end(src: Source, cls: ast.ClassDef) -> int:
    """The class's last line, counting comment lines indented under it that come
    after its last statement (commented-out code, a note): they belong to it."""
    deep = len(src.indent_of(cls.lineno))
    last = ln = cls.end_lineno
    while ln < len(src.line_starts):
        ln += 1
        t = src.line_text(ln)
        if not t.strip():
            continue
        if t.lstrip().startswith("#") and len(src.indent_of(ln)) > deep:
            last = ln
            continue
        break
    return last


def plan_scene_add(src: Source, current: str, name, where: str, defined: list[str], taken: set[str]) -> Plan:
    """A new scene class after `current` (where="after") or after the file's
    last scene class (where="end"): the same base classes as `current`, its
    TARGET and VOICE lines if it sets them itself, and a construct() holding
    only what the template starts with (apply_background()) or `pass`."""
    name = _check_new_name(src, name, taken)
    cur = _class(src, current)
    if where not in ("after", "end"):
        raise EditError(f"where must be 'after' or 'end', not {where!r}")
    nl = src.newline
    unit = src.indent_of(cur.body[0].lineno)[len(src.indent_of(cur.lineno)):] or "    "
    base = src.indent_of(cur.lineno)
    bases = ", ".join(src.text(b) for b in cur.bases) + (", " if cur.bases and cur.keywords else "") \
        + ", ".join(src.text(k) for k in cur.keywords)
    lines = [f"{base}class {name}({bases}):" if bases else f"{base}class {name}:"]
    copied = []
    found = [(st, attr) for attr in ("TARGET", "VOICE") for st in [_class_attr(cur, attr)]
             if st is not None and st.lineno == st.end_lineno]
    for st, attr in sorted(found, key=lambda x: x[0].lineno):  # in the file's order
        lines.append(base + unit + src.text(st))
        copied.append(attr)
    if copied:
        lines.append("")
    fn = next((b for b in cur.body if isinstance(b, ast.FunctionDef) and b.name == "construct"), None)
    lines.append(f"{base}{unit}def construct(self):")
    lines.append(base + unit * 2 + ("apply_background()" if _first_call(fn, "apply_background") else "pass"))
    text = nl.join(lines) + nl

    if where == "after":
        anchor = cur
    else:
        anchor = [n for n in src.tree.body if isinstance(n, ast.ClassDef) and n.name in defined][-1]
    end = src.line_end(_class_end(src, anchor))
    lead = nl if end == len(src.data) and not src.data.endswith(b"\n") else ""
    edits = [Edit(end, end, lead + nl + nl + text)]
    order_edits, also = _order_edits(src, defined, "add", new=name,
                                     after=current if where == "after" else None)
    note = f"scene {name} added " + (f"after {current}" if where == "after" else "at the end") \
        + (f", with {current}'s {' and '.join(copied)}" if copied else "") + also
    return Plan(edits + order_edits, note, checks={"new_scene": name})


# -- delete -------------------------------------------------------------------------------
def _class_lines(src: Source, cls: ast.ClassDef) -> tuple[int, int]:
    """Byte range of the class (decorators included) and the blank lines before it."""
    first = min([cls.lineno] + [d.lineno for d in cls.decorator_list])
    start_line = first
    while start_line > 1 and not src.line_text(start_line - 1).strip():
        start_line -= 1
    a = src.line_starts[start_line - 1]
    if start_line == 1:  # nothing before it: keep the blank lines after it instead
        a = src.line_starts[first - 1]
    return a, src.line_end(_class_end(src, cls))


def plan_scene_delete(src: Source, name: str, defined: list[str]) -> Plan:
    cls = _class(src, name)
    if [n for n in defined if n != name] == []:
        raise EditError("it's the file's only scene")
    refs = _refs(src, name, cls)
    if refs:
        raise EditError(f"other code names {name} (line {', '.join(map(str, refs))}); change that first")
    a, b = _class_lines(src, cls)
    order_edits, also = _order_edits(src, defined, "delete", name=name)
    return Plan([Edit(a, b, "")] + order_edits, f"scene {name} deleted" + also,
                checks={"gone_scene": name})


# -- rename -------------------------------------------------------------------------------
def plan_scene_rename(src: Source, name: str, new, defined: list[str], taken: set[str]) -> Plan:
    cls = _class(src, name)
    new = _check_new_name(src, new, taken)
    refs = _refs(src, name, None)
    if refs:
        raise EditError(f"code names {name} (line {', '.join(map(str, refs))}); rename it in the code")
    a = src.offset(cls.lineno, cls.col_offset)
    m = re.compile(rb"class\s+").match(src.data, a)
    if m is None or not src.data.startswith(name.encode("utf-8"), m.end()):
        raise EditError(f"can't find the name in 'class {name}' (line {cls.lineno})")
    edits = [Edit(m.end(), m.end() + len(name.encode("utf-8")), new)]
    order_edits, also = _order_edits(src, defined, "rename", name=name, new=new)
    return Plan(edits + order_edits, f"scene {name} renamed to {new}" + also,
                checks={"renamed": [name, new]})
