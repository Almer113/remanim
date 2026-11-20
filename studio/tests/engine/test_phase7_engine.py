"""Phase 7 through a real worker. Never run while the studio server or a
corpus run is busy (shared media/Tex_studio)."""

import asyncio

from studio.server.code.inserts import new_file_text
from studio.server.project import Document
from studio.tests.engine.test_engine import CORPUS, TMP, _quiet


def test_every_new_file_option_traces():
    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        for i, (target, voice) in enumerate([(None, False), (None, True), (7.5, True), (5.0, False)]):
            path = TMP / f"p7_new_{i}.py"
            path.write_bytes(new_file_text("Fresh", target=target, voice=voice).encode())
            doc = Document(path, [], _quiet)
            try:
                await doc.load()
                assert "Fresh" in doc.traces, doc.traces
                assert abs(doc.traces["Fresh"]["duration"] - (target or 0)) < 0.05, (target, doc.traces["Fresh"]["duration"])
            finally:
                doc.close()
    asyncio.run(go())


async def _edit(doc, msg):
    r = await doc.edit({"rev": doc.rev, **msg})
    assert r["type"] == "edit.done", r
    return r


def test_add_rename_delete_scene_then_undo_is_byte_identical():
    from studio.tests.engine.test_engine import ROOT

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        cases = [ROOT / "euler_identity.py", CORPUS / "inheritance.py", CORPUS / "formatting.py",
                 ROOT / "studio" / "tests" / "corpus" / "gallery" / "basic_concepts.py"]
        for src in cases:
            path = TMP / f"p7_scenes_{src.stem}.py"
            original = src.read_bytes()
            path.write_bytes(original)
            doc = Document(path, [], _quiet)
            try:
                await doc.load()
                scenes = list(doc.meta["scenes"])
                first = next(n for n in scenes if not doc.traces.get(n, {}).get("error"))
                r = await _edit(doc, {"type": "edit.scene_add", "scene": first, "name": "ZzAdded", "where": "after"})
                assert r["scene"] == "ZzAdded" and "ZzAdded" in doc.meta["scenes"], (src.name, r)
                r = await _edit(doc, {"type": "edit.scene_rename", "scene": "ZzAdded", "name": "ZzRenamed"})
                assert "ZzRenamed" in doc.meta["scenes"] and "ZzAdded" not in doc.meta["scenes"]
                await _edit(doc, {"type": "edit.scene_add", "scene": first, "name": "ZzLast", "where": "end"})
                await _edit(doc, {"type": "edit.scene_delete", "scene": "ZzLast"})
                assert "ZzLast" not in doc.meta["scenes"]
                for _ in range(4):
                    u = await doc.undo_redo("undo")
                    assert u.get("type") != "error", u
                assert path.read_bytes() == original, src.name
            finally:
                doc.close()
    asyncio.run(go())


def test_target_fit_set_ripple_and_undo():
    from studio.tests.engine.test_engine import ROOT
    from studio.server.project import content_end

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p7_target_euler.py"
        original = (ROOT / "euler_identity.py").read_bytes()
        path.write_bytes(original)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            fits = {}
            for name in doc.meta["scenes"]:
                tr = doc.traces[name]
                info = doc._scene_model(tr)["target_info"]
                assert info["own"] and info["editable"] and info["line"], (name, info)
                assert info["content_end"] == content_end(tr) <= tr["target"], (name, info)
                fits[name] = (tr["target"], info["content_end"])
                # the padding clip says what it is
                last = doc._scene_model(tr)["clips"][-1]
                if tr["duration"] - info["content_end"] > 1 / doc.meta["fps"]:
                    assert last.get("padding") and "padding to TARGET (line" in last["lock"], (name, last)
            # the hand-set TARGETs were the content end plus up to 0.3 s
            assert all(0 <= t - e <= 0.35 for t, e in fits.values()), fits
            fps = doc.meta["fps"]
            # a typed length, then fit
            r = await _edit(doc, {"type": "edit.target", "scene": "Walk", "value": 13})
            assert "TARGET 11.8 → 13" in r["summary"] and abs(doc.traces["Walk"]["duration"] - 13) < 1.5 / fps
            r = await _edit(doc, {"type": "edit.target", "scene": "Walk", "value": "fit"})
            want = fits["Walk"][1] + 0.1
            assert abs(doc.traces["Walk"]["duration"] - want) < 1.5 / fps + 0.01, (r, doc.traces["Walk"]["duration"])
            bad = await doc.edit({"rev": doc.rev, "type": "edit.target", "scene": "Walk", "value": 3})
            assert bad["type"] == "edit.refused" and "content runs to" in bad["reason"]
            for _ in range(2):
                await doc.undo_redo("undo")
            assert path.read_bytes() == original
            # ripple: shorten Walk's last pause (the at() before fade_all) by 0.5 s
            clips = doc._scene_model(doc.traces["Walk"])["clips"]
            k = max(i for i, c in enumerate(clips) if c["call_name"] == "at")
            d = clips[k]["duration"]
            r = await _edit(doc, {"type": "edit.timing", "scene": "Walk", "clip": k, "anim": None,
                                  "field": "duration", "value": round(d - 0.5, 4), "ripple": True})
            assert "ripple: TARGET 11.8 → 11.3" in r["summary"], r["summary"]
            assert abs(doc.traces["Walk"]["duration"] - 11.3) < 1.5 / fps
            await doc.undo_redo("undo")
            # without ripple, TARGET stays
            r = await _edit(doc, {"type": "edit.timing", "scene": "Walk", "clip": k, "anim": None,
                                  "field": "duration", "value": round(d - 0.5, 4), "ripple": False})
            assert "TARGET" not in r["summary"]
            await doc.undo_redo("undo")
            assert path.read_bytes() == original
        finally:
            doc.close()

        # + target on a scene without one; a computed one is refused
        path = TMP / "p7_target_new.py"
        path.write_bytes(new_file_text("Fresh", target=None).encode())
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            info = doc._scene_model(doc.traces["Fresh"])["target_info"]
            assert not info["own"] and info["value"] is None and info["editable"]
            await _edit(doc, {"type": "edit.target", "scene": "Fresh", "value": 4})
            assert b"    TARGET = 4\n" in path.read_bytes() and abs(doc.traces["Fresh"]["duration"] - 4) < 0.1
        finally:
            doc.close()
        path = TMP / "p7_target_computed.py"
        path.write_bytes(new_file_text("Fresh").replace("TARGET = 5.0", "TARGET = 2 * 3").encode())
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            info = doc._scene_model(doc.traces["Fresh"])["target_info"]
            assert info["computed"] and not info["editable"]
            bad = await doc.edit({"rev": doc.rev, "type": "edit.target", "scene": "Fresh", "value": 4})
            assert bad["type"] == "edit.refused" and "computed" in bad["reason"]
        finally:
            doc.close()
    asyncio.run(go())


def test_narrating_a_silent_scene_is_one_edit():
    # a line already in the voice cache (euler_identity.py), so no network is needed
    LINE = "Take the walk in small straight steps, and the steps close in on minus one."

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p7_voice_new.py"
        original = new_file_text("Fresh", target=8.0).encode()
        path.write_bytes(original)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            vs = doc._scene_model(doc.traces["Fresh"])["voice_state"]
            assert vs["silent"] and vs["owner"] == "Fresh"
            bad = await doc.edit({"rev": doc.rev, "type": "edit.voice", "scene": "Fresh", "action": "add",
                                  "t": 1.0, "value": LINE})
            assert bad["type"] == "edit.refused" and "no voice" in bad["reason"]
            r = await _edit(doc, {"type": "edit.voice", "scene": "Fresh", "action": "add", "t": 1.0,
                                  "value": LINE, "voice": "class"})
            assert "VOICE" in r["summary"] and "narration line added" in r["summary"]
            text = path.read_bytes().decode()
            assert 'VOICE = "en-US-AndrewNeural"' in text and "self.line(" in text
            lines = doc.traces["Fresh"]["audio"]["lines"]
            assert len(lines) == 1 and abs(lines[0]["start"] - 1.0) < 0.1 and lines[0]["duration"] > 2
            assert not doc._scene_model(doc.traces["Fresh"])["voice_state"]["silent"]
            await doc.undo_redo("undo")  # one step takes both back
            assert path.read_bytes() == original
        finally:
            doc.close()
    asyncio.run(go())


def test_fade_during_narration_is_flagged():
    """The Euler Walk case from the friction log: fade_all() at 9.27 s while the
    line runs to about 10.6 s is flagged; the fixed file (at 11.17) isn't."""
    from studio.tests.engine.test_engine import ROOT
    from studio.server.project import speech_warnings

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        good = (ROOT / "euler_identity.py").read_bytes()
        bad = good.replace(b"        self.at(11.17)\n", b"        self.at(9.27)\n")
        assert bad != good
        for data, flagged in ((good, False), (bad, True)):
            path = TMP / "p7_speech_walk.py"
            path.write_bytes(data)
            doc = Document(path, [], _quiet)
            try:
                await doc.load()
                tr = doc.traces["Walk"]
                w = speech_warnings(tr)
                assert bool(w) == flagged, w
                clips = doc._scene_model(tr)["clips"]
                marked = [c for c in clips if c.get("speech")]
                assert bool(marked) == flagged
                if flagged:
                    assert "FadeOut ends 1." in marked[0]["speech"] and "After time pi" in marked[0]["speech"], marked
                for name in doc.meta["scenes"]:
                    if name != "Walk" or not flagged:
                        assert not speech_warnings(doc.traces[name]), (name, speech_warnings(doc.traces[name]))
            finally:
                doc.close()

        # the warning arrives once, in the reply of the edit that causes it
        path = TMP / "p7_speech_walk.py"
        path.write_bytes(good)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            await doc.activate("Walk")
            clips = doc._scene_model(doc.traces["Walk"])["clips"]
            k = max(i for i, c in enumerate(clips) if c["call_name"] == "at")
            r = await _edit(doc, {"type": "edit.timing", "scene": "Walk", "clip": k, "anim": None,
                                  "field": "duration", "value": round(clips[k]["duration"] - 1.9, 4)})
            assert "mid-sentence" in r.get("warning", ""), r
            await doc.undo_redo("undo")
            assert path.read_bytes() == good
        finally:
            doc.close()
    asyncio.run(go())


def test_computed_lengths_arrive_read_only():
    """Step 8: the refusal reason is in the model before anyone presses Enter."""
    from studio.tests.engine.test_engine import ROOT

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p7_locks_euler.py"
        path.write_bytes((ROOT / "euler_identity.py").read_bytes())
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            clips = doc._scene_model(doc.traces["TimesI"])["clips"]
            looped = [c for c in clips if c["call_name"] == "at" and "2.4 * k" in (c["text"] or "")]
            assert looped and all("computed" in c.get("duration_lock", "") for c in looped), looped
            plain = [c for c in clips if c["call_name"] == "at" and c["text"] == "self.at(0.2)"]
            assert plain and not plain[0].get("duration_lock")
            # each reason is the one the edit itself gives
            c = looped[0]
            r = await doc.edit({"rev": doc.rev, "type": "edit.timing", "scene": "TimesI", "clip": c["index"],
                                "anim": None, "field": "duration", "value": c["duration"] + 0.5})
            assert r["type"] == "edit.refused" and r["reason"] == c["duration_lock"], (r, c["duration_lock"])
        finally:
            doc.close()
    asyncio.run(go())


def test_inspector_scale_and_two_decimal_moves():
    from studio.tests.engine.test_engine import ROOT

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p7_moves_euler.py"
        original = (ROOT / "euler_identity.py").read_bytes()
        path.write_bytes(original)
        doc = Document(path, [], _quiet)
        try:
            await doc.load()
            await doc.activate("Velocity")
            f = int(7.0 * doc.meta["fps"])
            r = await doc.frame("Velocity", f, ids=True)
            objs = r["objects"]
            plane = next(o for o in objs if o["class"] == "ComplexPlane")
            assert plane.get("scale_now") == 1.3, {k: plane.get(k) for k in ("site", "user_site", "in_helper", "how", "chain", "func")}
            rule = next(o for o in objs if o.get("name") == "right_rule")
            # a drag of 0.2419 is written 0.24; typed in the Inspector (exact) it is kept
            r = await _edit(doc, {"type": "edit.move", "scene": "Velocity", "object": rule, "f": f,
                                  "dx": -0.2419, "dy": 0})
            line = path.read_bytes().decode().splitlines()[127]  # right_rule's next_to (line 128)
            assert ".shift(0.24 * LEFT)" in line, (line, r["summary"])
            await doc.undo_redo("undo")
            rule = next(o for o in (await doc.frame("Velocity", f, ids=True))["objects"] if o.get("name") == "right_rule")
            await _edit(doc, {"type": "edit.move", "scene": "Velocity", "object": rule, "f": f,
                              "dx": -0.2419, "dy": 0, "exact": True})
            assert ".shift(0.2419 * LEFT)" in path.read_bytes().decode().splitlines()[127]
            await doc.undo_redo("undo")
            assert path.read_bytes() == original
        finally:
            doc.close()
    asyncio.run(go())


def test_undo_finds_its_frame_in_the_cache():
    """Step 13: undo brings back bytes whose frames were drawn before: no replay."""
    from studio.tests.engine.test_engine import ROOT

    async def go():
        TMP.mkdir(parents=True, exist_ok=True)
        path = TMP / "p7_undo_frame.py"
        original = (ROOT / "euler_identity.py").read_bytes()
        path.write_bytes(original)
        doc = Document(path, [], _quiet)
        frames = []
        real = doc._engine

        async def counting(msg, **kw):
            if msg.get("op") == "frame" and (msg.get("scene"), msg.get("f"), msg.get("size")) == ("Walk", 20, "full"):
                frames.append(doc.rev)  # this test's own frame, not the background prefetch
            return await real(msg, **kw)
        doc._engine = counting
        try:
            await doc.load()
            before = await doc.frame("Walk", 20, ids=True)
            assert "error" not in before and frames, before
            rev0 = doc.rev
            await _edit(doc, {"type": "edit.target", "scene": "Walk", "value": 13})
            frames.clear()
            await doc.frame("Walk", 20, ids=True)
            assert len(frames) == 1, frames  # other bytes: drawn afresh
            u = await doc.undo_redo("undo")
            assert u["type"] == "edit.done" and path.read_bytes() == original and doc.rev > rev0
            frames.clear()
            after = await doc.frame("Walk", 20, ids=True)
            assert frames == [], frames  # the same bytes as rev0: from the cache
            assert after["image"] == before["image"] if "image" in before else after is before
            r = await doc.undo_redo("redo")  # the edit's frame was drawn too
            assert r["type"] == "edit.done"
            frames.clear()
            await doc.frame("Walk", 20, ids=True)
            assert frames == [], frames
        finally:
            doc.close()
    asyncio.run(go())
