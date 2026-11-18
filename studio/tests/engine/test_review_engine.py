"""Engine regressions from the post-Phase-2 review (studio/docs/review_phase2.md).

Real worker processes; a few seconds per test. Never run while the studio
server or a corpus run is busy (they share media/Tex_studio).
"""

import asyncio
import time

import pytest

from studio.tests.engine.test_engine import _open, run


async def _wait_parked(doc, scene, want=None, limit=60):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        s = await doc.worker.request({"op": "status", "scene": scene})
        if s.get("of") and s.get("cursors", 0) >= (want or s["of"]):
            return s
        await asyncio.sleep(0.3)
    return s


def test_frames_outside_the_scene_answer_quickly():
    async def go():
        doc = _open("formatting.py")
        try:
            await doc.load()
            await doc.activate("Formatting")
            n = doc.frame_count("Formatting")
            for f in (-1, -50, n, n + 1000):
                t = time.monotonic()
                r = await doc.frame("Formatting", f)
                assert "error" not in r, (f, r.get("error"))
                assert time.monotonic() - t < 30, f"frame {f} took {time.monotonic() - t:.1f} s"
            assert doc.worker.restarts == 0
        finally:
            doc.close()
    run(go())


def test_unseeded_random_is_the_same_in_every_cursor():
    """Each cursor thread draws from its own generator, seeded like a fresh run."""
    async def centres(doc, f):
        r = await doc.frame("Unseeded", f, ids=True)
        assert "error" not in r, r.get("error")
        return sorted(tuple(round(v, 4) for v in o["center"]) for o in r["objects"] if o.get("center"))

    async def go():
        doc = _open("randomness.py")
        try:
            await doc.load()
            await doc.activate("Unseeded")
            await _wait_parked(doc, "Unseeded")
            early, late = await centres(doc, 3), await centres(doc, 12)  # different cursors
            assert early and early == late
            await doc.load()  # a fresh engine draws the same numbers again
            await doc.activate("Unseeded")
            assert await centres(doc, 7) == early
        finally:
            doc.close()
    run(go())


def test_closing_cursors_through_finally_wait_leaks_no_threads():
    async def go():
        doc = _open("finally_wait.py")
        try:
            await doc.load()
            await doc.activate("FinallyWait")
            s = await _wait_parked(doc, "FinallyWait")
            base = s["threads"]
            for _ in range(3):  # each reload closes the whole pool
                await doc.load()
                await doc.activate("FinallyWait")
                s = await _wait_parked(doc, "FinallyWait")
            await asyncio.sleep(1.0)
            s = await doc.worker.request({"op": "status", "scene": "FinallyWait"})
            # before the fix every reload left ~one blocked thread per cursor behind
            assert s["threads"] <= base + 3, (base, s["threads"])
            r = await doc.frame("FinallyWait", 20)
            assert "error" not in r
        finally:
            doc.close()
    run(go())


def test_error_mid_play_does_not_use_up_the_cursors():
    async def go():
        doc = _open("late_error.py")
        try:
            await doc.load()
            await doc.activate("LateError")
            await _wait_parked(doc, "LateError")
            n = doc.frame_count("LateError")
            errors = 0
            for f in range(n - 6, n):  # inside the failing play
                r = await doc.frame("LateError", f)
                errors += "error" in r
            if not errors:
                pytest.skip("this Manim build stops the scene at trace time; nothing to serve")
            t = time.monotonic()
            r = await doc.frame("LateError", n - 1)
            assert "error" in r and time.monotonic() - t < 5  # the stored error, not another replay
            s = await doc.worker.request({"op": "status", "scene": "LateError"})
            assert s["cursors"] >= 1, s  # spots refilled
            r = await doc.frame("LateError", 3)
            assert "error" not in r
        finally:
            doc.close()
    run(go())


def test_library_copies_get_distinct_ids():
    async def go():
        doc = _open("late_error.py")
        try:
            await doc.load()
            await doc.activate("Copies")
            n = doc.frame_count("Copies")
            r = await doc.frame("Copies", n // 2, ids=True)
            assert "error" not in r, r.get("error")
            ids = [o["id"] for o in r["objects"]]
            assert len(ids) == len(set(ids)), ids
        finally:
            doc.close()
    run(go())


def test_id_map_keeps_style_attributes_and_opacity_edits_verify():
    """Painting the ID map used to leave fill_opacity=1 on every object: the
    Inspector showed 1 and an opacity edit was refused as 'set again later'."""
    async def go():
        doc = _open("late_error.py")
        try:
            await doc.load()
            await doc.activate("Opacity")
            for f in (3, 3, 9):  # the same cursor, ID map after ID map
                r = await doc.frame("Opacity", f, ids=True)
                sq = next(o for o in r["objects"] if o["id"].startswith("Square"))
                assert sq["values"]["fill_opacity"] == pytest.approx(0.4), (f, sq["values"])
            r = await doc.edit({"type": "edit.prop", "rev": doc.rev, "scene": "Opacity", "object": sq,
                                "prop": "fill_opacity", "value": {"number": 0.6}, "f": 9})
            assert r["type"] == "edit.done", r
            assert b"fill_opacity=0.6" in doc.path.read_bytes()
        finally:
            doc.close()
    run(go())


def test_worker_restart_reloads_the_file():
    async def go():
        doc = _open("formatting.py")
        try:
            await doc.load()
            await doc.activate("Formatting")
            rev = doc.rev
            doc.worker.proc.kill()  # as if the engine crashed
            # the next request to notice (ours or the prefetch's) restarts it
            await doc.worker.request({"op": "status", "scene": "Formatting"})
            assert doc.worker.restarts == 1
            end = time.monotonic() + 60
            while doc.rev == rev or doc.load_lock.locked():
                assert time.monotonic() < end, "no reload after the restart"
                await asyncio.sleep(0.2)
            r = await doc.frame("Formatting", 10)
            assert "error" not in r, r.get("error")
        finally:
            doc.close()
    run(go())
