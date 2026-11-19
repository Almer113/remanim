"""Phase 4 through a real worker: narration recorded in the trace, the
scene's sound mixed, and timeline edits on a copy of order_matters.py,
undone back to the original bytes.

The text edit synthesises one new line with Edge TTS (network; cached in
media/voiceovers afterwards). Never run while the studio server or a corpus
run is busy (shared media/Tex_studio).
"""

import shutil

from studio.server import audio
from studio.server.project import Document
from studio.tests.engine.test_engine import ROOT, TMP, _quiet, run


async def _edit(doc, msg):
    r = await doc.edit({"rev": doc.rev, **msg})
    assert r["type"] == "edit.done", r
    return r


def _scene(doc, name):
    return next(s for s in doc.model()["scenes"] if s["name"] == name)


def test_narration_in_the_model_and_the_mix():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "om_audio.py"
        shutil.copy(ROOT / "order_matters.py", path)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            s = _scene(doc, "CompareMatrices")
            assert s["timed"] and s["burned_captions"]
            (v,) = s["voice"]
            assert v["text"].startswith("As matrices, S R") and v["caption"].startswith("As matrices, SR")
            assert v["movable"] and v["line"] == 193 and not v["lock"]
            assert s["captions"][0]["text"] == v["caption"]
            tr = doc.traces["CompareMatrices"]
            x = audio.mix(tr)
            assert abs(len(x) / audio.RATE - tr["duration"]) < 0.01
            # the voice starts at 0 and lasts ~3.8 s: sound there, silence at the end
            assert abs(x[: int(3 * audio.RATE)]).max() > 0.05
            assert abs(x[int(5 * audio.RATE):]).max() < 1e-4
            (w,) = audio.waveforms(tr)
            assert abs(w["duration"] - v["duration"]) < 0.05 and len(w["peaks"]) > 100
        finally:
            doc.close()
    run(go())


def test_timeline_edits_on_order_matters_and_undo():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "om_timeline.py"
        shutil.copy(ROOT / "order_matters.py", path)
        original = path.read_bytes()
        doc = Document(path, [], _quiet)
        S = "Question"
        try:
            await doc.load()
            s = _scene(doc, S)
            assert s["voice"][0]["start"] == 1.0

            # move the line later: an at() before its with block
            r = await _edit(doc, {"type": "edit.voice", "scene": S, "action": "move", "line": 0, "t": 1.5})
            assert "self.at(1.5)" in r["summary"]
            assert abs(_scene(doc, S)["voice"][0]["start"] - 1.5) < 0.07

            # caption different from the spoken text
            await _edit(doc, {"type": "edit.voice", "scene": S, "action": "caption", "line": 0,
                              "value": "Rotate then shear, or shear then rotate?"})
            assert 'caption="Rotate then shear, or shear then rotate?"' in path.read_text(encoding="utf-8")

            # move the first group with ripple: every later at() and TARGET follow
            r = await _edit(doc, {"type": "edit.shift", "scene": S, "plays": [0], "lines": [], "dt": 0.3,
                                  "ripple": True})
            text = path.read_text(encoding="utf-8")
            assert "self.at(0.5)" in text and "self.at(7.2)" in text and "TARGET = 7.8" in text
            assert abs(doc.traces[S]["duration"] - 7.8) < 0.07

            # offset the blob's fade inside the first play(): clip(), run_time spread
            first = next(c for c in _scene(doc, S)["clips"] if c["kind"] == "play")
            await _edit(doc, {"type": "edit.offset", "scene": S, "clip": first["index"], "anim": 1, "start": 0.4})
            text = path.read_text(encoding="utf-8")
            assert "clip(FadeIn(blob, shift=UP * 0.2), start=0.4, length=0.8)" in text
            assert "FadeIn(title, run_time=0.8)" in text
            ev = next(e for e in doc.traces[S]["events"] if e["kind"] == "play")
            assert abs(ev["anims"][1]["offset"] - 0.4) < 1e-6 and abs(ev["duration"] - 1.2) < 0.07

            # new words: synthesised by the trace
            await _edit(doc, {"type": "edit.voice", "scene": S, "action": "text", "line": 0,
                              "value": "Rotate, then shear. Or shear, then rotate. The same?"})
            assert _scene(doc, S)["voice"][0]["duration"] > 1

            for _ in range(5):
                r = await doc.undo_redo("undo")
                assert r["type"] != "error", r
            assert path.read_bytes() == original
        finally:
            doc.close()
    run(go())
