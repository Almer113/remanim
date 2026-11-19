"""Phase 4 exit check: re-cut and re-narrate a copy of order_matters.py with
the same edit messages the timeline sends, then print the diff.

    .venv/Scripts/python studio/tests/exit_phase4.py

Writes studio/tests/tmp/exit/order_matters_recut.py (render it afterwards
with tools/timeline_render.py, then tools/audio_check.py). New narration
goes to Edge TTS (network). Never run while the studio server is busy.
"""

import asyncio
import difflib
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from studio.server.project import Document  # noqa: E402

OUT = ROOT / "studio" / "tests" / "tmp" / "exit" / "order_matters_recut.py"


async def quiet(_m):
    pass


def scene(doc, name):
    return next(s for s in doc.model()["scenes"] if s["name"] == name)


async def open_scene(doc, name):
    """Click the scene in the UI: wait until the edit's retrace reaches it."""
    while name not in doc.traces:
        task = getattr(doc, "_load_task", None)
        if task is not None and not task.done():
            await task
        else:
            await asyncio.sleep(0.2)
    await doc.activate(name)
    return scene(doc, name)


def plays(doc, name):
    return [c for c in scene(doc, name)["clips"] if c["kind"] == "play"]


async def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "order_matters.py", OUT)
    original = OUT.read_bytes()
    doc = Document(OUT, [], quiet)
    log = []
    nonlocal_n = [0]

    async def edit(label, msg, may_refuse=False):
        t0 = time.perf_counter()
        r = await doc.edit({"rev": doc.rev, **msg})
        ok = r["type"] == "edit.done"
        log.append((label, ok, r.get("summary") or r.get("reason") or r.get("message"),
                    time.perf_counter() - t0))
        print(f"{'ok ' if ok else 'NO '} {label}: {log[-1][2]}  ({log[-1][3]:.1f} s)", flush=True)
        if not ok and not may_refuse:
            raise SystemExit(f"refused: {r}")
        return r

    try:
        await doc.load()
        Q, RS, CM, TA = "Question", "RotateThenShear", "CompareMatrices", "Takeaway"

        # -- Question: re-cut the opening, re-narrate the question ---------------
        await edit("section at 0", {"type": "edit.section", "scene": Q, "action": "add", "t": 0, "name": "Opening"})
        await edit("ripple-shift the first group +0.3 s",
                   {"type": "edit.shift", "scene": Q, "plays": [0], "lines": [], "dt": 0.3, "ripple": True})
        first = plays(doc, Q)[0]
        await edit("overlap: the blob fades in 0.4 s into the group",
                   {"type": "edit.offset", "scene": Q, "clip": first["index"], "anim": 1, "start": 0.4})
        first = plays(doc, Q)[0]
        await edit("re-ease the title (ease_out_back)",
                   {"type": "edit.timing", "scene": Q, "clip": first["index"], "anim": 0,
                    "field": "rate_func", "value": "ease_out_back"})
        await edit("move the line to 1.8 s", {"type": "edit.voice", "scene": Q, "action": "move", "line": 0, "t": 1.8})
        await edit("rewrite the line", {"type": "edit.voice", "scene": Q, "action": "text", "line": 0,
                                        "value": "Rotate, then shear. Or shear first, then rotate. Same result?"})
        await edit("caption the line", {"type": "edit.voice", "scene": Q, "action": "caption", "line": 0,
                                        "value": "Rotate then shear, or shear then rotate: same result?"})

        # -- RotateThenShear: tighten the first sweep ----------------------------
        await open_scene(doc, RS)
        sweep = next(c for c in plays(doc, RS) if "set_value(0.5)" in (c["text"] or ""))
        await edit("trim the first sweep 1.8 -> 1.4 s",
                   {"type": "edit.timing", "scene": RS, "clip": sweep["index"], "anim": None,
                    "field": "duration", "value": 1.4})

        # -- CompareMatrices: swap the two products, add a line -----------------
        await open_scene(doc, CM)
        ps = plays(doc, CM)
        await edit("reorder: RS written before SR",
                   {"type": "edit.reorder", "scene": CM, "play": ps[1]["play_index"],
                    "target": ps[0]["play_index"], "after": False})
        await edit("add a line at 5.0 s", {"type": "edit.voice", "scene": CM, "action": "add", "t": 5.0,
                                           "value": "Look at the first columns: that is where the green arrow lands."})
        # the new line runs past the fade-out: push the fade (and TARGET) later
        await open_scene(doc, CM)
        v = scene(doc, CM)["voice"][-1]
        fade = plays(doc, CM)[-1]
        dt = round(v["start"] + max(v["duration"], v.get("hold", 0)) + 0.3 - fade["start"], 1)
        await edit(f"move the fade-out {dt:+.1f} s, ripple",
                   {"type": "edit.shift", "scene": CM, "plays": [fade["play_index"]], "lines": [], "dt": dt,
                    "ripple": True})

        # -- Takeaway: replace the narration -------------------------------------
        await open_scene(doc, TA)
        await edit("delete the line", {"type": "edit.voice", "scene": TA, "action": "delete", "line": 0})
        await edit("add a new line at 1.8 s", {"type": "edit.voice", "scene": TA, "action": "add", "t": 1.8,
                                               "value": "So read S R from the right: R happens first."})
        # 1.6 s can be refused: Takeaway fades out a ClippedGrid while it turns
        # (manim_kit says not to), and whether that crashes depends on timing
        r = await edit("move the new line to 1.6 s",
                       {"type": "edit.voice", "scene": TA, "action": "move", "line": 0, "t": 1.6}, may_refuse=True)
        if r["type"] != "edit.done":
            await edit("move the new line to 2.0 s",
                       {"type": "edit.voice", "scene": TA, "action": "move", "line": 0, "t": 2.0})

        # -- the video: Takeaway before CompareMatrices --------------------------
        order = list(doc.meta["scenes"])
        i, j = order.index(CM), order.index(TA)
        order[i], order[j] = order[j], order[i]
        await edit("scene order", {"type": "edit.scene_order", "scene": Q, "order": order})

        print("\nwarnings:")
        for s in doc.model()["scenes"]:
            for v in s.get("voice") or []:
                for w in v.get("warnings") or []:
                    print(f"  {s['name']} line {v['index']}: {w}")
            print(f"  {s['name']}: {s.get('duration', 0):.2f} s, {len(s.get('voice') or [])} line(s)")

        # undo everything: the original bytes come back
        n = sum(1 for _, ok, *_ in log if ok)
        for _ in range(n):
            r = await doc.undo_redo("undo")
            assert r["type"] != "error", r
        assert OUT.read_bytes() == original, "undo did not restore the file"
        nonlocal_n[0] = n
        print(f"\n{n} undos restore the original bytes")
        for _ in range(n):
            r = await doc.undo_redo("redo")
            assert r["type"] != "error", r
    finally:
        doc.close()

    a = (ROOT / "order_matters.py").read_text(encoding="utf-8").splitlines()
    b = OUT.read_text(encoding="utf-8").splitlines()
    print("\n".join(difflib.unified_diff(a, b, "order_matters.py", OUT.name, lineterm="", n=1)))
    print(f"\n{len(log)} edits, {sum(t for *_, t in log):.0f} s in total")


if __name__ == "__main__":
    asyncio.run(main())
