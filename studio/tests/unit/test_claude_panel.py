"""Phase 6 optional item: the Claude panel, with a stand-in for the CLI (no
real Claude Code runs here)."""

import asyncio
import sys

from studio.server import app as appmod
from studio.server.claude_panel import ClaudePanel, summarise, where_note

FAKE = r'''
import json, sys, time
prompt = sys.stdin.read()
args = sys.argv[1:]
def out(o):
    print(json.dumps(o), flush=True)
out({"type": "system", "subtype": "init", "session_id": "0c6f4b1e-2d3a-4b5c-8d9e-0f1a2b3c4d5e", "model": "m"})
if "hang" in prompt:
    time.sleep(60)
out({"type": "assistant", "message": {"content": [
    {"type": "text", "text": "echo:" + prompt.splitlines()[-1]},
    {"type": "tool_use", "name": "Edit", "input": {"file_path": "order_matters.py"}}]}})
out({"type": "result", "subtype": "success", "is_error": False, "session_id": "0c6f4b1e-2d3a-4b5c-8d9e-0f1a2b3c4d5e",
     "total_cost_usd": 0.01, "num_turns": 2, "result": "done",
     "resumed": "--resume" in args})
'''


def _panel(tmp_path):
    fake = tmp_path / "fake_claude.py"
    fake.write_text(FAKE, encoding="utf-8")
    seen = []

    async def notify(m):
        seen.append(m)
    p = ClaudePanel(notify, cli="fake")
    real = p.args
    p.args = lambda session: [sys.executable, str(fake), *real(session)[1:]]
    return p, seen


def test_where_note_and_summaries():
    n = where_note({"file": "a.py", "scene": "Intro", "t": 1.234, "selection": {"label": "circle", "line": 12}})
    assert n == "[In the studio: file a.py; scene Intro; playhead at 1.23 s; selected: circle (line 12)]\n\n"
    assert where_note({}) == ""
    ev = {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"},
                                                       {"type": "tool_use", "name": "Read", "input": {"pattern": "*.py"}}]}}
    assert summarise(ev) == [{"kind": "text", "text": "hi"}, {"kind": "tool", "tool": "Read", "what": "*.py"}]
    assert summarise({"type": "user"}) == []


def test_ask_streams_and_resumes(tmp_path):
    async def go():
        p, seen = _panel(tmp_path)
        r = await p.ask("make it blue", {"file": "a.py"})
        assert r["type"] == "claude.started"
        assert (await p.ask("again", {}))["type"] == "error"  # one at a time
        await p.task
        kinds = [m["kind"] for m in seen]
        assert kinds == ["session", "text", "tool", "result"], seen
        assert seen[1]["text"] == "echo:make it blue"
        assert seen[3]["ok"] and seen[3]["session"] == "0c6f4b1e-2d3a-4b5c-8d9e-0f1a2b3c4d5e"
        seen.clear()
        await p.ask("follow up", {}, session="0c6f4b1e-2d3a-4b5c-8d9e-0f1a2b3c4d5e")
        await p.task
        assert seen[-1]["kind"] == "result" and seen[-1]["ok"]
        # a session id with anything odd in it is dropped, never passed to the CLI
        used = []
        args = p.args
        p.args = lambda s: used.append(s) or args(s)
        await p.ask("x", {}, session="a b;c")
        await p.task
        # nor a flag-shaped one: after --resume it would be read as a flag
        await p.ask("x", {}, session="--dangerously-skip-permissions")
        await p.task
        assert used == [None, None]
        # the tool set is limited, not just pre-approved, and the shell is off
        a = ClaudePanel(lambda m: None, cli="claude").args(None)
        assert a[a.index("--tools") + 1] == "Read,Edit,Write,Glob,Grep"
        assert a[a.index("--disallowedTools") + 1] == "Bash"
        # no code-running tools, file tools kept to the project, no MCP connectors
        assert "--restricted" in a and "--strict-mcp-config" in a
    asyncio.run(go())


def test_stop(tmp_path):
    async def go():
        p, seen = _panel(tmp_path)
        await p.ask("hang please", {})
        for _ in range(100):
            if seen:
                break
            await asyncio.sleep(0.05)
        assert (await p.stop())["type"] == "claude.stopping"
        await asyncio.wait_for(p.task, 10)
        last = seen[-1]
        assert last["kind"] == "result" and not last["ok"] and last["stopped"]
        assert (await p.stop())["type"] == "error"
        # a Stop that arrives while the process is still starting still stops it
        seen.clear()
        await p.ask("hang please", {})
        await p.stop()
        await asyncio.wait_for(p.task, 10)
        assert seen[-1]["kind"] == "result" and seen[-1]["stopped"], seen
    asyncio.run(go())


def test_refusals(tmp_path):
    async def go():
        p, _ = _panel(tmp_path)
        assert (await p.ask("   ", {}))["type"] == "error"
        assert (await p.ask("x" * 9000, {}))["type"] == "error"
        none = ClaudePanel(lambda m: None, cli="")
        assert not none.status()["available"]
        assert (await none.ask("hi", {}))["type"] == "error"
    asyncio.run(go())


def test_remote_pages_need_the_flag(monkeypatch):
    ask = {"type": "claude.ask", "prompt": "hi"}
    monkeypatch.setattr(appmod, "CLAUDE_REMOTE", False)
    assert appmod.gate(ask, "127.0.0.1:8770") is None
    assert appmod.gate(ask, "localhost:8770") is None
    r = appmod.gate(ask, "studio.tail1234.ts.net")
    assert r["type"] == "claude.status" and not r["available"]
    monkeypatch.setattr(appmod, "CLAUDE_REMOTE", True)
    assert appmod.gate(ask, "studio.tail1234.ts.net") is None


def test_show_in_folder_is_for_this_machine_only(monkeypatch):
    monkeypatch.setattr(appmod, "CLAUDE_REMOTE", True)  # no flag lets another machine open windows here
    msg = {"type": "export.reveal", "id": "x1", "i": 0}
    assert appmod.gate(msg, "127.0.0.1:8770") is None
    assert appmod.gate(msg, "studio.tail1234.ts.net")["type"] == "error"
    assert appmod.gate({"type": "export.list"}, "studio.tail1234.ts.net") is None
