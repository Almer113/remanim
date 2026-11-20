"""Starts, feeds and restarts engine worker processes (architecture.md §2)."""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import time

from .engine.worker import main as worker_main

# hello: the first `import manim` on a cold disk can take a minute or more
DEADLINES = {"hello": 180, "load": 120, "trace": 180, "frame": 60, "activate": 30,
             "status": 10, "verify": 240}


class WorkerDied(Exception):
    pass


class WorkerHandle:
    """One worker process for one file. Requests are serialised; interactive
    ones go before background prefetch (they wait on the same lock, and the
    prefetch loop steps aside while anyone is waiting)."""

    def __init__(self, path: str, quality: str = "l", on_restart=None):
        self.path, self.quality = path, quality
        self.lock = asyncio.Lock()
        self.waiting = 0
        self.proc = None
        self.conn = None
        self.restarts = 0
        self.closed = False
        # called (no arguments) after a fresh process replaced a dead or stuck one:
        # it has nothing loaded, so the owner must load the file again
        self.on_restart = on_restart
        self._start()

    def _start(self):
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        self.proc = ctx.Process(target=worker_main, args=(child, self.path, self.quality), daemon=True)
        self.proc.start()
        child.close()  # the child has its own copy; ours would keep the pipe open
        self.conn = parent

    def kill(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.kill()
            self.proc.join(5)
        if self.conn is not None:
            try:
                self.conn.close()
            except OSError:
                pass

    def close(self):
        """Stop the process without waiting on the event loop: ask it to exit,
        then kill it if it hasn't after a moment."""
        self.closed = True
        proc, conn = self.proc, self.conn
        try:
            if not self.lock.locked():  # a request in flight owns the pipe
                conn.send({"op": "exit"})
        except Exception:
            pass

        def finish():
            proc.join(3)
            if proc.is_alive():
                proc.kill()
                proc.join(5)
            try:
                conn.close()
            except OSError:
                pass
        import threading
        threading.Thread(target=finish, daemon=True).start()

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

    async def fresh(self):
        """Replace the process with a new one, after any request in flight:
        a module the scene imports changed, and Python keeps the old one."""
        async with self.lock:
            if self.closed:
                return
            await asyncio.to_thread(self.kill)
            self._start()

    async def request(self, msg: dict, background: bool = False) -> dict:
        counted = not background
        if counted:
            self.waiting += 1
        try:
            async with self.lock:
                if counted:
                    self.waiting -= 1
                    counted = False
                if self.closed:
                    return {"error": {"message": "the file was closed", "code": "closed"}}
                deadline = DEADLINES.get(msg["op"], 60)
                try:
                    return await asyncio.to_thread(self._roundtrip, msg, deadline)
                except (TimeoutError, WorkerDied, EOFError, OSError) as e:
                    if self.closed:  # we stopped it ourselves
                        return {"error": {"message": "the file was closed", "code": "closed"}}
                    await asyncio.to_thread(self.kill)
                    self.restarts += 1
                    self._start()
                    if self.on_restart is not None:
                        self.on_restart()
                    what = "took too long" if isinstance(e, TimeoutError) else str(e)
                    return {"error": {"message": f"the scene {what} ({msg['op']}); the engine was "
                                                 "restarted", "code": "timeout", "restarted": True}}
        finally:
            if counted:
                self.waiting -= 1
