"""Run the studio:  .venv/Scripts/python -m studio.server [--port 8770]"""

import argparse

from aiohttp import web


def main():
    ap = argparse.ArgumentParser(prog="python -m studio.server")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                    help="also answer to this host name (e.g. a `tailscale serve` name); "
                         "the server still listens on 127.0.0.1 only, and other machines need "
                         "the token link printed at start-up. Never point `tailscale funnel` at it")
    ap.add_argument("--dev", action="store_true",
                    help="let the vite dev server (npm run dev, port 5173) call the studio")
    args = ap.parse_args()
    from . import app
    from .app import make_app
    app.TRUSTED_HOSTS.update(h.strip().lower() for h in args.allow_host if h.strip())
    if args.dev:
        app.DEV_ORIGINS.update(app.VITE_ORIGINS)
    print(f"Manim Studio on http://127.0.0.1:{args.port}", flush=True)
    if app.TRUSTED_HOSTS:
        import secrets
        app.ACCESS_TOKEN = secrets.token_urlsafe(24)
        for h in sorted(app.TRUSTED_HOSTS):
            print(f"  from other machines: https://{h}:{args.port}/?token={app.ACCESS_TOKEN}", flush=True)
    web.run_app(make_app(), host="127.0.0.1", port=args.port, print=None)


if __name__ == "__main__":
    main()
