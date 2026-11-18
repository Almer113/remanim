"""The scene file as exact bytes plus an AST index.

Everything here works on bytes: AST columns are UTF-8 byte offsets, so a
span is a slice of `data` and an edit is a byte splice (code_spec.md §1).
No Manim import: this module must stay fast and testable on its own.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

SIMPLE_STATEMENTS = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.Return)


@dataclass(frozen=True)
class Span:
    """A source range as Python reports it (1-based lines, byte columns)."""
    line: int
    col: int
    end_line: int
    end_col: int

    @classmethod
    def of(cls, node) -> "Span":
        return cls(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)

    def as_list(self) -> list[int]:
        return [self.line, self.col, self.end_line, self.end_col]


class Source:
    def __init__(self, data: bytes):
        self.data = data
        self.line_starts = [0]
        for i, b in enumerate(data):
            if b == 0x0A:
                self.line_starts.append(i + 1)
        self.tree: ast.Module | None = None
        self.error: SyntaxError | None = None
        try:
            self.tree = ast.parse(data)
        except SyntaxError as e:
            self.error = e
        self._parents: dict[int, ast.AST] | None = None

    # -- positions -----------------------------------------------------------
    @property
    def ok(self) -> bool:
        return self.tree is not None

    @property
    def newline(self) -> str:
        """The file's line ending (CRLF in this repo)."""
        i = self.data.find(b"\n")
        return "\r\n" if i > 0 and self.data[i - 1:i] == b"\r" else "\n"

    def offset(self, line: int, col: int) -> int:
        return self.line_starts[line - 1] + col

    def span(self, node) -> tuple[int, int]:
        return (self.offset(node.lineno, node.col_offset),
                self.offset(node.end_lineno, node.end_col_offset))

    def text(self, node) -> str:
        a, b = self.span(node)
        return self.data[a:b].decode("utf-8")

    def line_text(self, line: int) -> str:
        a = self.line_starts[line - 1]
        b = self.line_starts[line] if line < len(self.line_starts) else len(self.data)
        return self.data[a:b].decode("utf-8").rstrip("\r\n")

    def line_end(self, line: int) -> int:
        """Byte offset just after the line's newline (or end of file)."""
        return self.line_starts[line] if line < len(self.line_starts) else len(self.data)

    def indent_of(self, line: int) -> str:
        t = self.line_text(line)
        return t[: len(t) - len(t.lstrip(" \t"))]

    # -- tree lookups ----------------------------------------------------------
    def parent(self, node) -> ast.AST | None:
        if self._parents is None:
            self._parents = {}
            for p in ast.walk(self.tree):
                for c in ast.iter_child_nodes(p):
                    self._parents[id(c)] = p
        return self._parents.get(id(node))

    def statement_at(self, line: int):
        """The innermost simple statement covering `line`."""
        best = None
        for node in ast.walk(self.tree):
            if isinstance(node, SIMPLE_STATEMENTS) and node.lineno <= line <= node.end_lineno:
                if best is None or node.lineno >= best.lineno:
                    best = node
        return best

    def find_call(self, span: Span) -> ast.Call | None:
        """The Call node at `span`, as reported by co_positions().

        Python reports a method call `recv.name(...)` from the method name
        onwards when the receiver spans lines, and from the receiver start
        otherwise; both are accepted. The end must match exactly."""
        if self.tree is None:
            return None
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call) or \
                    (node.end_lineno, node.end_col_offset) != (span.end_line, span.end_col):
                continue
            if (node.lineno, node.col_offset) == (span.line, span.col):
                return node
            f = node.func
            if isinstance(f, ast.Attribute) and f.end_lineno == span.line and \
                    f.end_col_offset - len(f.attr) == span.col:
                return node
        return None

    @staticmethod
    def keyword(call: ast.Call, name: str) -> ast.keyword | None:
        for k in call.keywords:
            if k.arg == name:
                return k
        return None

    @staticmethod
    def call_name(call: ast.Call) -> str | None:
        f = call.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
        return None
