# Standalone desktop GUIs, visual editors and no-code builders for Manim (as of 18 Nov 2026)

Method: on 2026-11-18 I took repo metadata (stars, open issues, created, last push, last commit, licence, releases) from the GitHub REST API via `gh api repos/<owner>/<repo>`. Repos came from about 30 `gh search repos` queries ("manim editor", "manim gui", "manim studio", "manimate", "manim ide", "manim timeline", "manim desktop", "manim wysiwyg", "manim pyqt", "manim tkinter", "manim blender", "manim godot" and others). PyPI data came from `pypi.org/pypi/<pkg>/json`, and download counts from pypistats.org. Feature claims come from each project's own README, which is self-description; I did not install or run any of these apps. "Open issues" from the API includes open PRs. Browser-only tools, IDE extensions and pure text-to-video generators are out of scope. They are mentioned only where they overlap or have been mislabelled as desktop apps. Several queries ("manim pyqt", "manim pyside", "manim electron", "manim godot", "manim node editor", "manim keyframe", "manimgl gui", "topic:manim-gui", "topic:manim-editor") returned no repositories at all, which itself shows how thin this niche is.

## Which desktop/standalone GUI projects exist, and what state are they in?

### Takeaway
Fewer than ten real, usable desktop visual editors for Manim exist, and none is mainstream. The best-starred one is kevcen/manimate (140 stars), which has been abandoned since 2024. The only active, release-shipping desktop apps in late 2026 are all very new (created Sep–Oct 2026) with 1–105 stars:
- diegormirhan/manim-editor: Windows, a Tauri timeline editor that generates Manim CE 0.21 code.
- pachterlab/Manimble: macOS only, a slide editor that round-trips through Python.
- lukaznj/manim-studio: Win/Mac/Linux, an AI-agent studio with a code-linked timeline.
- AniMathIO 2: Win/Mac/Linux, a timeline video editor that *imports* Manim scripts but renders with its own Rust engine, not Manim.

Everything else is a 0–14-star student or "vibecoded" prototype, or dead (2019–2024).

### Cited Findings

**Tier A — active, released desktop apps (2026)**

- **diegormirhan/manim-editor** ("A visual desktop editor for creating mathematical animations with Manim")
  - Tauri 2 + React 19 + TypeScript; Windows-only badge; pins `manim==0.21.0`.
  - 3 stars, 1 open issue; created 2026-09-06; last commit and release v3.1.0 on 2026-10-16; no licence file (API `license=null`).
  - Features:
    - Layered video-editor timeline (V1, V2… tracks) with drag, resize and snapping.
    - Inspector "Add animation" that places animations at the playhead.
    - Live preview that shows "Manim's own frame at the playhead, usually within half a second" from a Manim process kept running in the background.
    - Drag, scale and rotate on the stage with Canva-like guides.
    - Export to MP4, WebM, GIF or MOV (480p–4K), or "the same scene as readable Python".
    - Export of per-layer ProRes 4444 plus FCP7 XML / FCPXML timelines for Premiere, Resolve, VEGAS and Final Cut.
    - CLI for scripts and AI agents; bundled Python runtime.
  - The README calls it "a development MVP".
  - Limitations: one scene per project; "Existing Manim Python cannot be imported, and exported Python is not read back"; timing sits on a 15 fps grid; one animation per object at a time; licence review and Authenticode signing pending.
  - Sources: [GitHub API](https://api.github.com/repos/diegormirhan/manim-editor); [README](https://github.com/diegormirhan/manim-editor); [requirements.txt](https://github.com/diegormirhan/manim-editor/blob/main/requirements.txt)
- **pachterlab/Manimble** ("Edit manim slides"; from Lior Pachter's lab org)
  - Swift; BSD-2-Clause; 105 stars, 1 open issue; created 2026-10-07; last commit and release v0.4.7 on 2026-11-16; 13 releases; about 537 total release-asset downloads.
  - A slide editor for Manim + Manim Slides decks. "Every slide is Python code: edit it on the canvas like in PowerPoint or Keynote, in the built-in code editor, or with an AI coding agent such as Claude Code, Codex or Gemini CLI running in Manimble's terminal. All three can work on the same deck at the same time."
  - macOS 13+ only (universal binary, signed and notarized); "Windows and Linux versions are planned."
  - First launch installs a self-contained Python with Manim (~150 MB) and TinyTeX (~80 MB) if they are missing.
  - Docs: pachterlab.github.io/Manimble.
  - Sources: [GitHub API](https://api.github.com/repos/pachterlab/manimble); [README](https://github.com/pachterlab/Manimble); [releases](https://github.com/pachterlab/Manimble/releases)
- **lukaznj/manim-studio** ("Manim Studio — a desktop app for maths explainer videos made with manim")
  - TypeScript; AGPL-3.0; 1 star, 0 issues; created 2026-10-08; last commit and release v0.22.0 on 2026-11-17 (very frequent releases).
  - Installers for macOS (Apple Silicon, not notarized), Windows 10/11 x64 (`-Setup.exe`, SmartScreen warning) and Linux AppImage.
  - First launch installs its own Python with Manim (~750 MB) and LaTeX (~250 MB); the app self-updates from GitHub Releases.
  - "Learn" mode: course PDFs become an episode series, with no editor or code.
  - "Create" mode:
    - An AI agent (Claude, Codex or Antigravity/Gemini) edits `scene.py`, renders, inspects frames and fixes layout.
    - "The timeline comes from the render. Sections, every `self.play`, the narration and the subtitles, each linked to its line of code."
    - "Drag a clip's edge and the `run_time=` in the code changes."
    - Version history, narration, translation and dubbing, YouTube exports with thumbnails, and GPU encoding.
    - A Claude Desktop extension.
  - Sources: [GitHub API](https://api.github.com/repos/lukaznj/manim-studio); [README](https://github.com/lukaznj/manim-studio)
- **AniMathIO 2** (AniMathIO org; earlier name "ManimStudio" by MemerGamer / AniMathIO)
  - Rust; MIT; 13 stars, 14 open issues; created 2024-04-08; v2.0.0, v2.1.0 and v2.2.0 all published 2026-11-16/17.
  - Installers: Windows NSIS `x64-setup.exe`, macOS aarch64 dmg, Linux deb and AppImage (Windows and macOS builds unsigned).
  - "A desktop editor for math animation videos. Combine media, editable LaTeX, graphs and shapes on a multi-track timeline". Keyframes, undo/redo, captions, local Whisper subtitles, CLI, JSON-RPC/MCP control, and sandboxed WebAssembly plugins.
  - It is **not rendered by Manim**. The engine is Rust/Vello, and math typesetting is Typst plus MiTeX (LaTeX→Typst conversion).
  - Its Manim link is a **one-way importer**: `import-manim` "for Manim Community scene scripts (`.py`), parsed with a small pure-Rust Python parser", available as File → Import Manim scene, `animathio-cli import-manim`, or the MCP `import_manim_scene` tool.
  - v1 was Electron/Nextron with Mafs. Windows and Linux only, since macOS was dropped for lack of resources. It is frozen on the `legacy` branch.
  - The predecessor repo AniMathIO/ManimStudio ("video editor application for editing Python ManimCE video projects") has 1 star, was archived, and was last pushed 2024-06-24.
  - Sources: [GitHub API](https://api.github.com/repos/AniMathIO/AniMathIO); [README](https://github.com/AniMathIO/AniMathIO); [architecture.md](https://github.com/AniMathIO/AniMathIO/blob/main/docs/architecture.md); [migrating-from-v1.md](https://github.com/AniMathIO/AniMathIO/blob/main/docs/migrating-from-v1.md); [legacy README](https://github.com/AniMathIO/AniMathIO/tree/legacy); [AniMathIO/ManimStudio](https://github.com/AniMathIO/ManimStudio)

**Tier B — notable but stale / abandoned**

- **kevcen/manimate** ("An animation studio for Manim")
  - Python; MIT; 140 stars, 3 open issues; created 2022-02-11; last commit 2024-07-30; no releases.
  - A "WYSIWYG tool for creating animations with Manim … without needing to write any code":
    - Left object palette (circle, square, text, LaTeX…) and right property panel.
    - Bottom "state" (keyframe) panel; you change objects between states and it "automatically write[s] the Manim code to interpolate".
    - Export to Python code; binary-tree data type; import of custom user-defined Mobjects.
  - The README links 3b1b/manim, but requirements pin **Manim CE `manim==0.15.2`** plus moderngl 5.6.4, PySide6 6.3.0 + PySide2 and Python 3.10. It ran from source on Linux; the README recommends Xorg over Wayland.
  - Sources: [GitHub API](https://api.github.com/repos/kevcen/manimate); [README](https://github.com/kevcen/manimate); [requirements.txt](https://github.com/kevcen/manimate/blob/main/requirements.txt)
- **MathItYT/manim-studio** ("A GUI to easier make Manim animations"; PyPI `manim-studio`)
  - Python + PyQt6; README says MIT, but the API shows no licence file. 93 stars, 5 open issues; created 2023-09-10; last commit 2024-03-23.
  - PyPI 0.7.4 (2024-03-23; first release 0.1.0 on 2023-09-11). Requires `manim>=0.18.0,<0.19.0`, `pyqt6>=6.6.1` and Python `<3.13`. Registered as a `manim.plugins` entry point. About 395 downloads per month.
  - Features: live preview of Cairo-rendered animations; working with Mobjects in the GUI; a "live cell" to insert code into the scene; "Generate Python File" export; can attach to an existing scene (`manim-studio --file FILE --scene SCENE`).
  - Same author: mathlikeanim-rs.
  - Sources: [GitHub API](https://api.github.com/repos/MathItYT/manim-studio); [README](https://github.com/MathItYT/manim-studio); [PyPI JSON](https://pypi.org/pypi/manim-studio/json); [pyproject.toml](https://github.com/MathItYT/manim-studio/blob/main/pyproject.toml); [pypistats](https://pypistats.org/api/packages/manim-studio/recent)
- **ManimCommunity/manim_editor** ("Editor and Presenter for Manim Generated Content")
  - Python/Flask; MIT; 364 stars, 23 open issues; created 2021-10-19; last commit 2024-07-17; last release v0.3.8 on 2021-12-19.
  - A local web app (browser UI, supports Firefox, Chrome and Edge) that builds slide presentations from scenes rendered with `--save_sections`. It is not an animation authoring GUI.
  - PyPI pins `manim>=0.13.1,<0.14.0`, so it is broken on current CE. About 119 downloads per month. Superseded by manim-slides.
  - Sources: [GitHub API](https://api.github.com/repos/ManimCommunity/manim_editor); [README](https://github.com/ManimCommunity/manim_editor); [PyPI JSON](https://pypi.org/pypi/manim-editor/json)
- **eulertour/eulerv2** ("A web based frontend to manim")
  - Vue; 104 stars, 37 issues; last commit 2020-03-29; Pyodide build of a forked manim. Web, dead. Listed here for completeness only.
  - Source: [GitHub API](https://api.github.com/repos/eulertour/eulerv2)
- **EfficientManim** (programmersd21)
  - Python; MIT; 29 stars, 0 issues; created 2026-01-13; last push 2026-06-11 (5 months idle); no releases.
  - "A node-based visual IDE for mathematical animations". You "drag-and-drop Mobjects and Animations onto an infinite canvas, connect them with smart wires", with 60+ Manim CE classes, live static previews, AI scene generation from text or PDF slides, and a history system.
  - Announced on r/manim ("I built a node-based Manim IDE with AI assistance").
  - Sources: [GitHub API](https://api.github.com/repos/programmersd21/EfficientManim); [README](https://github.com/programmersd21/EfficientManim); [Reddit](https://www.reddit.com/r/manim/comments/1qck0ji/i_built_a_nodebased_manim_ide_with_ai_assistance/)

**Tier C — small / experimental / student projects (real and public)**

- **EasyManim** (tailwiinder/easymanim)
  - "An attempt to build a GUI video editor that uses manim under the hood". Python, Tkinter/ttkbootstrap; MIT; 14 stars, 5 issues; created and last pushed 2025-05-06 (single push).
  - v0.1 supports only Circle, Square and Text; a property panel (position, size, colours, opacity, stroke); intro animations (FadeIn, Write, GrowFromCenter); static preview image; MP4 render. "Tested with v0.18.0 and later."
  - Sources: [GitHub API](https://api.github.com/repos/tailwiinder/easymanim); [README](https://github.com/tailwiinder/easymanim)
- **LzdqesjG/ManimEditor**
  - Python (FastAPI + browser UI launched by `python main.py`); MIT; 2 stars; created 2026-10-04; last push 2026-10-06. Chinese README.
  - It uses reflection (`inspect`) to list all public Manim classes (about 148 Mobjects and 77 Animations) and auto-builds parameter forms from constructor signatures.
  - Timeline: animations that share a start time merge into one `self.play()`, and gaps become `self.wait()`.
  - Approximate canvas preview; live code panel for things the GUI can't do (3D, LaTeX, updaters); one-click render; JSON scene save; UI in English and simplified/traditional Chinese.
  - Requires `manim>=0.19`. Chained methods (`shift`, `scale`, `set_color`) are not covered by the GUI.
  - Sources: [GitHub API](https://api.github.com/repos/LzdqesjG/ManimEditor); [README](https://github.com/LzdqesjG/ManimEditor)
- **raywill/manim-ide** ("Manim Visual IDE")
  - JavaScript, served with `python -m http.server`, so it is effectively a local web page; MIT; 6 stars; 2025-11-02 to 2025-11-26.
  - Ten drawing tools (rectangle, ellipse, Bézier, sine, parabola, axes…), drag-to-draw, JSON save, undo/redo, export to Manim CE code. Chinese README.
  - Source: [GitHub API](https://api.github.com/repos/raywill/manim-ide)
- **Symmercy/manim_gui**
  - customtkinter; GPL-3.0; 0 stars; single day 2026-07-02. Self-described "vibecoded … in a span of a couple of hours", and the author does not accept PRs.
  - Source: [GitHub](https://github.com/Symmercy/manim_gui)
- **mrsaleem123/Manim-Editor** ("Manim Media Studio")
  - Python; 0 stars; 2026-08-12. A Windows desktop runner that pastes ChatGPT-generated Manim code, strips code fences, detects the Scene class, prompts for missing asset paths, and renders. Builds an offline `ManimStudio-Setup-1.1.0.exe`. A code runner, not a visual editor.
  - Source: [GitHub](https://github.com/mrsaleem123/Manim-Editor)
- **santhosh-005/ManiMate**
  - Electron + React + Vite; MIT; 2 stars; created 2025-08-16; last push 2026-06-16. "Desktop App: AI Math shapes video clips Generator using Manim". Prompt → clip; no visual editing.
  - Source: [GitHub](https://github.com/santhosh-005/ManiMate)
- **Code Animator** (HeyItsJhello, itch.io)
  - Desktop app that turns source-code files into animated MP4s, "powered by Manim under the hood". v0.1.0 released 2026-01-18 for macOS aarch64 only; Windows and Linux "coming soon". Called "open source" with no licence named; status "In development". Specialised (code walkthroughs), not a general editor.
  - Source: [itch.io devlog](https://jhello.itch.io/code-animator/devlog/1320913/new-open-source-tool-for-creators)
- **MathMotion Studio** (anurag-panda-dev)
  - Python FastAPI + React, launched locally and opened in the browser at 127.0.0.1:8765; Windows badge; Manim 0.19 badge; MIT; 0 stars; single push 2026-10-27.
  - No code: an external AI writes a declarative `scene.md` (19 object kinds, 15 action types), which is schema- and SymPy-validated and compiled to Manim. "Never executes AI-generated code."
  - Source: [GitHub](https://github.com/anurag-panda-dev/mathmotion-studio)
- **Dead early attempts (2019–2024)**
  - kilacoda/Manim-GUI: PySimpleGUI code editor and video player for 3b1b manim, 2 stars, 2020-05. README: "I'm not working on this anymore". — [GitHub](https://github.com/kilacoda/Manim-GUI)
  - sean-mcclure/manim_gui (1 star, 2020-05) and manim_gui2 (JS, 2021-04): web-service front ends with an empty README. — [GitHub](https://github.com/sean-mcclure/manim_gui)
  - flubon/Manim-Studio: Qt/C++ IDE, "haven't released yet", single push 2021-08-05. — [GitHub](https://github.com/flubon/Manim-Studio)
  - Rocky-Studios/Manim-Gui-Old: C#, 0 stars, 2024-07. — [GitHub](https://github.com/Rocky-Studios/Manim-Gui-Old)
  - gourab-ghosh/manim-gui (2020), Dann38/manim_gui (2023), surnom1/manim_GUI (2025), jake314jake/Manim-GUI-app (2023), Limbo-137/manihub (2021): all 0 stars and empty or near-empty READMEs. — [gh search "manim gui"](https://github.com/search?q=manim+gui&type=repositories&s=stars)
  - 7Wdev/manimce-blender: "manim plugin that … runs over blender", 2 stars, 2023-06. This is the only Blender-related hit; I found **no Godot or Blender-style editor that exports Manim code**. — [GitHub](https://github.com/7Wdev/manimce-blender)

**Adjacent items (out of scope, but often confused with desktop GUIs)**

- **BlommeJan/Manim-Motion**
  - "Figma-like visual animation editor powered by Manim". Vue 2.7 + Node 20 in the browser, with Manim CE running in **Docker**. 45 stars, 5 issues; created 2026-02-09; last push 2026-04-06. README badge says MIT, but the repo has no LICENSE file.
  - Features: drag-and-drop canvas, 16 shape types, `MathTex`, `Axes`, a 5-track timeline, Transform morphs, 17 easings, a code-only mode, and a generated-code view.
  - It is self-hosted (localhost) rather than a native desktop app; the closest feature match to a "Figma for Manim".
  - Sources: [GitHub API](https://api.github.com/repos/BlommeJan/Manim-Motion); [README](https://github.com/BlommeJan/Manim-Motion)
- **ManimStudio for iPhone/iPad** (developer chienchung Yu, App Store id6764472686)
  - Free; no listed in-app purchases; v1.7.
  - Bundles Manim, the scientific Python libraries and a LaTeX engine; runs offline.
  - Code editor with autocomplete, scene picker, export to MP4, GIF, HTML or MOV, and Apple Pencil sketch → Manim code.
  - Also installable on Apple-silicon Macs ("Not verified for macOS"). Rated 5.0 from 1 rating.
  - Mobile and code-first, not a visual editor.
  - Source: [App Store](https://apps.apple.com/app/id6764472686)
- **Animo** (animo.video; successor to marcelo-earth/generative-manim)
  - "Manim AI – Create Math Animations from Text". A downloadable app for Mac and Windows ("less than 7MB") with chat → AI-generated code → "Live Video".
  - Has a pricing page and sign-in, plus a PyPI client and a VS Code extension.
  - An AI generator, not a visual editor.
  - Sources: [animo.video](https://animo.video); [generative-manim README](https://raw.githubusercontent.com/marcelo-earth/generative-manim/main/README.md)
- **Yusuke710/Manimate**
  - Local *browser* app driving Claude Code or Codex; `npm install -g manimate`; MIT; 6 stars; pushed 2026-11-15.
  - Includes "Capture": paused frame plus timestamp sent to the chat as feedback.
  - Source: [GitHub](https://github.com/Yusuke710/Manimate)
- **instavm/manim-studio**
  - Prompt → OpenAI → render on InstaVM cloud VMs (manim 0.20.1); 9 stars; web.
  - Source: [GitHub](https://github.com/instavm/manim-studio)
- **`manim-studio-sdk`** (PyPI 0.2.0, 2026-07-29)
  - SDK for the hosted service manimstudio.me (repo Luna7282/Manim-online). Unrelated to MathItYT's package despite the name.
  - Source: [PyPI JSON](https://pypi.org/pypi/manim-studio-sdk/json)
- **Other plugins that are not GUIs**
  - `manim-interactive` (PyPI 0.1.0, 2025-10-27): OpenGL renderer plus a VS Code extension.
  - `manim-preview` (0.1.0, 2026-07-23): browser auto-preview CLI.
  - `manim-play-timeline` (abul4fia, 0.1.1, 2023): a `play_timeline` *code* helper, not a GUI; Python `<3.12`.
  - Sources: [PyPI manim-interactive](https://pypi.org/pypi/manim-interactive/json); [PyPI manim-preview](https://pypi.org/pypi/manim-preview/json); [PyPI manim-play-timeline](https://pypi.org/pypi/manim-play-timeline/json)
- **Name collisions to be aware of**
  - "Manim Studio" names at least five unrelated things: MathItYT's PyQt plugin, lukaznj's desktop app, AniMathIO's archived predecessor, the iOS app, and manimstudio.me.
  - "Manimate" names kevcen's studio, Yusuke710's AI browser app and bassimeledath's agent skill.
  - "Manim Editor" names the ManimCommunity presenter and diegormirhan's Tauri editor.
  - Sources: [gh search "manim studio"](https://github.com/search?q=manim+studio&type=repositories&s=stars); [gh search "manimate"](https://github.com/search?q=manimate&type=repositories&s=stars)

### Inferences
- In 2026 the niche split in two:
  - "Classic" visual editors: canvas plus property panel plus timeline that generate code (diegormirhan, LzdqesjG, EasyManim, EfficientManim, Manim-Motion).
  - AI-agent studios that use a GUI mainly for reviewing and retiming agent-written code (lukaznj Manim Studio, Manimble's agent terminal, Animo, Yusuke710 Manimate).
  New projects with real momentum are mostly of the second kind, or hybrids.
- No project has passed the "toy" adoption threshold. The highest-starred true authoring GUI (kevcen/manimate, 140) is dead, and every active one has 105 stars or fewer and is weeks old. Treat all 2026 entries as experimental, regardless of how polished their READMEs are.
- **For a Windows user on Manim CE 0.22**, the realistic candidates are:
  - diegormirhan/manim-editor (CE 0.21, Windows-native, generates code, no import).
  - lukaznj/manim-studio (Windows installer, own bundled Manim, AI-driven).
  - LzdqesjG/ManimEditor (`manim>=0.19`, runs locally in the browser).
  - AniMathIO 2 is Windows-ready but leaves Manim behind after import.
  - Manimble is macOS-only today.
- Two 0-star repos found in search, "lorileeconsumptive6527/manim-editor" (description copied in a marketing style, random-looking username) and "dunhillwilliam/manimeditor" (empty description), fit the pattern of lure repos. I did not inspect them and recommend not downloading their binaries.

### Gaps
- PyPI `manim-gui` is in the plugin registry, and its `/simple/` index and project page return HTTP 200. But the JSON API returned 404 and the page had no parsable description, so I could not identify its author, version or source.
- I could not check Reddit r/manim or Discord announcement channels systematically; WebSearch returned no Reddit threads. The only Reddit link found is the EfficientManim announcement, cited from its README.
- I could not get Animo's pricing (page truncated) or confirm whether its desktop app renders locally or in the cloud; the generative-manim README says local.
- No YouTube demo videos were reviewed.
- Feature claims were not tested by running the apps.

## Do they generate editable Manim code, round-trip, and support timelines, keyframes, LaTeX and live preview?

### Takeaway
Most code-generating editors are one-way (GUI → Python). True round-trip (code ↔ GUI on the same file) exists only in:
- **Manimble**: canvas, code editor and agent all edit the same Python slide.
- **lukaznj/manim-studio**: the timeline is derived from the rendered code, and dragging a clip rewrites `run_time=`.
- partially **MathItYT/manim-studio**: it can open an existing scene and export a new file.

**AniMathIO 2** imports Manim scripts one way into its own closed project format and never goes back to Manim. Timelines are now common in the 2026 tools. Frame-accurate live preview from real Manim is rare: diegormirhan renders single frames from a resident Manim process, and MathItYT renders Cairo live.

### Cited Findings
| Project | Editable Manim code out? | Code → GUI import? | Timeline / keyframes | LaTeX | Live preview |
|---|---|---|---|---|---|
| diegormirhan/manim-editor | Yes, "readable Python" export ([README](https://github.com/diegormirhan/manim-editor)) | No: "Existing Manim Python cannot be imported, and exported Python is not read back" | Multi-layer timeline, clips, snapping; one animation per object at a time; 15 fps grid | Yes (LaTeX equations, numbers, matrices) | Yes: real Manim frame at the playhead in about 0.5 s; full playback needs a render |
| pachterlab/Manimble | The source *is* Python per slide | Yes: canvas, code editor and agent edit the same deck simultaneously ([README](https://github.com/pachterlab/Manimble)) | Slide-based (Manim Slides), not a free timeline | Yes (installs TinyTeX) | Not confirmed in the README excerpt |
| lukaznj/manim-studio | Yes: the agent writes `scene.py` | Yes: timeline from render; "drag a clip's edge and the `run_time=` in the code changes"; the playing frame highlights its code line ([README](https://github.com/lukaznj/manim-studio)) | Code-linked timeline (sections, `self.play`, narration, subtitles) | Yes (bundled LaTeX) | Render-based playback |
| AniMathIO 2 | **No**: own `project.json` / `.amio` format, Rust renderer | One-way import of Manim CE `.py` via a Rust Python parser ([architecture.md](https://github.com/AniMathIO/AniMathIO/blob/main/docs/architecture.md)) | Multi-track timeline with keyframes ([README](https://github.com/AniMathIO/AniMathIO)) | Yes, through Typst + MiTeX, not TeX | Yes (own GPU preview) |
| kevcen/manimate | Yes: File → Export to Python ([README](https://github.com/kevcen/manimate)) | Imports custom Mobject classes only, not whole scenes | "States" (keyframes) with automatic interpolation | Yes (LaTeX object) | Interactive OpenGL (moderngl) canvas |
| MathItYT/manim-studio | Yes: "Generate Python File" | Partly: can open `--file FILE --scene SCENE` and continue ([README](https://github.com/MathItYT/manim-studio)) | No timeline mentioned; live code cell | Via Manim | Yes: Cairo live preview |
| LzdqesjG/ManimEditor | Yes: live code panel; GUI-uncovered features written by hand | Not stated (saves its own JSON) | Drag timeline; same-start animations merged into one `play()` | Hand-written in the code panel | Approximate canvas plus one-click render ([README](https://github.com/LzdqesjG/ManimEditor)) |
| EfficientManim | Generated from a node graph | Not stated | Node graph, not a timeline | Not stated | "Live static previews" ([README](https://github.com/programmersd21/EfficientManim)) |
| EasyManim | Not stated (renders directly) | No | Intro animations only | No (Text only) | Static preview image ([README](https://github.com/tailwiinder/easymanim)) |
| Manim-Motion (web/Docker) | Yes: generated-code view plus code-only mode | No | 5-track timeline, morphs, 17 easings | Yes (`MathTex`) | Canvas approximation; render via Docker ([README](https://github.com/BlommeJan/Manim-Motion)) |
| ManimCommunity/manim_editor | N/A (presentation tool) | Uses rendered sections | Slide sequencing | N/A | Browser presenter ([README](https://github.com/ManimCommunity/manim_editor)) |

- diegormirhan/manim-editor is the only tool found that exports an NLE-ready timeline: per-layer ProRes 4444 plus FCP7 XML / FCPXML. The README admits these files "have not yet been opened in each of those editors". — [README](https://github.com/diegormirhan/manim-editor)

### Inferences
- The hard problem every project avoids is parsing arbitrary Manim Python back into a GUI model. Only AniMathIO attempts a general parser, and it converts *out of* Manim. The round-trip tools instead keep Python as the single source of truth and either edit it directly (Manimble) or edit narrow, well-defined parameters such as `run_time=` (lukaznj). For a Claude-driven workflow like this project's, that "code is truth, GUI annotates it" model is the one that fits.
- Canvas positions in non-Manim previews (LzdqesjG, Manim-Motion, EasyManim) are approximations. diegormirhan explicitly needs Manim itself to report object bounds before stage dragging works.

### Gaps
- Manimble's live-preview behaviour and how it maps canvas drags into Python edits were not described in the README excerpt I read; the full docs are at pachterlab.github.io/Manimble and were not fetched.
- I did not verify how robust AniMathIO's Manim importer is (which Mobjects and Animations it maps); its docs list "Manim source import … Moved" but no coverage table was read.

## Which work with Manim CE 0.19+ (current 0.22.x), and which are pinned to old versions?

### Takeaway
Pinned to old Manim, and broken or likely to break on current Python and CE:
- ManimCommunity/manim_editor: `manim<0.14`.
- kevcen/manimate: `manim==0.15.2`, PySide6 6.3, Python 3.10.
- MathItYT/manim-studio: `manim>=0.18,<0.19`, Python `<3.13`. It cannot install alongside CE 0.22 or Python 3.13.

Explicitly 0.19+:
- diegormirhan/manim-editor: pins 0.21.0 in a bundled runtime.
- LzdqesjG/ManimEditor: `>=0.19`.
- MathMotion Studio: 0.19 badge.
- lukaznj/manim-studio bundles its own Manim. Its version is not stated; the app version v0.22.0 is its own numbering, not Manim's.

None targets ManimGL. Every visual editor found targets Manim CE. The only ManimGL tooling is IDE-side (Manim Notebook), which is out of scope.

### Cited Findings
- manim-editor PyPI 0.3.8 requires `manim (>=0.13.1,<0.14.0)` and Python `>=3.7,<4.0`. — [PyPI JSON](https://pypi.org/pypi/manim-editor/json)
- kevcen/manimate requirements: `manim==0.15.2`, `moderngl==5.6.4`, `moderngl_window==2.4.1`, `PySide6==6.3.0`, `PySide2`, `ipython==8.0.1`. — [requirements.txt](https://github.com/kevcen/manimate/blob/main/requirements.txt)
- manim-studio 0.7.4 requires `manim<0.19.0,>=0.18.0`, `pyqt6<7.0.0,>=6.6.1`, Python `<3.13,>=3.9`. — [PyPI JSON](https://pypi.org/pypi/manim-studio/json)
- diegormirhan/manim-editor `requirements.txt`: `manim==0.21.0`, `jsonschema==4.26.0`; downloads "carry their own Python". — [requirements.txt](https://github.com/diegormirhan/manim-editor/blob/main/requirements.txt); [README](https://github.com/diegormirhan/manim-editor)
- LzdqesjG/ManimEditor `requirements.txt`: `manim>=0.19`, `fastapi>=0.110`, `uvicorn[standard]>=0.27`. — [requirements.txt](https://github.com/LzdqesjG/ManimEditor/blob/main/requirements.txt)
- EasyManim: "tested with v0.18.0 and later", Python 3.12.3. — [README](https://github.com/tailwiinder/easymanim)
- Manimble and lukaznj/manim-studio install their own Python + Manim + LaTeX on first launch (Manimble ~150 MB Python and ~80 MB TinyTeX; lukaznj ~750 MB and ~250 MB). The Manim version is not stated in the excerpts read. — [Manimble README](https://github.com/pachterlab/Manimble); [lukaznj README](https://github.com/lukaznj/manim-studio)
- manim-play-timeline requires Python `<3.12` and `manim>=0.17` (a code helper). — [PyPI JSON](https://pypi.org/pypi/manim-play-timeline/json)

### Inferences
- Bundling a private Python/Manim/LaTeX runtime (diegormirhan, lukaznj, Manimble) is the 2026 answer to Manim's notoriously fiddly Windows install. It also means these apps won't automatically use a user's own CE 0.22 venv, or their custom modules such as this project's `style.py` and `manim_kit.py`, unless they offer a "use my Python" option. Manimble skips its install when "a Python that can import Manim is already found". I did not confirm whether the others allow this.
- Nothing scene-level found here breaks specifically between CE 0.19 and 0.22. Breakage for old tools comes from hard upper pins and Python-version caps, not documented API changes.

### Gaps
- I did not test any app against CE 0.22.1, so compatibility of apps pinned to 0.21 or 0.19+ is inferred from pins only.
- I did not find the bundled Manim version for lukaznj/manim-studio or Manimble.

## Are there commercial or freemium desktop products built on Manim?

### Takeaway
There are almost no commercial *visual-editor* products. The commercial or freemium desktop offerings built on Manim are AI generators:
- **Animo** (Mac and Windows download, with a pricing page and sign-in).
- the free **ManimStudio iOS/iPadOS app** (also on Apple-silicon Macs).

All the visual editors found are free and open source (MIT, BSD-2, AGPL-3.0 or GPL-3.0), or have no licence file. Hosted "Manim Studio" services (manimstudio.me, studio.academa.ai) are web products, out of scope here.

### Cited Findings
- Animo's site offers "Download for Mac / Download for Windows", "less than 7MB", AI chat → code → "Live Video", templates, and Pricing and Sign in pages. The generative-manim README presents Animo as its desktop successor that renders on the user's machine. — [animo.video](https://animo.video); [generative-manim README](https://raw.githubusercontent.com/marcelo-earth/generative-manim/main/README.md)
- The ManimStudio iOS app is free with no in-app purchases listed; it bundles Manim and LaTeX and runs offline with no telemetry. — [App Store](https://apps.apple.com/app/id6764472686)
- `manim-studio-sdk` (PyPI) is the SDK for the hosted manimstudio.me rendering service. — [PyPI JSON](https://pypi.org/pypi/manim-studio-sdk/json)
- Licences of the visual editors:
  - BSD-2-Clause: Manimble.
  - AGPL-3.0: lukaznj/manim-studio.
  - MIT: AniMathIO, kevcen/manimate, LzdqesjG, EasyManim, EfficientManim.
  - GPL-3.0: Symmercy.
  - None in the API (README may claim MIT): diegormirhan/manim-editor, MathItYT/manim-studio, Manim-Motion.
  - Sources: [GitHub API per repo](https://api.github.com/repos/pachterlab/manimble); [lukaznj](https://api.github.com/repos/lukaznj/manim-studio); [AniMathIO](https://api.github.com/repos/AniMathIO/AniMathIO); [diegormirhan](https://api.github.com/repos/diegormirhan/manim-editor)

### Inferences
- The AGPL-3.0 licence of lukaznj/manim-studio and the missing licence files on diegormirhan and MathItYT matter if anyone wants to fork or embed them. No licence legally means "all rights reserved", whatever the README says.
- The commercial energy around Manim in 2026 is in AI-generation services, not in GUI authoring tools. No company is selling a "Manim After Effects".

### Gaps
- Animo pricing tiers, usage caps and whether it requires the user's own LLM subscription could not be confirmed from the fetched page.
- I found no evidence of paid or freemium desktop editors on Gumroad, Microsoft Store or Steam; I did not search those stores directly.
