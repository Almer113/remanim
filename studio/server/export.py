"""Export: real renders with plain Manim (Phase 6 step 5, architecture.md §9).

Never the studio's engine: every scene is rendered by `manim` through
tools/timeline_render.py, exactly as on the command line (guarantee 4: no
hidden state). The whole job holds media/.render-<stem>.lock
(tools/render_lock.py), which the preview server honours too, so the two
never render the same file at once.

A job: some scenes of one file, a quality and a format; optionally joined
into one video (tools/concat.py, audio rebuilt as one track) and checked
(tools/audio_check.py on the scenes and the joined file). Scenes render one
process each, in order, so progress is per scene and a failed scene stops
the job before the join: no join over stale clips.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import render_lock  # noqa: E402

QUALITIES = {"l": "480p15", "m": "720p30", "h": "1080p60", "k": "2160p60"}
FORMATS = ("mp4", "webm", "gif", "png", "mov")
VIDEO_EXT = {"mp4": ".mp4", "webm": ".webm", "gif": ".gif", "mov": ".mov"}
LOG_TAIL = 12000

_ANIM = re.compile(r"Animation\s+(\d+)\s*:.*?(\d+)%")


class ExportError(Exception):
    pass


def kill_tree(proc) -> None:
    """End a render and everything it started (LaTeX, dvisvgm, the venv
    launcher's child python). proc.kill() alone ends only the top process on
    Windows, and the lock would then be released under a render still going."""
    if proc is None or proc.returncode is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(proc.pid, 9)  # started in its own session
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def check_spec(spec: dict, scenes_in_file: list[str]) -> dict:
    """A clean job spec, or ExportError saying what's wrong."""
    scenes = spec.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ExportError("choose at least one scene")
    bad = [s for s in scenes if s not in scenes_in_file]
    if bad:
        raise ExportError(f"not a scene of this file: {', '.join(map(str, bad))}")
    if len(set(scenes)) != len(scenes):
        raise ExportError("a scene is listed twice")
    q = spec.get("quality", "l")
    if q not in QUALITIES:
        raise ExportError("quality is one of l, m, h, k")
    fmt = spec.get("format", "mp4")
    if fmt not in FORMATS:
        raise ExportError(f"format is one of {', '.join(FORMATS)}")
    transparent = bool(spec.get("transparent"))
    if transparent and fmt not in ("mov", "png", "webm"):
        raise ExportError("a transparent background needs mov, webm or png")
    join = bool(spec.get("join"))
    if join and (fmt != "mp4" or transparent):
        raise ExportError("joining needs mp4 without transparency")
    if join and len(scenes) < 2:
        join = False  # one scene is already the whole video
    return {"scenes": scenes, "quality": q, "format": fmt, "transparent": transparent, "join": join,
            "check": bool(spec.get("check", True)) and fmt == "mp4" and not transparent}


class Job:
    _n = 0

    def __init__(self, file: str, spec: dict):
        Job._n += 1
        self.id = f"x{Job._n}"
        self.file = file
        self.spec = spec
        self.state = "queued"  # queued, waiting, rendering, joining, checking, done, failed, cancelled
        self.scenes = [{"name": s, "state": "queued", "out": None, "s": None, "pct": None} for s in spec["scenes"]]
        self.joined: str | None = None
        self.check: dict | None = None
        self.message = ""
        self.log = ""
        self.started = time.time()
        self.finished: float | None = None
        self.proc: asyncio.subprocess.Process | None = None
        self.cancel_asked = False

    def outputs(self) -> list[str]:
        out = [s["out"] for s in self.scenes if s["out"]]
        return out + ([self.joined] if self.joined else [])

    def view(self) -> dict:
        return {"id": self.id, "file": self.file, "spec": self.spec, "state": self.state,
                "scenes": self.scenes, "joined": self.joined, "check": self.check,
                "message": self.message, "log": self.log[-4000:] if self.state == "failed" else "",
                "started": self.started, "finished": self.finished}


def _newest(pattern_dir: Path, names: list[str], since: float) -> Path | None:
    best = None
    for n in names:
        for p in pattern_dir.glob(n):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m >= since - 1 and (best is None or m > best[0]):
                best = (m, p)
    return best[1] if best else None


def find_output(file: str, scene: str, fmt: str, transparent: bool, since: float,
                quality: str | None = None) -> Path | None:
    """Where Manim put this scene's render: media/videos/<stem>/<res>/ (or
    media/images/<stem>/ for a png sequence). The resolution folder depends
    on manim.cfg, so it's found, not assumed."""
    stem = Path(file).stem
    if fmt == "png":
        d = ROOT / "media" / "images" / stem
        return _newest(d, [f"{scene}*.png", f"*/{scene}*.png"], since)
    ext = ".mov" if transparent and fmt == "mp4" else VIDEO_EXT[fmt]
    d = ROOT / "media" / "videos" / stem
    # the quality's own folder first: a render of another quality that just
    # finished (the preview server's, say) must not pass for this one
    own = _newest(d / QUALITIES[quality], [f"{scene}{ext}"], since) if quality else None
    return own or _newest(d, [f"*/{scene}{ext}"], since)


def _has_cues(srt: Path) -> bool:
    try:
        return "-->" in srt.read_text(encoding="utf-8")
    except OSError:
        return False


def rel(p: Path | None) -> str | None:
    return p.relative_to(ROOT).as_posix() if p else None


class Exporter:
    def __init__(self, notify):
        self.notify = notify   # async callback(dict) to every client
        self.jobs: dict[str, Job] = {}
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.runner: asyncio.Task | None = None

    async def start(self, file: str, spec: dict, scenes_in_file: list[str]) -> dict:
        job = Job(file, check_spec(spec, scenes_in_file))
        self.jobs[job.id] = job
        while len(self.jobs) > 20:  # keep the last few for the dialog
            self.jobs.pop(next(iter(self.jobs)))
        await self.queue.put(job)
        if self.runner is None or self.runner.done():
            self.runner = asyncio.create_task(self._run_all())
        await self._send(job)
        return {"type": "export.started", "job": job.view()}

    async def cancel(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if job is None or job.state in ("done", "failed", "cancelled"):
            return {"type": "error", "message": "no export running with that id"}
        job.cancel_asked = True
        kill_tree(job.proc)
        if job.state == "queued":
            await self._finish(job, "cancelled", "cancelled before it started")
        return {"type": "export.cancelling", "id": job_id}

    def close(self):
        """Studio shutdown: no render may outlive it (its lock goes with it)."""
        for job in self.jobs.values():
            job.cancel_asked = True
            kill_tree(job.proc)

    def file_of(self, job_id: str, i: int) -> Path | None:
        """Only files an export made can be served (no paths from the client)."""
        job = self.jobs.get(job_id)
        if job is None:
            return None
        outs = job.outputs()
        if not 0 <= i < len(outs):
            return None
        p = (ROOT / outs[i]).resolve()
        return p if p.is_file() and (ROOT / "media") in p.parents else None

    async def _send(self, job: Job):
        await self.notify({"type": "export.progress", "job": job.view()})

    async def _finish(self, job: Job, state: str, message: str = ""):
        job.state, job.message, job.finished = state, message, time.time()
        await self._send(job)

    async def _run_all(self):
        while not self.queue.empty():
            job = await self.queue.get()
            if job.state != "queued":
                continue
            try:
                await self._run(job)
            except Exception as e:  # noqa: BLE001 - a job never takes the studio down
                await self._finish(job, "failed", f"{type(e).__name__}: {e}")

    async def _run(self, job: Job):
        stem = Path(job.file).stem
        spec = job.spec
        # the lock: wait for the preview server (or another export) to finish this file
        while not render_lock.try_acquire(stem, "studio export"):
            if job.cancel_asked:
                return await self._finish(job, "cancelled", "cancelled while waiting")
            if job.state != "waiting":
                job.state = "waiting"
                job.message = f"waiting for {(render_lock.holder(stem) or {}).get('owner', 'another render')}"
                await self._send(job)
            await asyncio.sleep(1)
        try:
            job.state, job.message = "rendering", ""
            for sc in job.scenes:
                ok = await self._render_scene(job, sc)
                if job.cancel_asked:
                    sc["state"] = "cancelled"
                    for later in job.scenes:
                        if later["state"] == "queued":
                            later["state"] = "skipped"
                    return await self._finish(job, "cancelled", f"cancelled during {sc['name']}")
                if not ok:
                    for later in job.scenes:
                        if later["state"] == "queued":
                            later["state"] = "skipped"
                    return await self._finish(job, "failed", f"{sc['name']} didn't render; nothing was joined")
            if spec["join"]:
                job.state = "joining"
                await self._send(job)
                out = ROOT / "media" / f"{stem}_full_{spec['quality']}.mp4"
                code, log = await self._tool(job, ["concat.py", str(out), *[str(ROOT / s["out"]) for s in job.scenes]])
                if job.cancel_asked:
                    return await self._finish(job, "cancelled", "cancelled while joining")
                if code != 0 or not out.is_file():
                    job.log += log
                    return await self._finish(job, "failed", "joining the scenes failed")
                job.joined = rel(out)
                for other in self.jobs.values():  # that file is this job's now
                    if other is not job and other.joined == job.joined:
                        other.joined = None
            if spec["check"]:
                job.state = "checking"
                await self._send(job)
                files = [str(ROOT / s["out"]) for s in job.scenes]
                # the joined file of silent scenes has a silent track: only check it when
                # some scene has narration cues (a silent scene alone passes by itself)
                narrated = any(_has_cues((ROOT / s["out"]).with_suffix(".srt")) for s in job.scenes)
                if job.joined and narrated:
                    files.append(str(ROOT / job.joined))
                code, log = await self._tool(job, ["audio_check.py", *files])
                job.check = {"ok": code == 0, "narrated": narrated, "report": log[-3000:]}
            await self._finish(job, "done", "" if not job.check or job.check["ok"]
                               else "rendered, but the narration check found problems")
        finally:
            render_lock.release(stem)

    async def _render_scene(self, job: Job, sc: dict) -> bool:
        spec = job.spec
        sc["state"] = "rendering"
        await self._send(job)
        args = [sys.executable, str(ROOT / "tools" / "timeline_render.py"), "render", f"-q{spec['quality']}",
                "--format", spec["format"]]
        if spec["transparent"]:
            args.append("-t")
        args += [str(ROOT / job.file), sc["name"]]
        t0 = time.time()
        code, log = await self._run_proc(job, args, sc)
        sc["s"] = round(time.time() - t0, 1)
        out = find_output(job.file, sc["name"], spec["format"], spec["transparent"], t0, spec["quality"])
        if code != 0 or out is None:
            sc["state"] = "failed"
            job.log += f"\n--- {sc['name']} ---\n" + log
            return False
        sc["state"], sc["out"], sc["pct"] = "done", rel(out), 100
        await self._send(job)
        return True

    async def _tool(self, job: Job, args: list[str]) -> tuple[int, str]:
        return await self._run_proc(job, [sys.executable, str(ROOT / "tools" / args[0]), *args[1:]], None)

    async def _run_proc(self, job: Job, args: list[str], sc: dict | None) -> tuple[int, str]:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", COLUMNS="200")
        job.proc = proc = await asyncio.create_subprocess_exec(
            *args, cwd=str(ROOT), env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            start_new_session=sys.platform != "win32")
        chunks: list[str] = []
        last_sent = 0.0
        buf = ""
        while True:
            data = await proc.stdout.read(4096)
            if not data:
                break
            text = data.decode("utf-8", "replace")
            chunks.append(text)
            if sc is None:
                continue
            buf = (buf + text)[-2000:]
            # Manim's progress bars: "Animation 12: Create(Circle):  45%|..." (\r-separated)
            m = None
            for m in _ANIM.finditer(buf):
                pass
            if m is not None:
                sc["anim"], sc["pct"] = int(m.group(1)), int(m.group(2))
                if time.monotonic() - last_sent > 0.5:
                    last_sent = time.monotonic()
                    await self._send(job)
        code = await proc.wait()
        job.proc = None
        log = "".join(chunks)
        return code, log[-LOG_TAIL:]
