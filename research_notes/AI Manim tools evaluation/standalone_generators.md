# Standalone AI "text/math -> Manim video" generators: evaluation

Researched 2026-11-14. Nothing was installed or run. Sources: GitHub READMEs, source and issues (pulled via `gh`), arXiv papers, and third-party pages for the commercial tools.
Context: one user, Claude Code desktop on Windows, Manim Community Edition 0.22.1 in a local venv.

## TL;DR

- **Don't adopt any of these as a runtime.** All the open-source pipelines do the same thing: plan, then generate code, then render, then repair errors, with an optional VLM critique step. Claude Code already does that loop natively and better (interactive, editable, on the user's own files). Each tool adds its own API keys, model lock-in (Codex/GPT-6, Gemini as critic, LiteLLM), Linux-oriented setup and pinned Manim versions (0.19 is common) that conflict with CE 0.22.1.
- **Borrow ideas aggressively.** The papers agree on what moves quality. Ranked by measured effect:
  1. Plan/storyboard before code.
  2. Discrete layout anchors instead of free coordinates.
  3. Render, then inspect frames/geometry, then make a targeted fix.
  4. Error-message-driven repair that widens scope only when needed.
  5. Deterministic geometric checks (bounding boxes) over pure VLM opinions.
- **One "tool-ish" thing worth knowing:** ManimGX (academa-labs/manimgx, MIT, 2.7k stars) has a `manimgx inspect` command. It writes a storyboard PNG plus machine-readable layout errors (off-frame, text collision, small text) with source lines. It is a different engine (Python 3.13+, CE-API-compatible but not identical), so it is not a drop-in for CE 0.22.1. Still, that command is the design to copy as a CE script.

## Repo stats (gh api, 2026-11-14)

| Project | Stars | Last push | License | Lang |
|---|---|---|---|---|
| HarleyCoops/Math-To-Manim | 2,869 | 2026-11-13 | MIT | Python |
| showlab/Code2Video | 2,389 | 2026-08-24 | MIT | Python |
| TIGER-AI-Lab/TheoremExplainAgent | 1,514 | 2025-07-27 (stale) | MIT | Python |
| marcelo-earth/generative-manim | 943 | 2026-09-17 | Apache-2.0 | Python |
| Wing900/ManimCat | 502 | 2026-11-11 | AGPL-3.0 | TypeScript |
| HyperCluster-Tech/manimator | 75 | 2025-02-14 (stale) | MIT | Python |
| academa-labs/manimgx (engine behind studio.academa.ai / ManimCat) | 2,736 | 2026-11-09 | MIT (wheels GPL-3 due to x264) | Rust/Python |
| f20220374/PhysicsSolutionAgent | 0 | 2026-01-26 | none | - |

(Note: TheoremExplainAgent's real org is `TIGER-AI-Lab`. A second "ManimCat", xjtai/ManimCat, is a 1-star fork.)

---

## Open-source pipelines

### Math-To-Manim (HarleyCoops)
- **What it is now:** a sprawling multi-provider "film" lab, not a simple tool. It has several silos:
  - **Astra** (default `math-to-manim` command): GPT-6 Astra via the Codex SDK, with optional gating by "Jev", a TypeSafe judge API.
  - **Mythos**: a six-stage chain on the Claude Agent SDK (default `M2M_MODEL=claude-fable-5-2`), plus an MCP server.
  - **Studio**: Claude Agent SDK plus Blender EEVEE and Manim.
  - Argon (Google ADK), Grok, GLM, MiMo, Sol pipelines.
  - Legacy: a Claude Code plugin/skill ("Reverse Knowledge Tree": recursively ask what the viewer must understand first, then enrich the math, then visual design, then a long "verbose prompt", then code).
- **Architecture (Mythos):**
  - Six JSON-producing stages: intent, then cartographer (knowledge map), curriculum, math-director (dossier), cinematographer (shot list) and scene-composer (scene spec).
  - Then codegen, then `verify` (static checks), then render. Failures go to `repair` (rewrites the whole file, at most 3 rounds).
  - Astra adds a "final-frame execution probe" plus frame extraction. The model inspects sampled frames and writes text observations, and a judge routes each defect to the math, storyboard or code stage.
  - Runs are fully manifested (hashes, logs, contact sheets).
- **Claude support:** yes (Mythos/Studio use the Claude Agent SDK; the legacy skill targets Claude Code). The primary path is OpenAI Codex, though.
- **CE vs GL:** CE. The pyproject pins vary by extra: `manim>=0.19,<0.20` in one and `manim>=0.22,<0.23` in another.
- **Windows:** the README documents MiKTeX/FFmpeg PATH setup. It needs Node 18+, npm, Codex login and possibly a TypeSafe key. The author's own README notes a Windows "access denied" failure on Codex startup.
- **Quality evidence:**
  - Showcase films are impressive (10-min Aaronson–Ambainis film, 964-line ThreeDScene made by Claude Opus 5.5).
  - But they start from heavily written human briefs (exact formulas, palette, nine scenes).
  - The README admits the Studio films had no critic: spin arrows touch, objects enter the caption band, no narration or audio.
  - Issue #31: a user found results "very poor" for a 2–3 min Euler-characteristic video, with the biggest problem being that output can't be edited.
  - Issue #34: the advertised Claude skill didn't exist at that path.
- **Steal:**
  - Stage artifacts as typed JSON files (intent, then knowledge map, then shot list, then scene spec) persisted to disk.
  - Explicit outcome states (`render_failed` vs `scene_ready`).
  - Contact sheets of N frames for review.
  - Route defects back to the earliest responsible stage (math, storyboard or code).
  - Don't spend model repair calls on environment errors (missing `latex`/`dvisvgm`).
  - The "prerequisite tree" planning idea.
- **Verdict: borrow ideas.** Too much moving machinery and provider churn to adopt.

### Code2Video (showlab, NUS; ICML 2026)
- **Architecture:** a tri-agent pipeline.
  - **Planner:** topic, then outline, then storyboard (lecture lines plus paired animations), plus asset retrieval (IconFinder icons and reference images, cached).
  - **Coder:** writes each section in parallel, with **ScopeRefine** debugging. It escalates from the error line ±1 to the enclosing block to regenerating the section.
  - **Critic:** a VLM (Gemini 2.5 Pro) watches the *rendered section video* plus a grid reference image. It returns JSON with up to 3 problems, each with a line number, the affected object and a fix expressed as a grid call.
- **Visual Anchor System:**
  - Lecture text sits on the left. The right side is a **6×6 grid A1–F6**.
  - The code may only use `self.place_at_grid(obj,'B2',scale_factor)` or `self.place_in_area(obj,'A1','C3',scale)`. The prompt says "NEVER use .to_edge(), .move_to()".
  - Labels must sit within 1 cell of their object.
  - An occupancy table (element to cells, scale, code lines) lets the critic find free cells.
- **LLMs:** the README says the best code comes from Claude-4-Opus. The paper's best result was Claude Opus 4.1 (aesthetics 87.9, TeachQuiz 86.0, vs direct one-shot Claude codegen at 37.8 / 40.0). Gemini is required for the critic, since it takes video input.
- **TTS:** none in the pipeline. An issue asks how sound was added to the dataset videos.
- **CE vs GL:** CE v0.19.0.
- **Windows:** `.sh` run scripts, `api_config.json` and IconFinder keys (the IconFinder API is no longer obtainable, per an issue). Workable via Git Bash, but friction.
- **Evidence (ablation, GPT-4.1, aesthetics/TeachQuiz):**

  | Configuration | Aesthetics | TeachQuiz |
  |---|---|---|
  | Full pipeline | 79.0 | 82.0 |
  | Without planner | 38.1 | 40.5 |
  | Without asset DB | 68.1 | 52.0 |
  | Without visual anchors | 69.2 | 55.2 |
  | Without critic | 72.5 | 60.7 |

  - A 6×6 grid beat coarser grids, free placement and 8×8 (which added clutter).
  - ScopeRefine vs full-code re-debugging: 15.4 vs 39.2 min, 30.8K vs 42.1K tokens.
  - Limits: about 15 min and 30–50K tokens per 1–2 min video. Human viewers were very sensitive to brief occlusions that the VLM missed. The human study was tiny (6–8 per group).
- **Verdict: borrow ideas** (anchor grid, ScopeRefine, JSON critic format). This is the single most useful paper/repo to copy from.

### TheoremExplainAgent (TIGER-AI-Lab; ACL 2025 oral)
- **Architecture:**
  - A planner agent (scene outline, then per-scene vision storyboard, technical implementation and animation/narration plan).
  - A coding agent with an error-fix loop (N=5).
  - Optional **RAG** over Manim docs (ChromaDB, queried at the storyboard, implementation and error-fix stages, relevance threshold 0.5).
  - Optional `--use_visual_fix_code` (a VLM fixes code from rendered visuals).
  - Optional in-context example code.
  - **TTS:** Kokoro ONNX via manim-voiceover. Multi-scene videos longer than 5 min.
- **LLMs:** any model via LiteLLM, so Claude works.
- **Results (2025 models):** o3-mini had a 93.8% success rate. Claude 3.5 Sonnet had 2.1% (14.6% with RAG). GPT-4o had 55%.
  - RAG was *inconsistent*: it hurt GPT-4o and o3-mini but helped Claude and Gemini, because of irrelevant retrievals.
  - Retries matter hugely (o3-mini: 7% at N=0 vs 93% at N=5).
  - Failure modes:
    - Manim API hallucinations (the majority of failures)
    - LaTeX errors
    - Missing imports and undefined variables
    - Layout overlaps
  - Prompts include "safe area margins and minimum spacing" rules.
- **CE vs GL:** CE.
- **Windows:** poor. It needs `export PYTHONPATH`, portaudio, conda and wget model downloads. Issues are full of "has anyone successfully run it?", `ModuleNotFoundError: src`, missing RAG files, and "combining video+audio takes 30 min". Stale since mid-2025.
- **Verdict: ignore as a tool; borrow ideas.** Take the retry budget, the voiceover-duration-driven timing and the observation that RAG must be targeted (API signature lookups), not generic.

### Generative Manim (marcelo-earth)
- **What it is:** a web demo, an API (Flask/Docker), and Animo (a desktop app using your Claude/ChatGPT subscription). It is basically a curated system prompt across about 25 models (many Claude versions). It also has a research track that fine-tunes 7B models with SFT, then DPO, then GRPO, using the renderer as the reward, plus a render-based benchmark (pass@k).
- **Architecture:** single-shot generation with a custom system prompt. No planner, no visual critic in the core.
- **CE.**
- **Security issues filed in 2026:** `shell=True` command injection, path traversal (now closed).
- **Steal:** "Manim is a deterministic verifier: it renders or it crashes". Use render success as a cheap gate. The linked `manim-awesome-skills` list is tiny (2 stars).
- **Verdict: ignore.** Claude Code with a good CLAUDE.md is strictly better than its system prompt.

### ManimCat (Wing900)
- **What it is:** a TypeScript web app (Express, Redis/Bull, React). Flow: concept designer, then an editable planning card, then a code generator, then render, then a render-failure patch loop.
  - Local MiniLM embeddings retrieve Manim/matplotlib API context.
  - Edge TTS narration with sentence-level cue alignment, plus subtitle burn-in.
  - A canvas for drawing reference images.
  - The "Agent mode" studio (builder, designer and reviewer agents) is still in development.
- **Engine:** **ManimGX** (not CE). Python 3.13/3.14, Typst typesetting.
- **LLM:** any OpenAI-compatible upstream (BYOK).
- **License:** AGPL-3.0.
- **Windows:** rendering is Linux-only (a mandatory bubblewrap sandbox; Docker with a custom seccomp profile).
- **Verdict: ignore** (wrong engine, Linux-only rendering, AGPL). **Borrow:** the editable planning card shown before code, and Edge TTS (free) for narration drafts.

### Manimator (HyperCluster-Tech; ICML 2025 workshop)
- **What it is:** paper PDF or arXiv ID, then an LLM scene description, then a code LLM writes Manim CE, then render. Few-shot prompts, LiteLLM, Gradio/FastAPI, Poetry.
- No visual loop and no TTS. The roadmap still lists "Improved Generation Quality".
- Stale since Feb 2025.
- **Verdict: ignore.** Only idea: "paper to scene description" as a separate step.

---

## Research papers (2026) and what they found

### LLM2Manim (arXiv 2604.05266, Apr 2026)
- A semi-automated, human-in-the-loop pipeline:
  - Constrained templates: scene goals, a **symbol ledger** (notation, units, assumptions), timed narration cues, storyboard frames, and code constraints (layout, timing, *allowed primitives*).
  - Low temperature.
  - Narration and code generated as parallel tracks; only the failing track/scene is regenerated.
  - Pre-render checks: imports and LaTeX, deterministic run, cue/event timing alignment, symbol/unit consistency, goal coverage.
  - Expert review on subject, pedagogy and engineering.
  - A build manifest (model, prompt version, seeds, Manim/LaTeX versions) and regression scenes.
- **Study (N=100 undergrads):** post-test 83.4 vs 78.1 (adjusted) vs PowerPoint, learning gain d=0.67, engagement d=0.94.
- Overlapping labels were still fixed by hand. The LLM isn't named and no repo is public.
- **Steal:** the symbol ledger (one file of notation/colours per video), the allowed-primitive whitelist, the cue-to-animation timing check, and regression scenes when upgrading Manim.

### PhysicsSolutionAgent (arXiv 2601.13453, Jan 2026)
- **Pipeline:** solver (JSON step-by-step solution), then planner (scenes with layout and narration), then coder (ChromaDB RAG over Manim docs plus few-shot examples). Narration uses manim-voiceover with Kokoro.
- **Repair:** run in a subprocess; feed the traceback, code and plan back for up to 5 attempts.
- **Visual critique:** a VLM gets **3 screenshots per scene (start/middle/end)**, scores them on a rubric (layout, readability, equation rendering, off-screen, content alignment) and returns change instructions. This runs once only, for cost.
- **Results (GPT-5-mini):** 100% completion, overall 3.8/5. The visual pass gave only *modest* gains (layout 3.64 to 3.66).
- Human review found the VLM misread frames, and redundant/verbose narration was the top issue.
- Timing: `tracker.duration` ties animation to the TTS length.
- **Steal:**
  - Solve the math first, as a separate artifact, before planning visuals.
  - Sample start/mid/end frames.
  - Score visual quality as the **mean of the two lowest sub-scores**, so the worst defects dominate.
  - Keep narration concise.

### ManimTrainer / ManimAgent (arXiv 2604.18364; NeurIPS 2026)
- SFT plus GRPO on less than 30B open models with code and visual rewards. Inference uses a renderer-feedback loop, with a variant that adds Manim API docs.
- **Best:** Qwen3-Coder-30B + GRPO + docs loop: 94% render success, 85.7% visual similarity (about 3 points above GPT-4.1).
- Proprietary models weren't trained. The relevant takeaway for us: **render-error feedback plus targeted doc lookup** is the inference recipe that works.
- **Verdict:** nothing to adopt.

### OmniManim, "See Before You Code" (arXiv 2605.15585, May 2026)
- **Agents:** four agents (Scene, Vision, Code, Repair) share a *structured scene state*. Per object it records id, type, role, layout box, schedule, code block and verification status.
- **Vision Agent:** a trained model that predicts **normalized bounding boxes at keyframes before code is written**, with a loss that penalises collisions at interpolated times (u=0.25/0.5/0.75).
- **Code Agent:** only maps boxes to Manim coordinates.
- **Repair Agent:** CV diagnostics on rendered frames: HSV masks, IoU of connected components, dilated-pixel overlap, text-line crossing, and 6×8 density grid. Temporal checks cover jitter and flicker; consistency checks cover blank frames.
  - Overlap/overflow goes to Vision, crashes go to Code, temporal issues go to Scene.
- **Key claim:** "natural-language feedback is difficult to translate into precise coordinate adjustments".
- **Results:** beats Code2Video on overlap (OV 0.763 vs 0.598) and layout quality (0.931 vs 0.742). Human study 81.0 vs 68.4. Without the Vision Agent, OV collapses to 0.491.
- Code is "intended" for release, not out. Uses Manim 0.19.0.
- **Steal:**
  - Plan explicit boxes/zones per object per beat *before* coding.
  - Check overlap *mid-transition*, not just at the end states.
  - Route defects by type.

### SGA, Scene-Graph Agent (arXiv 2607.18116, Jul 2026)
- A plug-in between the LLM and Manim:
  - AST-rewrite `construct()` so each statement is wrapped in try/except, then partially execute it **without rendering**.
  - Extract per-mobject records: label type (Text/Geom/Mark/Deco), centroid, width/height, variable name and source line.
  - **Deterministic AABB checks:**
    - overlap area > 0, with severity High above 30% coverage and Medium above 10%
    - off-frame beyond ±W/2, ±H/2
    - minimum legible scale 0.15 units
    - sampled at 11 times per animation; overlaps at t=0/1 count as persistent, mid-animation overlaps as transient
  - Then a localized patch prompt: a ±5-line window around the creation line plus a computed **minimum separation vector (dx, dy)**. The patch is checked by AST parse, with rollback on failure.
- **Cost:** under 5 s per check vs 30–90 s per render for VLM critique.
- **Results (MVQS):**
  - Code2Video/GPT-5.1: raw 62.97, with VLM critic 64.54, **with SGA 73.11**.
  - Improved in 7 of 8 configs. The exception was TheoremExplainAgent + Claude 4.6 Sonnet (63.84 to 62.83).
- 2D only. Code and scoring scripts are on the project page (jhedlp.github.io/projects/sga).
- **Steal:** this is the highest-leverage technique for a Claude Code workflow. A small CE script can do it (see below).

---

## Commercial / hosted

| Tool | What it is | Claude? | Verdict |
|---|---|---|---|
| **Codewords** templates ("Manim Animation Generator", "Educational Manim Video Generator") | No-code workflow templates: Claude writes the narrative, Perplexity the examples, plus "validated" Manim code. Output is a script you render yourself; no voiceover or visual loop described; pricing not shown. | Yes (narrative) | Ignore. Claude Code does this directly. |
| **Anim Lab AI** | Free Hugging Face Space (MCP-1st-Birthday hackathon) using Claude Sonnet to write Manim code and render it on shared HF hardware; also exposes a Gradio MCP endpoint. Silent output, fails on complex scenes / free-tier limits, no visible repo. | Yes | Ignore (a toy; an MCP to it adds nothing over local rendering). |
| **Manim AI** (manimai.vercel.app; Product Hunt May 2025) | Algorithm-to-animation web app; little verifiable detail. Not to be confused with Generative Manim/Animo. | Unknown | Ignore. |
| **studio.academa.ai / ManimGX** | Browser studio (WebGPU) on ManimGX, a Rust/wgpu engine with Manim-CE-compatible API, Typst instead of LaTeX, `self.say()` TTS sync, `manimgx inspect` layout checker. The engine is open (MIT) despite older claims it was closed. Python 3.13+, Windows wheels claimed. Not identical to CE: different imports, `.animate` and timing semantics, LaTeX packages/`\def` unsupported, `MovingCameraScene` merged into `Scene`. | Agent-agnostic (`llms.txt` for Claude Code/Codex/Cursor) | **Watch / borrow.** Don't switch engines mid-project, but `inspect` is the template for our own checker. Consider it for a fresh 3D-heavy project where 90× render speed matters. |

---

## Verdict per tool

| Tool | Verdict |
|---|---|
| Math-To-Manim | Borrow ideas (staged JSON artifacts, contact sheets, defect routing, prerequisite tree) |
| Code2Video | **Borrow ideas** (anchor grid, ScopeRefine, JSON critic format); top source |
| TheoremExplainAgent | Ignore as tool; borrow retry budget and voiceover timing |
| Generative Manim / Animo | Ignore |
| ManimCat | Ignore (ManimGX, Linux-only render, AGPL); borrow the editable plan card |
| Manimator | Ignore |
| LLM2Manim | Borrow (symbol ledger, primitive whitelist, regression scenes, build manifest) |
| PhysicsSolutionAgent | Borrow (solve first, start/mid/end frames, worst-two scoring) |
| ManimTrainer | Ignore (fine-tuning research) |
| OmniManim | Borrow (boxes before code, mid-transition overlap checks, defect routing) |
| SGA | **Borrow: implement this** (render-free bounding-box checker) |
| Codewords, Anim Lab AI, Manim AI | Ignore |
| ManimGX / Academa Studio | Watch; copy the `inspect` design |

## Top techniques to replicate in a Claude Code + ManimCE 0.22.1 workflow

1. **Plan before code, as files.** Removing the planner was the biggest ablation drop in Code2Video (about −41 points on both metrics).
   - Write `plan/<scene>.md` or JSON before any code: learning goal, prerequisites, a solved/checked math dossier, beats with timing, and narration lines.
   - Claude Code should show it for approval (the ManimCat "planning card" idea).
2. **Symbol/style ledger.** One `style.py` / `ledger.md` per video with notation, colours per concept, font sizes and an allowed-primitives whitelist (LLM2Manim). Import constants instead of hard-coding them.
3. **Discrete layout anchors.**
   - Add a helper (`place_at_grid(obj,'B2')`, `place_in_area(obj,'A1','C3')`) on a fixed grid. Code2Video used 6×6 on the right with text on the left.
   - Forbid free `move_to` coordinates for layout.
   - Keep labels within one cell of their object.
   - Without anchors, Code2Video lost about 27 TeachQuiz points.
4. **Render-free geometric lint (SGA-style), as a CE script.**
   - Run `construct()` with animations stubbed (or with `-s`/`--dry_run`).
   - At each `play`/`wait` end, and at a few interpolation points, walk `scene.mobjects` and collect bounding boxes via `get_critical_point`, width and height. Report:
     - pairwise overlaps of Text/MathTex and other objects (with severity)
     - anything outside ±7.11 × ±4 (with a safe margin)
     - text below a minimum height
     - the variable name and source line of each offender
     - a suggested separation vector
   - Exit non-zero on problems. Runs in seconds; SGA beat VLM critique (+10 MVQS vs +1.6) at about 1/6 the per-iteration cost.
5. **Then a visual check on real frames.**
   - Render at `-ql`. Extract frames at the end of each play, or start/mid/end per scene (PSA), and build a contact sheet (Math-To-Manim).
   - Have Claude read the PNGs against a fixed checklist: overlap, occlusion of text, off-screen/long labels, objects that should have faded out, empty regions.
   - Output structured fixes (line, object, concrete new anchor). Cap at about 3 issues and 1–2 rounds.
   - Treat VLM judgment as fallible; papers report it misses brief occlusions and misreads frames. Prefer the deterministic lint for geometry.
6. **Scoped error repair (ScopeRefine).**
   - Feed the traceback and fix the failing line ±1 first, then the enclosing block, and only then regenerate the scene.
   - Budget about 3–5 attempts (TEA: success went from 7% to 93% with 5 retries).
   - Classify environment errors (missing latex/dvisvgm/ffmpeg) separately and don't "fix" code for them.
7. **Targeted docs lookup, not bulk RAG.** RAG over generic Manim docs was inconsistent in TEA. Instead, when an error or uncertainty involves a specific class or kwarg, check the installed CE 0.22.1 source or signature (`inspect.signature`, `help()`) before writing it. API hallucination is the #1 failure mode.
8. **Narration-driven timing.** If voiceover is wanted, use manim-voiceover (Kokoro or Edge TTS, which are free) and tie `run_time` to `tracker.duration`. Keep narration concise; redundant narration was PSA's top complaint.
9. **Per-section rendering plus concat.** Render scenes/sections independently (and in parallel where possible), then join them with ffmpeg concat. Parallelism cut Code2Video's wall time 5.6×.
10. **Run manifest and regression scenes.** Record the Manim version, prompt/plan version and outcome per render. Keep a few golden scenes to re-render and diff after upgrading Manim (LLM2Manim, Math-To-Manim).
11. **Defect routing.** When a check fails, decide whether it is a math error (fix the dossier), a storyboard/layout error (fix the plan or anchors) or a code error (fix the code). Don't patch layout symptoms in code when the plan is overcrowded (OmniManim, Math-To-Manim Astra).

## Sources
- https://github.com/HarleyCoops/Math-To-Manim (README; issues #31, #34; legacy SKILL.md)
- https://github.com/showlab/Code2Video (README, prompts/stage3.py, prompts/stage4.py, src/agent.py); https://arxiv.org/abs/2510.01174
- https://github.com/TIGER-AI-Lab/TheoremExplainAgent ; https://arxiv.org/abs/2502.19400
- https://github.com/marcelo-earth/generative-manim
- https://github.com/Wing900/ManimCat
- https://github.com/HyperCluster-Tech/manimator ; https://arxiv.org/abs/2507.14306
- https://arxiv.org/abs/2604.05266 (LLM2Manim)
- https://arxiv.org/abs/2601.13453 (PhysicsSolutionAgent)
- https://arxiv.org/abs/2604.18364 (ManimTrainer)
- https://arxiv.org/abs/2605.15585 (OmniManim)
- https://arxiv.org/abs/2607.18116 (SGA)
- https://github.com/academa-labs/manimgx ; https://manimgx.academa.ai/user-guide/rendering/ ; https://manimgx.academa.ai/user-guide/coming-from-manim-ce/
- https://www.codewords.ai/templates/educational-manim-video-generator
- https://www.scriptbyai.com/math-educational-video (Anim Lab AI)
- https://www.trendhunter.com/trends/manim-ai
