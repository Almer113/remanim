"""Starts, feeds and restarts engine worker processes (architecture.md §2)."""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import time

from .engine.worker import main as worker_main

DEADLINES = {"hello": 60, "load": 120, "trace": 180, "frame": 60, "activate": 30,
             "status": 10, "verify": 240}


class WorkerDied(Exception):
    pass


class WorkerHandle:
    """One worker process for one file. Requests are serialised; interactive
    ones go before background prefetch (they wait on the same lock, and the
    prefetch loop steps aside while anyone is waiting)."""

    def __init__(self, path: str, quality: str = "l"):
        self.path, self.quality = path, quality
        self.lock = asyncio.Lock()
        self.waiting = 0
        self.proc = None
        self.conn = None
        self.restarts = 0
        self._start()

    def _start(self):
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        self.proc = ctx.Process(target=worker_main, args=(child, self.path, self.quality), daemon=True)
        self.proc.start()
        self.conn = parent

    def kill(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.kill()
            self.proc.join(5)

    def close(self):
        try:
            self.conn.send({"op": "exit"})
        except Exception:
            pass
        self.proc.join(3)
        self.kill()

    def _roundtrip(self, msg: dict, deadline: float) -> dict:
        self.conn.send(msg)
        end = time.monotonic() + deadline
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError
            if self.conn.poll(min(left, 0.5)):
                return self.conn.recv()
            if not self.proc.is_alive():
                raise WorkerDied(f"the engine process exited (code {self.proc.exitcode})")

    async def request(self, msg: dict, background: bool = False) -> dict:
        counted = not background
        if counted:
            self.waiting += 1
        try:
            async with self.lock:
                if counted:
                    self.waiting -= 1
                    counted = False
                deadline = DEADLINES.get(msg["op"], 60)
                try:
                    return await asyncio.to_thread(self._roundtrip, msg, deadline)
                except (TimeoutError, WorkerDied, EOFError, OSError) as e:
                    self.kill()
                    self.restarts += 1
                    self._start()
                    what = "took too long" if isinstance(e, TimeoutError) else str(e)
                    return {"error": {"message": f"the scene {what} ({msg['op']}); the engine was "
                                                 "restarted", "code": "timeout", "restarted": True}}
        finally:
            if counted:
                self.waiting -= 1
