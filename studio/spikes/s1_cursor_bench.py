"""Spike S1 benchmark for live cursors (cursor_engine.py).

Per scene: start a pool, wait until its cursors are parked (this is the
background warm-up after opening a scene or saving an edit), then measure
  - random:  frames at random times (clicking around the timeline)
  - scrub:   consecutive frames from a random point (dragging the playhead)
and check every frame against an uncached reference render.

  .venv/Scripts/python studio/spikes/s1_cursor_bench.py order_matters.py \
      [Scene ...] --ref-media media/studio_spikes/fresh
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cursor_engine import CursorPool  # noqa: E402
from frame_engine import ROOT, FrameEngine  # noqa: E402
from s1_bench import video_frames  # noqa: E402

OUT = ROOT / "media" / "studio_spikes" / "s1"


def rss_mb() -> float:
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                    ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 2**20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("scenes", nargs="*")
    ap.add_argument("--random", type=int, default=20)
    ap.add_argument("--scrub", type=int, default=20)
    ap.add_argument("--park-every", type=float, default=1.0)
    ap.add_argument("--ref-media", default=None)
    args = ap.parse_args()

    eng = FrameEngine(args.file)
    fps = 15
    rng = random.Random(1)
    report = {}
    for name in args.scenes or eng.scenes():
        events = eng.trace(name)
        total = events[-1][0] + events[-1][1]
        mem0 = rss_mb()
        t0 = time.perf_counter()
        pool = CursorPool(eng, name, total, park_every=args.park_every)
        pool.wait_parked()
        warm = time.perf_counter() - t0
        mem = rss_mb() - mem0
        print(f"  rss before {mem0:.0f} MB, parked {rss_mb():.0f} MB")

        frames: dict[float, np.ndarray] = {}

        def get(t):
            t1 = time.perf_counter()
            frames[t] = np.asarray(pool.frame_at(t))
            return time.perf_counter() - t1

        n_total = int(total * fps)
        rand_t = [rng.randrange(n_total) / fps + 1e-4 for _ in range(args.random)]
        rand = [get(t) for t in rand_t]
        s0 = rng.randrange(n_total - args.scrub)
        scrub = [get((s0 + i) / fps + 1e-4) for i in range(args.scrub)]

        diffs = []
        if args.ref_media:
            video = ROOT / args.ref_media / "videos" / Path(args.file).stem / "480p15" / f"{name}.mp4"
            if video.exists():
                ref = video_frames(video, fps, list(frames))
                pairs = [(float(np.abs(ref[t].astype(int) - img.astype(int)).mean()), t)
                         for t, img in frames.items() if t in ref]
                diffs = [d for d, _ in pairs]
                d, t = max(pairs)
                from PIL import Image
                Image.fromarray(np.concatenate([ref[t], frames[t]], axis=1).astype(np.uint8)).save(
                    OUT / f"{name}_cursor_worst.png")
                print(f"  worst diff {d:.2f} at t={t:.3f}")
        pool.close()
        r = {"duration": round(total, 1), "cursors": len(pool.spots),
             "warm_s": round(warm, 2), "mem_mb": round(mem),
             "random_median": round(statistics.median(rand), 3),
             "random_max": round(max(rand), 3),
             "scrub_median": round(statistics.median(scrub), 3),
             "scrub_max": round(max(scrub), 3),
             "diff_max": round(max(diffs), 2) if diffs else None}
        report[name] = r
        print(f"{name:15} {total:5.1f}s {r['cursors']:2} cursors warm {warm:5.1f}s"
              f" +{r['mem_mb']:4}MB | random median {r['random_median']:.3f}s"
              f" max {r['random_max']:.3f}s | scrub median {r['scrub_median']:.3f}s"
              f" max {r['scrub_max']:.3f}s | diff max {r['diff_max']}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{Path(args.file).stem}_cursors.json").write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
