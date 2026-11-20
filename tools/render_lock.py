"""One Manim render per file at a time, across processes.

Two renders of the same file fight over LaTeX temp files on Windows
(PermissionError: WinError 32) and over media/videos/<stem>/. Whoever
renders takes media/.render-<stem>.lock first. It's keyed by the file's
stem because that's how Manim names its output folder.

    with held("order_matters", "studio export", on_wait=print):
        subprocess.run([... manim ...])

The lock holds the owner's pid. A lock whose process is gone is stale and
is taken over. Used by preview_server.py and the studio's export.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media"


def lock_path(stem: str) -> Path:
    return MEDIA / f".render-{stem}.lock"


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) would terminate the process on Windows
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def holder(stem: str) -> dict | None:
    """Who holds the lock now, or None (free, or held by a process that died)."""
    try:
        info = json.loads(lock_path(stem).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or not pid_alive(int(info.get("pid", 0))):
        return None
    return info


def try_acquire(stem: str, owner: str) -> bool:
    p = lock_path(stem)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"pid": os.getpid(), "owner": owner, "started": time.time()})
    for _ in range(2):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if holder(stem) is not None:
                return False
            with contextlib.suppress(OSError):
                p.unlink()  # stale: its process is gone
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        return True
    return False


def release(stem: str) -> None:
    p = lock_path(stem)
    try:
        info = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(info, dict) and info.get("pid") == os.getpid():
        with contextlib.suppress(OSError):
            p.unlink()


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
