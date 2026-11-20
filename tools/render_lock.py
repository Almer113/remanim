"""One Manim render per file at a time, across processes.

Two renders of the same file fight over LaTeX temp files on Windows
(PermissionError: WinError 32) and over media/videos/<stem>/. Whoever
renders takes media/.render-<stem>.lock first. It's keyed by the file's
stem because that's how Manim names its output folder.

    with held("order_matters", "studio export", on_wait=print):
        subprocess.run([... manim ...])

The lock is an OS file lock (msvcrt on Windows, flock elsewhere) on a byte
far past the file's text, held through an open handle. The OS drops it when
the process ends, however it ends, so there is no stale lock to clear, no
pid to reuse and no unlink to race. The file's text says who holds it
(pid, owner, start time) for "waiting for ..." messages; the file itself is
never deleted. Used by preview_server.py and the studio's export.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media"
LOCK_AT = 1 << 30   # the locked byte: past the text, so the text stays readable
_O_BIN = getattr(os, "O_BINARY", 0)

_held: dict[str, int] = {}   # stem -> fd this process holds the lock through
_guard = threading.Lock()


def lock_path(stem: str) -> Path:
    return MEDIA / f".render-{stem}.lock"


def _lock(fd: int) -> bool:
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, LOCK_AT, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, LOCK_AT, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def _read(fd: int) -> dict:
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        info = json.loads(os.read(fd, 4096).decode("utf-8") or "{}")
    except (OSError, ValueError):
        return {}
    return info if isinstance(info, dict) else {}


def holder(stem: str) -> dict | None:
    """Who holds the lock now ({} if the holder hasn't written its name yet),
    or None if it's free."""
    with _guard:
        if stem in _held:
            return _read(_held[stem])
    try:
        fd = os.open(lock_path(stem), os.O_RDWR | _O_BIN)
    except OSError:
        return None
    try:
        if _lock(fd):
            _unlock(fd)
            return None
        return _read(fd)
    finally:
        os.close(fd)


def try_acquire(stem: str, owner: str) -> bool:
    with _guard:
        if stem in _held:   # held by this process already (another thread or job)
            return False
        p = lock_path(stem)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_RDWR | os.O_CREAT | _O_BIN)
        if not _lock(fd):
            os.close(fd)
            return False
        body = json.dumps({"pid": os.getpid(), "owner": owner, "started": time.time()})
        with contextlib.suppress(OSError):
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, body.encode("utf-8"))
        _held[stem] = fd
        return True


def release(stem: str) -> None:
    with _guard:
        fd = _held.pop(stem, None)
    if fd is None:
        return
    with contextlib.suppress(OSError):
        os.ftruncate(fd, 0)
    with contextlib.suppress(OSError):
        _unlock(fd)
    os.close(fd)


@contextlib.contextmanager
def held(stem: str, owner: str, poll: float = 1.0, timeout: float | None = None, on_wait=None, cancelled=None):
    """Wait for the lock, hold it for the block, release it after.
    on_wait(holder_info) is called once when we have to wait; cancelled()
    returning True stops the wait (TimeoutError, like a timeout)."""
    end = None if timeout is None else time.monotonic() + timeout
    told = False
    while not try_acquire(stem, owner):
        if not told and on_wait is not None:
            on_wait(holder(stem) or {})
            told = True
        if (end is not None and time.monotonic() > end) or (cancelled is not None and cancelled()):
            raise TimeoutError(f"{stem} is being rendered by {(holder(stem) or {}).get('owner', 'another process')}")
        time.sleep(poll)
    try:
        yield
    finally:
        release(stem)
