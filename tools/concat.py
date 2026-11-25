"""Join rendered scene videos into one file (video remuxed, audio rebuilt).

All inputs must come from the same render settings (same quality), which is
always true for scenes of one file rendered together. The scenes' .srt
captions are joined too (OUT.srt), with each cue moved to its scene's start.

Usage:
  .venv\\Scripts\\python tools\\concat.py OUT.mp4 IN1.mp4 IN2.mp4 ...
  .venv\\Scripts\\python tools\\concat.py media/pythagoras_full.mp4 \\
      --scenes pythagoras.py Intro Squares Proof Example Outro --quality h
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


AUDIO_RATE = 48000


def video_end(path: Path) -> float:
    """End time (s) of a clip's video stream."""
    end = 0.0
    with av.open(str(path)) as src:
        st = src.streams.video[0]
        for pkt in src.demux(st):
            if pkt.pts is not None:
                end = max(end, float((pkt.pts + (pkt.duration or 0)) * st.time_base))
    return end


def build_audio(inputs: list[Path], offsets: list[float], total: float) -> np.ndarray | None:
    """One stereo float track for the whole video: each clip's audio placed at
    that clip's start, silence where a clip has none. None if no clip has audio."""
    if not any(len(av.open(str(p)).streams.audio) for p in inputs):
        return None
    buf = np.zeros((2, int(np.ceil(total * AUDIO_RATE)) + AUDIO_RATE), dtype=np.float32)
    resampler = av.AudioResampler(format="fltp", layout="stereo", rate=AUDIO_RATE)
    for path, off in zip(inputs, offsets):
        with av.open(str(path)) as src:
            if not src.streams.audio:
                continue
            pos = int(round(off * AUDIO_RATE))
            frames = list(src.decode(src.streams.audio[0]))
            for frame in frames + [None]:  # None flushes the resampler
                for out in resampler.resample(frame):
                    x = out.to_ndarray()
                    n = min(x.shape[1], buf.shape[1] - pos)
                    buf[:, pos:pos + n] += x[:, :n]
                    pos += x.shape[1]
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=AUDIO_RATE)
    return buf[:, :int(round(total * AUDIO_RATE))]


def concat(out: Path, inputs: list[Path]) -> float:
    """Join clips end to end. Video is remuxed untouched; audio is rebuilt as
    one AAC track (silence where a clip has none), so a clip without
    narration (title card, music-free intro) no longer drops the whole track.

    Each clip starts where the previous clip's *video* ended, so picture and
    sound stay in sync even when a clip's audio is shorter than its video.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    offsets, t = [], 0.0
    for p in inputs:
        offsets.append(t)
        t += video_end(p)
    total = t
    audio = build_audio(inputs, offsets, total)

    with av.open(str(out), "w") as dst:
        with av.open(str(inputs[0])) as first:
            ov = dst.add_stream_from_template(first.streams.video[0])
        apkts = []
        if audio is not None:
            oa = dst.add_stream("aac", rate=AUDIO_RATE, layout="stereo")
            oa.bit_rate = 192_000
            for i in range(0, audio.shape[1], 1024):
                fr = av.AudioFrame.from_ndarray(np.ascontiguousarray(audio[:, i:i + 1024]),
                                                format="fltp", layout="stereo")
                fr.rate, fr.pts = AUDIO_RATE, i
                apkts += oa.encode(fr)
            apkts += oa.encode(None)

        def flush_audio(until: float):
            while apkts and (apkts[0].pts is None or float(apkts[0].pts * apkts[0].time_base) <= until):
                dst.mux(apkts.pop(0))

        for path, off in zip(inputs, offsets):
            with av.open(str(path)) as src:
                ist = src.streams.video[0]
                base = int(round(off / ov.time_base))
                for pkt in src.demux(ist):
                    if pkt.dts is None:
                        continue
                    pts = pkt.pts if pkt.pts is not None else pkt.dts
                    pkt.pts = int(round(pts * ist.time_base / ov.time_base)) + base
                    pkt.dts = int(round(pkt.dts * ist.time_base / ov.time_base)) + base
                    pkt.stream = ov
                    flush_audio(float(pkt.dts * ov.time_base))
                    dst.mux(pkt)
        flush_audio(float("inf"))
    join_srt(out, inputs, offsets)
    return total


_CUE = re.compile(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)\s*\n(.*)", re.S)


def _stamp(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def join_srt(out: Path, inputs: list[Path], offsets: list[float]) -> int:
    """The clips' .srt cues, each moved by its clip's start, as out's .srt.
    Captions for the whole video, and what audio_check.py checks the joined
    file against (every cue must have sound under it). No cues: no .srt (an
    old one is removed, so it can't describe another join)."""
    sec = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for p, off in zip(inputs, offsets):
        srt = p.with_suffix(".srt")
        if not srt.is_file():
            continue
        for block in srt.read_text(encoding="utf-8").replace("\r\n", "\n").strip().split("\n\n"):
            m = _CUE.search(block)
            if m:
                g = m.groups()
                cues.append((sec(*g[:4]) + off, sec(*g[4:8]) + off, g[8].strip()))
    dst = out.with_suffix(".srt")
    if not cues:
        dst.unlink(missing_ok=True)
        return 0
    dst.write_text("".join(f"{i}\n{_stamp(a)} --> {_stamp(b)}\n{text}\n\n" for i, (a, b, text) in enumerate(cues, 1)),
                   encoding="utf-8")
    return len(cues)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("--scenes", nargs="+", metavar=("FILE", "SCENE"),
                    help="a scene file followed by scene names, in order")
    ap.add_argument("--quality", choices=list(QUALITY_DIRS), default="h")
    args = ap.parse_args()

    inputs = [Path(p) for p in args.inputs]
    if args.scenes:
        src, *names = args.scenes
        d = ROOT / "media" / "videos" / Path(src).stem / QUALITY_DIRS[args.quality]
        inputs += [d / f"{n}.mp4" for n in names]
    missing = [str(p) for p in inputs if not p.exists()]
    if not inputs or missing:
        sys.exit(f"Missing inputs: {missing or 'none given'}")
    dur = concat(Path(args.out), inputs)
    print(f"wrote {args.out} ({len(inputs)} clips, {dur:.1f}s)")


if __name__ == "__main__":
    main()
