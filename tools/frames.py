"""Frame review for Manim scenes: contact sheet + exact frames.

Renders the scene at low quality (unless the video is already newer than the
source file), then writes:

  media/review/<Scene>_sheet.png   evenly spaced frames in a labelled grid
  media/review/<Scene>_t<sec>.png  full-size frames for each --at timestamp

Usage:
  .venv\\Scripts\\python tools\\frames.py my_scene.py SceneName
  .venv\\Scripts\\python tools\\frames.py my_scene.py SceneName --at 2.5 4
  .venv\\Scripts\\python tools\\frames.py my_scene.py SceneName --grid 3x3 --quality m
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
QUALITY_DIRS = {"l": "480p15", "m": "720p30", "h": "1080p60"}
OUT = ROOT / "media" / "review"


def video_path(src: Path, scene: str, q: str) -> Path:
    return ROOT / "media" / "videos" / src.stem / QUALITY_DIRS[q] / f"{scene}.mp4"


def render(src: Path, scene: str, q: str) -> None:
    cmd = [sys.executable, "-m", "manim", "render", f"-q{q}", str(src), scene]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
        sys.exit(f"Render failed for {scene}")


def frames_at(video: Path, times: list[float]) -> list[tuple[float, Image.Image]]:
    """Decode the frame shown at each requested time (in seconds)."""
    out = []
    with av.open(str(video)) as c:
        stream = c.streams.video[0]
        frames = [(float(f.time), f.to_image()) for f in c.decode(stream)]
    if not frames:
        return out
    for t in times:
        best = frames[0]
        for ft, img in frames:
            if ft <= t + 1e-6:
                best = (ft, img)
            else:
                break
        out.append((t, best[1]))
    return out


def duration(video: Path) -> float:
    with av.open(str(video)) as c:
        s = c.streams.video[0]
        if s.duration and s.time_base:
            return float(s.duration * s.time_base)
        return float(c.duration or 0) / av.time_base


def contact_sheet(tiles: list[tuple[float, Image.Image]], cols: int, path: Path):
    tw = 400
    th = int(tw * tiles[0][1].height / tiles[0][1].width)
    label_h = 22
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + label_h + 6) + 6), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    for i, (t, img) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = 6 + c * (tw + 6)
        y = 6 + r * (th + label_h + 6)
        draw.text((x + 2, y + 2), f"#{i + 1}  t={t:.2f}s", fill=(230, 230, 230), font=font)
        sheet.paste(img.resize((tw, th)), (x, y + label_h))
    sheet.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("scene")
    ap.add_argument("--grid", default="4x4", help="contact sheet COLSxROWS (default 4x4)")
    ap.add_argument("--at", type=float, nargs="*", default=[], help="also save full frames at these seconds")
    ap.add_argument("--quality", choices=list(QUALITY_DIRS), default="l")
    ap.add_argument("--no-render", action="store_true", help="use the existing video as-is")
    args = ap.parse_args()

    src = Path(args.file).resolve()
    video = video_path(src, args.scene, args.quality)
    stale = not video.exists() or video.stat().st_mtime < src.stat().st_mtime
    if stale and not args.no_render:
        render(src, args.scene, args.quality)
    if not video.exists():
        sys.exit(f"No video at {video}")

    OUT.mkdir(parents=True, exist_ok=True)
    cols, rows = (int(n) for n in args.grid.lower().split("x"))
    n = cols * rows
    dur = duration(video)
    # Sample the middle of n equal slices, plus the very last frame.
    times = [dur * (i + 0.5) / n for i in range(n - 1)] + [max(dur - 0.01, 0)]
    sheet_path = OUT / f"{args.scene}_sheet.png"
    contact_sheet(frames_at(video, times), cols, sheet_path)
    print(f"duration {dur:.2f}s")
    print(f"sheet    {sheet_path.relative_to(ROOT)}")
    for t, img in frames_at(video, args.at):
        p = OUT / f"{args.scene}_t{t:.2f}.png"
        img.save(p)
        print(f"frame    {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
