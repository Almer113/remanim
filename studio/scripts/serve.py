"""Run reManim as a background server (for the Home Server Hub, or by hand).

    .venv/Scripts/python studio/scripts/serve.py start | stop | restart | status [--json]

start   builds the UI if web/src is newer than the build, starts the server
        (port 8770, this PC only, plus the tailnet name through `tailscale serve`
        with the token kept in studio/data/access_token), and exits once it answers.
stop    ends the server this script started (its pid, checked against what the
        server says about itself), with its engine processes.
status  one line of JSON: {"running", "ours", "pid", "since", "message"}.

The server's output goes to studio/data/server.log. Follows the hub contract in
D:/Projects/AI Code Projects/Home Server Hub/docs/APP_CONTRACT.md.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
ROOT = STUDIO.parent
DATA = STUDIO / "data"
PIDFILE = DATA / "server.pid"
LOG = DATA / "server.log"
TOKEN = DATA / "access_token"
PORT = 8770
# the name `tailscale serve --https=8770` answers to; other machines need the token
TAILNET_NAME = "your-pc.your-tailnet.ts.net"
HEALTH = f"http://127.0.0.1:{PORT}/api/health"


def say(*a):
    print(*a, flush=True)


def health(timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(HEALTH, timeout=timeout) as r:
            d = json.loads(r.read(4096))
            return d if d.get("app") == "remanim" else None
    except Exception:
        return None


def port_busy() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def recorded() -> dict | None:
    try:
        return json.loads(PIDFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return f'"{pid}"' in out.stdout


def command_line(pid: int) -> str:
    out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                          f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
                         capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return out.stdout.strip()


def ui_outdated() -> bool:
    built = STUDIO / "web" / "dist" / "index.html"
    if not built.exists():
        return True
    src = [STUDIO / "web" / "src", STUDIO / "web" / "public", STUDIO / "web" / "index.html"]
    files = [p for d in src for p in ([d] if d.is_file() else d.rglob("*")) if p.is_file()]
    return max((p.stat().st_mtime for p in files), default=0) > built.stat().st_mtime + 1


def build_ui() -> str | None:
    node = shutil.which("node")
    web = STUDIO / "web"
    if node is None:
        return "Node isn't on PATH, so the UI can't be built"
    for args in (["node_modules/typescript/bin/tsc", "--noEmit", "-p", "."],
                 ["node_modules/vite/bin/vite.js", "build"]):
        r = subprocess.run([node, *args], cwd=web, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode != 0:
            lines = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()]
            for ln in lines[-15:]:
                say(ln)
            return f"UI build failed ({Path(args[0]).stem})"
    return None


def status() -> dict:
    rec = recorded()
    h = health()
    if h:
        out = {"running": True, "ours": True, "pid": h.get("pid"), "since": h.get("since")}
        if not rec or rec.get("pid") != h.get("pid"):
            out["message"] = "started outside the hub (a terminal or a Claude preview)"
        return out
    if rec and alive(rec["pid"]) and "studio.server" in command_line(rec["pid"]):
        return {"running": True, "ours": True, "pid": rec["pid"], "since": rec.get("since"),
                "message": "running but not answering"}
    if port_busy():
        return {"running": False, "ours": False, "message": f"port {PORT} is used by another program"}
    return {"running": False, "ours": True}


def start() -> int:
    say("::hub-step check Check")
    if health():
        say(f"reManim is already running on http://127.0.0.1:{PORT}/")
        return 0
    if port_busy():
        say(f"Port {PORT} is used by another program")
        return 1
    if ui_outdated():
        say("::hub-step build Build UI")
        why = build_ui()
        if why:
            say(why)
            return 1
    say("::hub-step start Start")
    DATA.mkdir(parents=True, exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > 5 * 1024 * 1024:
        LOG.replace(LOG.with_suffix(".log.1"))
    cmd = [sys.executable, "-m", "studio.server", "--port", str(PORT),
           "--allow-host", TAILNET_NAME, "--token-file", str(TOKEN)]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    env.pop("HUB_RUN", None)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(LOG, "ab") as log:
        log.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())
        log.flush()
        kw = dict(cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                  close_fds=True)
        try:  # out of the caller's job, so the hub ending `start` leaves the server running
            p = subprocess.Popen(cmd, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw)
        except OSError:
            p = subprocess.Popen(cmd, creationflags=flags, **kw)
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    PIDFILE.write_text(json.dumps({"pid": p.pid, "since": since}), encoding="utf-8")
    for _ in range(300):
        h = health(1.0)
        if h:
            if h.get("pid") != p.pid:
                PIDFILE.write_text(json.dumps({"pid": h["pid"], "since": h.get("since", since)}), encoding="utf-8")
            say(f"reManim is running on http://127.0.0.1:{PORT}/ (pid {h.get('pid')})")
            return 0
        if p.poll() is not None:
            tail = LOG.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:]
            PIDFILE.unlink(missing_ok=True)
            say(f"The server exited at start-up: {tail[0] if tail else 'see studio/data/server.log'}")
            return 1
        time.sleep(0.2)
    say("The server didn't answer within 60 s; see studio/data/server.log")
    return 1


def stop() -> int:
    rec = recorded()
    h = health()
    if rec is None:
        if h:
            say(f"reManim on port {PORT} was started outside the hub (pid {h.get('pid')}); stop it where it runs")
            return 1
        say("reManim isn't running")
        return 0
    pid = rec["pid"]
    ours = (h and h.get("pid") == pid) or (alive(pid) and "studio.server" in command_line(pid))
    if not ours:
        PIDFILE.unlink(missing_ok=True)
        if h:
            say(f"reManim on port {PORT} was started outside the hub (pid {h.get('pid')}); stop it where it runs")
            return 1
        say("reManim isn't running")
        return 0
    # its engine processes are its children: /T ends them too
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(100):
        if not port_busy() and not alive(pid):
            PIDFILE.unlink(missing_ok=True)
            say("reManim stopped")
            return 0
        time.sleep(0.1)
    say(f"Couldn't stop reManim (pid {pid})")
    return 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        return start()
    if cmd == "stop":
        return stop()
    if cmd == "restart":
        r = stop()
        return r if r else start()
    if cmd == "status":
        print(json.dumps(status()), flush=True)
        return 0
    say(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
