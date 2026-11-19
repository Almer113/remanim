"""A scene's sound, mixed from the trace (protocol.md `GET /audio`).

The trace records every narration line and `add_sound()` with its file and
start time (engine/narration.py). This module decodes those files with PyAV
(installed with Manim), mixes them onto one mono track and gives waveform
peaks per clip for the timeline. Pure functions plus a small cache keyed by
the files' paths and mtimes, so an edit that changes one line decodes one
file.
"""

from __future__ import annotations

import functools
import io
import os
import wave
from pathlib import Path

import numpy as np

RATE = 24000          # Edge TTS speaks at 24 kHz; enough for a preview
PEAKS_PER_S = 50      # waveform resolution on the timeline


@functools.lru_cache(maxsize=256)
def _decode(path: str, mtime: float) -> np.ndarray:
    import av
    out = []
    with av.open(path) as c:
        stream = next(s for s in c.streams if s.type == "audio")
        res = av.AudioResampler(format="flt", layout="mono", rate=RATE)
        for packet in c.demux(stream):
            for fr in packet.decode():
                for r in res.resample(fr):
                    out.append(r.to_ndarray().reshape(-1))
        for r in res.resample(None):
            out.append(r.to_ndarray().reshape(-1))
    return np.concatenate(out).astype(np.float32) if out else np.zeros(0, np.float32)


def decode(path: str | Path) -> np.ndarray:
    p = str(Path(path))
    return _decode(p, os.path.getmtime(p))


def clips_of(trace: dict) -> list[dict]:
    """Every sound the scene plays: {file, start, gain}. Narration lines are
    sounds too (say() and voiceover() both call add_sound)."""
    a = trace.get("audio") or {}
    return [{"file": s["file"], "start": float(s["start"]), "gain": s.get("gain")}
            for s in a.get("sounds", []) if s.get("file") and os.path.exists(s["file"])]


def mix(trace: dict) -> np.ndarray:
    """The scene's sound as mono float32 at RATE, as long as the scene."""
    n = int(round(float(trace.get("duration") or 0) * RATE))
    track = np.zeros(max(n, 0), np.float32)
    for c in clips_of(trace):
        x = decode(c["file"])
        if c["gain"]:
            x = x * (10 ** (float(c["gain"]) / 20))
        i = int(round(c["start"] * RATE))
        if i < 0:
            x, i = x[-i:], 0
        end = min(len(track), i + len(x))
        if end > i:
            track[i:end] += x[: end - i]
    np.clip(track, -1, 1, out=track)
    return track


def wav_bytes(samples: np.ndarray) -> bytes:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def peaks(samples: np.ndarray, per_s: int = PEAKS_PER_S) -> list[float]:
    """Peak level per 1/per_s seconds, 0..1, rounded for JSON."""
    step = max(1, RATE // per_s)
    n = len(samples) // step
    if n == 0:
        return []
    m = np.abs(samples[: n * step]).reshape(n, step).max(axis=1)
    return [round(float(v), 3) for v in m]


def waveforms(trace: dict) -> list[dict]:
    """Peaks for each sound on its own (narration rows draw their own line)."""
    out = []
    for c in clips_of(trace):
        x = decode(c["file"])
        out.append({"file": c["file"], "start": c["start"], "duration": round(len(x) / RATE, 4),
                    "peaks": peaks(x)})
    return out
