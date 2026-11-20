"""Trace cache (Phase 6 step 2): a scene's trace, kept for the same code.

A trace is plain data (clips, narration, duration), so the same bytes give
the same trace. The key covers everything a trace depends on that can
change without the file changing:

- the file's bytes and the bytes of every local module it imported
  (`style.py`, `manim_kit.py`, ...), as the engine reports them;
- `manim.cfg` next to the file and in the project root;
- the engine's own code, the Manim and Python versions, and the quality.

Kept in memory (undo and redo come back to earlier bytes) and on disk
under media/studio_cache/traces (a reopen). A trace that ended in an error
is never kept: some errors (a TTS stall) don't come back. Any doubt costs
a retrace, never a wrong trace: a missing or unreadable entry is a miss.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "media" / "studio_cache" / "traces"
MEMORY = 64        # traces kept in memory
DISK_LIMIT = 2000  # files kept on disk; the oldest go first


def _engine_digest() -> str:
    h = hashlib.sha256()
    for p in sorted((Path(__file__).parent / "engine").glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    try:
        from importlib.metadata import version
        h.update(version("manim").encode())
    except Exception:  # noqa: BLE001
        h.update(b"manim?")
    h.update(sys.version.encode())
    return h.hexdigest()


ENGINE = _engine_digest()


def _read(p: Path) -> bytes:
    try:
        return p.read_bytes()
    except OSError:
        return b"<missing>"


def deps_digest(path: Path, deps: list[str]) -> str:
    """The local modules the file imported, and the config files."""
    h = hashlib.sha256()
    files = sorted({str(Path(d).resolve()) for d in deps})
    for cfg in (path.parent / "manim.cfg", ROOT / "manim.cfg"):
        files.append(str(cfg))
    for f in files:
        h.update(f.encode("utf-8", "replace"))
        h.update(_read(Path(f)))
    return h.hexdigest()


def scene_text(tree, data: bytes, scene: str, scenes: list[str]) -> bytes:
    """The parts of the file a scene's trace can depend on: every top-level
    statement except the classes of the *other* scenes (unless this scene
    inherits from them), each with its position, because the trace records
    line numbers. An edit inside another scene, or below this one without
    moving it, keeps this scene's trace."""
    import ast
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    keep, todo = set(), [scene]
    while todo:  # this scene and the classes of this file it inherits from
        name = todo.pop()
        if name in keep or name not in classes:
            continue
        keep.add(name)
        todo += [b.id for b in classes[name].bases if isinstance(b, ast.Name)]
    others = set(scenes) - keep
    lines = data.splitlines(keepends=True)
    out = []
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name in others:
            continue
        first = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
        out.append(f"@{first}:{n.col_offset}\n".encode())
        out.append(b"".join(lines[first - 1:n.end_lineno]))
    return b"".join(out)


def key(data: bytes, deps: str, scene: str, quality: str = "l") -> str:
    h = hashlib.sha256()
    for part in (ENGINE.encode(), deps.encode(), quality.encode(), scene.encode("utf-8"), data):
        h.update(len(part).to_bytes(8, "little"))
        h.update(part)
    return h.hexdigest()


class TraceCache:
    def __init__(self, folder: Path = DIR):
        self.dir = folder
        self.mem: OrderedDict[str, dict] = OrderedDict()
        self.hits = self.misses = 0

    def get(self, k: str | None) -> dict | None:
        if not k:
            return None
        tr = self.mem.get(k)
        if tr is None:
            try:
                tr = json.loads((self.dir / f"{k}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                tr = None
            if not isinstance(tr, dict) or "events" not in tr:
                self.misses += 1
                return None
            self._remember(k, tr)
        else:
            self.mem.move_to_end(k)
        self.hits += 1
        return json.loads(json.dumps(tr))  # callers may annotate it: never share the cached one

    def put(self, k: str | None, tr: dict):
        if not k or not isinstance(tr, dict) or tr.get("error") or "events" not in tr:
            return
        self._remember(k, json.loads(json.dumps(tr)))
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.dir / f"{k}.{os.getpid()}.tmp"
            tmp.write_text(json.dumps(tr), encoding="utf-8")
            os.replace(tmp, self.dir / f"{k}.json")
            self._trim()
        except (OSError, TypeError, ValueError):
            pass  # a cache that can't be written is only slower

    def _remember(self, k: str, tr: dict):
        self.mem[k] = tr
        self.mem.move_to_end(k)
        while len(self.mem) > MEMORY:
            self.mem.popitem(last=False)

    _puts = 0

    def _trim(self):
        self._puts += 1
        if self._puts % 50:
            return
        try:
            files = sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        except OSError:
            return
        for p in files[:max(0, len(files) - DISK_LIMIT)]:
            try:
                p.unlink()
            except OSError:
                pass


CACHE = TraceCache()
