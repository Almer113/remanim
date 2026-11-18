"""Phase 3 exit run: how many on-screen objects a canvas drag moves exactly.

For every scene in every scene file (as corpus_run.py finds them), at a
still frame (the middle of the last pause, so nothing is mid-animation),
each drawn object is dragged by (0.4, -0.25) through the same Document path
the server uses, then dragged back. A drag counts when the edit is verified
(the replay puts the object where it was dropped); "back" counts when the
drag back restores the file byte for byte.

Copies live in studio/tests/tmp/drag/ so originals are never touched.
Never run while the studio server or another engine run is busy (shared
media/Tex_studio).

Run:  .venv/Scripts/python -u -m studio.tests.drag_run [filter] [--max N]
      (no filter: the corpus and fixtures; name a repo video to include it)
Report: studio/tests/tmp/drag_report.json
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from studio.server.app import scene_files  # noqa: E402
from studio.server.project import Document  # noqa: E402
from studio.tests.corpus_run import group_of  # noqa: E402

TMP = ROOT / "studio" / "tests" / "tmp" / "drag"
PER_SCENE = 600  # seconds
DX, DY = 0.4, -0.25


async def quiet(_msg):
    pass


def still_frame(doc: Document, scene: str) -> int:
    """The middle of the last pause; the last frame when there is none."""
    n = doc.frame_count(scene)
    fps = doc.meta.get("fps", 15)
    waits = [e for e in doc.traces[scene]["events"] if e["kind"] == "wait" and e["duration"] >= 2 / fps]
    if not waits:
        return max(0, n - 1)
    w = waits[-1]
    return max(0, min(n - 1, int((w["start"] + w["duration"] / 2) * fps)))


async def _edit(doc: Document, msg: dict) -> dict:
    r = await doc.edit({"rev": doc.rev, **msg})
    if r["type"] == "edit.preview":  # drags inside helpers ask first; the run says yes
        r = await doc.confirm(r["token"])
        r["confirmed"] = True
    return r


def owners(objs: list) -> list:
    """What a person drags: a part made inside library code (a glyph of a
    Tex, a line of a grid) stands for the nearest object the scene made."""
    out, seen = [], set()
    for o in objs:
        if o.get("virtual"):
            continue
        u, n = o, 0
        while not u.get("site") and u.get("parent") is not None and n < 8:
            u, n = objs[u["parent"]], n + 1
        if not u.get("site"):
            u = o  # nobody owns it: counted, and refused
        if u["id"] not in seen:
            seen.add(u["id"])
            out.append(u)
    return out


async def settled(doc: Document):
    """An edit replies once the active scene is traced; the rest follow."""
    t = getattr(doc, "_load_task", None)
    if t is not None and not t.done():
        await t


async def run_scene(doc: Document, scene: str, dst: Path, limit: int) -> dict:
    await settled(doc)
    await doc.activate(scene)
    tr = doc.traces.get(scene) or {}
    if tr.get("error"):
        return {"scene": scene, "skipped": f"scene stops: {tr['error'].get('message', '')[:80]}"}
    f = still_frame(doc, scene)
    r = await doc.frame(scene, f, ids=True)
    if "error" in r:
        return {"scene": scene, "skipped": f"frame: {r['error']}"}
    objs = owners(r.get("objects", []))
    out = {"scene": scene, "f": f, "on_screen": len(objs), "tried": 0, "moved": 0, "back": 0,
           "confirm": 0, "fails": []}
    orig = dst.read_bytes()
    for o in objs[:limit]:
        out["tried"] += 1
        t = time.monotonic()
        r = await _edit(doc, {"type": "edit.move", "scene": scene, "object": o, "f": f, "dx": DX, "dy": DY})
        took = round(time.monotonic() - t, 1)
        if r["type"] != "edit.done":
            out["fails"].append({"id": o["id"], "class": o["class"], "tier": o.get("tier"),
                                 "reason": r.get("reason") or r.get("message", "")})
            continue
        out["moved"] += 1
        out["confirm"] += bool(r.get("confirmed"))
        await settled(doc)
        r2 = await doc.frame(scene, f, ids=True)
        o2 = next((x for x in r2.get("objects", []) if x["id"] == o["id"]), None)
        same = False
        if o2 is not None:
            await _edit(doc, {"type": "edit.move", "scene": scene, "object": o2, "f": f, "dx": -DX, "dy": -DY})
            same = dst.read_bytes() == orig
        out["back"] += same
        if not same:
            out["fails"].append({"id": o["id"], "class": o["class"], "back": False, "took": took,
                                 "summary": r.get("summary", "")})
            dst.write_bytes(orig)
            await doc.file_changed()
            await settled(doc)
    return out


async def run_file(rel: str, limit: int) -> dict:
    group = group_of(rel)
    dst = TMP / group / Path(rel).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / rel, dst)
    doc = Document(dst, [], quiet)
    res = {"file": rel, "group": group, "scenes": []}
    try:
        await doc.load()
        if doc.error:
            res["error"] = doc.error.get("code")
            return res
        for scene in list(doc.traces):
            t = time.monotonic()
            try:
                s = await asyncio.wait_for(run_scene(doc, scene, dst, limit), PER_SCENE)
            except Exception as e:  # noqa: BLE001
                s = {"scene": scene, "crash": f"{type(e).__name__}: {e}"}
            s["s"] = round(time.monotonic() - t, 1)
            res["scenes"].append(s)
            print("   ", line_for(s), flush=True)
    finally:
        doc.close()
    return res


def line_for(s: dict) -> str:
    if "crash" in s or "skipped" in s:
        return f"{s['scene']}: {s.get('crash') or s.get('skipped')}"
    return (f"{s['scene']} f={s['f']}: moved {s['moved']}/{s['tried']} (of {s['on_screen']} on screen), "
            f"back {s['back']}, asked {s['confirm']}, {s['s']} s")


def totals(out: list) -> dict:
    t = {"tried": 0, "moved": 0, "back": 0, "confirm": 0}
    for r in out:
        for s in r.get("scenes", []):
            for k in t:
                t[k] += s.get(k, 0)
    t["pct_moved"] = round(100 * t["moved"] / t["tried"], 1) if t["tried"] else None
    return t


async def main(filt: str | None, limit: int):
    files = [f["path"] for f in scene_files() if f.get("scenes") and not f.get("error")]
    files = [f for f in files if (filt in f if filt else group_of(f) != "repo")]  # repo videos: by filter
    report = TMP.parent / "drag_report.json"
    out = []
    for rel in files:
        print(rel, flush=True)
        try:
            out.append(await run_file(rel, limit))
        except Exception as e:  # noqa: BLE001
            out.append({"file": rel, "crash": f"{type(e).__name__}: {e}"})
            print("    CRASH", e, flush=True)
        report.write_text(json.dumps({"totals": totals(out), "files": out}, indent=1), encoding="utf-8")
    print("\ntotals:", totals(out))
    print(f"report: {report}")


if __name__ == "__main__":
    args = sys.argv[1:]
    limit = 12
    if "--max" in args:
        i = args.index("--max")
        limit = int(args[i + 1])
        del args[i:i + 2]
    asyncio.run(main(args[0] if args else None, limit))
