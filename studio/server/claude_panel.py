"""The Claude panel (Phase 6, optional item 2): ask Claude Code about the
open file from inside the studio.

It runs the user's own Claude Code CLI headless (`claude -p`), in the project
root, so CLAUDE.md and the project's settings apply as in a terminal. The
prompt goes in on stdin with a short note of where the user is (file, scene,
playhead, selection). Output is read as stream-json and pushed to the page
line by line. Claude edits the .py file with its own tools; the studio's file
watcher picks the change up like any other save, so the panel needs no edit
path of its own (the file stays the only source of truth).

Limits:
- one question at a time; Stop kills it;
- tools: read and edit files, search; no shell. `--tools` limits the set
  Claude Code offers at all (allowedTools alone only pre-approves), Bash is
  disallowed on top, `--restricted` keeps the file tools inside the project
  and ignores settings files that could allow more, and `--strict-mcp-config`
  leaves out MCP servers and claude.ai connectors (found in the review after
  Phase 6: the panel's Claude could see the user's Google Docs connectors).
  Permission mode acceptEdits: an edit needs no prompt (nobody could answer
  one). Side effect: the user's settings (their model choice) don't apply;
- off for pages reached through an `--allow-host` name (a tailnet) unless the
  server was started with `--allow-claude-remote`: a remote page could
  otherwise run an agent on this machine;
- a follow-up continues the same Claude Code session (`--resume`).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = "Read Edit Write Glob Grep"
# Claude Code session ids are UUIDs; anything else is dropped, never passed on
# (a value like "--some-flag" after --resume would be read as a flag)
SESSION_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
SYSTEM = (
    "You are answering inside reManim, a visual editor for Manim CE scene files. "
    "The studio reloads the file by itself when you save it, so after an edit just say what you changed. "
    "Keep edits small and readable; the user also edits this file by hand and in the studio. "
    "You have no shell here: don't try to render; the studio shows the result."
)
MAX_PROMPT = 8000


def find_cli() -> str | None:
    """The `claude` executable: PATH first, then the native installer's place."""
    exe = shutil.which("claude")
    if exe:
        return exe
    for p in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude"):
        if p.is_file():
            return str(p)
    return None


def where_note(ctx: dict) -> str:
    """What the user is looking at, as plain words before the question."""
    bits = []
    if ctx.get("file"):
        bits.append(f"file {ctx['file']}")
    if ctx.get("scene"):
        bits.append(f"scene {ctx['scene']}")
    if isinstance(ctx.get("t"), (int, float)):
        bits.append(f"playhead at {ctx['t']:.2f} s")
    sel = ctx.get("selection")
    if isinstance(sel, dict) and sel.get("label"):
        line = f" (line {sel['line']})" if isinstance(sel.get("line"), int) else ""
        bits.append(f"selected: {sel['label']}{line}")
    return ("[In the studio: " + "; ".join(bits) + "]\n\n") if bits else ""


def summarise(ev: dict) -> list[dict]:
    """One stream-json event as the few things the page shows."""
    t = ev.get("type")
    out: list[dict] = []
    if t == "system" and ev.get("subtype") == "init":
        out.append({"kind": "session", "session": ev.get("session_id"), "model": ev.get("model")})
    elif t == "assistant":
        for part in (ev.get("message") or {}).get("content") or []:
            if part.get("type") == "text" and part.get("text"):
                out.append({"kind": "text", "text": part["text"]})
            elif part.get("type") == "tool_use":
                inp = part.get("input") or {}
                what = inp.get("file_path") or inp.get("pattern") or inp.get("path") or ""
                if what:
                    try:
                        what = Path(what).resolve().relative_to(ROOT).as_posix()
                    except (ValueError, OSError):
                        pass
                out.append({"kind": "tool", "tool": part.get("name"), "what": str(what)[:200]})
    elif t == "result":
        out.append({"kind": "result", "ok": not ev.get("is_error") and ev.get("subtype") == "success",
                    "session": ev.get("session_id"), "cost": ev.get("total_cost_usd"),
                    "turns": ev.get("num_turns"), "text": ev.get("result") if ev.get("is_error") else None})
    return out


class ClaudePanel:
    def __init__(self, notify, cli: str | None = None):
        self.notify = notify   # async callback(dict) to every client
        self.cli = cli if cli is not None else find_cli()
        self.proc: asyncio.subprocess.Process | None = None
        self.task: asyncio.Task | None = None
        self.run_id = 0
        self.stop_asked = False

    def status(self) -> dict:
        return {"type": "claude.status", "available": bool(self.cli), "busy": self.busy,
                "run": self.run_id if self.busy else None,
                "why": None if self.cli else "Claude Code isn't installed (no `claude` on PATH)"}

    @property
    def busy(self) -> bool:
        return self.task is not None and not self.task.done()

    def args(self, session: str | None) -> list[str]:
        a = [self.cli, "-p", "--output-format", "stream-json", "--verbose",
             "--permission-mode", "acceptEdits", "--tools", TOOLS.replace(" ", ","), "--allowedTools", TOOLS,
             "--disallowedTools", "Bash", "--restricted", "--strict-mcp-config",
             "--append-system-prompt", SYSTEM]
        if session:
            a += ["--resume", session]
        return a

    async def ask(self, prompt: str, ctx: dict, session: str | None = None) -> dict:
        if not self.cli:
            return {"type": "error", "message": "Claude Code isn't installed (no `claude` on PATH)"}
        prompt = (prompt or "").strip()
        if not prompt:
            return {"type": "error", "message": "ask something first"}
        if len(prompt) > MAX_PROMPT:
            return {"type": "error", "message": f"keep the question under {MAX_PROMPT} characters"}
        if self.busy:
            return {"type": "error", "message": "Claude is still answering; stop it or wait"}
        if session is not None and not (isinstance(session, str) and SESSION_RE.match(session)):
            session = None
        self.run_id += 1
        self.stop_asked = False
        rid = self.run_id
        self.task = asyncio.create_task(self._run(rid, where_note(ctx) + prompt, session))
        return {"type": "claude.started", "id": rid}

    async def stop(self) -> dict:
        if not self.busy:
            return {"type": "error", "message": "Claude isn't running"}
        self.stop_asked = True
        if self.proc is not None and self.proc.returncode is None:
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
        return {"type": "claude.stopping", "id": self.run_id}

    async def _push(self, rid: int, item: dict):
        await self.notify({"type": "claude.event", "id": rid, **item})

    async def _run(self, rid: int, prompt: str, session: str | None):
        t0 = time.monotonic()
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        try:
            self.proc = proc = await asyncio.create_subprocess_exec(
                *self.args(session), cwd=str(ROOT), env=env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=16 * 1024 * 1024)
        except OSError as e:
            await self._push(rid, {"kind": "result", "ok": False, "text": f"couldn't start Claude Code: {e}"})
            return
        if self.stop_asked:  # Stop came while the process was starting
            proc.kill()
        try:
            proc.stdin.write(prompt.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            pass  # it exited early; its stderr says why, below
        err_task = asyncio.create_task(proc.stderr.read())  # read alongside, or a full pipe stalls it
        got_result = False
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            for item in summarise(ev):
                got_result |= item["kind"] == "result"
                if item["kind"] == "result":
                    item["s"] = round(time.monotonic() - t0, 1)
                await self._push(rid, item)
        err = (await err_task).decode("utf-8", "replace")
        code = await proc.wait()
        self.proc = None
        if not got_result:
            text = "stopped" if self.stop_asked else (err.strip()[-1500:] or f"Claude Code exited with code {code}")
            await self._push(rid, {"kind": "result", "ok": False, "stopped": self.stop_asked, "text": text,
                                   "s": round(time.monotonic() - t0, 1)})

    def close(self):
        if self.proc is not None and self.proc.returncode is None:
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
