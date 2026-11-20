"""Phase 6 through a real worker: the trace cache (a cached trace is the
trace), a changed local module, the last good version while the file is
broken, stopping a runaway scene, a deleted and a read-only file.

Never run while the studio server or another engine run is busy (shared
media/Tex_studio).
"""

import asyncio
import json
import os
import stat
import time

import pytest

from studio.server import tracecache
from studio.server.project import Document
from studio.tests.engine.test_engine import TMP, _quiet, run

THREE = '''from manim import *


class One(Scene):
    def construct(self):
        c = Circle()
        self.play(Create(c), run_time=1)
        self.wait(0.5)


class Two(Scene):
    def construct(self):
        s = Square()
        self.play(FadeIn(s), run_time=0.8)
        self.wait(1)


class Three(Scene):
    def construct(self):
        t = Triangle()
        self.add(t)
        self.play(t.animate.shift(RIGHT), run_time=1.2)
'''


@pytest.fixture
def cache(tmp_path, monkeypatch):
    c = tracecache.TraceCache(tmp_path / "traces")
    monkeypatch.setattr(tracecache, "CACHE", c)
    return c


def _file(name: str, text: str):
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / name
    if p.exists():
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    p.write_text(text, encoding="utf-8", newline="\n")
    return p


async def _settled(doc: Document):
    t = getattr(doc, "_load_task", None)
    if t is not None and not t.done():
        await t


def _plain(tr: dict) -> str:
    return json.dumps(tr, sort_keys=True)


def test_cached_traces_are_the_traces(cache):
    async def go():
        path = _file("p6_three.py", THREE)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            assert set(doc.traces) == {"One", "Two", "Three"}
            assert cache.misses == 3 and cache.hits == 0
            # an edit in One: verify traces One; the reload takes all three from the cache
            clip = doc._scene_model(doc.traces["One"])["clips"][0]
            r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "One", "clip": clip["index"],
                                "field": "duration", "value": 1.5})
            assert r["type"] == "edit.done", r
            await _settled(doc)
            assert cache.hits == 3, (cache.hits, cache.misses)
            assert doc.traces["One"]["events"][0]["duration"] == pytest.approx(1.5, abs=0.07)
            got = {n: _plain(t) for n, t in doc.traces.items()}
        finally:
            doc.close()
        # the same bytes, traced afresh with no cache: identical
        fresh = Document(path, [], _quiet)
        fresh._no_cache = True
        try:
            await fresh.load()
            assert {n: _plain(t) for n, t in fresh.traces.items()} == got
        finally:
            fresh.close()
        # a reopen traces nothing
        again = Document(path, [], _quiet)
        try:
            h = cache.hits
            await again.load()
            assert cache.hits == h + 3
        finally:
            again.close()
    run(go())


def test_changed_local_module_restarts_the_engine(cache):
    async def go():
        mod = _file("p6_helper_mod.py", "RUN = 1.0\n")
        path = _file("p6_uses_mod.py", '''from manim import *
from p6_helper_mod import RUN


class Uses(Scene):
    def construct(self):
        self.play(Create(Circle()), run_time=RUN)
''')
        said = []

        async def notify(m):
            said.append(m.get("by"))
        doc = Document(path, [], notify)
        try:
            await doc.load()
            assert doc.depends_on(mod)
            assert doc.traces["Uses"]["duration"] == pytest.approx(1.0, abs=0.07)
            # an event with nothing changed (Windows reports reads as changes): no restart
            proc = doc.worker.proc
            await doc.deps_changed()
            assert "dependency" not in said and doc.worker.proc is proc
            mod.write_text("RUN = 2.0\n", encoding="utf-8")
            await doc.deps_changed()
            assert "dependency" in said
            assert doc.traces["Uses"]["duration"] == pytest.approx(2.0, abs=0.07)
        finally:
            doc.close()
    run(go())


def test_broken_file_keeps_showing_the_last_version_that_ran(cache):
    async def go():
        path = _file("p6_breaks.py", THREE)
        busy = []

        async def notify(m):
            if m.get("type") == "engine.busy":
                busy.append(m["what"])
        doc = Document(path, [], notify)
        try:
            await doc.load()
            healthy = [(o["name"], o["tier"]) for o in (await doc.frame("Two", 5, ids=True))["objects"]]
            assert [n for n, _ in healthy] == ["s"]
            for broken, code in ((THREE.replace("c = Circle()", "c = Circle("), "parse"),
                                 (THREE.replace("class One(Scene):", "1 / 0\n\n\nclass One(Scene):"), "crash")):
                path.write_text(broken, encoding="utf-8", newline="\n")
                await doc.file_changed()
                m = doc.model()
                assert m["error"]["code"] == code and m["stale"] is True
                assert busy[-1] is None, busy  # no "loading…" left showing after a failed load
                assert [s["name"] for s in m["scenes"]] == ["One", "Two", "Three"]
                assert m["source"] == broken and m["literals"] == []
                fr = await doc.frame("Two", 5, ids=True)
                assert "error" not in fr and fr.get("image"), fr
                # named from the version that ran, not from the broken file
                assert [(o["name"], o["tier"]) for o in fr["objects"]] == healthy, fr["objects"]
                r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "One", "clip": 0,
                                    "field": "duration", "value": 2})
                assert r["type"] == "edit.refused", r
            path.write_text(THREE, encoding="utf-8", newline="\n")
            await doc.file_changed()
            m = doc.model()
            assert m["error"] is None and m["stale"] is False and len(m["scenes"]) == 3
        finally:
            doc.close()
    run(go())


def test_stop_a_runaway_scene(cache):
    async def go():
        path = _file("p6_runaway.py", THREE.replace(
            "        t = Triangle()\n", "        t = Triangle()\n        while True:\n            pass\n"))
        doc = Document(path, [], _quiet)
        try:
            task = asyncio.create_task(doc.load())
            t0 = time.monotonic()
            while not (doc.tracing and doc.tracing[0] == "Three"):
                assert time.monotonic() - t0 < 120, "never got to Three"
                await asyncio.sleep(0.2)
            await asyncio.sleep(1)
            r = await doc.stop()
            assert r == {"type": "stopped", "scene": "Three"}
            await task
            t0 = time.monotonic()
            while set(doc.traces) != {"One", "Two", "Three"} or doc.tracing:
                assert time.monotonic() - t0 < 120, "the reload never finished"
                await asyncio.sleep(0.2)
            assert doc.traces["Three"]["error"]["code"] == "stopped"
            assert not doc.traces["One"].get("error") and not doc.traces["Two"].get("error")
            assert doc.error is None
            fr = await doc.frame("One", 3)
            assert "error" not in fr, fr
            # the stopped scene's frames are refused, not run (that would loop again)
            t1 = time.monotonic()
            fr = await doc.frame("Three", 0, ids=True)
            assert fr["error"]["code"] == "stopped" and time.monotonic() - t1 < 1, fr
            assert (await doc.stop())["type"] == "error"  # nothing running now
        finally:
            doc.close()
    run(go())


def test_deleted_then_restored_file(cache):
    async def go():
        path = _file("p6_deleted.py", THREE)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            path.unlink()
            await doc.file_changed()
            assert doc.error["code"] == "missing"
            assert len(doc.model()["scenes"]) == 3  # still shown
            r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "One", "clip": 0,
                                "field": "duration", "value": 2})
            assert r["type"] == "edit.refused"
            path.write_text(THREE, encoding="utf-8", newline="\n")
            await doc.file_changed()
            assert doc.error is None
        finally:
            doc.close()
    run(go())


def test_read_only_file_is_named(cache):
    async def go():
        path = _file("p6_readonly.py", THREE)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            os.chmod(path, stat.S_IREAD)
            clip = doc._scene_model(doc.traces["One"])["clips"][0]
            r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "One", "clip": clip["index"],
                                "field": "duration", "value": 1.5})
            assert r["type"] == "edit.refused" and "read-only" in r["reason"], r
            assert path.read_text(encoding="utf-8") == THREE
        finally:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            doc.close()
    run(go())


EXPORT = '''from manim import *


class First(Scene):
    def construct(self):
        self.play(Create(Circle()), run_time=0.5)


class Second(Scene):
    def construct(self):
        self.play(FadeIn(Square()), run_time=0.5)
'''


def test_export_waits_for_the_lock_renders_joins_and_checks():
    import sys
    from studio.server.export import ROOT, Exporter
    sys.path.insert(0, str(ROOT / "tools"))
    import render_lock

    async def go():
        path = _file("p6_export.py", EXPORT)
        rel_file = path.relative_to(ROOT).as_posix()
        seen = []

        async def notify(m):
            seen.append(m["job"]["state"])
        ex = Exporter(notify)
        # someone else (the preview server, say) is rendering this file: the job waits
        assert render_lock.try_acquire("p6_export", "test")
        r = await ex.start(rel_file, {"scenes": ["First", "Second"], "join": True}, ["First", "Second"])
        job = ex.jobs[r["job"]["id"]]
        t0 = time.monotonic()
        while job.state != "waiting":
            assert time.monotonic() - t0 < 20
            await asyncio.sleep(0.2)
        assert "test" in job.message
        render_lock.release("p6_export")
        await ex.runner
        assert job.state == "done", (job.message, job.log[-2000:])
        assert [s["state"] for s in job.scenes] == ["done", "done"]
        for s in job.scenes:
            assert (ROOT / s["out"]).is_file() and s["out"].endswith(".mp4")
        assert job.joined and (ROOT / job.joined).is_file()
        assert job.check["ok"] and not job.check["narrated"], job.check
        assert ex.file_of(job.id, 2) == (ROOT / job.joined).resolve()
        assert ex.file_of(job.id, 3) is None
        assert render_lock.holder("p6_export") is None
        assert "waiting" in seen and seen[-1] == "done"

        # cancel while rendering: stops, releases the lock, joins nothing
        r = await ex.start(rel_file, {"scenes": ["First", "Second"], "join": True, "quality": "m"},
                           ["First", "Second"])
        job = ex.jobs[r["job"]["id"]]
        t0 = time.monotonic()
        while job.proc is None:
            assert time.monotonic() - t0 < 30
            await asyncio.sleep(0.05)
        await ex.cancel(job.id)
        await ex.runner
        assert job.state == "cancelled" and job.joined is None
        assert render_lock.holder("p6_export") is None
    run(go())


def _ranked(objects) -> str:
    """Objects with each move's "order" (a process-wide counter, so only its
    rank means anything) replaced by its rank."""
    seen = set()

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("order"), int) and o["order"] >= 0:
                seen.add(o["order"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(objects)
    rank = {v: i for i, v in enumerate(sorted(seen))}

    def norm(o):
        if isinstance(o, dict):
            return {k: (rank.get(v, v) if k == "order" else norm(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [norm(v) for v in o]
        return o
    return json.dumps(norm(objects), sort_keys=True)


def test_the_edits_own_run_gives_the_next_frame(cache):
    """The verify run draws the frame at the playhead; after the write it is
    cached for the new revision, and it is exactly the frame the loaded engine
    draws (image, objects, id map)."""
    async def go():
        path = _file("p6_seed.py", THREE)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            f = 10
            clip = doc._scene_model(doc.traces["One"])["clips"][0]
            asked = []
            real = doc.worker.request

            async def spy(msg, **kw):
                asked.append(msg["op"])
                return await real(msg, **kw)
            doc.worker.request = spy
            r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "One", "clip": clip["index"],
                                "field": "duration", "value": 1.5, "at": f})
            assert r["type"] == "edit.done", r
            asked.clear()
            seeded = await doc.frame("One", f, ids=True)
            assert "frame" not in asked, asked  # served from the cache: no engine run
            doc.frames.items.clear()
            fresh = await doc.frame("One", f, ids=True)
            assert seeded["image"] == fresh["image"]
            assert seeded["idmap"] == fresh["idmap"]
            assert _ranked(seeded["objects"]) == _ranked(fresh["objects"])
            # a playhead past the new end is not cached (frames clamp to the scene)
            r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "One", "clip": clip["index"],
                                "field": "duration", "value": 0.5, "at": 30})
            assert r["type"] == "edit.done", r
            assert (doc.rev, "One", 30, "full", "png") not in doc.frames.items
        finally:
            doc.close()
    run(go())
