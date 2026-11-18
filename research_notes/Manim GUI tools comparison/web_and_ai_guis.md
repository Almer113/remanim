# Browser-based / online GUIs for Manim and AI tools that wrap Manim in a GUI (state as of 2026-11-18)

Scope: web front-ends and playgrounds, plus AI products/apps with a GUI. Desktop drag-and-drop editors and IDE/notebook extensions are excluded (covered elsewhere). Background on the open-source AI pipelines (architecture, papers, quality) is already in `research_notes/AI Manim tools evaluation/standalone_generators.md`; this file covers what is new or GUI-specific. Nothing was installed or run. Pages were read via fetch, so "not mentioned" means the fetched page did not say, not that the feature is absent.

GitHub stats pulled with `gh api` on 2026-11-18:

| Repo | Stars | Last push | Licence |
|---|---|---|---|
| academa-labs/manimgx (engine of Academa Studio) | 2,796 | 2026-11-16 | MIT |
| marcelo-earth/generative-manim | 941 | 2026-09-17 | Apache-2.0 |
| maloyan/manim-web (TypeScript port) | 519 | 2026-11-15 | MIT |
| Wing900/ManimCat | 505 | 2026-11-11 | AGPL-3.0 |
| rohitg00/manim-video-generator | 312 | 2026-01-29 | MIT |
| HyperCluster-Tech/manimator | 75 | 2025-02-14 (stale) | MIT |
| ManimCommunity/jupyter_examples (Binder notebooks) | 26 | 2026-11-03 | MIT |
| christopher-besch/manim_web_presenter | 11 | 2021-11-18 (archived) | MIT |
| birol-dev/Manim-Fullstack ("Manim Studio"/"Manim Composer") | 0 | 2026-11-13 | MIT |
| pushpitkamboj/AnimAI | 0 | 2026-06-09 | Apache-2.0 |
| ManimCommunity/manim-editor | repo not found (404) via gh api | - | - |

## Which online Manim editors/playgrounds exist and work today? Can Manim run client-side in the browser yet, or do they all render server-side?

### Takeaway
Real Manim CE still does not run client-side in a browser: no Pyodide/JupyterLite build of CE was found (Cairo/Pango native deps are the blocker), so every "real CE" online option renders on a server (Binder, HF Spaces, a vendor backend) or on your own machine behind a browser UI. The two things that do run client-side are re-implementations: Academa Studio (Rust/WebGPU engine compiled to WASM, loaded into Pyodide; "ManimGX"-family, closed product but MIT engine) and manim-web (a TypeScript port with a py2ts converter). Neither runs CE 0.22 code unchanged.

### Cited Findings
**Official / community playground**
- `try.manim.community` is a redirect stub that sends you to a Binder (mybinder.org) notebook "First Steps with Manim.ipynb" from ManimCommunity/jupyter_examples; i.e. server-side Jupyter, not in-browser execution. Version and limits are not stated on the page — [try.manim.community](https://try.manim.community/); repo last pushed 2026-11-03 (gh api).

**Academa Studio (studio.academa.ai), client-side via WebGPU**
- Show HN: the team reimplemented Manim's Python API on a Rust core using wgpu, compiled to WebAssembly and loaded into Pyodide as a PyO3 extension, so rendering runs client-side on the GPU; Monaco editor with live preview; built-in AI agent — [HN thread](https://hn.svelte.dev/item/49091703)
- The live page shows the in-browser boot sequence: loading a Python runtime, installing "manimx and dependencies", warming up the renderer; panes are code editor, AI chat and preview, sign-in via Google/GitHub — [studio.academa.ai](https://studio.academa.ai/)
- Launched publicly on 2026-07-29 per a third-party review, described as an "AI-native Manim editor" — [zeli.app / kompozy summaries via search](https://zeli.app/story/49091703), [kompozy](https://kompozy.io/reviews/manim-webgpu)
- Goal stated by developers is 1:1 API compatibility with Manim CE; a commenter argued it is only partly compatible. The product was described in the thread as closed source, and the developers said the engine is their own work, not a fork of Manim — [HN thread](https://hn.svelte.dev/item/49091703). Note: the engine repo academa-labs/manimgx is MIT on GitHub (2,796 stars, pushed 2026-11-16), so "closed" applies to the Studio web app, not the engine (gh api; and earlier notes).
- Known CE differences (from earlier notes): different imports, `.animate` and timing semantics, Typst instead of LaTeX, LaTeX packages/`\def` unsupported, `MovingCameraScene` merged into `Scene` — [ManimGX "coming from CE" guide](https://manimgx.academa.ai/user-guide/coming-from-manim-ce/)
- HN users reported: no WebGPU on Safari (no error shown), WebGPU error on Windows-on-ARM, laggy intro on Chrome, unclear UI with no obvious Run/Render button; critics objected to the branding implying a 3Blue1Brown link — [HN thread](https://hn.svelte.dev/item/49091703)

**manim-web (maloyan), TypeScript port, client-side**
- "Manim in the browser. No Python." A TypeScript port; includes `tools/py2ts.cjs` to convert Python Manim scripts to TS; claims 429/429 "feasible" ManimCE 0.22.0 public symbols ported (see PARITY.md); LaTeX via KaTeX ("large but incomplete subset"), opt-in Typst via WASM; GIF/MP4/WebM export; React/Vue/web-component embeds; MIT; 519 stars, 1,202 commits — [GitHub](https://github.com/maloyan/manim-web); docs/playground at [maloyan.github.io/manim-web](https://maloyan.github.io/manim-web/)
- Show HN (roughly early 2026): Canvas/WebGL (Three.js for 3D), MathJax/KaTeX; author said parity still in progress and that the code was "100% generated by the agent"; users reported flicker, fuzzy text, broken 3D lighting — [HN thread](https://hn.svelte.dev/item/47155375)
- A separate PyPI package also named `manim-web` is loaded into Pyodide with `micropip.install("manim-web")` from an HTML page — [PyPI manim-web](https://pypi.org/project/manim-web/) (relationship to the TS repo not verified)

**Manim Studio / "Manim Composer" (birol-dev/Manim-Fullstack), local server + browser UI**
- Describes itself as a free, open-source, local studio "built on Manim Community"; no account; projects stay on your computer. Author mode: Python scene editor, live render progress, **timeline**, render comparison, asset library; template videos, batch creation from CSV/XLSX (up to 200 variations), MP4/GIF/WebM/MOV/PNG export; MCP so AI clients can edit projects, inspect storyboards and queue exports; Windows desktop packages; source build needs Python 3.11+, Node 20.19+ — [llms.txt](https://manim-fullstack.pages.dev/llms.txt), [site](https://manim-fullstack.pages.dev/)
- An earlier description (search snippet of the same site) called it "Manim Composer / Manim GUI": FastAPI backend, React/Vite frontend, Monaco editor, KaTeX sandbox, AST-based scene discovery, WebSocket render logs, Manim CE subprocesses, Python 3.9+ — [search snippet of manim-fullstack.pages.dev](https://manim-fullstack.pages.dev/). The two descriptions conflict on Python version and positioning; it appears to have been rebranded and widened toward template videos.
- Repo: MIT, 0 stars, last push 2026-11-13 (gh api) — very early/obscure.

**Others**
- manim_web_presenter (christopher-besch): web presenter for rendered Manim, archived since 2021 — dead (gh api).
- Hugging Face Spaces exist that render Manim server-side (e.g. euler314/manim_builder, community TheoremExplainAgent clones); one TheoremExplainAgent Space snapshot showed "Runtime error" and the menamiai variant runs a simulated demo mode by default because HF Spaces lacks system libraries — [HF search results](https://huggingface.co/spaces/ManojINaik/menamiai/blob/main/huggingface_app.py), [manim_builder](https://huggingface.co/spaces/euler314/manim_builder/blob/0ef6cca5f60145eb42c8051e9559931e2f08d52f/app.py)
- Generic Pyodide constraint: packages need a wheel; JupyterLite fails with "Can't find a pure Python 3 wheel" for native packages; pycairo builds fail even on Colab in some trackers — [JupyterLite/VTK issue](https://gitlab.kitware.com/vtk/vtk/-/issues/18806), [jupyter-manim issues](https://issues.ecosyste.ms/hosts/GitHub/repositories/krassowski%2Fjupyter-manim/issues)

### Inferences
- For a CE 0.22.1 project the only zero-change online option is a server-side notebook (Binder/Colab/HF Space) running real CE. The client-side options require porting (manim-web via py2ts) or an engine switch (ManimGX).
- Manim Studio/Composer is the only browser UI found that drives real Manim CE with a timeline, but it is local-first, brand new and unproven (0 stars); it overlaps with "desktop editors" since it ships Windows packages.
- The project's own `preview_server.py` (browser-pane live preview) already covers the "browser front-end over local CE" niche.

### Gaps
- No evidence either way of an official Manim Community JupyterLite/Pyodide build; I found no issue or doc announcing one, so "not possible yet" is inferred from absence plus the Cairo/Pango dependency.
- Manim CE version used in the Binder notebooks not checked.
- manim-editor (ManimCommunity) repo returned 404; its status (presenter tool, docs.editor.manim.community) not re-verified.
- Did not test whether Academa Studio's free tier allows rendering without sign-in.

## Which AI tools have a real GUI beyond a chat box (scene list, timeline, visual tweaks, re-render of a single scene)?

### Takeaway
Very few. Most AI Manim products are "prompt → code → video" with at best a code pane. The richer GUIs are: AnimG (spec → approve → code → video stages plus a code playground), ManimCat (editable planning card, stage-timing panel, per-scene agent conversations, still in development), Academa Studio (chat + full code editor + live preview), and Animo (desktop: chat, live preview, slides, templates, 3D view). No product found offers a true visual/drag editor or a timeline for AI-generated Manim; Manim Studio (above) has a timeline but its AI comes only via MCP from an external client.

### Cited Findings
- **AnimG (animg.app, VoyCrew Studio)**: prompt box with subject and model selector (example shows Claude Sonnet); workflow stages Spec → Approve → Process → Done with Spec/Code/Video views; "My Animations" library; a browser Playground to write, compile and render Manim code; MP4 output; no timeline or visual editing mentioned — [animg.app](https://animg.app/en). Pricing per search result: free tier of 2 animations, Pro $9.99/month — [animg.app search snippet](https://animg.app/en)
- **AnimoX (animox.ai)**: sells "narrated explainer videos" that are "editable", with a desktop app and local rendering; plans Free (200 one-time credits ≈ 1 narrated video), Starter $10/mo, Pro $20/mo, Team $40/mo (prices shown as annual-billing equivalents; yearly saves 50%), Lifetime listed without details; editor/timeline/code export not described — [animox.ai/pricing](https://animox.ai/pricing). Search structured data gave different prices (Starter $20, Pro $40, Team $80, Lifetime $1,999), so treat prices as unstable — [search snippet](https://animox.ai/pricing)
- **Animo (animo.video, from the Generative Manim author)**: desktop app (Mac/Windows/Linux), not web; chat panel, live video preview, Slides, templates library, interactive 3D view of final objects; exports MP4, GIF, PNG sequences in 16:9/9:16/1:1; one-time $29 lifetime licence, uses your existing ChatGPT/Claude/OpenCode/Antigravity CLI subscription, or AI credits $15/mo after free credits — [animo.video](https://animo.video/); "turns plain English descriptions into animated videos", renders locally, code is yours to export and version-control — [generative-manim README](https://github.com/marcelo-earth/generative-manim)
- **Generative Manim web demo (generative-manim.vercel.app)**: prompt box + model selector, Generate, code area, Render Video, video panel, tabs (Generate Video, Render Engine, Prompt Generator), project/version history with sign-in; free models GPT-4o, fine-tuned GPT-3.5, DeepSeek R1; Claude models marked "Upgrade Required" — [generative-manim.vercel.app](https://generative-manim.vercel.app/). Repo last push 2026-09-17 (gh api).
- **ManimCat (Wing900)**: natural language → editable planning card → Manim code → render; workflow mode can re-render from existing code; Agent mode with per-scene conversations still in development; stage-timing panel; downloads with burned-in subtitles; hosted at manimcat.5051001.xyz; deploy via Docker image `wingflow/manimcat`, HF Spaces (browser-only mode if no user namespaces); local rendering needs Linux + bubblewrap; engine ManimGX 0.1.1 — [GitHub](https://github.com/Wing900/ManimCat)
- **Academa Studio**: AI chat panel with suggested prompts, Manim code editor with render-error status, live preview, "New video"/example videos; no timeline or scene list mentioned — [studio.academa.ai](https://studio.academa.ai/), [HN](https://hn.svelte.dev/item/49091703)
- **Scholarly.so** "AI Math Animation Generator": part of a study-tool platform; Free = one lifetime AI creation at 720p, fixed 2-min length; Premium $30/mo or $144/yr (10 creations/week); Laureate $99/mo (80/week) — [scholarly.so](https://scholarly.so/tools/manim-math-animation-generator) (from search summary; page not fetched)
- **Simple OSS web UIs** (prompt → code → video, no editor features beyond code view): rohitg00/manim-video-generator (web UI, code access, video/GIF download, MIT, 312 stars, last push 2026-01-29); AnimAI (LangGraph agents + RAG + optional HTTP API, 0 stars, last push 2026-06-09); AniMath (Gemini); yashksaini-coder/manim-ai (Clerk auth, OpenAI/Groq) — [search results](https://github.com/yashksaini-coder/manim-ai), [AnimAI](https://gh.r-mj.com/pushpitkamboj/AnimAI); gh api stats
- **Manimator**: Gradio app + HF Space (HyperCluster/manimator), paper/arXiv → scene → CE code; repo stale since 2025-02-14 — [HF Space README](https://huggingface.co/spaces/HyperCluster/manimator/blob/6f1a9775ad8b5861c869dda32857096cd5a3b541/README.md); gh api
- **TheoremExplainAgent**: no official live demo found; only community HF Spaces, one in "Runtime error", one in simulated demo mode — [HF](https://huggingface.co/spaces/ManojINaik/menamiai/blob/main/huggingface_app.py)
- **Anim Lab AI** (HF Space, Claude Sonnet, Gradio MCP endpoint) and **Manim AI** (manimai.vercel.app) — covered in earlier notes as toys / unverifiable.

### Inferences
- "Approve the plan before code" (AnimG's Spec→Approve, ManimCat's planning card) is the main GUI idea the market has converged on; it matches this project's `plans/<video>.md` + user-OK step.
- None of the AI tools has a timeline, per-object visual tweaking, or a "re-render scene 3 only" control documented. Claude Code in this project (one Scene class per beat, `frames.py`, re-render one scene) already exceeds them on granular control.

### Gaps
- AnimG, AnimoX and Animo were assessed from marketing pages only; actual UI depth (e.g. whether AnimoX "editable" means code or a visual editor) not verified.
- No Product Hunt / Reddit user reviews were gathered for AnimG, AnimoX or Scholarly due to the call budget.
- Whether AnimoX and Animo are related (similar names, both desktop + credits) is unclear; I found no source linking them.

## Which AI tools output clean, editable Manim CE code that could be dropped into an existing CE 0.22 project, and which lock you into their platform?

### Takeaway
Code you can take away and run on CE: Generative Manim web demo / Animo (CE code, exportable), AnimG playground (code visible/editable, edition unstated), rohitg00 / Manimator / TheoremExplainAgent (CE, but older pins like 0.19). Engine lock-in: Academa Studio and ManimCat produce ManimGX code (CE-like API, not identical; Typst, not LaTeX). manim-web produces TypeScript. AnimoX and Scholarly sell videos and do not document code export.

### Cited Findings
- Generative Manim/Animo: generated Manim code "is yours to export, version-control, and reuse"; links to manim.community — [GitHub](https://github.com/marcelo-earth/generative-manim)
- AnimG: review the generated plan, then edit the Manim code in the Playground; edition (CE/GL) and export of code not stated — [animg.app](https://animg.app/en)
- Academa Studio installs "manimx" in the browser; engine aims at but does not fully match CE API — [studio.academa.ai](https://studio.academa.ai/), [HN](https://hn.svelte.dev/item/49091703), [ManimGX CE guide](https://manimgx.academa.ai/user-guide/coming-from-manim-ce/)
- ManimCat: engine ManimGX 0.1.1; CE never mentioned — [GitHub](https://github.com/Wing900/ManimCat)
- manim-web: TypeScript; py2ts converts Python → TS (one-way) — [GitHub](https://github.com/maloyan/manim-web)
- AnimoX: "editable" videos, export always free; no mention of code export or Manim edition — [animox.ai/pricing](https://animox.ai/pricing)
- Earlier notes: Manimator, TheoremExplainAgent, Code2Video target CE (0.19 pins common) — `standalone_generators.md`

### Inferences
- For dropping code into this CE 0.22.1 project, generated output from any of these still needs the project's `style.py`/`place()` conventions and check loop; none of them know the house style, so the practical value is low versus generating with Claude Code in-repo.
- Platform lock-in is mainly engine lock-in (ManimGX) rather than file lock-in; ManimGX code is close to CE but would need porting (imports, timing, LaTeX → Typst).

### Gaps
- Did not test any tool's actual output against CE 0.22.1.
- AnimG's Manim edition and whether a code download exists are unknown.

## Privacy/data handling and cost for the hosted ones

### Takeaway
None of the hosted products' fetched pages summarise data handling; all only link to privacy policies, and all send prompts to third-party LLMs. Cost ranges from free/BYO-subscription (Animo $29 one-time, Academa editor/render free) to $10–$100/month subscriptions. Self-hosted/local options (Manim Studio, ManimCat, Generative Manim API) keep data local except the LLM call.

### Cited Findings
| Tool | Hosting | Price | Privacy info found |
|---|---|---|---|
| Academa Studio | Hosted UI, rendering client-side (WebGPU) | Free: chat with weekly AI limits; editor, render and video download free. Plus $20/mo (7-day trial), Pro $100/mo; paid: unlimited videos + cloud storage, export any resolution/fps — [pricing](https://studio.academa.ai/pricing), [HN](https://hn.svelte.dev/item/49091703) | Policy link only; Google/GitHub sign-in; cloud storage of videos — [site](https://studio.academa.ai/) |
| AnimG | Hosted (VoyCrew Studio) | Free 2 animations; Pro $9.99/mo (search snippet) — [animg.app](https://animg.app/en) | Privacy/Terms/Refund links only |
| AnimoX | Desktop app + credits, local rendering | Free 200 credits; $10/$20/$40 per month (annual) — [pricing](https://animox.ai/pricing); conflicting snippet $20/$40/$80, Lifetime $1,999 | Privacy/Cookie links only |
| Animo | Desktop, local render | $29 one-time; uses your own ChatGPT/Claude CLI subscription or $15/mo credits — [animo.video](https://animo.video/) | Privacy link only |
| Generative Manim demo | Hosted (Vercel) | Free models; Claude models "Upgrade Required" — [demo](https://generative-manim.vercel.app/) | Policy link only; API self-hostable (Apache-2.0, Docker) — [GitHub](https://github.com/marcelo-earth/generative-manim) |
| Scholarly.so | Hosted | Free 1 creation; $30/mo or $144/yr; $99/mo — [scholarly.so](https://scholarly.so/tools/manim-math-animation-generator) | Not checked |
| ManimCat | Self-host (Docker/HF) or public instance | Free, BYOK OpenAI-compatible API | AGPL-3.0; local — [GitHub](https://github.com/Wing900/ManimCat) |
| Manim Studio / Composer | Local | Free (MIT) | Data stays local; data sent to AI depends on the MCP client — [llms.txt](https://manim-fullstack.pages.dev/llms.txt) |
| Binder (try.manim.community) | Hosted, ephemeral | Free | Public Binder infrastructure — [try.manim.community](https://try.manim.community/) |

- Earlier security note: Generative Manim API had `shell=True` command injection and path traversal reports in 2026 (path traversal closed) — `standalone_generators.md`, [GitHub](https://github.com/marcelo-earth/generative-manim)

### Inferences
- Academa is the only hosted tool where rendering happens on the user's GPU, so only prompts/code (for AI) and stored videos go to the vendor; everything else renders server-side or locally.
- For this user (Claude subscription, local CE), Animo is the cheapest commercial GUI, but it would duplicate what Claude Code already does here.

### Gaps
- Privacy policies were not read in full for any vendor; retention, training-on-data and LLM sub-processors are unknown.
- Company status (funding, team size) for AnimG/VoyCrew, AnimoX, Academa not researched; none appears shut down as of this check (all sites loaded). Dead/stale: manim_web_presenter (archived 2021), Manimator (stale since Feb 2025), TheoremExplainAgent (no official demo, stale mid-2025), community TEA HF Space (runtime error).
