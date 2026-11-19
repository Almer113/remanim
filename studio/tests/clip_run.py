"""Share of timeline clips the studio can retime (corpus.md §4, target ≥ 98%).

For every scene of every scene file, each `play()` / `wait()` clip on the
timeline is planned with a trim of +0.1 s (code_spec §4.4). A clip counts as
retimable when the plan is made, including plans that ask first (a call in
a loop). Locked clips (inside a helper, timed by library code) and refused
plans count against, with their reasons. Every 8th planned edit (at most
two per scene) is also written, verified by replay and undone, and the
file must come back byte for byte.

Copies live in studio/tests/tmp/clips/ so originals are never touched.
Never run while the studio server or another engine run is busy (shared
media/Tex_studio).

Run:  .venv/Scripts/python -u -m studio.tests.clip_run [filter]
Report: studio/tests/tmp/clip_report.json
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from studio.server.app import scene_files  # noqa: E402
from studio.server.code import planner  # noqa: E402
from studio.server.code.splice import EditError  # noqa: E402
from studio.server.project import Document  # noqa: E402
from studio.tests.corpus_run import group_of, quiet, round_trip  # noqa: E402

TMP = ROOT / "studio" / "tests" / "tmp"
PER_FILE = 1800
EVERY = 8
PER_SCENE_VERIFY = 2


def reason_key(text: str) -> str:
    """Group reasons: drop line numbers and names after the first clause."""
    t = (text or "").split("(line")[0].split(" — ")[0]
    for prefix in ("inside ", "timed by "):
        if t.startswith(prefix):
            return prefix + "…"
    return t[:90]


async def run_file(rel: str, api: list[str]) -> dict:
    group = group_of(rel)
    dst = TMP / "clips" / group / Path(rel).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / rel, dst)
    orig = dst.read_bytes()
    doc = Document(dst, api, quiet)
    res = {"file": rel, "group": group, "clips": 0, "retimable": 0, "locked": 0, "refused": 0,
           "verified": 0, "verify_failed": [], "reasons": Counter(), "scenes": []}
    try:
        await doc.load()
        if doc.error:
            res["error"] = doc.error.get("code")
            return res
        planned_seen = 0
        for name in doc.meta.get("scenes", []):
            tr = doc.traces[name]
            if tr.get("error"):
                res["scenes"].append({"scene": name, "skipped": "scene stops early"})
                continue
            sm = doc._scene_model(tr)
            s = Counter()
            verified_here = 0
            for clip in sm["clips"]:
                if clip["kind"] not in ("play", "wait"):
                    continue
                s["clips"] += 1
                if clip["lock"]:
                    s["locked"] += 1
                    res["reasons"]["locked: " + reason_key(clip["lock"])] += 1
                    continue
                c = dict(clip)
                if clip["anims"]:
                    c["default_rate_func"] = clip["anims"][0]["default_rate_func"]
                value = round(clip["duration"] + 0.1, 4)
                try:
                    planner.plan_timing(doc.src, c, "duration", value)
                except EditError as e:
                    s["refused"] += 1
                    res["reasons"]["refused: " + reason_key(str(e))] += 1
                    continue
                s["retimable"] += 1
                planned_seen += 1
                if planned_seen % EVERY == 1 and verified_here < PER_SCENE_VERIFY:
                    await doc.activate(name)
                    r = await round_trip(doc, orig, {"type": "edit.timing", "scene": name,
                                                     "clip": clip["index"], "field": "duration",
                                                     "value": value})
                    verified_here += 1
                    if r["type"] == "edit.done" and r["bytes_ok"]:
                        res["verified"] += 1
                    else:
                        res["verify_failed"].append({"scene": name, "line": clip["line"], **r})
                    if dst.read_bytes() != orig:  # never carry a failed undo into the next plan
                        dst.write_bytes(orig)
                        await doc.file_changed()
            for k in ("clips", "retimable", "locked", "refused"):
                res[k] += s[k]
            res["scenes"].append({"scene": name, **s})
        res["bytes_ok"] = dst.read_bytes() == orig
    finally:
        doc.close()
    res["reasons"] = dict(res["reasons"].most_common())
    return res


def totals(out: list) -> dict:
    t = Counter()
    reasons = Counter()
    for r in out:
        for k in ("clips", "retimable", "locked", "refused", "verified"):
            t[k] += r.get(k, 0)
        t["verify_failed"] += len(r.get("verify_failed", []))
        reasons.update(r.get("reasons", {}))
    d = dict(t)
    d["pct"] = round(100 * t["retimable"] / t["clips"], 1) if t["clips"] else None
    d["reasons"] = dict(reasons.most_common())
    return d


async def main(filt: str | None):
    files = sorted({f["path"] for f in scene_files() if f.get("scenes") and not f.get("error")
                    and not f["path"].startswith("studio/tests/tmp/")})
    if filt:
        files = [f for f in files if filt in f]
    from studio.server.host import WorkerHandle
    h = WorkerHandle(str(ROOT / files[0]))
    api = (await h.request({"op": "hello"})).get("api", [])
    h.close()
    out = []
    report = TMP / "clip_report.json"
    for rel in files:
        t = time.monotonic()
        try:
            r = await asyncio.wait_for(run_file(rel, api), PER_FILE)
        except Exception as e:  # noqa: BLE001
            r = {"file": rel, "group": group_of(rel), "crash": f"{type(e).__name__}: {e}"}
        r["total_s"] = round(time.monotonic() - t, 1)
        out.append(r)
        if "crash" in r:
            print(f"CRASH {rel}: {r['crash']}", flush=True)
        else:
            print(f"{rel}: {r['retimable']}/{r['clips']} retimable, {r['locked']} locked, "
                  f"{r['refused']} refused, verified {r['verified']}, failed {len(r['verify_failed'])}, "
                  f"bytes_ok={r.get('bytes_ok')}, {r['total_s']} s", flush=True)
        report.write_text(json.dumps({"totals": totals(out), "files": out}, indent=1), encoding="utf-8")
    print("\ntotals:", json.dumps(totals(out), indent=1))
    print(f"report: {report}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
