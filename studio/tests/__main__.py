"""Every studio check in one command.

    .venv/Scripts/python -m studio.tests            unit + engine tests (~8 min)
    .venv/Scripts/python -m studio.tests --quick    unit tests only (~1 min, no LaTeX)
    .venv/Scripts/python -m studio.tests --all      + the corpus run and the four benches (~1.5 h)

Stops at the first step that fails. Never run while the studio server or
another engine run is busy: they share media/Tex_studio.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def step(name: str, args: list[str]) -> None:
    print(f"\n=== {name}: {' '.join(args)}", flush=True)
    t = time.monotonic()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", STUDIO_NO_SPARE="1")
    code = subprocess.call([PY, *args], cwd=ROOT, env=env)
    print(f"=== {name}: {'ok' if code == 0 else f'FAILED ({code})'} in {time.monotonic() - t:.0f} s", flush=True)
    if code != 0:
        sys.exit(code)


def main(argv: list[str]) -> None:
    if "--quick" in argv:
        step("unit tests", ["-m", "pytest", "-q", "studio/tests/unit"])
        return
    step("unit and engine tests", ["-m", "pytest", "-q", "studio/tests"])
    if "--all" in argv:
        step("corpus run", ["-u", "-m", "studio.tests.corpus_run"])
        step("census", ["-u", "-m", "studio.tests.census_run"])
        step("drag bench", ["-u", "-m", "studio.tests.drag_run"])
        step("clip bench", ["-u", "-m", "studio.tests.clip_run"])
        step("speed bench", ["-u", "-m", "studio.tests.speed_run"])
    print("\nall green", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
