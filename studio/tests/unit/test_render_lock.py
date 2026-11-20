"""tools/render_lock.py: one render per file across processes, freed by the OS
when its holder dies (review after Phase 6: the pid-file version could wedge
on Windows, take a lock twice while stale, and trust a reused pid)."""

import subprocess
import sys
import time

from studio.server.export import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import render_lock  # noqa: E402

STEM = "zz_lock_test"
HOLD = (
    "import sys, time; sys.path.insert(0, sys.argv[1]); import render_lock as r\n"
    "assert r.try_acquire(sys.argv[2], 'child'); print('held', flush=True); time.sleep(60)\n"
)


def _child():
    p = subprocess.Popen([sys.executable, "-c", HOLD, str(ROOT / "tools"), STEM],
                         stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "held"
    return p


def test_one_holder_per_file_and_a_killed_holder_frees_it():
    assert render_lock.holder(STEM) is None
    p = _child()
    try:
        info = render_lock.holder(STEM)
        assert info and info["owner"] == "child" and info["pid"] != 0
        assert not render_lock.try_acquire(STEM, "test")   # someone else has it
    finally:
        p.kill()
        p.wait()
    # the OS dropped it with the process: no stale lock to clear
    assert render_lock.holder(STEM) is None
    assert render_lock.try_acquire(STEM, "test")
    try:
        assert render_lock.holder(STEM)["owner"] == "test"
        assert not render_lock.try_acquire(STEM, "again")  # this process already holds it
    finally:
        render_lock.release(STEM)
    assert render_lock.holder(STEM) is None


def test_held_waits_and_gives_up_on_cancel():
    p = _child()
    try:
        told = []
        t0 = time.monotonic()
        try:
            with render_lock.held(STEM, "test", poll=0.05, on_wait=told.append,
                                  cancelled=lambda: time.monotonic() - t0 > 0.3):
                raise AssertionError("got a lock that was held")
        except TimeoutError as e:
            assert "child" in str(e)
        assert told and told[0]["owner"] == "child"
    finally:
        p.kill()
        p.wait()
    with render_lock.held(STEM, "test", poll=0.05):
        assert render_lock.holder(STEM)["owner"] == "test"
    assert render_lock.holder(STEM) is None
