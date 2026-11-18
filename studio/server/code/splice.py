"""Byte splices and value formatting (code_spec.md §1, §3)."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path

from .source import Source


@dataclass(frozen=True)
class Edit:
    start: int  # byte offsets into the file
    end: int
    text: str

    def as_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "text": self.text}


class EditError(Exception):
    """An edit the studio refuses to make; the message says why."""


def apply(data: bytes, edits: list[Edit]) -> bytes:
    """Apply non-overlapping edits. Offsets refer to `data`."""
    out, pos = [], 0
    for e in sorted(edits, key=lambda e: (e.start, e.end)):
        if e.start < pos:
            raise EditError("overlapping edits")
        out.append(data[pos:e.start])
        out.append(e.text.encode("utf-8"))
        pos = e.end
    out.append(data[pos:])
    return b"".join(out)


def inverse(data: bytes, edits: list[Edit]) -> list[Edit]:
    """Edits that turn apply(data, edits) back into data."""
    inv, shift = [], 0
    for e in sorted(edits, key=lambda e: (e.start, e.end)):
        new_len = len(e.text.encode("utf-8"))
        start = e.start + shift
        inv.append(Edit(start, start + new_len, data[e.start:e.end].decode("utf-8")))
        shift += new_len - (e.end - e.start)
    return inv


def write_atomic(path: Path, data: bytes) -> None:
    """Never write a file that doesn't parse; replace it in one step."""
    if not Source(data).ok:
        raise EditError("the result would not parse")
    tmp = path.with_name(path.name + ".studio-tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# -- numbers -----------------------------------------------------------------
def fmt(v: float, like: str | None = None) -> str:
    """Shortest decimal form, rounded to 4 places, in the style of `like`:
    "0.5" stays a decimal ("1.0" never becomes "1"); "2" stays whole
    when the value is whole; ".5" keeps its bare point."""
    v = round(float(v), 4)
    if v == 0:
        v = 0.0  # no "-0"
    keep_point = like is not None and "." in like
    s = None
    for d in range(1 if keep_point else 0, 5):
        cand = f"{v:.{d}f}"
        if abs(float(cand) - v) < 1e-9:
            s = cand
            break
    if s is None:
        s = f"{v:.4f}".rstrip("0")
    if like is not None and like.lstrip("-").startswith(".") and s.lstrip("-").startswith("0."):
        s = s.replace("0.", ".", 1)
    if like is not None and like.endswith(".") and s.endswith(".0"):
        s = s[:-1]
    return s


def number_of(node) -> float | None:
    """The value of a numeric literal (`2`, `-0.5`, `+1`), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = number_of(node.operand)
        if v is not None:
            return -v if isinstance(node.op, ast.USub) else v
    return None


def set_number(src: Source, node, value: float) -> Edit:
    """Replace a numeric literal, keeping its written style."""
    a, b = src.span(node)
    old = src.text(node)
    return Edit(a, b, fmt(value, old.lstrip("+-")))


# -- keyword arguments --------------------------------------------------------
def set_keyword(src: Source, call: ast.Call, name: str, value: str | None) -> Edit:
    """Set, add or (value=None) remove `name=` on `call`. Only the tokens of
    that argument change: an added keyword goes after the last argument,
    on the same line when the call fits on one line."""
    kw = Source.keyword(call, name)
    if kw is not None:
        if value is not None:
            a, b = src.span(kw.value)
            return Edit(a, b, value)
        return _remove_argument(src, call, kw)
    if value is None:
        raise EditError(f"{name}= is not set")
    args = list(call.args) + list(call.keywords)
    if not args:
        # `f()` -> `f(name=value)`: insert before the closing paren
        end = src.offset(call.end_lineno, call.end_col_offset) - 1
        return Edit(end, end, f"{name}={value}")
    last = max(args, key=lambda n: (n.end_lineno, n.end_col_offset))
    _, at = src.span(last)
    if call.lineno == call.end_lineno:
        return Edit(at, at, f", {name}={value}")
    # multi-line call: one argument per line? then add a line in that style
    if last.lineno > call.lineno and _one_per_line(call, args):
        indent = src.indent_of(last.lineno)
        trailing = src.data[at:src.offset(call.end_lineno, call.end_col_offset) - 1]
        has_comma = trailing.lstrip().startswith(b",")
        line_end = src.line_end(last.end_lineno)
        nl = src.newline
        if has_comma:
            return Edit(line_end, line_end, f"{indent}{name}={value},{nl}")
        return Edit(at, at, f",{nl}{indent}{name}={value}")
    return Edit(at, at, f", {name}={value}")


def _one_per_line(call, args) -> bool:
    lines = [a.lineno for a in args]
    return len(set(lines)) == len(lines) and all(a.lineno > call.lineno for a in args)


def _remove_argument(src: Source, call: ast.Call, kw: ast.keyword) -> Edit:
    args = sorted(list(call.args) + list(call.keywords), key=lambda n: (n.lineno, n.col_offset))
    i = next(j for j, n in enumerate(args) if n is kw)
    a, b = src.span(kw)
    # alone on its own line(s), as in a one-per-line call: drop the lines
    first = src.line_text(kw.lineno)
    last = src.line_text(kw.end_lineno)
    if kw.lineno > call.lineno and first[: kw.col_offset].strip() == "" and             last[kw.end_col_offset:].strip() in ("", ",") and kw.end_lineno < call.end_lineno:
        if i == len(args) - 1 and last[kw.end_col_offset:].strip() == "" and i > 0:
            # last argument without a trailing comma: remove ",<nl>  kw"
            _, prev_end = src.span(args[i - 1])
            return Edit(prev_end, b, "")
        return Edit(src.line_starts[kw.lineno - 1], src.line_end(kw.end_lineno), "")
    if i > 0:
        _, prev_end = src.span(args[i - 1])
        return Edit(prev_end, b, "")  # ", name=value"
    if len(args) > 1:
        nxt, _ = src.span(args[1])
        return Edit(a, nxt, "")  # "name=value, "
    close = src.offset(call.end_lineno, call.end_col_offset) - 1
    return Edit(a, close, "")
