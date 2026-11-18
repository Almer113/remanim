# Claude-specific integrations for Manim: evaluation

Date: 2026-11-14. Context: Claude Code desktop app on Windows 10, ManimCE 0.22.1 in `.venv` (Python 3.13.3), manimpango 0.7.1. Nothing was installed or run. Everything below comes from reading repo source through the GitHub API and PyPI metadata. Star counts and dates are as of 2026-11-14.

## Bottom line

Plain Claude Code (write file, shell out to `manim`, Read the PNGs) already does everything every integration reviewed here does mechanically. No MCP server adds a capability. The real gains come from **knowledge and process**:

1. A visual verification loop: render sparse PNG frames, build a contact sheet, look at it.
2. Layout rules that prevent overlap and overflow when the code is built, not afterwards.
3. ManimCE-specific gotchas, so CE and GL APIs don't get mixed up.

All three fit in a project `CLAUDE.md`, optionally with a small local skill and a contact-sheet script. Recommendation: **write your own short CLAUDE.md and borrow ideas. Don't install a third-party skill wholesale, and don't install any MCP server.**

---

## 1. adithya-s-k/manim_skill: borrow ideas (selectively)

- 1,312 stars, last commit 2026-01-23 (10 months stale). MIT for the CE skill and the composer. **The ManimGL skill is CC BY-NC-SA 4.0** because its examples are adapted from 3b1b/videos.
- Three skills:
  - `manimce-best-practices`: targets **ManimCE**. SKILL.md is an index, plus 23 rule files (~4-6 KB each), 6 example scripts and 3 templates.
  - `manimgl-best-practices`: targets **ManimGL** (InteractiveScene, `-se`, `t2c`, frame/embedding). Not relevant to this user.
  - `manim-composer`: engine-agnostic planning. It researches the topic, asks the user about audience, length and style, then writes a `scenes.md` covering overview/hook/key insight, per-scene duration, purpose, visual elements, narration notes and technical notes, plus a color palette and implementation order. Also includes "3b1b-style principles": progressive revelation, transform rather than replace, color as meaning, pose questions, pause for insight.
- What the CE rules contain: mostly a paraphrase of the official docs, organized by topic (scenes, mobjects, animations, positioning, grouping, text, LaTeX, timing/rate functions, updaters, camera, 3D, CLI, config, shapes, lines, colors, styling). Each file ends with 4-6 generic "best practices", such as "use next_to for relative positioning", "keep run_time 0.5-3 s", "use substrings_to_isolate for coloring", and "use VGroup over Group".
- Quality assessment: **mediocre**. Accurate enough for the basics, but:
  - **Factual errors in `rules/config.md`.** Its example `manim.cfg` puts settings under `[renderer]`, `[output]`, `[style]` and `[tex]` sections. ManimCE reads only `[CLI]` (plus logger, ffmpeg and jupyter sections). I checked `_config/default.cfg` in the local 0.22.1 install: `background_color`, `media_dir` and so on live under `[CLI]`. Those example settings would be silently ignored.
  - `positioning.md` invents a `center_on()` helper.
  - Nothing on a visual verification loop, frame bounds or overlap. Those are the most common failure modes for LLM-written Manim.
  - Nothing Windows-specific beyond "use `python -m manim` if not on PATH".
  - Claude already knows most of this content, so it costs context without adding much.
- Worth borrowing: the composer's `scenes.md` planning template, which is a good idea for multi-scene videos. The CE/GL disambiguation table, which is useful as a 5-line rule.

## 2. Entries on plugins.manim.community

The plugin site is a JS listing of PyPI packages, so I checked PyPI directly.

### manim-claude (PyPI 0.1.0, 2026-03-18, MIT): borrow ideas, don't install

- `uvx manim-claude install` copies a Claude Code skill: 24 reference guides, `safe_manim.py` wrappers, `render_scene.sh`, templates and `style.py`. Its GitHub homepage (atsubhas/manim-claude) now returns 404.
- It appears to be a packaged snapshot of **AmitSubhash/3brown1blue**: 47 stars, last push 2026-06-27, MIT. That repo is more current, so I evaluated it instead.
- 3brown1blue targets ManimCE by default.
- Its SKILL.md starts with 14 "gotchas", e.g. `MathTex` with `$` crashes, use `ReplacementTransform` for chained transforms, `.animate` only inside `play()`, mp4 has no alpha so use `--format webm -t`, and `Write()` vs `Create()` for text.
- Rule files cover explanation design (drawn from Grant Sanderson's talks), a pedagogy checklist, visual-design principles and catalog, scene planning, paper explainers, voiceover (Kokoro), troubleshooting and Remotion integration.
- **Best file: `rules/production-quality.md`.** It is the most useful layout material found anywhere:
  - Named screen regions: title band y≈2.8-3.5, left/right panels, bottom band y≈-3.5 to -2.5.
  - Safe bounds of about |x|≤6.5 and |y|≤3.5, plus a "coordinate budget": no absolute x>5.5 or y>3.2.
  - `safe_text()` scale-to-fit width caps.
  - Container-bounds rules.
  - "FadeOut before reusing a region".
  - "Dim beside, FadeOut under".
  - Minimum font size ~20, plus data-viz minimums.
  - A pre-render checklist and a post-render checklist.
  - A two-phase test: `py_compile`, then a `-ql` render of every scene.
  - A list of recurring failure patterns: `next_to` pushing things off-screen when the anchor is at |x|>2.5, `Write()` garbling small notes, legend placement, and so on.
- `scripts/audit_video.sh` extracts 5 frames per scene with ffmpeg for review.
- Caveats:
  - Some gotchas are overstated. In CE 0.22, `wait(frozen_frame=None)` auto-detects time-based updaters, so the blanket "add `frozen_frame=False`" isn't needed.
  - Some style rules are opinionated: mandatory question frames, "no two consecutive scenes with the same technique".
  - The scripts are bash.
- Worth borrowing: the layout system and the pre/post-render checklists (MIT, paraphrase them).

### manim-mcp (PyPI 0.1.0, 2026-02-01; paulnegz/manim-mcp, 22 stars, MIT): ignore

- **Targets ManimGL**, not CE.
- A text-to-video pipeline: Gemini by default (Claude/DeepSeek optional), ChromaDB RAG over 3b1b scenes, optional S3/MinIO, and an MCP server wrapper.
- Heavy dependencies (torch/transformers for the RAG extra) and needs an API key.
- It duplicates what Claude Code already does, with a second LLM in the loop.

### llmanim (PyPI 0.1.3, 2026-07-31; rishabhbhartiya/LLManim, 0 stars, MIT): ignore for this purpose

- Not a Claude integration at all. "LLM" refers to the topic: a library of reusable CE components for drawing transformer/attention diagrams, requiring `manim>=0.18`.
- Only relevant if the user makes videos about LLMs.
- (roykhushi/llmanim, 2 stars, is a separate web app.)

## 3. Manim MCP servers: ignore

**abhiemj/manim-mcp-server** (658 stars, last commit 2025-05-19, MIT) is one 60-line `src/manim_server.py` with two tools:

- `execute_manim_code(manim_code)` writes the code to a fixed `media/manim_tmp/scene.py` and runs `manim -p scene.py` with no scene name and no quality flag. It returns only "success" or stderr. It returns no file paths and no frames, and `-p` pops a video player each time.
- `cleanup_manim_temp_dir(directory)` runs `shutil.rmtree` on **any path the model passes**. That is an unnecessary deletion footgun.
- It was built for Claude Desktop (chat), which has no shell. For Claude Code it is strictly worse than Bash: one file, no multi-scene, no CLI flags, no PNG output.

**Others found**, all with 0-22 stars and mostly abandoned:

| Repo | Target | Notes |
|---|---|---|
| wstcpyt/manim-mcp | — | 19 stars, 2025-05 |
| Avik-creator/manim-mcp | — | 16 stars, 2025-05 |
| ajay-sreeram/manim-mcp | CE | 0 stars; returns artifact paths and logs |
| zcsabbagh/manim-mcp | — | — |
| zcq100/manim-mcp-server | — | HTTP transport |
| daedalus/mcp-manimgl | ManimGL | 0 stars, 2026-05; I found no "manimgl-mcp" with traction |
| scharanruka/manimgx-mcp-server | — | — |

**Does MCP add anything over shell access?** No. Every one of these servers wraps `subprocess.run(["manim", ...])`. Claude Code's Bash/PowerShell tools already run the real CLI with every flag, and its Read tool already views PNGs. MCP only makes sense for chat clients without a shell, or for a server that does something new, such as returning rendered frames as images or bounding-box overlap reports. None of the servers reviewed does that well.

## 4. 3b1b/videos CLAUDE.md: borrow ideas (paraphrase only)

- Repo: 11,489 stars, pushed 2026-11-10. CLAUDE.md was added 2025-06-30 and updated 2025-07-01 and 2026-04-28.
- **License: CC BY-NC-SA 4.0** (repo contents; the manimgl library itself is MIT). Summarize, don't copy.
- It is short. It looks like a `/init`-generated file with Grant's hand-edits, the "Python Code Style" section especially.
- Contents:
  - Commands: `manimgl file scene`, `-se <line>` to drop into interactive mode at a line, `-p`, `checkpoint_paste()` variants, and `stage_scenes.py`.
  - Repo layout: `_YYYY/` year folders, `custom/`, `once_useful_constructs/`, `manim_imports_ext.py`, `custom_config.yml` (4K at 30 fps).
  - Patterns: `InteractiveScene`; `Tex(R"...")` and not `MathTex`; `lag_ratio`; `t2c={...}` for coloring; `self.frame` for the camera; `f_always`; `LaggedStart`.
  - Code organization: config constants at the top of the file, class attributes for scene configuration, `get_*` helper names.
  - Style rules Grant added (the valuable part):
    - No whitespace on blank lines.
    - Prefer existing utilities over hand-rolled index arithmetic, e.g. `color_gradient(colors, n)` instead of looping over `interpolate_color`.
    - Build VGroups declaratively (`VGroup(... for ...)`) rather than `.add()` in a loop.
    - **Use the layout methods (`arrange`, `next_to`, `move_to`) instead of bespoke coordinate arithmetic. A bit of redundant movement beats manual math that is easy to get wrong.**
  - No test framework: scenes are verified by visual preview.

**Transfers to ManimCE:**

- The layout-methods rule.
- Declarative VGroups.
- Use library utilities (`color_gradient` exists in CE).
- Constants at the top of the file; class attributes for scene configuration; `get_*` helpers.
- `lag_ratio` and `LaggedStart`.
- `add_updater`.
- Raw strings for LaTeX.
- Verify visually.

**Does not transfer:**

| ManimGL (3b1b) | ManimCE equivalent |
|---|---|
| `manimgl`, `-se`, `checkpoint_paste`, `InteractiveScene` | `manim` CLI, `Scene` |
| `self.frame` for the camera | `MovingCameraScene` + `self.camera.frame` |
| `Tex` as the math default | `MathTex` for math; `Tex` is text mode |
| `t2c=` | `tex_to_color_map=` or `set_color_by_tex` with `substrings_to_isolate` |
| `f_always` | none (GL only) |
| `custom_config.yml` | `manim.cfg` with a `[CLI]` section |
| Pi creatures, `manim_imports_ext` | none |

## 5. Other skills, plugins and posts

- **DominikPeters/manim-skill** (1 star, MIT, VERSION 1.0.22, pushed 2026-11-01): **best match for the verification loop. Borrow it, or adopt it if you want ready-made scripts.**
  - Small SKILL.md: render sparse PNG frames with `manim -ql --fps 2 --format=png`, which writes to `media/images/<file>/`.
  - `refresh_frames.py` deletes stale frames and re-renders.
  - `make_contact_sheet.py` builds a 4x4 grid of evenly sampled frames.
  - Process: **read the contact sheet first, then at least one full-size frame. Raise `--fps` to 4 or 8 to see between two frames.**
  - Bundles CE docs converted to markdown (MIT, from ManimCE) for grepping.
  - Cross-platform Python. It uses `python3`, so on this machine call `.venv\Scripts\python`.
- **Yusuke710/manim-skill** (203 stars, MIT, pushed 2026-10-07; a Claude Code plugin, CE): borrow its narration-first idea if doing voiceover.
  - Pipeline: narration.txt → local **Kokoro** TTS (`timestamps.json` with exact per-line durations) → code with explicit `run_time` on every `play()` and `wait(max(0, dur - used))` to fill each segment → `add_subcaption()` for `.srt` → `lint-subtitles.py` simulates timing → render → ffmpeg concat and mux → a browser video viewer where the user captures timestamped notes.
  - **When feedback cites a timestamp, it extracts that exact frame with ffmpeg and reads it before editing.**
  - Opinionated: writes into `~/.manim-skill/`, not the project. Setup docs are macOS-only (brew, MacTeX).
- **davila7/claude-code-templates `manim`** (repo 33k stars, MIT) is a generic docs digest. **affaan-m/ECC `manim-video`** is generic workflow advice: thesis → 3-6 scenes → smoke test at `-ql` → polish. **vumichien/manim-skill** (10 stars, Apache-2.0) is a 4-role researcher/planner/implementer agent pipeline, overkill here. **awesome-skills/manim-skill** (15 stars, MIT) is a playbook. **Science-Prof-Robot/recursive-math-animator** (13 stars) was flagged "suspicious patterns" on ClawHub, so avoid it. **nicglazkov/Chalkboard** (22 stars) is a self-hosted narrated-explainer pipeline. **wilwaldon/Claude-Code-Video-Toolkit** (115 stars, no license) is a link collection. All of these: ignore.
- **No Anthropic-official Manim skill.** Nothing in anthropics/skills or anthropics/claude-plugins-official matches "manim".
- Posts and research:
  - sola-fide blog, "Creating math animations with Claude and Manim, part 2" (2026-02-03): state the teaching goal and audience; build scene by scene; expect 2-3 render rounds with concrete feedback ("the squares overlap"); set timing explicitly because defaults feel rushed; keep a series-wide style guide.
  - arXiv 2605.15585 (OmniManim, 2026): LLM-written Manim routinely compiles but renders with overlap, overflow, leftover objects and scale mismatch, and these problems are only detectable after rendering. **Two valid keyframes can still collide mid-transition**, so sample intermediate frames (the paper uses u=0.25, 0.5, 0.75), not just the end states. This supports a sparse-fps frame dump over `-s` last-frame-only checks.
  - A recurring community point: prevent overlap when building the scene (relative layout, self-arranging groups) rather than only checking for it afterwards.

## 6. manim-voiceover: adopt only when narration is needed (with caveats)

- ManimCommunity/manim-voiceover: 327 stars, MIT. **v0.4.0 released 2026-06-14**, last commit 2026-06-15.
- The June 2026 work was a big modernization: src layout, uv, pydantic cache, Gemini TTS service, a strict CI quality gate. No commits since, and about 30 open issues/PRs, including Kokoro (#121, #136), Edge TTS (#143), Pocket TTS and a faster-whisper migration (#124).
- Requires Python >=3.11 (classifiers 3.11-3.13), so the 3.13 venv is OK. The manim dependency is unpinned. **CI runs on ubuntu only and the lockfile pins manim 0.20.1**, so neither Windows nor ManimCE 0.22.1 is officially tested. I found no 0.22-specific breakage reported, but it is unverified.
- TTS backends in 0.4.0:

  | Service | Offline? | Notes |
  |---|---|---|
  | Azure | No | Needs a key |
  | gTTS | No | Free, unofficial Google endpoint |
  | OpenAI | No | — |
  | ElevenLabs | No | Pinned `elevenlabs<0.3`, a very old SDK |
  | Gemini | No | New in 0.4 |
  | pyttsx3 | Yes | Uses SAPI5 on Windows; robotic voice |
  | RecorderService | Yes | Your own microphone, via PyAudio + pynput |
  | Stitcher | — | — |

  Coqui is no longer in the services folder. **There is no high-quality local TTS built in.** For Kokoro or Edge-TTS you would subclass `SpeechService` yourself or wait for the open PRs.
- Windows notes:
  - `pydub` needs ffmpeg on PATH.
  - `sox` (pysox) wraps the SoX binary, used only for `adjust_speed`. Without SoX installed it warns on import, and speed adjustment fails.
  - The `transcribe` extra (openai-whisper + stable-ts) is fragile: issue #129 reports a `pkg_resources` import failure. It is only needed for word-level bookmarks with the recorder.
  - PyAudio has Windows wheels.
- Alternative: the Yusuke710 approach. Generate TTS outside Manim, read the durations, drive `run_time`/`wait` from them, then mux with ffmpeg. That has fewer moving parts inside the render and doesn't depend on plugin compatibility.

---

## 7. Verdict table

| Item | Verdict | Why |
|---|---|---|
| adithya-s-k/manim_skill (CE + composer) | Borrow ideas | scenes.md planning template and CE/GL table; rules are generic, partly wrong (manim.cfg sections), no verification loop |
| adithya-s-k/manim_skill (GL) | Ignore | ManimGL; CC BY-NC-SA |
| manim-claude / 3brown1blue | Borrow ideas | Best layout rules and checklists (MIT); too large and opinionated to install whole; bash scripts |
| manim-mcp (paulnegz) | Ignore | ManimGL, second LLM, heavy dependencies |
| llmanim | Ignore (unless making LLM-topic videos) | Component library, not an integration |
| abhiemj/manim-mcp-server and other MCP servers | Ignore | Thin subprocess wrappers; less capable than Bash; rmtree tool |
| 3b1b/videos CLAUDE.md | Borrow ideas | Layout-methods and declarative-code rules; GL-specific otherwise; CC BY-NC-SA |
| DominikPeters/manim-skill | Borrow (or adopt the scripts) | Exactly the right verification loop; MIT; tiny |
| Yusuke710/manim-skill | Borrow ideas for narration | Narration-first timing, subcaptions, frame-at-timestamp review |
| manim-voiceover 0.4.0 | Adopt when narrating (test first) | Maintained, MIT; Windows and 0.22 untested; local TTS weak |

---

## 8. Draft outline: project CLAUDE.md (or `.claude/skills/manim/SKILL.md`)

Keep it under ~150 lines. Put long checklists in a `docs/` or skill `references/` file that Claude reads on demand.

### A. Environment (facts Claude can't guess)
- ManimCE **0.22.1** (`from manim import *`). **Never ManimGL**: no `manimlib`, `InteractiveScene`, `t2c=`, `self.frame` or `-se`.
- Windows. Run through the venv: `.venv\Scripts\python -m manim ...`, or `.venv\Scripts\manim.exe`. Use PowerShell syntax; pass paths with spaces in quotes.
- State which LaTeX distribution is installed (MiKTeX or TeX Live), whether ffmpeg is on PATH, and the font families available.
- `preview_server.py` already exists (watches *.py and re-renders on save at http://localhost:8765). Say when to use it and when to render directly.

### B. Render commands
- Smoke test (fast): `manim -ql file.py Scene`. Output goes to `media/videos/<file>/480p15/`.
- Frame dump for review: `manim -ql --fps 2 --format=png --disable_caching file.py Scene`. Output goes to `media/images/<file>/`; clear old PNGs first.
- Last frame only: `manim -s -ql file.py Scene`. Fine for static layouts, but it misses mid-transition problems.
- Partial: `-n 3,7` renders animations 3-7 only. `--save_sections` with `self.next_section()` for long scenes. `--dry_run` checks the code without writing output.
- Final: `-qh` (1080p60) or `-qk`. Only after the low-quality frames pass review.
- Do not use `-p`: it opens a player window, which is useless to the agent.

### C. Verification loop (mandatory after every non-trivial change)
1. Render at `-ql`. A Python error means fixing it before anything else.
2. Dump frames at 2 fps (more for fast motion). Build a contact sheet: a 4x4 grid made with a small Pillow script in `tools/`.
3. Read the contact sheet, then full-size frames at key transitions and the final frame. Check intermediate frames as well as end states.
4. Check against the post-render checklist: no text-on-text or text-on-shape overlap, nothing clipped at the frame edges, no leftover objects, labels legible at 480p, colors consistent with the palette, nothing important on screen too briefly.
5. Fix, re-render only the affected scene, and repeat. Report what you looked at. Don't claim "fixed" without re-viewing the frame.
6. When the user cites a timestamp, extract that frame (`ffmpeg -ss T -i video.mp4 -frames:v 1 f.png`) and view it first.

### D. Layout conventions
- Frame is about 14.2 × 8 units. Keep content within |x|≤6.5 and |y|≤3.5. Treat absolute coordinates beyond about x=5.5 or y=3.2 as suspect.
- Named regions (define them in `style.py`): title band at the top, main area, optional left/right panels, captions/notes band at the bottom.
- Use `arrange`, `arrange_in_grid`, `next_to` and `align_to`, not hand-computed coordinates (3b1b rule). Build groups declaratively.
- Use `scale_to_fit_width` / a `safe_text()` helper for any text that could be long. Manim doesn't wrap, so break lines manually.
- A region is cleared (FadeOut) before new content uses it. Dim elements that stay beside new content; FadeOut elements that would sit under it.
- Minimum font size about 20 at 1080p. Edge buff ≥0.5. For an anchor near the frame edge, place annotations below it rather than beside it.

### E. ManimCE gotchas (short list)
- `MathTex` is already math mode (no `$`). `Tex` is text mode. Always use raw strings.
- Chained transforms: use `ReplacementTransform`, or remember that `Transform` keeps the original object.
- `.animate` belongs only inside `self.play()`. Chain order matters.
- To color parts of an equation, use `substrings_to_isolate` or `{{ }}` and `set_color_by_tex`. `index_labels()` helps when debugging.
- Use `TransformMatchingTex` / `TransformMatchingShapes` for derivations.
- `manim.cfg` uses only the `[CLI]` section for render settings.
- Transparency needs `--format webm -t` (mp4 has no alpha).
- Use `MovingCameraScene` + `self.camera.frame` for zoom and pan.

### F. Project structure and style
- One file per video or section. One `Scene` class per beat, with descriptive names like `S01_Hook`.
- Shared `style.py`: palette (color = meaning, used consistently), font sizes, region constants, helpers.
- Constants at the top of the file. Optionally a `scenes.md` plan per video: hook, key insight, per-scene purpose, duration, visuals, narration notes (composer idea).
- Explicit `run_time` on any `play()` that matters, and `self.wait()` after key reveals. Default pacing tends to be too fast.

### G. Narration (only if used)
- Option 1: manim-voiceover with `VoiceoverScene`, starting with `pyttsx3` or `gTTS` for drafts. Needs ffmpeg, plus SoX for speed changes.
- Option 2: narration-first (Yusuke710 pattern). Write the script, generate TTS outside Manim, budget each segment's `run_time`/`wait` to the measured duration, use `add_subcaption()` for `.srt`, mux with ffmpeg.

### H. Don'ts
- Don't install packages or change the venv without asking.
- Don't delete `media/` wholesale. Clear only that scene's frame folder.
- Don't render `-qh` or `-qk` until the `-ql` frames are approved.

---

## Sources

- https://github.com/adithya-s-k/manim_skill
- https://github.com/3b1b/videos/blob/master/CLAUDE.md
- https://github.com/abhiemj/manim-mcp-server
- https://github.com/paulnegz/manim-mcp
- https://pypi.org/project/manim-claude/
- https://github.com/AmitSubhash/3brown1blue
- https://pypi.org/project/llmanim/
- https://github.com/DominikPeters/manim-skill
- https://github.com/Yusuke710/manim-skill
- https://github.com/ManimCommunity/manim-voiceover
- https://voiceover.manim.community
- https://github.com/davila7/claude-code-templates
- https://github.com/affaan-m/ECC
- https://sola-fide-web.pages.dev/blog/creating-math-animations-with-claude-and-manim-part-2
- https://arxiv.org/abs/2605.15585
- Local check: `.venv/Lib/site-packages/manim/_config/default.cfg` and `cli/render/*.py` (0.22.1) for config sections and CLI flags.
