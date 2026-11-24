"""Run the studio:  .venv/Scripts/python -m studio.server [--port 8770]"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from aiohttp import web


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def ui_note() -> str | None:
    """Whether the built UI is there and up to date with web/src."""
    from .app import ROOT, WEB
    src = ROOT / "studio" / "web" / "src"
    built = WEB / "index.html"
    if not built.exists():
        return "the web UI isn't built: run `npm install` once, then `npm run build`, in studio/web"
    newest = max((p.stat().st_mtime for p in src.rglob("*") if p.is_file()), default=0)
    if newest > built.stat().st_mtime + 1:
        return "the built UI is older than studio/web/src: run `npm run build` in studio/web to see the changes"
    return None


def app_browser() -> str | None:
    """Edge or Chrome, for an app window (--app): no tabs or address bar."""
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        exe = shutil.which(name)
        if exe:
            return exe
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            if base and (Path(base) / rel).is_file():
                return str(Path(base) / rel)
    return None


def is_studio(url: str) -> bool:
    """Is the program on that port reManim (not some other server)?"""
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return b"<title>reManim</title>" in r.read(65536)
    except Exception:
        return False


def open_app_window(url: str, background: bool = True):
    """Once the server answers, open it as an app window."""
    exe = app_browser()
    if exe is None:
        print(f"No Edge or Chrome found for an app window; open {url} in a browser.", flush=True)
        return

    def go():
        for _ in range(100):
            try:
                urllib.request.urlopen(url + "api/status", timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        subprocess.Popen([exe, f"--app={url}", "--window-size=1500,950"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if background:
        threading.Thread(target=go, daemon=True).start()
    else:
        go()


def access_token(path: str | None) -> str:
    """A new token, or the one kept in `path` (written there the first time).
    A token of your own choosing can be put in the file; at least 8 characters."""
    import secrets
    if path:
        f = Path(path)
        t = ""
        if f.exists():
            # a file someone wrote is never replaced behind their back: a token that can't
            # be used stops the start with the reason (utf-8-sig: Notepad may add a BOM)
            try:
                t = f.read_text(encoding="utf-8-sig").strip()
            except (OSError, UnicodeDecodeError) as e:
                sys.exit(f"Can't read the access token in {path} ({e}); fix or delete the file")
            if t and not (len(t) >= 8 and t.isascii() and t.isprintable() and " " not in t):
                sys.exit(f"The access token in {path} must be at least 8 characters: letters, digits "
                         "or punctuation, no spaces. Fix the file, or delete it for a new random token")
            if t:
                return t
        t = secrets.token_urlsafe(24)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(t, encoding="ascii")
        return t
    return secrets.token_urlsafe(24)


def main():
    ap = argparse.ArgumentParser(prog="python -m studio.server")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                    help="also answer to this host name (e.g. a `tailscale serve` name); "
                         "the server still listens on 127.0.0.1 only, and other machines need "
                         "the token link printed at start-up. Never point `tailscale funnel` at it")
    ap.add_argument("--allow-claude-remote", action="store_true",
                    help="let pages opened through an --allow-host name use the Claude panel "
                         "(it runs Claude Code on this machine); off by default")
    ap.add_argument("--token-file", metavar="PATH",
                    help="with --allow-host: keep the access token in this file (made if missing), so "
                         "it, the browsers' cookies and installed apps survive restarts")
    ap.add_argument("--app", action="store_true",
                    help="open the studio in its own window (Edge or Chrome in app mode)")
    ap.add_argument("--dev", action="store_true",
                    help="let the vite dev server (npm run dev, port 5173) call the studio")
    args = ap.parse_args()
    from . import app
    from .app import make_app
    app.TRUSTED_HOSTS.update(h.strip().lower() for h in args.allow_host if h.strip())
    app.CLAUDE_REMOTE = args.allow_claude_remote
    if args.dev:
        app.DEV_ORIGINS.update(app.VITE_ORIGINS)
    if not port_free(args.port):
        if args.app and is_studio(f"http://127.0.0.1:{args.port}/"):
            # already running: just open another window onto it
            open_app_window(f"http://127.0.0.1:{args.port}/", background=False)
            return
        sys.exit(f"Port {args.port} is in use: the studio is probably running already "
                 f"(open http://127.0.0.1:{args.port}), or start this one with --port <another>.")
    note = ui_note()
    if note:
        print(f"Note: {note}", flush=True)
    print(f"reManim on http://127.0.0.1:{args.port}", flush=True)
    if app.TRUSTED_HOSTS:
        app.ACCESS_TOKEN = access_token(args.token_file)
        if args.token_file:
            app.TOKEN_DAYS = 400  # the longest a browser keeps a cookie
        for h in sorted(app.TRUSTED_HOSTS):
            if args.token_file:
                # a kept token never goes in the output: under the hub it ends up in a log file
                # anyone who can open the hub can read
                print(f"  from other machines: https://{h}:{args.port}/ (the token is in {args.token_file})", flush=True)
            else:
                print(f"  from other machines: https://{h}:{args.port}/?token={app.ACCESS_TOKEN}", flush=True)
    if args.app:
        open_app_window(f"http://127.0.0.1:{args.port}/")
    web.run_app(make_app(), host="127.0.0.1", port=args.port, print=None)


if __name__ == "__main__":
    main()
