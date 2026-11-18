"""Run the studio:  .venv/Scripts/python -m studio.server [--port 8770]"""

import argparse

from aiohttp import web


def main():
    ap = argparse.ArgumentParser(prog="python -m studio.server")
    ap.add_argument("--port", type=int, default=8770)
    args = ap.parse_args()
    from .app import make_app
    print(f"Manim Studio on http://127.0.0.1:{args.port}", flush=True)
    web.run_app(make_app(), host="127.0.0.1", port=args.port, print=None)


if __name__ == "__main__":
    main()
