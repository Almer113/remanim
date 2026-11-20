"""Phase 6 speed bench (docs/phase6/plan.md step 1).

For each scene file (the repo videos and the gallery by default), on a copy
in studio/tests/tmp/speed/, through the same Document path the server uses:

- open: a new Document (a new engine process) loads the file with an empty
  trace cache; "view" is when the first scene is traced and shown, "all"
  when every scene is; "start", "load" and "trace" say where the time went;
- reopen: the same file again, as the server opens it: a spare engine
  started ahead, and the traces cached by the first open;
- first frame: the full frame with ids at the scene's still frame;
- scrub: 20 random half-size frames, with the background prefetch off,
  so every one is an engine frame and not a cache hit;
- edits, each followed by the new frame and then undone: a retime of the
  first retimable clip, a drag of the first editable object, a colour
  change of the same object. "took" is from sending the edit to having
  the new frame; refusals are listed, not timed.

Never run while the studio server or another engine run is busy (shared
media/Tex_studio).

Run:     .venv/Scripts/python -u -m studio.tests.speed_run [filter] [--old]
         (--old: no trace cache and no spare engine, as before Phase 6; run
         both back to back when comparing, since timings depend on the load)
Report:  studio/tests/tmp/speed_report.json (--old: speed_report_old.json)
"""

from __future__ import annotations

import asyncio
import json
import random
import shutil
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from studio.server.app import scene_files  # noqa: E402
from studio.server import tracecache  # noqa: E402
from studio.server.host import WorkerHandle  # noqa: E402
from studio.server.project import Document  # noqa: E402
from studio.tests.corpus_run import group_of  # noqa: E402
from studio.tests.drag_run import owners, settled, still_frame  # noqa: E402

TMP = ROOT / "studio" / "tests" / "tmp"
SCRUB = 20
OLD = False  # --old: measure the way the studio worked before Phase 6 (no cache, no spare engine)
PER_FILE = 1800


def _s(t0: float) -> float:
    return round(time.monotonic() - t0, 3)


async def open_doc(path: Path, api: list, worker=None) -> tuple[Document, dict]:
    """Load a new Document; time to the first scene shown and to all traced."""
    t0 = time.monotonic()
    seen = {}

    async def notify(msg):
        if "view" in seen or msg.get("type") != "model":
            return
        sc = msg.get("scenes") or []
        if any(not s.get("pending") for s in sc):
            seen["view"] = _s(t0)

    doc = Document(path, api, notify, worker=worker)
    doc._no_cache = OLD  # --old: no trace cache, as before Phase 6
    # where the time goes: engine start (process + imports), module load, tracing
    req = doc.worker.request
    parts = {"trace": 0.0}

    async def request(msg, *a, **k):
        t = time.monotonic()
        if msg.get("op") == "load" and "start" not in parts:  # the process is already spawned: wait for imports
            await req({"op": "hello"})
            parts["start"] = _s(t)
            t = time.monotonic()
        r = await req(msg, *a, **k)
        if msg.get("op") == "load":
            parts["load"] = _s(t)
        elif msg.get("op") == "trace":
            parts["trace"] = round(parts["trace"] + time.monotonic() - t, 3)
        return r
    doc.worker.request = request
    await doc.load()
    doc.worker.request = req
    out = {"view": seen.get("view"), "all": _s(t0), **parts}
    return doc, out


async def timed_edit(doc: Document, scene: str, f: int, msg: dict) -> dict:
    t0 = time.monotonic()
    # the playhead goes with the edit, as the UI sends it (not in --old: that came later)
    at = {} if getattr(doc, "_no_cache", False) else {"at": f}
    r = await doc.edit({"rev": doc.rev, "scene": scene, **at, **msg})
    if r["type"] == "edit.preview":
        r = await doc.confirm(r["token"])
    if r["type"] != "edit.done":
        return {"refused": (r.get("reason") or r.get("message") or r["type"])[:120]}
    plan_s = _s(t0)
    # as the UI sees it: the reply (the active scene is traced again), then
    # the frame; the other scenes keep tracing in the background
    fr = await doc.frame(scene, f, ids=True)
    took = _s(t0)
    await settled(doc)
    t1 = time.monotonic()
    u = await doc.undo_redo("undo")
    await doc.frame(scene, f, ids=True)
    undo_s = _s(t1)
    await settled(doc)
    return {"done_s": plan_s, "took": took, "undo_s": undo_s, "frame_error": "error" in fr,
            "undo_ok": u["type"] == "edit.done"}


async def run_file(rel: str, api: list) -> dict:
    dst = TMP / "speed" / group_of(rel) / Path(rel).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / rel, dst)
    orig = dst.read_bytes()
    res = {"file": rel, "group": group_of(rel)}
    # open: nothing cached, a new engine process (the worst case)
    tracecache.CACHE = tracecache.TraceCache(TMP / "speed" / "cache" / str(time.time_ns()))
    doc, res["open"] = await open_doc(dst, api)
    doc.close()
    # reopen: as the server does it, with a spare engine started ahead and the traces cached
    spare = None
    if not OLD:
        spare = WorkerHandle("")
        await spare.request({"op": "hello"})
    doc, res["reopen"] = await open_doc(dst, api, worker=spare)
    try:
        if doc.error:
            res["error"] = doc.error.get("code")
            return res
        scene = next((s for s in doc.meta.get("scenes", []) if not doc.traces[s].get("error")), None)
        if scene is None:
            res["error"] = "no scene runs"
            return res
        res["scene"] = scene
        res["scenes"] = len(doc.meta.get("scenes", []))
        await doc.activate(scene)
        if doc.prefetch_task:
            doc.prefetch_task.cancel()
        f = still_frame(doc, scene)
        t0 = time.monotonic()
        r = await doc.frame(scene, f, ids=True)
        res["first_frame"] = _s(t0)
        n = doc.frame_count(scene)
        rng = random.Random(6)
        times = []
        for g in rng.sample(range(n), min(SCRUB, n)):
            t0 = time.monotonic()
            await doc.frame(scene, g, "half", "jpeg")
            times.append(time.monotonic() - t0)
        res["frames"] = n
        res["scrub"] = {"median": round(statistics.median(times), 3), "max": round(max(times), 3)}

        edits = {}
        clip = next((c for c in doc._scene_model(doc.traces[scene])["clips"]
                     if c["kind"] in ("play", "wait") and not c["lock"]), None)
        if clip is not None:
            edits["retime"] = await timed_edit(doc, scene, f, {"type": "edit.timing", "clip": clip["index"],
                                                               "field": "duration",
                                                               "value": round(clip["duration"] + 0.1, 4)})
        objs = [o for o in owners(r.get("objects", [])) if o.get("site") and o.get("tier", 3) <= 2]
        if objs:
            o = objs[0]
            edits["drag"] = await timed_edit(doc, scene, f, {"type": "edit.move", "object": o, "f": f,
                                                             "dx": 0.4, "dy": -0.25})
            r = await doc.frame(scene, f, ids=True)
            o = next((x for x in r.get("objects", []) if x["id"] == o["id"]), o)
            edits["colour"] = await timed_edit(doc, scene, f, {"type": "edit.prop", "object": o, "f": f,
                                                               "prop": "color", "value": {"name": "YELLOW"}})
        res["edits"] = edits
        res["bytes_ok"] = dst.read_bytes() == orig
    finally:
        doc.close()
    return res


def line_for(r: dict) -> str:
    if "crash" in r or "error" in r:
        return f"{r['file']}: {r.get('crash') or r.get('error')}"
    e = " ".join(f"{k} {v.get('took', 'refused')}" for k, v in r.get("edits", {}).items())
    return (f"{r['file']}: open {r['open']['view']}/{r['open']['all']} s, reopen {r['reopen']['view']}/"
            f"{r['reopen']['all']} s, first frame {r.get('first_frame')} s, scrub {r.get('scrub', {}).get('median')} s, "
            f"edits: {e}")


def summary(out: list) -> dict:
    ok = [r for r in out if "open" in r and "error" not in r and "crash" not in r]

    def med(xs):
        xs = [x for x in xs if x is not None]
        return round(statistics.median(xs), 2) if xs else None
    s = {"files": len(ok)}
    for k in ("open", "reopen"):
        s[k + "_view"] = med([r[k]["view"] for r in ok])
        s[k + "_all"] = med([r[k]["all"] for r in ok])
    s["first_frame"] = med([r.get("first_frame") for r in ok])
    s["scrub_median"] = med([r.get("scrub", {}).get("median") for r in ok])
    for kind in ("retime", "drag", "colour"):
        s[kind] = med([r.get("edits", {}).get(kind, {}).get("took") for r in ok])
        s[kind + "_reply"] = med([r.get("edits", {}).get(kind, {}).get("done_s") for r in ok])
        s[kind + "_undo"] = med([r.get("edits", {}).get(kind, {}).get("undo_s") for r in ok])
    return s


async def main(filt: str | None):
    files = [f["path"] for f in scene_files() if f.get("scenes") and not f.get("error")
             and Path(f["path"]).name not in ("eola_common.py", "manim_kit.py")
             and not f["path"].startswith(("reference/", "studio/tests/tmp/"))]
    files = [f for f in files if group_of(f) in ("repo", "gallery")]
    if filt:
        files = [f for f in files if filt in f]
    from studio.server.host import WorkerHandle
    h = WorkerHandle(str(ROOT / files[0]))
    api = (await h.request({"op": "hello"})).get("api", [])
    h.close()
    out = []
    report = TMP / ("speed_report_old.json" if OLD else "speed_report.json")
    for rel in files:
        try:
            r = await asyncio.wait_for(run_file(rel, api), PER_FILE)
        except Exception as e:  # noqa: BLE001
            r = {"file": rel, "crash": f"{type(e).__name__}: {e}"}
        out.append(r)
        print(line_for(r), flush=True)
        report.write_text(json.dumps({"summary": summary(out), "files": out}, indent=1), encoding="utf-8")
    print("\nsummary:", summary(out))
    print(f"report: {report}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--old" in args:
        args.remove("--old")
        OLD = True
    asyncio.run(main(args[0] if args else None))
