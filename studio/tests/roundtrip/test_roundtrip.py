"""Edit -> verify -> write -> undo must give the original bytes back (Phase 2 exit).

Uses the corpus runner on a few representative files; the full corpus is
`python -u studio/tests/corpus_run.py` (report in studio/tests/tmp/).
Never run while the studio server or a corpus run is busy (shared Tex folder).
"""

import asyncio

import pytest

from studio.tests.corpus_run import ROOT, run_file

FILES = [
    "studio/tests/corpus/awkward/formatting.py",
    "studio/tests/corpus/awkward/timing.py",
    "order_matters.py",
]


@pytest.mark.parametrize("rel", FILES)
def test_round_trip(rel):
    original = (ROOT / rel).read_bytes()
    r = asyncio.run(run_file(rel, []))
    assert not r.get("error"), r.get("error")
    assert r["bytes_ok"]
    edits = [s[k] for s in r["scenes"] for k in ("timing_edit", "number_edit", "colour_edit") if k in s]
    assert edits, "no editable value found"
    for e in edits:
        assert e["bytes_ok"]
        assert e["type"] in ("edit.done", "edit.refused"), e
        if e["type"] == "edit.done":
            assert e["changed_file"] and e["undo"] == "edit.done"
        else:
            assert e["reason"]
    assert any(e["type"] == "edit.done" for e in edits)
    for s in r["scenes"]:
        assert not s["noop"]["changed"], s["noop"]["changed"]
        assert all(f["error"] is None for f in s["frames"]), s["frames"]
    assert (ROOT / rel).read_bytes() == original  # the original was never touched
