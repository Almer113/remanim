"""Spike S1 benchmark: how fast, and how right, is frame_at(t)?

For each scene: trace it, then ask for frames at evenly spaced times.
Speed: time per frame_at() call (the first call per scene is reported apart,
since it includes compiling LaTeX into the studio's own cache).
Correctness: compare each frame with the same frame of the rendered 480p
video, if there is one (mean absolute pixel difference, 0-255).

  .venv/Scripts/python studio/spikes/s1_bench.py order_matters.py [Scene ...] [--n 8]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import av
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_engine import ROOT, FrameEngine  # noqa: E402

OUT = ROOT / "media" / "studio_spikes" / "s1"


def video_frames(path: Path, fps: int, times: list[float]) -> dict[float, np.ndarray]:
    """Frames of the rendered video at the given times (frame index = t*fps)."""
    want = {round(t * fps): t for t in times}
    got = {}
    with av.open(str(path)) as c:
        for i, fr in enumerate(c.decode(video=0)):
            if i in want:
                got[want[i]] = fr.to_ndarray(format="rgb24")
            if len(got) == len(want):
                break
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("scenes", nargs="*")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--ref-media", default="media",
                    help="media folder of an UNCACHED reference render "
                         "(cached plays shift the clock by up to a frame)")
    args = ap.parse_args()

    t0 = time.perf_counter()
    eng = FrameEngine(args.file)
    load = time.perf_counter() - t0
    print(f"load {args.file}: {load:.2f}s")
    scenes = args.scenes or eng.scenes()
    fps = 15
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"file": args.file, "load_s": round(load, 3), "scenes": {}}

    for name in scenes:
        t0 = time.perf_counter()
        events = eng.trace(name)
        first = time.perf_counter() - t0
        total = events[-1][0] + events[-1][1] if events else 0.0
        # frame-aligned sample times, avoiding the very end
        times = [round((total * (k + 0.5) / args.n) * fps) / fps + 1e-4 for k in range(args.n)]
        lat, frames = [], {}
        for t in times:
            t1 = time.perf_counter()
            frames[t] = np.asarray(eng.frame_at(name, t))
            lat.append(time.perf_counter() - t1)
        video = ROOT / args.ref_media / "videos" / Path(args.file).stem / "480p15" / f"{name}.mp4"
        diffs = []
        if video.exists():
            ref = video_frames(video, fps, times)
            for t, img in frames.items():
                if t in ref and ref[t].shape == img.shape:
                    diffs.append(float(np.abs(ref[t].astype(int) - img.astype(int)).mean()))
        worst_t = None
        if diffs:
            worst_i = int(np.argmax(diffs))
            worst_t = times[worst_i]
            # save the worst pair side by side for a look
            from PIL import Image
            pair = np.concatenate([ref[worst_t], frames[worst_t]], axis=1)
            Image.fromarray(pair.astype(np.uint8)).save(OUT / f"{name}_worst.png")
        r = {
            "duration": round(total, 2), "plays": len(events),
            "first_s": round(first, 3),
            "median_s": round(statistics.median(lat), 3),
            "max_s": round(max(lat), 3),
            "diff_mean": round(statistics.mean(diffs), 2) if diffs else None,
            "diff_max": round(max(diffs), 2) if diffs else None,
            "worst_t": worst_t,
        }
        report["scenes"][name] = r
        print(f"{name:14} {total:6.1f}s {len(events):3} plays | first {first:5.2f}s"
              f" median {r['median_s']:5.3f}s max {r['max_s']:5.3f}s"
              f" | diff mean {r['diff_mean']} max {r['diff_max']} (t={worst_t})")
    (OUT / f"{Path(args.file).stem}.json").write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
