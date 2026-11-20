"""Live preview for Manim scenes (a Manim Sideview stand-in for the Claude app).

Watches *.py files in this folder. When one is saved, every Scene in it is
re-rendered with `manim -a`, and the page at http://localhost:8765 plays the
newest videos and shows render errors.

Per scene, the page also shows:
- a timeline linked to the code: every play()/wait() as a block, with the
  line that called it (recorded by tools/timeline_render.py), the narration
  lines from the .srt, and the audio waveform. Click to seek; the line under
  the timeline shows which code is running at the playhead.
- an "outdated" badge when the source is newer than the video, or while it
  is being re-rendered;
- Compare: the previous render next to the current one, playing in sync.

Run:  .venv\\Scripts\\python preview_server.py   (or via the app's preview pane)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from render_lock import held as render_lock  # noqa: E402  (the studio's export takes the same lock)

ROOT = Path(__file__).resolve().parent
MEDIA_ROOT = ROOT / "media"
MEDIA = MEDIA_ROOT / "videos"
PREV = MEDIA_ROOT / "preview_prev"  # the render before the latest one, for Compare
PORT = int(os.environ.get("PREVIEW_PORT", "8765"))
IGNORE = {"preview_server.py"}
SHARED = ("style.py", "manim_kit.py")  # changes here make every video outdated
QUALITY_DIRS = {"l": "480p15", "m": "720p30", "h": "1080p60"}
WAVE_BINS = 600

lock = threading.Lock()
state = {
    "version": 0,
    "status": "idle",  # idle | rendering | ok | error
    "file": None,
    "quality": "l",
    "log": "",
    "started": None,
    "finished": None,
    "waiting": None,  # who else is rendering this file, while we wait for them
}
pending: set[str] = set()
wake = threading.Event()
wave_cache: dict[tuple[str, float], list[float]] = {}


def scene_files() -> list[str]:
    out = []
    for p in sorted(ROOT.glob("*.py")):
        if p.name in IGNORE:
            continue
        try:
            if re.search(r"^class\s+\w+\(.*Scene.*\):", p.read_text(encoding="utf-8"), re.M):
                out.append(p.name)
        except OSError:
            pass
    return out


def source_mtime(file: str) -> float:
    paths = [ROOT / file] + [ROOT / s for s in SHARED]
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def media_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return "/" + quote(rel) + f"?t={int(path.stat().st_mtime)}"


def videos_for(file: str, quality: str) -> list[dict]:
    d = MEDIA / Path(file).stem / QUALITY_DIRS[quality]
    if not d.is_dir():
        return []
    src_time = source_mtime(file)
    prev_dir = PREV / Path(file).stem / QUALITY_DIRS[quality]
    vids = []
    for mp4 in sorted(d.glob("*.mp4")):
        st = mp4.stat()
        prev = prev_dir / mp4.name
        vids.append({
            "scene": mp4.stem,
            "path": mp4.relative_to(ROOT).as_posix(),
            "url": media_url(mp4),
            "mtime": st.st_mtime,
            "outdated": src_time > st.st_mtime + 1,
            "prev": media_url(prev) if prev.exists() else None,
            "prevTime": prev.stat().st_mtime if prev.exists() else None,
        })
    vids.sort(key=lambda v: v["mtime"], reverse=True)
    return vids


def keep_previous(file: str, quality: str) -> None:
    """Copy the current videos aside before a render, for Compare."""
    d = MEDIA / Path(file).stem / QUALITY_DIRS[quality]
    if not d.is_dir():
        return
    out = PREV / Path(file).stem / QUALITY_DIRS[quality]
    out.mkdir(parents=True, exist_ok=True)
    for mp4 in d.glob("*.mp4"):
        try:
            shutil.copy2(mp4, out / mp4.name)
            tl = mp4.with_suffix(".timeline.json")
            if tl.exists():
                shutil.copy2(tl, out / tl.name)
        except OSError:
            pass


def srt_cues(path: Path) -> list[dict]:
    if not path.exists():
        return []
    t = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)\n(.*)", block, re.S)
        if m:
            g = m.groups()
            cues.append({"t": t(*g[:4]), "end": t(*g[4:8]), "text": g[8].strip().replace("\n", " ")})
    return cues


def waveform(path: Path, bins: int = WAVE_BINS) -> list[float]:
    """Peak level per bin over the whole video (0..1, scaled to the loudest bin)."""
    key = (str(path), path.stat().st_mtime)
    if key in wave_cache:
        return wave_cache[key]
    import av  # PyAV ships with Manim
    import numpy as np
    peaks: list[float] = []
    with av.open(str(path)) as c:
        dur = float(c.duration or 0) / av.time_base
        if c.streams.audio and dur > 0:
            rate = 8000
            res = av.AudioResampler(format="flt", layout="mono", rate=rate)
            chunks = [o.to_ndarray().reshape(-1)
                      for f in c.decode(c.streams.audio[0]) for o in res.resample(f)]
            x = np.abs(np.concatenate(chunks)) if chunks else np.zeros(1)
            edges = np.linspace(0, dur * rate, bins + 1).astype(int)
            raw = [float(x[a:b].max()) if b > a and a < len(x) else 0.0
                   for a, b in zip(edges, edges[1:])]
            top = max(raw) or 1.0
            peaks = [round(v / top, 3) for v in raw]
    wave_cache[key] = peaks
    return peaks


def detail(rel: str) -> dict:
    """Timeline, narration cues and waveform for one video."""
    mp4 = (ROOT / rel).resolve()
    mp4.relative_to(MEDIA_ROOT.resolve())  # raises if outside media/
    tl = mp4.with_suffix(".timeline.json")
    timeline = None
    if tl.exists():
        timeline = json.loads(tl.read_text(encoding="utf-8"))
        # a timeline older than the video belongs to an earlier render
        timeline["stale"] = tl.stat().st_mtime < mp4.stat().st_mtime - 5
    return {"timeline": timeline, "cues": srt_cues(mp4.with_suffix(".srt")),
            "wave": waveform(mp4)}


def render(file: str) -> None:
    with lock:
        q = state["quality"]
        state.update(status="rendering", file=file, log="", started=time.time())
        state["version"] += 1
    def waiting(who: dict) -> None:
        with lock:
            state["waiting"] = who.get("owner") or "another process"
            state["version"] += 1

    with render_lock(Path(file).stem, "preview server", on_wait=waiting):
        with lock:
            state["waiting"] = None
            state["version"] += 1
        keep_previous(file, q)
        cmd = [sys.executable, str(ROOT / "tools" / "timeline_render.py"), "render", f"-q{q}", "-a", file]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", COLUMNS="200")
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env)
    log = (proc.stdout + "\n" + proc.stderr).strip()
    with lock:
        state.update(status="ok" if proc.returncode == 0 else "error",
                     log=log[-20000:], finished=time.time())
        state["version"] += 1


def worker() -> None:
    while True:
        wake.wait()
        time.sleep(0.4)  # debounce bursts of save events
        wake.clear()
        with lock:
            files = sorted(pending)
            pending.clear()
        for f in files:
            render(f)


def queue(file: str) -> None:
    with lock:
        pending.add(file)
    wake.set()


class Watcher(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory or event.event_type not in ("modified", "created", "moved"):
            return
        path = Path(getattr(event, "dest_path", "") or event.src_path)
        if path.parent == ROOT and path.name in scene_files():
            queue(path.name)
        elif path.name in SHARED:  # shared code changed: refresh the open file
            with lock:
                current = state["file"]
            if current:
                queue(current)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path == "/api/state":
            with lock:
                s = dict(state)
            files = scene_files()
            current = s["file"] or (files[0] if files else None)
            s["files"] = files
            s["current"] = current
            s["videos"] = videos_for(current, s["quality"]) if current else []
            return self._json(s)
        if url.path == "/api/detail":
            try:
                return self._json(detail(qs.get("video", [""])[0]))
            except (ValueError, OSError) as e:
                return self._json({"error": str(e)}, 404)
        if url.path.startswith("/media/") and url.path.endswith(".mp4"):
            return self._serve_video(ROOT / unquote(url.path.lstrip("/")))
        self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path == "/api/render":
            f = qs.get("file", [None])[0]
            if f not in scene_files():
                return self._json({"error": "unknown file"}, 400)
            q = qs.get("quality", [None])[0]
            if q in QUALITY_DIRS:
                with lock:
                    state["quality"] = q
            queue(f)
            return self._json({"queued": f})
        if url.path == "/api/select":
            f = qs.get("file", [None])[0]
            if f in scene_files():
                with lock:
                    state["file"] = f
                    state["version"] += 1
            return self._json({"ok": True})
        self.send_error(404)

    def _serve_video(self, path: Path):
        try:
            path.resolve().relative_to(MEDIA_ROOT.resolve())
            size = path.stat().st_size
        except (ValueError, OSError):
            return self.send_error(404)
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m:
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            elif m.group(2):
                start = max(0, size - int(m.group(2)))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        length = end - start + 1
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(1 << 16, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Manim Preview</title>
<style>
:root{--bg:#111316;--panel:#1a1d22;--line:#2b3038;--text:#e6e8eb;--muted:#9aa3ad;
--ok:#3fb950;--err:#f85149;--busy:#d29922;--accent:#58a6ff;--voice:#3fb950;--track:#14171b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.4 system-ui,Segoe UI,sans-serif}
header{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:10px 14px;
border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:5}
header h1{font-size:15px;margin:0 8px 0 0;font-weight:600}
select,button{background:var(--bg);color:var(--text);border:1px solid var(--line);
border-radius:6px;padding:5px 9px;font:inherit}
button{cursor:pointer}button:hover{border-color:var(--accent)}
button.on{border-color:var(--accent);color:var(--accent)}
button.small{padding:2px 8px;font-size:12px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;
border:1px solid var(--line);font-size:13px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted)}
.ok .dot{background:var(--ok)}.error .dot{background:var(--err)}
.rendering .dot{background:var(--busy);animation:p 1s infinite}
@keyframes p{50%{opacity:.3}}
main{padding:14px;display:grid;gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}
.card h2{margin:0;padding:8px 12px;font-size:13px;font-weight:600;border-bottom:1px solid var(--line);
display:flex;gap:10px;align-items:center;color:var(--muted)}
.card h2 .name{color:var(--text)}.card h2 .grow{flex:1}
.badge{font-size:11px;font-weight:600;padding:1px 8px;border-radius:999px;
background:#3a2d0c;color:#f0c45a;border:1px solid #6b5212}
.stage{display:grid;grid-template-columns:1fr;gap:2px;background:#000;position:relative}
.stage.compare{grid-template-columns:1fr 1fr}
.stage figure{margin:0;position:relative}
.stage figcaption{position:absolute;top:6px;left:6px;font-size:11px;padding:1px 7px;border-radius:4px;
background:rgba(0,0,0,.65);color:var(--muted)}
.stage.outdated video{opacity:.55}
video{display:block;width:100%;background:#000;aspect-ratio:16/9}
.tl{position:relative;margin:8px 12px 4px 52px;cursor:pointer;user-select:none}
.row{position:relative;height:22px;background:var(--track);border-radius:3px;margin-bottom:3px}
.row .lab,.wavelab{position:absolute;left:-42px;top:4px;font-size:10px;color:#6b737d;pointer-events:none}
.wavelab{top:auto;bottom:8px}
.blk{position:absolute;top:2px;bottom:2px;border-radius:3px;font-size:10px;line-height:16px;
padding:0 4px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.blk.play{background:#1f3a5c;color:#bcd7ff;border:1px solid #2f5a8f}
.blk.wait{background:transparent;border:1px dashed #333a44}
.blk.hold{background:repeating-linear-gradient(45deg,#1b1e23 0 4px,#22262c 4px 8px);border:1px solid #2b3038}
.blk.cue{background:#16351f;color:#a7e3b4;border:1px solid #23683a}
.blk.cur{outline:2px solid var(--accent);z-index:2}
canvas.wave{display:block;width:100%;height:28px;background:var(--track);border-radius:3px}
.head{position:absolute;top:0;bottom:0;width:2px;background:#ff5d5d;pointer-events:none;z-index:3}
.info{margin:2px 12px 10px;font:12px/1.5 Consolas,monospace;color:var(--muted);display:flex;gap:10px;
align-items:baseline;min-height:18px}
.info code{color:var(--text);white-space:pre;overflow:hidden;text-overflow:ellipsis;flex:1}
.info .ln{color:var(--accent);cursor:pointer}
.note{margin:0 12px 10px;font-size:12px;color:var(--muted)}
pre{margin:0;padding:12px;max-height:45vh;overflow:auto;font:12px/1.45 Consolas,monospace;
white-space:pre-wrap;word-break:break-word;color:#ffb4ae}
.empty{padding:40px 16px;text-align:center;color:var(--muted)}
.muted{color:var(--muted);font-size:12px}
</style></head><body>
<header>
  <h1>Manim Preview</h1>
  <select id="file" aria-label="Scene file"></select>
  <select id="quality" aria-label="Quality">
    <option value="l">480p15</option><option value="m">720p30</option><option value="h">1080p60</option>
  </select>
  <button id="render">Render now</button>
  <span id="status" class="pill"><span class="dot"></span><span id="statusText">idle</span></span>
  <span id="time" class="muted"></span>
</header>
<main id="main"></main>
<script>
let lastKey="";
const comparing=new Set();      // scene names with Compare on (survives rebuilds)
const $=id=>document.getElementById(id);
async function post(u){await fetch(u,{method:"POST"});tick();}
$("render").onclick=()=>post(`/api/render?file=${encodeURIComponent($("file").value)}&quality=${$("quality").value}`);
$("file").onchange=()=>post(`/api/select?file=${encodeURIComponent($("file").value)}`);
$("quality").onchange=()=>$("render").click();
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
const fmt=t=>`${Math.floor(t/60)}:${(t%60).toFixed(2).padStart(5,"0")}`;

async function tick(){
  let s; try{s=await (await fetch("/api/state")).json()}catch{ $("statusText").textContent="server offline";return}
  const opts=s.files.map(f=>`<option ${f===s.current?"selected":""}>${esc(f)}</option>`).join("");
  if($("file").innerHTML!==opts) $("file").innerHTML=opts;
  $("quality").value=s.quality;
  $("status").className="pill "+s.status;
  $("statusText").textContent=s.status==="rendering"?(s.waiting?`waiting for ${s.waiting} to finish ${s.file}…`:`rendering ${s.file}…`):s.status;
  $("time").textContent=s.finished&&s.status!=="rendering"?`${((s.finished-s.started)).toFixed(1)}s · ${new Date(s.finished*1000).toLocaleTimeString()}`:"";
  const busy=s.status==="rendering"&&s.file===s.current;
  const key=JSON.stringify([s.version,s.videos.map(v=>[v.url,v.prev,v.outdated]),s.status,busy]);
  if(key===lastKey) return; lastKey=key;
  let html="";
  if(s.status==="error") html+=`<div class="card"><h2>Render error</h2><pre>${esc(s.log)}</pre></div>`;
  if(!s.files.length) html+=`<div class="empty">No scene files yet. Save a .py file with a Scene class in this folder.</div>`;
  else if(!s.videos.length && s.status!=="rendering") html+=`<div class="empty">No renders of ${esc(s.current)} at this quality yet. Save the file or press Render now.</div>`;
  s.videos.forEach((v,i)=>{
    const stale=busy||v.outdated;
    const badge=busy?"outdated · re-rendering":(v.outdated?"outdated · source changed":"");
    const cmp=comparing.has(v.scene)&&v.prev;
    html+=`<div class="card" id="c${i}">
      <h2><span class="name">${esc(v.scene)}</span>${badge?`<span class="badge">${badge}</span>`:""}
      <span class="grow"></span>
      ${v.prev?`<button class="small ${cmp?"on":""}" data-cmp="${esc(v.scene)}" title="Previous render next to this one">Compare</button>`:""}
      <span>${new Date(v.mtime*1000).toLocaleTimeString()}</span></h2>
      <div class="stage ${cmp?"compare":""} ${stale?"outdated":""}">
        ${cmp?`<figure><video class="prev" src="${v.prev}" muted playsinline></video><figcaption>previous · ${new Date(v.prevTime*1000).toLocaleTimeString()}</figcaption></figure>`:""}
        <figure><video class="cur" src="${v.url}" controls autoplay muted loop playsinline></video>${cmp?`<figcaption>current</figcaption>`:""}</figure>
      </div>
      <div class="tl"></div><div class="info"></div></div>`;
  });
  $("main").innerHTML=html;
  document.querySelectorAll("[data-cmp]").forEach(b=>b.onclick=()=>{
    const n=b.dataset.cmp; comparing.has(n)?comparing.delete(n):comparing.add(n); lastKey=""; tick();});
  s.videos.forEach((v,i)=>setupCard($("c"+i),v,s.current));
}

async function setupCard(card,v,file){
  const vid=card.querySelector("video.cur"), prev=card.querySelector("video.prev");
  const tl=card.querySelector(".tl"), info=card.querySelector(".info");
  if(prev){ // keep the previous render in step with the current one
    const sync=()=>{ if(Math.abs(prev.currentTime-vid.currentTime)>0.08) prev.currentTime=Math.min(vid.currentTime,prev.duration||1e9);
      if(vid.paused!==prev.paused) vid.paused?prev.pause():prev.play().catch(()=>{}); };
    ["play","pause","seeked","timeupdate"].forEach(e=>vid.addEventListener(e,sync));
  }
  let d; try{d=await (await fetch("/api/detail?video="+encodeURIComponent(v.path))).json()}catch{return}
  if(d.error) return;
  const evs=(d.timeline&&d.timeline.events)||[];
  const dur=Math.max(vid.duration||0,(d.timeline&&d.timeline.duration)||0,
                     ...d.cues.map(c=>c.end),...evs.map(e=>e.t+e.d),0.01);
  const pct=t=>(100*t/dur)+"%";
  let rows=`<div class="row"><span class="lab">code</span>`;
  evs.forEach((e,k)=>{
    const cls=e.kind==="play"?"play":(e.line?"wait":"hold");
    const tip=e.line?`line ${e.line}: ${e.code}`:"end hold (scene padded to its length)";
    rows+=`<div class="blk ${cls}" data-k="${k}" style="left:${pct(e.t)};width:${pct(e.d)}" title="${esc(fmt(e.t)+"  "+tip)}">${e.kind==="play"?esc(e.label):""}</div>`;
  });
  rows+=`</div><div class="row"><span class="lab">voice</span>`;
  d.cues.forEach(c=>rows+=`<div class="blk cue" style="left:${pct(c.t)};width:${pct(c.end-c.t)}" title="${esc(fmt(c.t)+"  "+c.text)}">${esc(c.text)}</div>`);
  rows+=`</div><canvas class="wave"></canvas><span class="wavelab">audio</span><div class="head"></div>`;
  tl.innerHTML=rows;
  if(!d.timeline) info.insertAdjacentHTML("afterend",`<div class="note">No code timeline yet: it is recorded when the preview server renders this file.</div>`);
  else if(d.timeline.stale) info.insertAdjacentHTML("afterend",`<div class="note">Code timeline is from an earlier render (the video was made outside the preview server).</div>`);
  // waveform
  const cv=tl.querySelector("canvas"), dpr=window.devicePixelRatio||1;
  const drawWave=()=>{const w=cv.clientWidth,h=cv.clientHeight; cv.width=w*dpr; cv.height=h*dpr;
    const g=cv.getContext("2d"); g.scale(dpr,dpr); g.fillStyle="#5d6670";
    const n=d.wave.length; if(!n){g.fillStyle="#3a4048";g.font="10px system-ui";g.fillText("no audio",4,17);return}
    const span=(vid.duration||dur)/dur; // the waveform covers the video's own length
    for(let x=0;x<w;x++){const k=Math.floor(x/(w*span)*n); if(k>=n)break; const a=d.wave[k]*(h/2-1);
      g.fillRect(x,h/2-a,1,Math.max(1,2*a));}};
  drawWave(); new ResizeObserver(drawWave).observe(cv);
  // seeking, playhead, current code line
  const head=tl.querySelector(".head"), blks=[...tl.querySelectorAll(".blk[data-k]")];
  tl.onclick=e=>{const r=tl.getBoundingClientRect(); vid.currentTime=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*dur;};
  let lastK=-2;
  const step=()=>{
    if(!card.isConnected) return;
    const t=vid.currentTime; head.style.left=pct(t);
    let k=evs.findIndex(e=>e.kind==="play"&&t>=e.t&&t<e.t+e.d);
    if(k<0) k=evs.findIndex(e=>t>=e.t&&t<e.t+e.d);
    if(k!==lastK){
      blks.forEach(b=>b.classList.toggle("cur",+b.dataset.k===k)); lastK=k;
      const e=evs[k];
      info.innerHTML=e?`<span>${fmt(t)}</span>${e.line?`<span class="ln" title="Copy file:line">${esc(file)}:${e.line}</span><code>${esc(e.code)}</code>`
        :`<code>end hold</code>`}`:"";
      const ln=info.querySelector(".ln"); if(ln) ln.onclick=()=>navigator.clipboard&&navigator.clipboard.writeText(`${file}:${e.line}`);
    } else if(info.firstChild) info.firstChild.textContent=fmt(t);
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
tick(); setInterval(tick,1000);
</script></body></html>"""


def main() -> None:
    threading.Thread(target=worker, daemon=True).start()
    obs = Observer()
    obs.schedule(Watcher(), str(ROOT), recursive=False)
    obs.start()
    print(f"Manim preview on http://localhost:{PORT}  (watching {ROOT})", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    finally:
        obs.stop()


if __name__ == "__main__":
    main()
