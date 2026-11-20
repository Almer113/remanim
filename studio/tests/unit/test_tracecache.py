"""Phase 6 step 2: the trace cache's key and store."""

from studio.server import tracecache
from studio.server.tracecache import TraceCache, deps_digest, key

TRACE = {"name": "A", "events": [{"kind": "wait", "start": 0, "duration": 1}], "duration": 1, "error": None}


def test_key_changes_with_every_part(tmp_path):
    base = key(b"x = 1", "d", "A", "l")
    assert key(b"x = 1", "d", "A", "l") == base
    assert key(b"x = 2", "d", "A", "l") != base
    assert key(b"x = 1", "e", "A", "l") != base
    assert key(b"x = 1", "d", "B", "l") != base
    assert key(b"x = 1", "d", "A", "h") != base
    # parts can't run into each other
    assert key(b"1", "d", "A", "l") != key(b"", "d", "A1", "l")


def test_deps_digest_follows_module_bytes_and_config(tmp_path):
    scene = tmp_path / "s.py"
    scene.write_text("x = 1")
    dep = tmp_path / "style.py"
    dep.write_text("A = 1")
    d1 = deps_digest(scene, [str(dep)])
    assert deps_digest(scene, [str(dep)]) == d1
    dep.write_text("A = 2")
    d2 = deps_digest(scene, [str(dep)])
    assert d2 != d1
    (tmp_path / "manim.cfg").write_text("[CLI]\nframe_rate = 30\n")
    assert deps_digest(scene, [str(dep)]) != d2


def test_store_round_trip_disk_and_copies(tmp_path):
    c = TraceCache(tmp_path)
    c.put("k1", TRACE)
    got = c.get("k1")
    assert got == TRACE
    got["events"].append("changed")  # a caller's change never reaches the cache
    assert c.get("k1") == TRACE
    fresh = TraceCache(tmp_path)  # a new process: from disk
    assert fresh.get("k1") == TRACE


def test_errors_and_junk_are_never_kept(tmp_path):
    c = TraceCache(tmp_path)
    c.put("bad", {**TRACE, "error": {"message": "TTS stalled"}})
    assert c.get("bad") is None
    c.put(None, TRACE)
    assert c.get(None) is None
    (tmp_path / "junk.json").write_text("{not json")
    assert c.get("junk") is None
    (tmp_path / "other.json").write_text('{"no": "events"}')
    assert c.get("other") is None


def test_memory_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(tracecache, "MEMORY", 3)
    c = TraceCache(tmp_path)
    for i in range(6):
        c.put(f"k{i}", TRACE)
    assert len(c.mem) == 3 and "k5" in c.mem and "k0" not in c.mem


def test_engine_digest_is_stable():
    assert tracecache._engine_digest() == tracecache.ENGINE


SRC = b'''from manim import *

R = 1


def helper(m):
    return m.shift(UP)


class Base(Scene):
    def setup(self):
        self.c = Circle(radius=R)


class A(Base):
    def construct(self):
        self.play(Create(self.c))


class B(Scene):
    def construct(self):
        self.wait(1)
'''


def _text(data: bytes, scene: str) -> bytes:
    import ast
    from studio.server.tracecache import scene_text
    return scene_text(ast.parse(data), data, scene, ["A", "B"])


def test_scene_key_ignores_other_scenes_but_not_shared_code():
    a, b = _text(SRC, "A"), _text(SRC, "B")
    # an edit inside B, same line count: A keeps its trace, B doesn't
    edited = SRC.replace(b"self.wait(1)", b"self.wait(2)")
    assert _text(edited, "A") == a and _text(edited, "B") != b
    # shared code (a constant, a helper, a base class A inherits) changes A
    assert _text(SRC.replace(b"R = 1", b"R = 2"), "A") != a
    assert _text(SRC.replace(b"shift(UP)", b"shift(DOWN)"), "A") != a
    assert _text(SRC.replace(b"radius=R", b"radius=2"), "A") != a
    assert _text(SRC.replace(b"radius=R", b"radius=2"), "B") != b  # B sees the module's code too


def test_scene_key_follows_line_positions():
    a, b = _text(SRC, "A"), _text(SRC, "B")
    # a line added inside B, below A: A unchanged
    below = SRC.replace(b"        self.wait(1)\n", b"        self.wait(1)\n        self.wait(1)\n")
    assert _text(below, "A") == a
    # a line added above B (inside A): B's lines move, so its trace does too
    above = SRC.replace(b"        self.play(Create(self.c))\n",
                        b"        self.play(Create(self.c))\n        self.wait()\n")
    assert _text(above, "B") != b
