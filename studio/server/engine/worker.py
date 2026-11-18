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
        if self.engine is not None:
            self.engine.close()
            self.engine = None
        self.engine = Engine(self.path, msg["data"], self.quality)
        w, h = self.engine.size
        return {"scenes": self.engine.scenes(), "fps": self.engine.fps, "width": w, "height": h}

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
        out = {"image": _encode(c.frame, msg.get("size", "full"), msg.get("fmt", "png"))}
        if c.idmap is not None:
            out["idmap"] = _encode_ids(c.idmap)
            boxes = _boxes(c.idmap, len(c.objects))
            for o, b in zip(c.objects, boxes):
                o["box"] = b
            out["objects"] = c.objects
        return out

    def op_verify(self, msg):
        """Trace edited bytes without replacing the loaded revision; with
        `object` and `f`, also describe that object at that frame."""
        from .runtime import Engine, EngineError
        try:
            eng = Engine(self.path, msg["data"], self.quality)
        except EngineError as e:
            return {"error": {"message": str(e), "line": e.line}}
        try:
            out = {"trace": eng.trace(msg["scene"])}
            if msg.get("object") and out["trace"]["error"] is None:
                t = msg["f"] / eng.fps + 1e-4
                c = eng.frame(msg["scene"], t, True)
                out["object"] = next((o for o in c.objects if o["id"] == msg["object"]), None)
                out["objects"] = c.objects
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
