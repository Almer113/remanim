# Programmatic / Code-Based Alternatives to Manim (as of Nov 2026)

Research note scope: code-first tools for math/science/explainer animation, compared with Manim (ManimCE / ManimGL). Budget-limited pass (~20 tool calls). Items marked **[background, unverified this session]** come from the researcher's prior knowledge (cutoff mid-2026) and were NOT confirmed with a live source here. The report writer should treat them as lower confidence or omit them.

## Q1. Catalog: language, paradigm, strengths/weaknesses vs Manim, maturity, licensing, notable users

### Takeaway
The only close, mature peer to Manim for code-first explainer video is Motion Canvas (TypeScript), with its forks Canvas Commons (community-maintained) and Revideo (now the engine behind a commercial AI product, Midrender). Remotion is the most-adopted code-to-video tool overall but is React/DOM-based, source-available, and paid for companies above 3 people. Rust (Ranim) and browser/TS Manim ports are the main 2025-2026 newcomers; most are early-stage or closed-source.

### Cited Findings

**Motion Canvas (TypeScript, generator-function procedural animation + browser editor)**
- TypeScript library with a built-in animation editor/timeline; can also be used for interactive blog posts and embedded animations — [LibHunt comparison](https://www.libhunt.com/compare-ManimCommunity--manim-vs-motion-canvas)
- GitHub repo shows ~19.8k stars, MIT license, 955 commits, no archive notice and no maintenance warning in README — [GitHub motion-canvas/motion-canvas](https://github.com/motion-canvas/motion-canvas) (fetched Nov 2026)
- Latest version found in changelogs: 3.17.2 (2024-12-14); repo last push 2025-02-16 per an index snapshot — [Yarn changelog @motion-canvas/ui](https://classic.yarnpkg.com/en/package/@motion-canvas/ui); [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fmotion-canvas%2Fmotion-canvas)
- Newest blog release notes found = 3.16.0 (added Camera node); "version 4" only appears as a forward-looking deprecation note in 3.9.0 notes. No v4 release found — [motioncanvas.io blog v3.16.0](https://motioncanvas.io/blog/version-3.16.0); [v3.9.0](https://motioncanvas.io/blog/version-3.9.0)
- Maintainer aarthificial proposed relicensing MIT -> GPLv3 (Mar 29, 2024); postponed "indefinitely" (Apr 4, 2024) after contributor/plugin-author pushback. Maintainer stated he "still write[s] 99% of Motion Canvas" (single-maintainer risk); planned to drop motion-canvas-player in v4 in favor of a Lottie exporter — [GitHub discussion #1015](https://github.com/orgs/motion-canvas/discussions/1015)
- vs Remotion: draws to a single canvas (not DOM), generator-based; can render in the browser; open source — [Remotion docs: compare/motion-canvas](https://www.remotion.dev/docs/compare/motion-canvas) (vendor-written)
- Weaknesses per a 2026 comparison: no arbitrary HTML/CSS, no server/batch rendering, no player component, no REST API; outputs image sequence / MP4; audio supported — [PkgPulse 2026 guide](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)
- npm ~8K weekly downloads (@motion-canvas/core, Mar 2026 avg) — [PkgPulse](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)
- Stars: ~18.5k Motion Canvas vs ~36k Manim; LibHunt says motion-canvas "last updated over 1 year ago", Manim 6 months ago — [LibHunt](https://www.libhunt.com/compare-ManimCommunity--manim-vs-motion-canvas)

**Canvas Commons (TypeScript fork of Motion Canvas)**
- Described as "the actively-maintained community fork"; same API, only imports change (`@canvas-commons/2d`, `@canvas-commons/core`); a Manim-to-Motion-Canvas blogger migrated his tutorial series to it — [slama.dev Motion Canvas series](https://slama.dev/motion-canvas/2/)
- Recommended on HN as the active fork, docs at canvascommons.io — [HN thread 47155375](https://hn.svelte.dev/item/47155375)
- Not to be confused with `@hhenrichsen/canvas-commons`, a component add-on library (Scrollable, FileTree) — [GitHub hhenrichsen/canvas-commons](https://github.com/hhenrichsen/canvas-commons)

**Revideo (TypeScript, fork of Motion Canvas; programmatic/templated video)**
- Docs state Revideo was forked from Motion Canvas — [Revideo docs](https://docs.re.video/designing-animations)
- README describes it as MIT-licensed engine behind Midrender — [Revideo README (jsDelivr)](https://cdn.jsdelivr.net/gh/midrender/revideo@main/README.md)
- Midrender (YC S23, 1-person team) is a visual editor for AI-powered motion graphics; users describe animations in plain English then edit — [YC: Midrender](https://www.ycombinator.com/companies/midrender); [Extruct](https://www.extruct.ai/hub/re-video/)
- Third-party directory: team now mainly works on Midrender; recent engine changes not pushed to the open-source repo — [Webfolio](https://www.webfolio.to/tools/revideo) (secondhand; no official pivot announcement found)
- Strengths: Node.js rendering API, variable-based templating, batch rendering; weaknesses: smallest adoption (~3K weekly npm downloads, ~2K stars, v0.x) — [PkgPulse](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)

**Remotion (TypeScript/React, declarative components rendered per-frame via headless Chromium)**
- Renders a full DOM tree; needs a headless browser to produce video — [Remotion compare docs](https://www.remotion.dev/docs/compare/motion-canvas)
- License: free for individuals and orgs with up to 3 employees; company license otherwise; Creators seat $25/mo; Enterprise from $500/mo — [Remotion license](https://remotion.dev/license); [Remotion pricing docs](https://www.remotion.dev/docs/license/pricing). Conflicting third-party pricing figures exist (e.g., PkgPulse describes it as BUSL with ARR-based tiers) — [PkgPulse](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026); treat PkgPulse licensing claims as unreliable vs Remotion's own pages.
- ~60K weekly npm downloads (Mar 2026), 21K+ stars; Lambda cloud rendering; Player component; 150 frames @1080p in 8-15 s on CI (vendor-ish claim) — [PkgPulse](https://www.pkgpulse.com/guides/remotion-vs-motion-canvas-vs-revideo-programmatic-video-2026)
- npm package version 4.0.529 exists (indicates very active release cadence) — [jsDelivr remotion@4.0.529 LICENSE](https://cdn.jsdelivr.net/npm/remotion@4.0.529/LICENSE.md)

**Manim ports / Manim-like engines (2025-2026 entrants)**
- **Ranim** (Rust, wgpu): inspired by 3b1b/manim and JAnim; early-stage, unstable APIs; newer releases add a CLI with hot-reload preview app; latest found 0.2.1 — [docs.rs ranim 0.2.1](https://docs.rs/crate/ranim/0.2.1/source/README.md); [lib.rs](https://lib.rs/crates/ranim); repo github.com/AzurIce/ranim
- **Manim-Web** (TypeScript, MIT): browser port of Manim using Canvas/WebGL, Three.js for 3D, MathJax/KaTeX for LaTeX; author says code was "100% generated by the agent" — [HN Show HN 47155375](https://hn.svelte.dev/item/47155375)
- **studio.academa.ai** (Rust core + wgpu, PyO3 Python API compatible with ManimCE, WASM/Pyodide in browser, Monaco editor + live preview, AI agent): closed source, paid AI features; HN commenters criticized calling it "Manim" — [HN 49091703](https://hn.svelte.dev/item/49091703)
- Other open-source alternatives named by HN commenters: manim-web, ManimML, reactive-manim, ManimGL, mathlikeanim-rs, "manim mcp" — [HN 49091703](https://hn.svelte.dev/item/49091703)

**Reanimate (Haskell, SVG-based functional animation)**
- SVG-based animation library exporting GIF/MP4; latest Hackage release 1.1.6.0 uploaded June 2022 — [Hackage reanimate](https://hackage-origin.haskell.org/package/reanimate); [GitHub](https://github.com/Lemmih/reanimate). No evidence of activity since 2022.

**Javis.jl (Julia, built on Luxor.jl)**
- Central package of JuliaAnimators org; repo last pushed 2024-04-16 with 76 open issues (early-2025 snapshot); latest release "about 2 years ago" per older index — [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fjuliaanimators%2Fjavis.jl); [JuliaAnimators](https://juliaanimators.github.io). No archive notice found.

**Penrose (CMU; DSL trio Domain/Substance/Style -> optimized diagrams)**
- Turns abstract math notation into diagrams (SIGGRAPH 2020) — [CMU News](https://www.cmu.edu/news/stories/archives/2020/june/tool-turns-math-into-pictures.html)
- Penrose 3.0: reworked core API, geometric queries, gallery; `roger` headless CLI renderer — [Penrose 3.0 blog](https://penrose.cs.cmu.edu/blog/v3); [Using Penrose](https://penrose.cs.cmu.edu/docs/ref/using)
- Community Penrose MCP server (Jan 2025) — [ecosyste.ms penrose-mcp](https://awesome.ecosyste.ms/projects/github.com%2Fbmorphism%2Fpenrose-mcp)

**Typst slides (Touying)**
- Supports `#pause`/`#meanwhile`, math-equation animation and CeTZ/Fletcher diagram animation; exports PPTX/HTML — [Typst Universe: touying](https://typst.app/universe/package/touying)
- Users on Typst forum ask for more complex animation/video; no native video export found — [Typst forum](https://forum.typst.app/t/is-there-an-external-package-that-can-implement-more-complex-animations-for-slides-from-touying-or-polylux/9860)

**Blender bpy / Primer**
- primerpython: Blender library of high-level build/animate functions, structure largely borrowed from Manim; ARCHIVED; author moved to Helpsypoo/primerunity (Unity) — [GitHub Helpsypoo/primerpython](https://github.com/Helpsypoo/primerpython)

**AI explainer generators (mostly LLM -> Manim code)**
- TheoremExplainAgent (MIT; with TheoremExplainBench) generates Manim scripts for long-form explainers — [arXiv 2502.19400](https://arxiv.org/abs/2502.19400)
- Manimator: paper/prompt -> scene description -> Manim code — [arXiv 2507.14306](https://arxiv.org/html/2507.14306v1)
- Human-in-the-loop LLM->narrated Manim pipeline with student study vs PowerPoint — [arXiv 2604.05266](https://arxiv.org/abs/2604.05266)
- Product-level tools (Math-To-Manim, Anim Lab AI, ManimAI, Codewords template, Hermes "manim-video" skill) exist; claims unverified — [Bright Coding blog](https://blog.brightcoding.dev/2026/02/22/math-to-manim-the-revolutionary-tool-every-math-educator-needs); [ScriptByAI](https://www.scriptbyai.com/math-educational-video)
- Midrender (Revideo engine) is the main AI-native motion-graphics product built on a Motion Canvas lineage — [YC](https://www.ycombinator.com/companies/midrender)

### Inferences
- **[background, unverified this session]** Other tools in the brief, summarized for the writer at lower confidence:
  - matplotlib.animation (Python, FuncAnimation; BSD-style license; strong for data plots, weak for choreographed explainer motion; LaTeX via usetex). Plotly (Python/JS, MIT; interactive frames/sliders, not video-first). Makie.jl (Julia, MIT; `record` for animations, GPU 3D via GLMakie — strongest 3D-plot animation in Julia). Luxor.jl (Julia 2D Cairo drawing; Javis's backend).
  - p5.js/Processing (JS/Java, LGPL/GPL-ish; creative coding, immediate-mode draw loop; no LaTeX/timeline). D3.js (ISC; data-driven DOM/SVG with transitions; web-interactive, not video). three.js (MIT; general WebGL 3D). MathBox (MIT, Steven Wittens; WebGL math presentation, largely dormant). Nannou (Rust creative coding, slow activity).
  - Asymptote (C++-like DSL, LGPL; precise 2D/3D vector math figures with native LaTeX, animation via `animate` module, little modern tooling). TikZ/Beamer (`animate` package, overlays; best LaTeX fidelity, painful for motion).
  - Slidev (Vue/Markdown slides, MIT) with Shiki Magic Move for animated code transitions; reveal.js (MIT) with auto-animate; Animotion (Svelte-based presentation framework by Joy of Code). Code Hike (MDX/React code walkthroughs, MIT). Keynote Magic Move (proprietary, GUI).
  - Theatre.js (Apache/AGPL split; code + visual timeline editor for web animation). GSAP (now free incl. plugins after Webflow acquisition in 2024; general web tweening). Lottie (JSON vector animation format from After Effects/bodymovin; playback, not authoring).
  - Mathematica Manipulate/Animate (proprietary; superb symbolic math, interactive), MATLAB (proprietary), Desmos API (free for non-commercial with key), GeoGebra (scripting/GGBScript, free non-commercial), Cinderella (interactive geometry, CindyJS), SageMath (`animate`, GPL), Mathigon/Polypad (interactive courseware, acquired by Amplify 2023), Idyll (explorable explanations markup, largely dormant), Observable (notebooks + Observable Plot/Framework).
  - Unity/Godot: Primer moved from Blender to Unity (confirmed above); general game engines give real-time 3D and simulation but no LaTeX/math primitives.
- Comparison axes vs Manim (synthesized):
  - **LaTeX**: Manim has first-class TeX->SVG with per-glyph morphing (TransformMatchingTex). Motion Canvas has a `Latex` node (MathJax) but weaker glyph-level morphing; Manim-Web uses MathJax/KaTeX (cited); Remotion only via KaTeX/MathJax React components; Asymptote/TikZ/Typst have best typesetting but weak motion.
  - **Timeline/preview UI**: Manim has none built-in beyond ManimGL interactive window / CE `--preview`; Motion Canvas/Canvas Commons/Revideo have a browser editor with timeline and hot reload (cited); Remotion has Studio + Player; Ranim adds a hot-reload preview app (cited); Theatre.js offers a visual keyframe editor.
  - **Rendering speed**: Manim CE (Cairo, CPU) is notoriously slow; ManimGL and the Rust/wgpu engines (Ranim, academa) target GPU speed; Remotion depends on headless Chromium (memory-heavy, cited).
  - **3D**: Manim has ThreeDScene (limited, Cairo) and ManimGL OpenGL 3D; Motion Canvas is 2D-first; Blender/Unity/three.js/Makie are far stronger in 3D.
  - **Audio sync**: Motion Canvas/Revideo/Remotion all support audio tracks with timeline sync (cited: PkgPulse); Manim relies on `add_sound` or external tools/manim-voiceover.
  - **Learning curve**: Manim and Motion Canvas comparable for programmers; Remotion easiest for React developers; Penrose/Typst/TikZ declarative for static-ish math content.

### Gaps
- Could not verify current (Nov 2026) GitHub commit activity for Motion Canvas, Canvas Commons, Javis, Reanimate, Ranim — fetched pages did not show commit dates.
- No live verification this session for GSAP, Theatre.js, Lottie, Nannou, MathBox, Code Hike, Shiki Magic Move, Slidev, Animotion, reveal.js, Idyll, Observable, Desmos, GeoGebra, Cinderella, Sage, Mathigon/Polypad, Mathematica, MATLAB, Plotly, matplotlib, Makie, Asymptote, TikZ, Unity/Godot, "Animation Nodes". "Animo", "Cosmos", "Presenter" as named in the brief: no sources found/searched.
- Notable users mostly undocumented; only confirmed: Primer (Blender then Unity), slama.dev tutorial series (Motion Canvas -> Canvas Commons), aarthificial's own YouTube channel (Motion Canvas origin).

## Q2. Which are actively maintained in 2026 vs abandoned?

### Takeaway
Upstream Motion Canvas appears dormant since roughly Dec 2024 / Feb 2025 (not archived; described by defenders as "stable"); Canvas Commons is the community-maintained continuation. Revideo's open-source repo lags behind its commercial use in Midrender. Remotion is very active. Reanimate (last release 2022), Javis.jl (last push Apr 2024) and primerpython (archived) are inactive; Ranim is active but alpha-quality.

### Cited Findings
- HN commenter (2026): Motion Canvas "abandoned", main site down, last commit Dec 2024; rebuttal: "considered 'stable'", 2800+ Discord members, author had life changes that stopped his YouTube channel — [HN 47155375](https://hn.svelte.dev/item/47155375)
- LibHunt: official domain returning NXDOMAIN claim; repo stale — [LibHunt motion-canvas](https://www.libhunt.com/r/motion-canvas) (unofficial; note that motioncanvas.io blog pages were still indexed in search results, so the domain-down claim may be intermittent/conflicting)
- "the original Motion Canvas project is no longer maintained" — [slama.dev](https://slama.dev/motion-canvas/2/)
- Last Motion Canvas release found: 3.17.2 (2024-12-14) — [Yarn changelog](https://classic.yarnpkg.com/en/package/@motion-canvas/ui); no v4 found — [motioncanvas.io blog](https://motioncanvas.io/blog)
- Revideo engine changes not pushed to OSS; team focused on Midrender — [Webfolio](https://www.webfolio.to/tools/revideo)
- Remotion at v4.0.5xx on npm — [jsDelivr](https://cdn.jsdelivr.net/npm/remotion@4.0.529/LICENSE.md)
- Reanimate last Hackage upload June 2022 — [Hackage](https://hackage-origin.haskell.org/package/reanimate)
- Javis.jl last push 2024-04-16 — [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fjuliaanimators%2Fjavis.jl)
- primerpython archived; author uses primerunity — [GitHub](https://github.com/Helpsypoo/primerpython)
- Ranim releases up to 0.2.1, APIs unstable — [docs.rs](https://docs.rs/crate/ranim/0.2.1/source/README.md)
- ManimCE is the actively maintained Manim edition — [beginnersinai 2026 comparison](https://beginnersinai.org/remotion-vs-motion-canvas-vs-manim/) (SEO/vendor content; low weight)

### Inferences
- "Motion Canvas 4" as listed in the brief does not appear to have shipped; any claim of it should be treated as unconfirmed.
- For a user choosing a TS Manim alternative in late 2026, Canvas Commons (MIT-compatible API) is the safer bet than upstream Motion Canvas; Revideo is best for templated/batch server rendering but with lagging OSS.

### Gaps
- Canvas Commons license, maintainers, release cadence and star count not confirmed (official repo not found in results).
- Whether motioncanvas.io is currently online could not be confirmed.

## Q3. Community sentiment (HN, Reddit "Manim vs Motion Canvas")

### Takeaway
Sentiment: Motion Canvas is praised as "manim but typescript" with a real editor/timeline; Manim remains the "gold standard" for math with larger community; main concern about Motion Canvas is maintenance. HN is skeptical of closed-source or AI-generated tools branding themselves "Manim". No Reddit threads surfaced in search.

### Cited Findings
- Motion Canvas called mature, popular "manim but typescript" with animation editor/timeline; widely used on YouTube — [HN 47155375](https://hn.svelte.dev/item/47155375)
- Replicating 3b1b style "probably reasonably simple ... just animating an SVG stroke" plus colors/typography — [HN 47155375](https://hn.svelte.dev/item/47155375)
- HN commenters objected to studio.academa.ai's naming ("should not be called Manim" if only partly compatible) and to closed source + subscription — [HN 49091703](https://hn.svelte.dev/item/49091703)
- 2026 comparison: Manim "gold standard" for math/science visualization especially for Python users — [beginnersinai](https://beginnersinai.org/remotion-vs-motion-canvas-vs-manim/) (low-quality source)
- Remotion's own comparison acknowledges Motion Canvas is "truly open source" unlike Remotion — [Remotion docs](https://www.remotion.dev/docs/compare/motion-canvas)
- 2026 comparison sites note Manim and Motion Canvas code is structured enough for coding agents, but teams must supply validation loops — via search summary of [autoae.online](https://autoae.online/blog/motion-canvas-vs-remotion) (low weight)
- LLM->Manim generation needs sandboxing and human checking for correctness — [TheoremExplainAgent review via dev.co](https://dev.co/ai/rag/theoremexplainagent)

### Inferences
- Manim's moat in 2026 is increasingly its role as the default target language for LLM-generated math video (many AI tools emit Manim code), on top of LaTeX handling and 3b1b brand.

### Gaps
- No Reddit (r/manim, r/javascript, r/math) threads retrieved; sentiment from Reddit is unverified.
- Most 2026 "comparison" articles are SEO/vendor content; no independent benchmark of render speed between Manim, Motion Canvas, and Remotion was found.
