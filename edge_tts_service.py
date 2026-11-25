"""manim-voiceover speech service backed by Microsoft Edge's free neural voices.

manim-voiceover 0.4.0 has no Edge TTS backend, so this adapter provides one.
It uses the `edge-tts` package; there's no API key or account, but the
narration text is sent to Microsoft's online service. Results are cached in
media/voiceovers, so a voice line is only synthesised again when its text,
voice or rate changes.

Word timings from Edge are passed on as manim-voiceover "word boundaries", so
`<bookmark mark="X"/>` tags and `tracker.time_until_bookmark("X")` work.

    from edge_tts_service import EdgeTTSService
    self.set_speech_service(EdgeTTSService(voice="en-US-AndrewNeural"))
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

import edge_tts
from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService, initialize_speech_service, path_to_string


class EdgeTTSService(SpeechService):
    def __init__(self, voice: str = "en-US-AndrewNeural", rate: str = "+0%",
                 pitch: str = "+0Hz", **kwargs) -> None:
        """
        voice: any Edge neural voice (list them with `edge-tts --list-voices`).
        rate:  speaking speed, e.g. "-10%" for slower, "+10%" for faster.
        """
        initialize_speech_service(self, kwargs)
        self.voice, self.rate, self.pitch = voice, rate, pitch

    def _input_data(self, text: str) -> dict:
        return {"input_text": remove_bookmarks(text), "service": "edge-tts",
                "voice": self.voice, "rate": self.rate, "pitch": self.pitch}

    def _wrap_generate_from_text(self, text: str, **kwargs) -> dict:
        # manim-voiceover appends a cache entry on EVERY call, cache hits
        # included: cache.json grew by one copy per spoken line per render
        # (934 entries for 95 lines), every say() re-parsed all of it, and
        # two processes writing it at once corrupted it. A hit is returned
        # as stored, without writing.
        #
        # Several processes (a render, the preview server, studio workers) can
        # meet the same new line at once. cache.json is read-modify-written, so
        # the whole lookup-or-synthesise runs under a lock file in the cache
        # folder: the second process waits, then finds the first one's entry.
        # A hit is looked up first without the lock, so lines already spoken
        # never wait behind another process's synthesis.
        hit = self._cached_line(text, kwargs, quiet=True)
        if hit is not None:
            return hit
        with _cache_lock(Path(self.cache_dir)):
            hit = self._cached_line(text, kwargs)
            if hit is not None:
                return hit
            return super()._wrap_generate_from_text(text, **kwargs)

    def _cached_line(self, text: str, kwargs: dict, quiet: bool = False):
        if kwargs.get("path") is not None or self.global_speed != 1:
            return None
        norm = " ".join(text.split())  # as the base class does
        try:
            cached = self.get_cached_result(self._input_data(norm), self.cache_dir)
        except Exception:  # noqa: BLE001  (unlocked: cache.json may be mid-write)
            if not quiet:
                raise
            return None
        return cached if cached is not None and "final_audio" in cached else None

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kwargs) -> dict:
        cache_dir = Path(cache_dir or self.cache_dir)
        input_data = self._input_data(text)
        input_text = input_data["input_text"]

        cached = self.get_cached_result(input_data, cache_dir)
        if cached is not None:
            return cached

        audio_path = path_to_string(path) if path else self.get_audio_basename(input_data) + ".mp3"
        audio, words = self._synthesise(input_text)
        tmp = cache_dir / (audio_path + f".{os.getpid()}.tmp")
        tmp.write_bytes(audio)
        os.replace(tmp, cache_dir / audio_path)  # never a half-written mp3

        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
            "word_boundaries": _to_word_boundaries(input_text, words),
        }

    # A stalled connection once hung a run for two hours despite edge-tts's own
    # timeouts, so each attempt gets a hard deadline and a few retries.
    TIMEOUT_S, ATTEMPTS = 45, 4

    def _synthesise(self, text: str) -> tuple[bytes, list[dict]]:
        async def once():
            comm = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch,
                                        boundary="WordBoundary", connect_timeout=10,
                                        receive_timeout=30)
            audio, words = bytearray(), []
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append(chunk)
            return bytes(audio), words

        last_err = None
        for attempt in range(self.ATTEMPTS):
            try:
                audio, words = asyncio.run(asyncio.wait_for(once(), self.TIMEOUT_S))
                if audio:
                    return audio, words
                last_err = RuntimeError("Edge TTS returned no audio")
            except Exception as e:  # timeout, network error, service hiccup
                last_err = e
            print(f"[edge-tts] attempt {attempt + 1} failed ({last_err!r}); retrying", flush=True)
        raise RuntimeError(f"Edge TTS failed {self.ATTEMPTS} times. Are you online? {last_err!r}")


def _to_word_boundaries(text: str, words: list[dict]) -> list[dict]:
    """Map Edge's word events (offsets in 100 ns ticks, same unit manim-voiceover
    uses) to character offsets in `text`."""
    out, pos = [], 0
    for w in words:
        word = w["text"]
        m = re.search(re.escape(word), text[pos:])
        if m is None:  # Edge may normalise a token (e.g. numbers); skip it
            continue
        start = pos + m.start()
        out.append({
            "audio_offset": int(w["offset"]),
            "duration_milliseconds": int(w["duration"] / 10_000),
            "text_offset": start,
            "word_length": len(word),
            "text": word,
            "boundary_type": "Word",
        })
        pos = start + len(word)
    return out


LOCK_WAIT_S = 600  # longer than one line's worst case (4 attempts x 45 s)


@contextmanager
def _cache_lock(cache_dir: Path):
    """An exclusive lock between processes on `cache_dir/.cache.lock`."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = open(cache_dir / ".cache.lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            deadline = time.monotonic() + LOCK_WAIT_S
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"voiceover cache {cache_dir} stayed locked for {LOCK_WAIT_S} s")
                    time.sleep(0.05)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()
