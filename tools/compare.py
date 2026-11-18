"""Side-by-side comparison: reference video | our render, at matching times.

Each row is one timestamp: the reference frame on the left, ours on the right.
Our clip's local time t is matched to reference time ref_start + t.

  media/review/compare_<name>.png

Usage:
  # one scene: its rendered mp4 against the reference section that starts at 53.1 s
  .venv\\Scripts\\python tools\\compare.py --ours media/videos/eola_preview/480p15/S06_NumericVsGeometric.mp4 --ref-start 53.1
  # whole video, explicit times (seconds)
  .venv\\Scripts\\python tools\\compare.py --ours media/eola_full.mp4 --at 10 60 120 --name full
  # evenly spaced
  .venv\\Scripts\\python tools\\compare.py --ours clip.mp4 --ref-start 12.4 --n 6
"""

from __future__ import annotations

import argparse
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "media" / "review"
DEFAULT_REF = ROOT / "reference" / "original_video.mp4"


def duration(video: Path) -> float:
    with av.open(str(video)) as c:
        s = c.streams.video[0]
        if s.duration and s.time_base:
            return float(s.duration * s.time_base)
        return float(c.duration or 0) / av.time_base


def frame_at(video: Path, t: float) -> Image.Image:
    """Seek near t, then decode forward to the frame shown at time t."""
    with av.open(str(video)) as c:
        s = c.streams.video[0]
        c.seek(max(0, int((t - 1.0) / s.time_base)), stream=s, backward=True)
        last = None
        for f in c.decode(s):
            if f.time is not None and f.time > t + 1e-6 and last is not None:
                break
            last = f.to_image()
        return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--ref", default=str(DEFAULT_REF))
    ap.add_argument("--ref-start", type=float, default=0.0)
    ap.add_argument("--at", type=float, nargs="*", help="local times in our clip")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--name")
    ap.add_argument("--width", type=int, default=560)
    a = ap.parse_args()

    ours, ref = Path(a.ours), Path(a.ref)
    times = a.at
    if not times:
        d = duration(ours)
        times = [round(d * (i + 0.5) / a.n, 2) for i in range(a.n)]

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    w, label = a.width, 24
    h = w * 9 // 16
    sheet = Image.new("RGB", (2 * w + 18, len(times) * (h + label + 6) + 6), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for r, t in enumerate(times):
        y = 6 + r * (h + label + 6)
        for col, (vid, vt, tag) in enumerate(((ref, a.ref_start + t, "reference"),
                                               (ours, t, "ours"))):
            img = frame_at(vid, vt).convert("RGB").resize((w, h))
            x = 6 + col * (w + 6)
            sheet.paste(img, (x, y + label))
            m, s = divmod(vt, 60)
            draw.text((x + 4, y + 3), f"{tag}  {int(m)}:{s:05.2f}", fill=(230, 230, 230), font=font)
    OUT.mkdir(parents=True, exist_ok=True)
    name = a.name or ours.stem
    path = OUT / f"compare_{name}.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
