"""Spike S2 benchmark: drag an object, edit the code, check the result.

For each scene, at a few still moments (middle of wait()s) and optionally
near the end of plays, every selectable object (S3's resolution of each
drawn leaf) is "dragged" by (DX, DY):
  1. code_edit.candidates() ranks possible edits
  2. verify-by-replay: apply the first, write the file to studio/spikes/tmp/
     (the preview server only watches the top folder), replay to the same
     time, check the object's centre moved by exactly (DX, DY); else try the
     next candidate
  3. report: which candidate worked, the change, bytes changed, which other
     objects moved too (dependents such as next_to(target) are expected;
     listed for review), and whether dragging back by (-DX, -DY) on the
     edited file restores the original bytes

  .venv/Scripts/python studio/spikes/s2_bench.py test_scene.py --plays 5
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from code_edit import MorphRecorder, MoveRecorder, Source, apply, candidates  # noqa: E402
from frame_engine import ROOT, FrameEngine  # noqa: E402
from identity import OriginTracker, parent_map, resolve  # noqa: E402
from s3_bench import drawn_leaves  # noqa: E402

DX, DY = 0.4, -0.25
TMP = ROOT / "studio" / "spikes" / "tmp"
OUT = ROOT / "media" / "studio_spikes" / "s2"


def selectables(scene):
    parents = parent_map(scene)
    seen = {}
    for leaf in drawn_leaves(scene):
        sel, origin, how = resolve(leaf, parents)
        if sel is not None:
            seen.setdefault(id(sel), (sel, origin, how))
    return list(seen.values())


def key_of(mob, line_shift=None):
    """Identity across the original and an edited replay: columns can move
    when an edit lands earlier on the same line, and lines move after an
    inserted line (line_shift = (first moved line, +n))."""
    o = getattr(mob, "_studio_origin", None)
    if o is None:
        return None
    s = o.site or o.user_site
    if s is None:
        return None
    line = s.line
    if line_shift and line >= line_shift[0]:
        line -= line_shift[1]
    return (type(mob).__name__, s.func, line, o.occurrence, o.site is not None)


def positions(scene, line_shift=None) -> dict:
    out = {}
    for m in scene.get_mobject_family_members():
        k = key_of(m, line_shift)
        if k is not None:
            out.setdefault(k, m.get_center().copy())
    return out


def inserted_lines(original: bytes, edits):
    for e in edits:
        n = e.text.count("\n") - original[e.start:e.end].count(b"\n")
        if n:
            return (original[:e.start].count(b"\n") + 1, n)
    return None


class Bench:
    def __init__(self, path: Path, tracker):
        self.path, self.tracker = path, tracker
        self.original = path.read_bytes()
        self.n = 0

    def replay_edited(self, data: bytes, name: str, t: float):
        self.n += 1
        tmp = TMP / f"{self.path.stem}__e{self.n}.py"
        tmp.write_bytes(data)
        self.tracker.files.add(str(tmp.resolve()).lower())
        self.tracker._user_files.clear()
        try:
            eng = FrameEngine(tmp.relative_to(ROOT))
            self.tracker.reset_counts()
            _, scene = eng._run(name, t, None)
            return scene, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"[:100]
        finally:
            tmp.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("scenes", nargs="*")
    ap.add_argument("--waits", type=int, default=2, help="still moments per scene")
    ap.add_argument("--plays", type=int, default=0, help="moments near the end of plays")
    ap.add_argument("--max", type=int, default=14, help="objects per moment")
    args = ap.parse_args()

    path = (ROOT / args.file).resolve()
    tracker = OriginTracker([path])
    MoveRecorder(tracker)
    MorphRecorder()
    eng = FrameEngine(args.file)
    TMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    bench = Bench(path, tracker)
    original = bench.original
    src = Source(original)
    report, totals = {}, Counter()

    for name in args.scenes or eng.scenes():
        events = eng.trace(name)
        waits = [(s + d / 2) for s, d, k in events if k == "wait" and d >= 0.3]
        picks = [waits[int(i * len(waits) / args.waits)] for i in range(min(args.waits, len(waits)))]
        plays = [(s + d * 0.9) for s, d, k in events if k == "play"]
        picks += [plays[int(i * len(plays) / args.plays)] for i in range(min(args.plays, len(plays)))]
        rows, done = [], set()
        print(f"\n{name}", flush=True)
        for t in picks:
            tracker.reset_counts()
            _, scene = eng._run(name, t, None)
            before = positions(scene)
            for sel, origin, how in selectables(scene)[: args.max]:
                k = key_of(sel)
                if k is None or (k, round(t, 1)) in done:
                    continue
                done.add((k, round(t, 1)))
                row = {"t": round(t, 2), "object": f"{k[0]} @ {k[1]}:{k[2]}", "how": how}
                cands = candidates(sel, src, DX, DY)
                if not cands:
                    row["result"] = "blocked"
                    totals["blocked"] += 1
                    rows.append(row)
                    print(f"  t={row['t']:5} {row['object']:40} blocked", flush=True)
                    continue
                for i, (note, edits) in enumerate(cands[:3]):
                    dx, dy = DX, DY
                    for attempt in range(2):
                        if attempt:
                            # calibrate by replay: later scale()s act on the
                            # shift linearly, so correct the delta once
                            dx, dy = DX * DX / got[0], DY * DY / got[1]
                            note, edits = candidates(sel, src, dx, dy)[i]
                            note += f" (delta x{DX / got[0]:.2f}, x{DY / got[1]:.2f})"
                        new = apply(original, edits)
                        shift = inserted_lines(original, edits)
                        scene2, err = bench.replay_edited(new, name, t)
                        if scene2 is None:
                            row.setdefault("tried", []).append(f"{note}: crash {err}")
                            break
                        after = positions(scene2, shift)
                        moved = after.get(k)
                        got = None if moved is None else [float(v) for v in (moved - before[k])[:2]]
                        if got is not None and np.allclose(got, [DX, DY], atol=0.01):
                            break
                        row.setdefault("tried", []).append(
                            f"{note}: moved {None if got is None else [round(g, 2) for g in got]}")
                        if got is None or abs(got[0]) < 0.05 or abs(got[1]) < 0.03 \
                                or got[0] * DX < 0 or got[1] * DY < 0:
                            break  # not a scaled version of the drag
                    if scene2 is None or got is None or not np.allclose(got, [DX, DY], atol=0.01):
                        continue
                    fam = {key_of(m) for m in sel.get_family()}
                    row.update(result="moved", candidate=i + 1, edit=note,
                               change=" | ".join(f"{original[e.start:e.end].decode()!r} -> {e.text!r}"
                                                 for e in edits),
                               diff_bytes=sum(len(e.text) + (e.end - e.start) for e in edits),
                               others=sorted({f"{kk[0]} @ {kk[2]}" for kk, v in before.items()
                                              if kk[-1] and kk not in fam and kk in after
                                              and not np.allclose(after[kk], v, atol=1e-4)})[:5])
                    # drag back on the edited file, using what its replay recorded
                    obj2 = next((m for m in scene2.get_mobject_family_members()
                                 if key_of(m, shift) == k), None)
                    back = candidates(obj2, Source(new), -dx, -dy) if obj2 is not None else []
                    # dragging back re-runs the ranking; the edit that wins
                    # is the same kind as the one that worked here
                    row["back_identical"] = any(apply(new, e) == original for _, e in back[:3])
                    break
                else:
                    row["result"] = "FAILED"
                totals[row["result"]] += 1
                if row["result"] == "moved":
                    totals[f"candidate {row['candidate']}"] += 1
                    totals["back_identical"] += row["back_identical"]
                rows.append(row)
                print(f"  t={row['t']:5} {row['object']:40} {row['result']:7}"
                      f" #{row.get('candidate', '-')} {row.get('edit', '')[:52]:52}"
                      f" {row.get('change', '')[:64]}"
                      + (f"  others {row['others']}" if row.get("others") else "")
                      + ("" if row.get("back_identical", True) else "  back!=orig")
                      + (f"  tried {row['tried']}" if row["result"] != "moved" and row.get("tried") else ""),
                      flush=True)
        report[name] = rows
    print("\nTOTAL", dict(totals))
    (OUT / f"{path.stem}.json").write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
