"""Engine worker process: one per open scene file (architecture.md §2).

Requests and replies are dicts over a multiprocessing pipe. One request at
a time; the server kills and restarts the process if one takes too long.
"""

from __future__ import annotations

import io
import traceback
from pathlib import Path


def _encode(frame, size: str, fmt: str) -> bytes:
    from PIL import Image
    img = Image.fromarray(frame)
    if size == "half":
        img = img.resize((img.width // 2, img.height // 2), Image.BILINEAR)
    buf = io.BytesIO()
    if fmt == "jpeg":
        img.convert("RGB").save(buf, "JPEG", quality=82)
    else:
        img.convert("RGB").save(buf, "PNG", compress_level=1)
    return buf.getvalue()


def _encode_ids(idmap) -> bytes:
    import numpy as np
    from PIL import Image
    rgb = np.stack([(idmap >> 16) & 255, (idmap >> 8) & 255, idmap & 255], axis=-1).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, "PNG", compress_level=1)
    return buf.getvalue()


def _boxes(idmap, n: int) -> list:
    """Pixel box [x0, y0, x1, y1] of each object index in the ID map."""
    import numpy as np
    out = [None] * n
    ys, xs = np.nonzero(idmap)
    if len(ys) == 0:
        return out
    ids = idmap[ys, xs]
    for i in range(1, n + 1):
        m = ids == i
        if m.any():
            out[i - 1] = [int(xs[m].min()), int(ys[m].min()), int(xs[m].max()) + 1, int(ys[m].max()) + 1]
    return out


def _group_boxes(objects: list) -> None:
    """A group drawn only through its parts gets the union of their boxes."""
    for _ in range(6):  # nested groups: children first
        for o in objects:
            if not o.get("virtual"):
                continue
            kids = [k["box"] for k in objects if k.get("parent") is not None
                    and objects[k["parent"]] is o and k.get("box")]
            if kids:
                o["box"] = [min(b[0] for b in kids), min(b[1] for b in kids),
                            max(b[2] for b in kids), max(b[3] for b in kids)]


def _local_modules(path: Path) -> list[str]:
    """Files of the modules imported from the project (style.py,
    manim_kit.py, ...): what the scene depends on besides its own file.
    Not the studio, not the venv, not the scene file itself."""
    import sys
    root = Path(__file__).resolve().parents[3]
    skip = (root / ".venv", root / "studio" / "server")
    out = set()
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if not f or getattr(m, "__name__", "").startswith("_studio_"):
            continue
        try:
            p = Path(f).resolve()
        except (OSError, ValueError):
            continue
        if p.suffix == ".py" and p != path.resolve() and p.is_relative_to(root) \
                and not any(p.is_relative_to(s) for s in skip) and p != root / "studio" / "__init__.py":
            out.add(str(p))
    return sorted(out)


class Worker:
    def __init__(self, path: str, quality: str):
        from .runtime import install
        install()
        self.path, self.quality = Path(path), quality
        self.engine = None

    def handle(self, msg: dict) -> dict:
        op = msg["op"]
        return getattr(self, "op_" + op)(msg)

    def op_hello(self, msg):
        from .runtime import api_names
        return {"api": api_names()}

    def op_load(self, msg):
        from .runtime import Engine
        if msg.get("path"):  # a spare process, started before the file was chosen, adopts it
            self.path = Path(msg["path"])
        # the new revision first: if it doesn't run, the last one that did stays
        # loaded, so the studio can keep showing it (frames) beside the error
        new = Engine(self.path, msg["data"], self.quality)
        if self.engine is not None:
            self.engine.close()
        self.engine = new
        w, h = self.engine.size
        fw, fh = self.engine.frame_units
        return {"scenes": self.engine.scenes(), "fps": self.engine.fps, "width": w, "height": h,
                "frame_width": fw, "frame_height": fh, "deps": _local_modules(self.path)}

    def op_trace(self, msg):
        if self.engine is None:
            return {"error": {"message": "nothing is loaded in the engine", "code": "not_loaded"}}
        return self.engine.trace(msg["scene"])

    def op_activate(self, msg):
        if self.engine is None:
            return {"error": {"message": "nothing is loaded in the engine", "code": "not_loaded"}}
        self.engine.activate(msg["scene"], msg["duration"])
        return {}

    def op_status(self, msg):
        import threading
        pool = self.engine.pools.get(msg["scene"]) if self.engine else None
        return {"cursors": pool.parked() if pool else 0, "of": len(pool.spots) if pool else 0,
                "threads": threading.active_count()}

    def op_frame(self, msg):
        if self.engine is None:
            return {"error": {"message": "nothing is loaded in the engine", "code": "not_loaded"}}
        fps = self.engine.fps
        t = max(0, int(msg["f"])) / fps + 1e-4  # a negative frame would never be reached
        c = self.engine.frame(msg["scene"], t, msg.get("ids", False))
        return _pack(c, msg.get("size", "full"), msg.get("fmt", "png"))

    def op_verify(self, msg):
        """Trace edited bytes without replacing the loaded revision; with
        `object` and `f`, also describe that object at that frame."""
        from .runtime import Engine, EngineError
        try:
            eng = Engine(self.path, msg["data"], self.quality)
        except EngineError as e:
            return {"error": {"message": str(e), "line": e.line}}
        try:
            if msg.get("object") or msg.get("objects"):
                # one run: the whole trace, and the objects at f on the way
                t = max(0, int(msg["f"])) / eng.fps + 1e-4
                # with glyphs: that object's glyph map too (part colour checks)
                want = msg.get("object") if msg.get("glyphs") and msg.get("object") else True
                tr, c = eng.trace(msg["scene"], t, want)
                out = {"trace": tr}
                if tr["error"] is None and c is not None:
                    # (no boxes here: only centres and sites are compared)
                    out["object"] = next((o for o in c.objects if o["id"] == msg.get("object")), None)
                    out["objects"] = c.objects
                    out["camera"] = c.camera
                    if msg.get("frame"):
                        # the edited scene's frame at f, as the frame op draws it after the
                        # write: the studio caches it for the new revision (one run, not two)
                        out["frame"] = _pack(c, "full", "png")
            else:
                out = {"trace": eng.trace(msg["scene"])}
            if msg.get("eval_name"):
                from .runtime import _hex
                try:
                    v = eval(msg["eval_name"], eng.module.__dict__)  # a bare name the planner checked
                    out["eval"] = _hex(v) or (v if isinstance(v, (int, float, str)) else repr(v))
                except Exception as e:
                    out["eval_error"] = f"{type(e).__name__}: {e}"
            return out
        finally:
            eng.close()


def _pack(c, size: str, fmt: str) -> dict:
    """A Capture as the frame op answers it."""
    out = {"image": _encode(c.frame, size, fmt), "camera": c.camera}
    if c.idmap is not None:
        out["idmap"] = _encode_ids(c.idmap)
        boxes = _boxes(c.idmap, len(c.objects))
        for o, b in zip(c.objects, boxes):
            o["box"] = b
        _group_boxes(c.objects)
        out["objects"] = c.objects
        if c.ghosts:
            out["ghosts"] = c.ghosts
    return out


def main(conn, path: str, quality: str):
    from .runtime import EngineError
    try:
        worker = Worker(path, quality)
    except Exception as e:
        conn.send({"error": {"message": f"{type(e).__name__}: {e}"}})
        return
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return
        if msg.get("op") == "exit":
            return
        try:
            reply = worker.handle(msg)
        except EngineError as e:
            reply = {"error": {"message": str(e), "line": e.line, "traceback": e.tb}}
        except Exception as e:
            reply = {"error": {"message": f"{type(e).__name__}: {e}",
                               "traceback": traceback.format_exc()[-4000:]}}
        conn.send(reply)
