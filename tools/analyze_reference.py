"""Break a reference video into shots and contact sheets for recreation work.

Samples the video at --fps (default 2), measures how much each sampled frame
differs from the previous one, and marks a shot boundary where the change is
large. Writes, under --out (default reference/analysis):

  shots.csv              shot number, start, end, duration, change score
  sheet_<start>-<end>.png  contact sheets, --per-sheet frames each, timestamped
  frames/<t>.png         full-size frame at the middle of each shot

Usage:
  .venv\\Scripts\\python tools\\analyze_reference.py reference\\original_video.mp4
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def sample(video: Path, fps: float):
    """Yield (time, small grey array, full PIL image) about `fps` times a second."""
    next_t = 0.0
    with av.open(str(video)) as c:
        s = c.streams.video[0]
        s.thread_type = "AUTO"
        for f in c.decode(s):
            t = float(f.time)
            if t + 1e-6 < next_t:
                continue
            next_t = t + 1 / fps
            img = f.to_image()
            small = np.asarray(img.convert("L").resize((160, 90)), dtype=np.float32)
            yield t, small, img


def sheet(frames, path: Path, cols: int):
    tw = 384
    th = int(tw * frames[0][1].height / frames[0][1].width)
    lh = 20
    rows = (len(frames) + cols - 1) // cols
    out = Image.new("RGB", (cols * (tw + 4) + 4, rows * (th + lh + 4) + 4), (40, 40, 40))
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    for i, (t, img) in enumerate(frames):
        r, c = divmod(i, cols)
        x, y = 4 + c * (tw + 4), 4 + r * (th + lh + 4)
        m, s = divmod(t, 60)
        d.text((x + 2, y + 2), f"{int(m)}:{s:05.2f}", fill=(235, 235, 235), font=font)
        out.paste(img.resize((tw, th)), (x, y + lh))
    out.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--out", default="reference/analysis")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--cut", type=float, default=18.0,
                    help="mean abs grey diff (0-255) that counts as a shot change")
    ap.add_argument("--per-sheet", type=int, default=24)
    ap.add_argument("--cols", type=int, default=6)
    args = ap.parse_args()

    out = Path(args.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    samples, diffs = [], []
    prev = None
    for t, small, img in sample(Path(args.video), args.fps):
        diffs.append(0.0 if prev is None else float(np.abs(small - prev).mean()))
        prev = small
        samples.append((t, img))

    # Shot boundaries where the change spikes.
    bounds = [0] + [i for i, d in enumerate(diffs) if d >= args.cut] + [len(samples)]
    bounds = sorted(set(bounds))
    shots = []
    for a, b in zip(bounds, bounds[1:]):
        if b <= a:
            continue
        start = samples[a][0]
        end = samples[b][0] if b < len(samples) else samples[-1][0] + 1 / args.fps
        shots.append((start, end, diffs[a]))
        mid = samples[(a + b - 1) // 2]
        mid[1].save(out / "frames" / f"{mid[0]:07.2f}.png")

    with open(out / "shots.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["shot", "start", "end", "duration", "change"])
        for i, (s, e, d) in enumerate(shots, 1):
            w.writerow([i, f"{s:.2f}", f"{e:.2f}", f"{e - s:.2f}", f"{d:.1f}"])

    for i in range(0, len(samples), args.per_sheet):
        chunk = samples[i:i + args.per_sheet]
        sheet(chunk, out / f"sheet_{chunk[0][0]:06.1f}-{chunk[-1][0]:06.1f}.png", args.cols)

    print(f"{len(samples)} samples, {len(shots)} shots, "
          f"{(len(samples) + args.per_sheet - 1) // args.per_sheet} sheets -> {out}")


if __name__ == "__main__":
    main()
