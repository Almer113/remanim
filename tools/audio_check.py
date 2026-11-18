"""Check that rendered videos actually contain the narration.

For a scene clip, each subtitle cue in the .srt Manim writes next to it must
have sound under it. For any file, it prints the audio length, peak level,
and the spans where something is audible.

Usage:
  .venv\\Scripts\\python tools\\audio_check.py --scenes order_matters.py Question Takeaway --quality l
  .venv\\Scripts\\python tools\\audio_check.py media/order_matters_full.mp4

Exit code 1 if any file has no audio or any cue is silent.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import av
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
QUALITY_DIRS = {"l": "480p15", "m": "720p30", "h": "1080p60"}
WIN = 0.05        # seconds per loudness window
THRESH = 0.01     # RMS above this counts as sound


def loudness(path: Path):
    """(window RMS array, video duration) or (None, duration) if no audio."""
    with av.open(str(path)) as c:
        vdur = float(c.duration or 0) / av.time_base
        if not c.streams.audio:
            return None, vdur
        res = av.AudioResampler(format="flt", layout="mono", rate=16000)
        chunks = []
        for f in c.decode(c.streams.audio[0]):
            for o in res.resample(f):
                chunks.append(o.to_ndarray().reshape(-1))
        x = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
    n = int(16000 * WIN)
    x = x[: len(x) // n * n].reshape(-1, n)
    return np.sqrt((x ** 2).mean(axis=1)), vdur


def spans(rms):
    out, start = [], None
    for i, loud in enumerate(np.append(rms > THRESH, False)):
        if loud and start is None:
            start = i
        elif not loud and start is not None:
            if (i - start) * WIN >= 0.2:
                out.append((start * WIN, i * WIN))
            start = None
    return out


def srt_cues(path: Path):
    if not path.exists():
        return []
    t = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)\n(.*)", block, re.S)
        if m:
            g = m.groups()
            cues.append((t(*g[:4]), t(*g[4:8]), g[8].strip().replace("\n", " ")))
    return cues


def check(path: Path) -> bool:
    rms, vdur = loudness(path)
    if rms is None:
        srt = path.with_suffix(".srt")
        if not srt_cues(srt):  # no .srt (or no cues): a scene without narration
            print(f"ok   {path.name}: silent scene (no narration cues), video {vdur:.1f}s")
            return True
        print(f"FAIL {path.name}: no audio track (video {vdur:.1f}s)")
        return False
    sp = spans(rms)
    heard = sum(b - a for a, b in sp)
    print(f"{'ok  ' if sp else 'FAIL'} {path.name}: audio {len(rms) * WIN:.1f}s / video {vdur:.1f}s, "
          f"peak {rms.max():.3f}, sound in {len(sp)} spans ({heard:.1f}s)")
    good = bool(sp)
    for a, b, text in srt_cues(path.with_suffix(".srt")):
        i, j = int(a / WIN), max(int(b / WIN), int(a / WIN) + 1)
        if not (rms[i:j] > THRESH).any():
            print(f"     SILENT cue {a:6.2f}-{b:6.2f}s: {text[:60]!r}")
            good = False
    return good


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--scenes", nargs="+", metavar=("FILE", "SCENE"))
    ap.add_argument("--quality", choices=list(QUALITY_DIRS), default="l")
    a = ap.parse_args()
    paths = [Path(f) for f in a.files]
    if a.scenes:
        src, *names = a.scenes
        d = ROOT / "media" / "videos" / Path(src).stem / QUALITY_DIRS[a.quality]
        paths += [d / f"{n}.mp4" for n in names]
    ok = all([check(p) for p in paths])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
