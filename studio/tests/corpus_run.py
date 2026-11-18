"""Phase 2 exit run over the corpus (testing.md).

For every scene file in the project (repo videos, tool fixtures, the awkward
corpus, the gallery) this opens a copy through the same Document path the
server uses and checks:

  open    every scene traces, frames render at start / middle / end,
          objects are found at the middle frame
  no-op   reading and planning the same value back never changes a byte
  edits   one timing edit, one number edit and one colour edit per file
          (where the code allows): edit -> verify -> write -> undo, and the
          file must come back byte-identical

Copies live in studio/tests/tmp/<group>/ so originals are never touched.
Run:  .venv/Scripts/python -u -m studio.tests.corpus_run [filter]
Report: studio/tests/tmp/corpus_report.json
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
from studio.server.code import planner  # noqa: E402
from studio.server.code.source import Source  # noqa: E402
from studio.server.code.splice import EditError, apply  # noqa: E402
from studio.server.project import Document  # noqa: E402

TMP = ROOT / "studio" / "tests" / "tmp"
PER_FILE = 1200  # seconds


def group_of(rel: str) -> str:
    if rel.startswith("studio/tests/corpus/awkward/"):
        return "awkward"
    if rel.startswith("studio/tests/corpus/gallery/"):
        return "gallery"
    if rel.startswith("tools/fixtures/"):
        return "fixtures"
    return "repo"


async def quiet(_msg):
    pass


def same_value_plans(doc: Document, sm: dict) -> dict:
    """Plan every clip's duration back to its current value."""
    out = {"identical": 0, "insert_only": 0, "refused": 0, "changed": []}
    for clip in sm["clips"]:
        if clip["lock"] or clip["kind"] not in ("play", "wait"):
            continue
        c = dict(clip)
        if clip["anims"]:
            c["default_rate_func"] = clip["anims"][0]["default_rate_func"]
        try:
            plan = planner.plan_timing(doc.src, c, "duration", clip["duration"])
        except EditError:
            out["refused"] += 1
            continue
        new = apply(doc.data, plan.edits)
        if new == doc.data:
            out["identical"] += 1
        elif all(e.start == e.end for e in plan.edits):
            out["insert_only"] += 1  # e.g. bare wait() -> wait(1): same time, now explicit
        else:
            out["changed"].append({"line": clip["line"], "note": plan.note})
    return out


async def settle(doc: Document, r: dict) -> dict:
    if r.get("type") == "edit.preview":
        r = await doc.confirm(r["token"])
    return r


async def round_trip(doc: Document, orig: bytes, msg: dict) -> dict:
    t = time.monotonic()
    r = await settle(doc, await doc.edit({**msg, "rev": doc.rev}))
    res = {"type": r.get("type"), "reason": r.get("reason") or r.get("message"),
           "summary": r.get("summary"), "edit_s": round(time.monotonic() - t, 1)}
    if r.get("type") != "edit.done":
        res["bytes_ok"] = doc.path.read_bytes() == orig
        return res
    res["changed_file"] = doc.path.read_bytes() != orig
    u = await doc.undo_redo("undo")
    res["undo"] = u.get("type")
    res["bytes_ok"] = doc.path.read_bytes() == orig
    return res


def pick_number(objs: list) -> tuple[dict, str, float] | None:
    for o in objs:
        if o.get("tier") != 1 or o.get("in_helper") or not o.get("site"):
            continue
        for k, v in (o.get("kwargs") or {}).items():
            if k in ("run_time", "rate_func"):
                continue
            try:
                n = float(v)
            except ValueError:
                continue
            return o, k, n
    return None


def pick_colour(objs: list) -> tuple[dict, str] | None:
    for o in objs:
        if o.get("tier") != 1 or o.get("in_helper") or not o.get("site"):
            continue
        v = (o.get("kwargs") or {}).get("color")
        if v and v.replace("_", "").isalnum():
            return o, ("RED" if v != "RED" else "BLUE")
    return None


async def run_file(rel: str, api: list[str]) -> dict:
    src = ROOT / rel
    group = group_of(rel)
    dst = TMP / group / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    orig = dst.read_bytes()
    res: dict = {"file": rel, "group": group, "scenes": []}
    doc = Document(dst, api, quiet)
    try:
        t = time.monotonic()
        await doc.load()
        res["load_s"] = round(time.monotonic() - t, 1)
        res["error"] = doc.error
        timing_done = prop_done = colour_done = False
        for name in doc.meta.get("scenes", []) if not doc.error else []:
            tr = doc.traces[name]
            sm = doc._scene_model(tr)
            s = {"name": name, "events": len(tr["events"]), "duration": round(tr["duration"], 3),
                 "error": (tr.get("error") or {}).get("message"), "frames": [],
                 "locked_clips": sum(1 for c in sm["clips"] if c["lock"])}
            await doc.activate(name)
            if doc.prefetch_task:
                doc.prefetch_task.cancel()  # keep the run about what we ask for
            n = doc.frame_count(name)
            mid = n // 2
            for f in sorted({0, mid, n - 1}):
                t = time.monotonic()
                r = await doc.frame(name, f)
                s["frames"].append({"f": f, "s": round(time.monotonic() - t, 2),
                                    "error": (r.get("error") or {}).get("message") if "error" in r else None})
            t = time.monotonic()
            r = await doc.frame(name, mid, ids=True)
            objs = r.get("objects", []) if "error" not in r else []
            s["objects"] = len(objs)
            s["objects_s"] = round(time.monotonic() - t, 2)
            s["noop"] = same_value_plans(doc, sm)
            if not tr.get("error"):
                if not timing_done:
                    for c in sm["clips"]:
                        if c["lock"] or c["tier"] != 1:
                            continue
                        if c["kind"] == "wait" or c.get("play_runtime"):
                            v = round(c["duration"] + 0.5, 2)
                            s["timing_edit"] = await round_trip(doc, orig, {
                                "type": "edit.timing", "scene": name, "clip": c["index"],
                                "field": "duration", "value": v})
                            s["timing_edit"]["line"] = c["line"]
                            timing_done = True
                            break
                if not prop_done and (p := pick_number(objs)):
                    o, k, num = p
                    if float(num).is_integer() and "." not in o["kwargs"][k]:
                        v = int(num) + 1  # counts stay whole
                    elif 0 < num <= 1:
                        v = round(num * 0.8, 3)  # opacities stay in range
                    else:
                        v = round(num * 1.25 + 0.1, 3)
                    s["number_edit"] = await round_trip(doc, orig, {
                        "type": "edit.prop", "scene": name, "object": o, "prop": k,
                        "value": {"number": v}, "f": mid})
                    s["number_edit"].update(object=o["id"], prop=k)
                    prop_done = True
                if not colour_done and (p := pick_colour(objs)):
                    o, colour = p
                    s["colour_edit"] = await round_trip(doc, orig, {
                        "type": "edit.prop", "scene": name, "object": o, "prop": "color",
                        "value": {"name": colour}, "f": mid})
                    s["colour_edit"].update(object=o["id"])
                    colour_done = True
            res["scenes"].append(s)
        res["bytes_ok"] = dst.read_bytes() == orig
        res["restarts"] = doc.worker.restarts
    finally:
        doc.close()
    return res


async def main(filt: str | None):
    files = [f["path"] for f in scene_files() + [{"path": p} for p in broken_files()]
             if not f["path"].startswith("studio/tests/tmp/")]
    files = sorted(set(files))
    if filt:
        files = [f for f in files if filt in f]
    from studio.server.host import WorkerHandle
    h = WorkerHandle(str(ROOT / files[0]))
    api = (await h.request({"op": "hello"})).get("api", [])
    h.close()
    out = []
    report = TMP / "corpus_report.json"
    for rel in files:
        t = time.monotonic()
        try:
            r = await asyncio.wait_for(run_file(rel, api), PER_FILE)
        except Exception as e:  # noqa: BLE001
            r = {"file": rel, "group": group_of(rel), "crash": f"{type(e).__name__}: {e}"}
        r["total_s"] = round(time.monotonic() - t, 1)
        out.append(r)
        print(line_for(r), flush=True)
        report.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nreport: {report}")


def broken_files() -> list[str]:
    """scene_files() skips files that don't parse; the corpus must open them read-only too."""
    d = ROOT / "studio" / "tests" / "corpus" / "awkward"
    return [f"studio/tests/corpus/awkward/{p.name}" for p in d.glob("broken_*.py")]


def line_for(r: dict) -> str:
    if "crash" in r:
        return f"CRASH {r['file']}: {r['crash']}"
    sc = r["scenes"]
    bad_frames = sum(1 for s in sc for f in s["frames"] if f["error"])
    edits = []
    for s in sc:
        for k in ("timing_edit", "number_edit", "colour_edit"):
            if k in s:
                e = s[k]
                edits.append(f"{k[0]}:{'ok' if e['type'] == 'edit.done' and e['bytes_ok'] else e['type']}")
    err = f" error={r['error']['code']}" if r.get("error") else ""
    return (f"{r['file']}: {len(sc)} scenes, {bad_frames} bad frames, bytes_ok={r.get('bytes_ok')}"
            f"{err}, edits[{' '.join(edits)}], {r['total_s']} s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
