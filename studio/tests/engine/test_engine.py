"""Engine behaviour through a real worker process (Manim patched there, not here).

Slow-ish (a few seconds per file). Never run while the studio server or a
corpus run is busy: they share media/Tex_studio.
"""

import asyncio
import shutil
from pathlib import Path

import pytest

from studio.server.project import Document

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "studio" / "tests" / "corpus" / "awkward"
TMP = ROOT / "studio" / "tests" / "tmp" / "engine"


async def _quiet(_m):
    pass


def _open(name: str) -> Document:
    TMP.mkdir(parents=True, exist_ok=True)
    dst = TMP / name
    shutil.copyfile(CORPUS / name, dst)
    return Document(dst, [], _quiet)


def run(coro):
    return asyncio.run(coro)


def test_nominal_duration_and_mid_create_objects():
    async def go():
        doc = _open("formatting.py")
        try:
            await doc.load()
            sm = doc._scene_model(doc.traces["Formatting"])
            wait = [c for c in sm["clips"] if c["kind"] == "wait"][0]
            assert wait["duration"] == pytest.approx(0.5)          # the code's number
            assert wait["played"] == pytest.approx(7 / 15, abs=1e-6)  # whole frames at 15 fps
            await doc.activate("Formatting")
            # frame 18 is mid Create(Square): reading side_length there used to raise
            r = await doc.frame("Formatting", 18, ids=True)
            assert "error" not in r, r.get("error")
            assert len(r["objects"]) >= 2
            r2 = await doc.frame("Formatting", 30, ids=True)   # the cursor survived
            assert "error" not in r2
        finally:
            doc.close()
    run(go())


def test_broken_files_open_read_only():
    async def go():
        for name, code in (("broken_syntax.py", "parse"), ("broken_runtime.py", None)):
            doc = _open(name)
            try:
                before = doc.path.read_bytes()
                await doc.load()
                m = doc.model()
                if code:
                    assert m["error"]["code"] == code
                else:  # runs until the bad line: an error on the scene, not a crash of the studio
                    assert m["error"] or any(s.get("error") for s in m["scenes"])
                assert doc.path.read_bytes() == before
            finally:
                doc.close()
    run(go())
