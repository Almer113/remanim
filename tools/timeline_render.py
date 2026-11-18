"""Run `manim` as usual, and also write a timeline for each rendered scene.

For every play() and wait() it records when it starts, how long it runs, and
which line of the scene file called it. The result is saved next to the video:
media/videos/<file>/<quality>/<Scene>.timeline.json

The preview server renders through this, so its timeline can link each
animation to its source line. Scene code needs no changes.

Usage (same arguments as manim):
  .venv\\Scripts\\python tools\\timeline_render.py render -ql -a my_scene.py
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from manim import Wait
from manim.__main__ import main as manim_main
from manim.manager import Manager


def scene_file_from_argv(argv: list[str]) -> Path | None:
    for a in argv:
        if a.endswith(".py"):
            return Path(a).resolve()
    return None


def describe(args) -> tuple[str, str]:
    """(kind, label) for the things passed to play()."""
    if len(args) == 1 and isinstance(args[0], Wait):
        return "wait", "wait"
    names = []
    for a in args:
        name = type(a).__name__
        if name == "_AnimationBuilder":
            name = "animate"
        names.append(name)
    return "play", ", ".join(names)


def install(src: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    orig_play, orig_render = Manager.play, Manager.render

    def caller_line() -> int | None:
        # innermost frame in the scene file: the self.play / self.at line
        for fr in inspect.stack()[2:]:
            try:
                if Path(fr.filename).resolve() == src:
                    return fr.lineno
            except OSError:
                continue
        return None

    def play(self: Manager, *args, **kwargs):
        start = self.time
        orig_play(self, *args, **kwargs)
        line = caller_line()
        kind, label = describe(args)
        events = getattr(self, "_timeline", None)
        if events is not None:
            events.append({
                "t": round(start, 4), "d": round(self.time - start, 4),
                "kind": kind, "label": label, "line": line,
                "code": lines[line - 1].strip() if line and line <= len(lines) else "",
            })

    def render(self: Manager, *args, **kwargs):
        self._timeline = []
        try:
            return orig_render(self, *args, **kwargs)
        finally:
            try:
                movie = Path(self.file_writer.movie_file_path)
                out = movie.with_suffix(".timeline.json")
                # only for scenes that produced a video (`-a` also runs empty
                # helper base classes)
                if movie.exists() and self._timeline:
                    out.write_text(json.dumps({
                        "scene": type(self.scene).__name__,
                        "file": src.name,
                        "duration": round(self.time, 4),
                        "events": self._timeline,
                    }, indent=1), encoding="utf-8")
            except Exception as e:  # never break a render over the timeline
                print(f"timeline_render: could not write timeline: {e}", file=sys.stderr)

    Manager.play = play
    Manager.render = render


if __name__ == "__main__":
    src = scene_file_from_argv(sys.argv[1:])
    if src and src.exists():
        install(src)
    sys.argv = ["manim", *sys.argv[1:]]
    manim_main()
