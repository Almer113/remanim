# IDE extensions, notebook integrations and live-preview / hot-reload tools for Manim (as of 2026-11-18)

Method note: Star counts, last-push dates, licences and open-issue counts come from the GitHub REST API (`api.github.com/repos/...` and `/search/repositories`), queried 2026-11-18. VS Code install counts, versions and "last updated" dates come from the VS Code Marketplace gallery API (`marketplace.visualstudio.com/_apis/public/gallery/extensionquery`, search "manim"). Open VSX counts come from `open-vsx.org/api/-/search?query=manim`. PyPI versions and dates come from `pypi.org/pypi/<pkg>/json`. These API results are cited below as [GH API], [VSM API], [OVSX API] and [PyPI API]. CLI facts for Manim CE were read directly from the installed Manim CE 0.22.1 (`python -m manim render --help` and the package source in this project's `.venv`), cited as [local CE 0.22.1]. Some GitHub search queries ("manim live reload", "manim hot reload", "manim gui", "manim interactive", "manim zed") returned no results. That was probably API rate limiting, so the absence of hits does not prove that nothing exists.

API endpoints used:
- GH API: https://api.github.com/repos/{owner}/{repo} and https://api.github.com/search/repositories?q=manim+vscode (and similar queries)
- VSM API: https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery
- OVSX API: https://open-vsx.org/api/-/search?query=manim
- PyPI API: https://pypi.org/pypi/{package}/json

## VS Code / Cursor extensions for Manim

### Takeaway
Manim Sideview (Rickaym) is the only mass-adoption extension: about 129.5k Marketplace installs, Manim CE, render-to-side-panel with render-on-save, updated 2026-09. Manim Notebook is the serious ManimGL option: a 3b1b-style interactive "Manim Cells" workflow with about 2.5k installs. Its last Marketplace release was 2025-04 and it has an open Windows bug. Around these two sits a long tail of small 2025–26 extensions: Manim Viewer, MarkHoo's Runner/LiveView, manim-dock, several ports of Grant's Sublime commands, and a manim-slides live preview. The most notable newcomer is **Manim Cue** (Benjamin Hackl, a Manim CE core developer, v0.3.1, 2026-11-12). It shows a frame, timeline and video, but it needs Manim CE from the unreleased `main` branch.

### Cited Findings
**Manim Sideview (Rickaym.manim-sideview), Manim CE**
- Marketplace: v0.4.3, last updated 2026-09-09, 129,495 installs, rating 5.0 from 8 reviews. Description: "Video/Image live previews and code snippets for manim." — [VSM API](https://marketplace.visualstudio.com/items?itemName=Rickaym.manim-sideview)
- Open VSX (used by Cursor, VSCodium and Windsurf): v0.4.2 (2026-08-13), 13,118 downloads. Open VSX lags one version behind the Marketplace. — [OVSX API](https://open-vsx.org/extension/Rickaym/manim-sideview)
- Repo: 187 stars, MIT, 14 open issues, last push 2026-09-09. — [GH API](https://github.com/Rickaym/Manim-Sideview)
- Features: renders the current scene and shows video or image output in a side media player (seek, loop, autoplay, portrait mode); render on save via `manim-sideview.runOnSave` (a file must be rendered manually once before it is watched); detects `Scene` subclasses; Mobject Gallery webview that inserts snippet code; post-render terminal command; Stop command. Requires Manim on PATH or `manim-sideview.defaultManimPath`, plus the Python extension. — [GitHub README](https://github.com/Rickaym/Manim-Sideview)
- Known caveats from its README: avoid quality flags such as `-ql` in `commandLineArgs` because they change the output path; if a `manim.cfg` exists, all `commandLineArgs` are ignored. The README changelog is stale (an old 0.1.1 entry is still tagged "Latest"). Paths are normalised for Windows backslashes. The README does not mention ManimGL. — [GitHub README](https://github.com/Rickaym/Manim-Sideview)

**Manim Notebook (Manim-Notebook.manim-notebook), ManimGL only**
- Marketplace: v1.0.1, last updated 2025-04-14, 2,497 installs, no ratings. — [VSM API](https://marketplace.visualstudio.com/items?itemName=Manim-Notebook.manim-notebook)
- GitHub releases: v1.0.0 (2025-02-21) and v1.0.1 (2025-04-14). Repo: 49 stars, MIT, 22 open issues, last push 2026-08-05. — [GH API](https://github.com/Manim-Notebook/manim-notebook)
- The README warns that it is for 3b1b's Manim and "*NOT* the Manim Community Edition". It says the extension was motivated by Grant Sanderson's "How I animate 3Blue1Brown" Sublime workflow. "Manim Cells" are comments starting with `##`, each with a CodeLens to preview it. You can preview any selection, reload changed Python files without restarting, and export video through a wizard. The extension parses `manimgl` terminal output to show a VS Code progress bar, supports a startup delay (for venv activation) and tracks state to prevent overlapping runs. A debugger is a stated long-term aim, not a feature. — [GitHub README](https://github.com/Manim-Notebook/manim-notebook)
- The older `bhoov.vscode-manim` (v0.0.3, 2024-10-15, 1,537 installs; "Replicates Grant Sanderson's sublime workflow for manim in VSCode") is the predecessor. Its repo README now redirects to Manim Notebook. — [VSM API](https://marketplace.visualstudio.com/items?itemName=bhoov.vscode-manim); [bhoov/vscode-manim README](https://github.com/bhoov/vscode-manim)
- Windows problem: Manim-Notebook issue #18 reports that on Windows 11 (GitBash and Conda/PowerShell, reproduced on two PCs), "Preview Manim Cell" types `checkpoint_paste()` into a running `manimgl ... -se` session but it never executes. I found no confirmed fix. — [Issue #18 (mirror)](https://cf-workers-proxy-9e9.pages.dev/Manim-Notebook/manim-notebook/issues/18) (seen via a search result on a proxy mirror; not confirmed on github.com)

**Manim Cue (behackl.manim-cue), Manim CE (dev branch)**
- Marketplace: v0.3.1, last updated 2026-11-12, 76 installs. Publisher: Benjamin Hackl. — [VSM API](https://marketplace.visualstudio.com/items?itemName=behackl.manim-cue)
- Features: after a save it shows the frame at a selected time, then a timeline of plays, waits, sections, captions and sounds, then the video. It can loop part of the video, jump from a timeline entry to its source line, compare two frames (wipe or overlay), measure coordinates and distances in scene units, and export a frame, video or timeline. Requires desktop VS Code ≥ 1.96, the Python extension and Python ≥ 3.11. **It needs Manim CE from the `main` branch "until the next Manim release".** A setup command creates a `.venv` (with `uv` and Python 3.13 if available). Preview plays silently. Measurement assumes a centred 2D camera. Stale frames are shown labelled "OUTDATED" while a re-render runs. — [Marketplace listing](https://marketplace.visualstudio.com/items?itemName=behackl.manim-cue)
- Repo: MIT, 86 commits, 9 stars. — [GitHub](https://github.com/behackl/manim-cue)

**Other VS Code / Open VSX extensions (small, 2025–26)**
- **Manim Viewer** (marcel-goldschen-ohm.manim-viewer): v2.0.2, 2025-07-11, 9,427 installs, Manim CE. Webview panel with scene selection, optional auto-load of the scene under the cursor, re-render on save only when the code changed (caches scene code in `manimViewer.json`), up-to-date status, cleans partial movie files. Repo has 3 stars, MIT. — [VSM API](https://marketplace.visualstudio.com/items?itemName=marcel-goldschen-ohm.manim-viewer); [README](https://github.com/marcel-goldschen-ohm/manim-viewer)
- **Manim Runner** and **Manim LiveView** (MarkHoo): both v1.0.0 (2025-12-30), 3,056 and 1,387 Marketplace installs, plus 3,329 and 2,646 Open VSX downloads. "Run and preview Manim scenes in VS Code with live updates." MarkHoo also maintains Chinese ManimCE docs. — [VSM API](https://marketplace.visualstudio.com/items?itemName=MarkHoo.manim-liveview); [OVSX API](https://open-vsx.org/extension/MarkHoo/manim-runner)
- **manim-dock** (Open VSX only, manim-dock.manim-dock): v0.2.9, 2026-10-10, 2,486 downloads. "Dock Outline, Stage, and Timeline beside ManimCE Python for educational video production." — [OVSX API](https://open-vsx.org/extension/manim-dock/manim-dock)
- **Manim Slides Preview** (Alamin-H-M): a VS Code extension distributed as a `.vsix` from GitHub, not found on the Marketplace. Every Ctrl+S re-renders and refreshes a manim-slides presentation in a browser tab, a VS Code tab or the native presenter, and keeps a PowerPoint copy updated. Requires Manim CE ≥ 0.19 and manim-slides ≥ 5.1.10; notes that FFmpeg is not needed since CE 0.19 (PyAV). Repo has 5 stars, MIT, last push 2026-09-03. — [README](https://github.com/Alamin-H-M/manim-slides-preview); [GH API](https://api.github.com/repos/Alamin-H-M/manim-slides-preview)
- **ManimGL "Sublime workflow" ports**: `manim helper` (stormtorch, 2,519 installs, 2025-07); `manimvs` (lolloz98, 777 installs, v0.0.3 2026-09-13), which sends checkpoint_paste for the comment block or selection under the cursor to a chosen terminal already running `manimgl ... -se`; `Manim Tool` (thePANE, 1,188 installs, 2025-06; "running Manim commands and managing checkpoints"); `Manimgl Helper` (BeiChenStanly, 43 installs, 2026-07); `manine-commands` (ajiu9, 45 installs, 2026-08, "port of 3b1b's Sublime custom commands to VS Code"); `ManimSelect` (133 installs). — [VSM API](https://marketplace.visualstudio.com/search?term=manim&target=VSCode); [manimvs README](https://github.com/lolloz98/manimvs)
- **Manim CE for Jupyter** (tan-o.manim-ce-jupyter): v0.18.0, 2026-08-04, 304 installs. "A standalone *.manim.ipynb studio with a real IPykernel, Manim, Typst, Jupyter-style HTML slides and PPTX export." — [VSM API](https://marketplace.visualstudio.com/items?itemName=tan-o.manim-ce-jupyter)
- **Manim Studio** (bearx, 758 installs, rating 3.5 from 2, 2026-03; "manim tools") and **Snippet Gallery** (90 installs; visual gallery of Manim snippets). — [VSM API](https://marketplace.visualstudio.com/search?term=manim&target=VSCode)
- AI overlap (out of scope): **Animo** ("Cursor for Manim", 593 Marketplace installs and 6,082 Open VSX downloads, 2025-11). Engine-specific extensions for non-Manim engines: Gaanim (2026-10) and Fluxion Engine (2026-01). — [VSM API](https://marketplace.visualstudio.com/items?itemName=Animo.animo); [OVSX API](https://open-vsx.org/api/-/search?query=manim)
- Dead or older: `dipamsen/vscode-manim` (5 stars, last push 2021-12). — [GH API search](https://github.com/dipamsen/vscode-manim)

### Inferences
- For Manim CE on Windows, Sideview is the default choice. Manim Viewer, MarkHoo's extensions and Manim Cue cover the same render-on-save niche with different UX. Manim Cue is the most ambitious (timeline, frame scrubbing, measurement) and is written by a core developer, so it may track CE changes closely. Its dependence on unreleased CE `main` probably means it relies on CE APIs that arrive after 0.22.1 (likely the next 0.22.x/0.23 release). Expect it to become usable on a stable release only after that release.
- Cursor and VSCodium users get Sideview through Open VSX, but one version behind. Several ManimGL helpers exist only on the Microsoft Marketplace.
- Every ManimGL extension wraps the same mechanism: typing `checkpoint_paste()` into a terminal running `manimgl -se`. They inherit its terminal and clipboard fragility, which is worse on Windows (issue #18).

### Gaps
- I could not confirm the current state of Manim-Notebook issue #18 on github.com itself.
- I did not get Marketplace review texts or issue lists for Sideview (14 open issues), so I have no catalogue of its specific bugs.
- Whether Manim Cue works on Windows is not stated.
- I did not find installs or ratings for the Alamin-H-M extension because it is not on the Marketplace.

## JetBrains / PyCharm, Neovim, Sublime, Zed and other editors

### Takeaway
Outside VS Code the tooling is very thin. Sublime Text has Grant Sanderson's own ManimGL commands (the reference workflow). Neovim has several tiny plugins (≤ 8 stars). PyCharm has essentially nothing maintained. I found nothing for Zed.

### Cited Findings
- **Sublime Text (ManimGL)**: the 3b1b/videos README describes installing Terminus and copying `sublime_custom_commands` into `Packages/User/`, with keybindings for `manim_run_scene`, `manim_checkpoint_paste`, `manim_recorded_checkpoint_paste`, `manim_skipped_checkpoint_paste` and `manim_exit`. — [3b1b/videos README](https://github.com/3b1b/videos) (via earlier notes, creator_toolchains.md)
- Other Sublime items: `hyu56/ManimScript` (0 stars, 2024-02, build tool). — [GH API search](https://github.com/hyu56/ManimScript)
- **Neovim**: `yeasin50/manim.nvim` (8 stars, MIT, pushed 2026-11-08, "Play and preview Manim Community scenes directly from Neovim"); `UsUsStudios/manimvim.nvim` (7 stars, 2026-02, run a scene); `vedantwpatil/manim-nvim` (4 stars, 2026-09, "replicate 3b1b's manim environment", i.e. ManimGL); `ahmeds0s/manim_runner.nvim` (3 stars, 2025-09); `DanielHermosilla/mavim` (1 star, 2025-07). — [GH API search "manim neovim"/"manim nvim"](https://github.com/search?q=manim+nvim&type=repositories)
- **PyCharm / JetBrains**: `npetrangelo/manim-plugin` (1 star, last push 2021-04-23, "A PyCharm plugin for writing Manim scenes"); `JACazares/manim-sideview-pycharm` (0 stars, MIT, 2025-06-30, "visualize manim scenes inline in PyCharm"). I found no JetBrains Marketplace plugin with meaningful adoption. — [GH API search "manim pycharm"](https://github.com/search?q=manim+pycharm&type=repositories)
- **Zed, Emacs and others**: the GitHub search for "manim zed" returned nothing. I did not search Emacs. — [GH API search](https://github.com/search?q=manim+zed&type=repositories)

### Inferences
- PyCharm users usually fall back on a Run Configuration that calls `python -m manim` plus an external video player, or on the CE OpenGL live window. Neovim users use one of the small plugins or a terminal split.

### Gaps
- I did not check the JetBrains Marketplace directly, so a plugin published only there might exist.
- I did not read the manim.nvim README (raw `main/README.md` returned 404, probably a different default branch).

## Jupyter, Colab, marimo and other notebook integrations

### Takeaway
Manim CE's built-in `%%manim` cell magic is the standard. It renders the scene and embeds the video or image in the cell, works in Jupyter and Colab (with an apt/pip setup on every Colab session) and powers the Binder tutorial at try.manim.community. Newer projects add real interactivity. **manim-widget** serialises CE scenes to JSON and plays them in the browser with the manim-web TS port (Jupyter and marimo). **manim-marimo** re-renders ManimGL scenes when marimo values change. manim-slides has its own IPython magic. Older third-party magics (jupyter-manim, AkashKarnatak/manim_notebook) are superseded.

### Cited Findings
- `%%manim` is built into Manim CE. Usage: `%%manim -qm -v WARNING SquareToCircle`. Config options: `media_width` (default `25vw`) and `media_embed`. Videos are always embedded when running in Google Colab. — [Manim docs: Jupyter](https://docs.manim.community/en/stable/installation/jupyter.html); [local CE 0.22.1] `manim/utils/ipython_magic.py`, lines 79–101 and 183–185
- The CE 0.22.1 CLI still has a `--jupyter` flag ("Using jupyter notebook magic."). — [local CE 0.22.1] `manim render --help`
- Colab recipe from the official docs: `apt install libcairo2-dev texlive texlive-latex-extra texlive-fonts-extra texlive-latex-recommended texlive-science tipa libpango1.0-dev`, then `pip install manim` and `pip install IPython==8.21.0` (the docs give no reason for the pin), then restart the runtime. The setup does not persist between sessions. — [Manim docs: Jupyter](https://docs.manim.community/en/stable/installation/jupyter.html)
- Binder: try.manim.community is the example environment, with source in ManimCommunity/jupyter_examples (26 stars, MIT, pushed 2026-11-03). The docs' Binder Dockerfile example still uses the `v0.9.0` tag, which you must change to match your version. — [Manim docs: Jupyter](https://docs.manim.community/en/stable/installation/jupyter.html); [GH API](https://github.com/ManimCommunity/jupyter_examples)
- **manim-widget** (rambip): "Manim in your notebooks, truly interactive, without the hassle." Rendering uses maloyan/manim-web (the TypeScript port); the repo serialises Python scenes to a JSON spec. Install with `uv add manim-widget`; the README says LaTeX is not required. It works in Jupyter and marimo and has a marimo demo on molab. The author says AI was used extensively and that the JavaScript was not reviewed. Repo: 10 stars, MIT, 12 open issues, pushed 2026-11-16. PyPI v0.2.1 (2026-07-15), Python ≥ 3.11. — [GitHub README](https://github.com/rambip/manim-widget); [GH API](https://api.github.com/repos/rambip/manim-widget); [PyPI API](https://pypi.org/project/manim-widget/)
- **manim-marimo** (peter-gy): renders **ManimGL** scenes (example code uses `from manimlib import ...`, `ShowCreation`) inside marimo notebooks through marimo-studio. Notebook variables are read with `value("trajectory", default=...)`, and Studio re-renders the movie when a value changes, so it works with marimo sliders. It needs a pixi/conda-forge environment for OpenGL and Pango. PyPI 0.0.1 (2026-10-19), Apache-2.0, Python 3.10–3.14. Repo has 3 stars, pushed 2026-11-01. It is listed in the Manim CE plugin registry despite targeting ManimGL. — [README](https://github.com/peter-gy/manim-marimo); [PyPI API](https://pypi.org/project/manim-marimo/); [plugins.json](https://plugins.manim.community/plugins.json) (via earlier notes)
- `eringrant/manimo` ("Slides with `manim` via `marimo`", 1 star, 2026-06), plus several marimo course repos that embed Manim (mrcal17/ml-course, info-theory-course). — [GH API search "manim marimo"](https://github.com/search?q=manim+marimo&type=repositories)
- **jupyter-manim** (krassowski): third-party `%%manim` magic. PyPI 1.3 from 2020-04-12; repo has 198 stars, MIT, pushed 2026-04-13. It predates and is superseded by the built-in magic. — [GH API](https://github.com/krassowski/jupyter-manim); [PyPI API](https://pypi.org/project/jupyter-manim/)
- `AkashKarnatak/manim_notebook` (7 stars, 2020-07; the only "manim jupyterlab" search hit). I found no dedicated JupyterLab extension. — [GH API search](https://github.com/AkashKarnatak/manim_notebook)
- The manim-slides docs index has an "IPython magic" page and a Jupyter magic example, so slides can be rendered inside notebooks. — [manim-slides docs](https://manim-slides.eertmans.be/latest/)
- VS Code's `tan-o.manim-ce-jupyter` provides a `*.manim.ipynb` studio (see the previous section). — [VSM API](https://marketplace.visualstudio.com/items?itemName=tan-o.manim-ce-jupyter)

### Inferences
- `%%manim` gives "render and show", not live interaction. manim-widget (CE API, browser playback) and manim-marimo (ManimGL, reactive re-render) are the only notebook tools that link controls to scenes, and both are very young (single maintainer, ≤ 10 stars).
- The IPython pin in the Colab recipe and the outdated v0.9.0 Binder tag suggest the notebook documentation gets little maintenance.

### Gaps
- I did not verify that try.manim.community is currently online, or which Manim version its Binder image runs.
- I found no report on whether `%%manim` works in VS Code's own notebook UI on Windows (it should, since it only embeds HTML video, but this is not verified).

## Interactive scene shells: ManimGL `-se` / `checkpoint_paste` and Manim CE OpenGL live preview / `interactive_embed`

### Takeaway
ManimGL's interactive mode (open a window plus IPython at a line, then `checkpoint_paste()`) is the most mature "live" workflow and the one Grant uses. ManimGL's last PyPI release is still 1.7.2 (Dec 2024), so the README tells users to install from source, and the paste-into-terminal mechanism is fragile on Windows. In Manim CE, 0.22.0 (2026-10-08) reworked the CLI. `-l/--live-preview` now opens the OpenGL live window (it replaced `--force_window`), `--write_to_movie` was removed and `-p` now opens the finished file for both renderers. `embed()` and `interactive_embed()` still exist but only work in a live OpenGL window with file output off, and they need IPython. `--enable_gui` (DearPyGui control panel) remains. CE 0.22.1 has no `--watch` flag.

### Cited Findings
- ManimGL: `manimgl <file> <Scene> -se <line>` opens an interactive IPython session at that line. `checkpoint_paste()` runs the clipboard contents, saving and restoring scene state keyed on a leading comment, with `skip` and `record` variants. — [3b1b/videos README](https://github.com/3b1b/videos) (via earlier notes)
- ManimGL releases: v1.7.2 (2024-12-13), v1.7.1 (2024-10-23), v1.7.0 (2024-10-16). The repo was last pushed 2026-09-09 and has 519 open issues and 96.6k stars. PyPI `manimgl` is still 1.7.2. — [GH API releases](https://github.com/3b1b/manim/releases); [PyPI API](https://pypi.org/project/manimgl/)
- A 3b1b/manim discussion notes that reloading a scene can require exiting IPython, which closes the window, and rerunning the command. — [discussion #2238 (mirror)](https://github.imc.re/3b1b/manim/discussions/2238) (search-result mirror; summary from the search tool)
- CE 0.22.0 (released 2026-10-08, PR #4966): "the OpenGL renderer now writes files by default, just like Cairo". `-l` / `--live-preview` "shows a live window (OpenGL)" and replaces `--force_window`. `-p` opens the finished file with either renderer. Removed: `--write_to_movie` (use `format = none`), `-g/--save_pngs` (now `--format png-sequence`), `-i/--save_as_gif` (now `--format gif`), `--custom_folders` and `--flush_cache` (now `manim cache clear`). New `--format auto|none|png|png-sequence|gif|mp4|webm|mov`. Several OpenGL fixes (#4929: OpenGL code paths skipped because the renderer comparison against "opengl" never matched; #4962; #5040 `set_camera_orientation` under OpenGL; #4953/#4955/#4956/#4957). PR #4976 makes custom renderers declare `capabilities`. — [CE 0.22.0 changelog](https://docs.manim.community/en/latest/changelog/0.22.0-changelog.html)
- Installed CE 0.22.1 CLI: `-l, --live-preview  Display frames in a renderer-provided live preview. With --format=auto, no media file is written.`; `--enable_gui`, `--gui_location`, `--fullscreen`, `--enable_wireframe`, `--renderer [cairo|opengl]`. No `--watch` or `--interactive_embed` option. — [local CE 0.22.1] `python -m manim render --help`
- CE source (0.22.1): `CairoRenderer` declares `RendererCapabilities(live_preview=False)` and `OpenGLRenderer` declares `live_preview=True`. Asking for `-l` with Cairo raises "does not support live preview". `-l` cannot be combined with `--dry_run` or last-frame PNG output. `--enable_gui` implies live preview. — [local CE 0.22.1] `manim/_config/render_session.py` lines 55–110, `renderer/cairo_renderer.py:40`, `renderer/opengl_renderer.py:544`
- CE `Scene.interactive_embed()` ("Like embed(), but allows for screen interaction") is disabled with a warning when media output is enabled, when no window exists, under `dry_run` or when `skip_animation_preview` is set. It starts an IPython `InteractiveShellEmbed` with manim and manim.opengl loaded and a `rerun()` helper. `embed()` warns "Called embed() while no live preview window is available" and is skipped while writing to a file. The DearPyGui panel is used only if `dearpygui` is importable and `enable_gui` is set. Neither IPython nor dearpygui is a default dependency (both were missing in this project's venv). — [local CE 0.22.1] `manim/scene/scene.py` lines 1419–1610

### Inferences
- In CE 0.22, `interactive_embed()` works only with `--renderer=opengl -l` and the default `--format auto`, which writes no file when `-l` is set. This follows from the checks in `check_interactive_embed_is_valid` and the `-l` help text; I did not test it on screen. The OpenGL renderer has long been CE's "experimental" path. The batch of OpenGL bug fixes in 0.22.0 (including code paths that were silently skipped) shows it was under-tested until recently, so treat it as usable for exploration but not as a polished GUI. Cairo-only features (for example some `ThreeDScene` behaviour) may differ.
- CE has no file-watching hot reload. "Re-render on save" comes from external tools (Sideview, Manim Viewer, Manim Cue, custom servers such as this project's `preview_server.py`).
- For ManimGL on Windows, the interactive workflow works best by typing `checkpoint_paste()` manually or through Sublime/Terminus. Clipboard-injecting VS Code extensions have reported failures there.

### Gaps
- I did not find the CE changelog entries for 0.19–0.21 about the OpenGL window, `--watch` (which existed in earlier CE versions per community memory) or `interactive_embed`, so I cannot say exactly when `--watch` was removed.
- I found no 2026 user reports (Reddit/Discord) on how stable CE `-l` or `interactive_embed` is on Windows.
- ManimGL's master-branch changes since 1.7.2 (relevant to `-se` behaviour) were not reviewed.

## Live reload / watch tools and browser preview servers

### Takeaway
No widely adopted standalone "manim-watch" tool exists. Live reload is delivered by editor extensions (above), a few tiny GitHub projects and engines that were designed for it. JAnim is the main Python alternative with a built-in live-refresh, scrubbable preview. It overlaps with the GUI tools, but it is a separate engine, not Manim.

### Cited Findings
- `manim-preview` on PyPI: v0.1.0 (2026-07-23), "a manim animation preview tool", Python ≥ 3.13, no homepage listed. `manim-interactive` on PyPI: v0.1.0 (2025-10-27), no summary. Both are effectively unknown packages. — [PyPI API manim-preview](https://pypi.org/project/manim-preview/); [PyPI API manim-interactive](https://pypi.org/project/manim-interactive/)
- `wenhaoquestion/Manim-live-preview` (11 stars, MIT, last push 2025-08-26; README not retrievable); `Baelyk/manim-watcher` (0 stars, 2025-07). — [GH API search "manim preview"/"manim watch"](https://github.com/search?q=manim+preview&type=repositories)
- `m4nd0r4s/kinemo` ("Explanatory animations in Python, with a live preview and a Rust core", 4 stars, Apache-2.0, 2026-11): another new engine, not Manim. — [GH API search](https://github.com/m4nd0r4s/kinemo)
- **JAnim** (jkjkil4): "Programmatic animation engine for creating precise and smooth animations with real-time feedback". 290 stars, MIT, pushed 2026-11-11, PyPI janim 5.0.3 (2026-11-11), Python ≥ 3.12. — [GH API](https://github.com/jkjkil4/JAnim); [PyPI API](https://pypi.org/project/janim/)
- `manim-livestream` (NeoPlato): "livestreaming configurations for Manim", PyPI 0.0.3 from 2021-10-03, Python < 4.0. Dead. — [PyPI API](https://pypi.org/project/manim-livestream/)
- `manim-studio` (PyPI 0.7.4, 2024-03-23, "A GUI for Manim", Python < 3.13). Stale and incompatible with Python 3.13. — [PyPI API](https://pypi.org/project/manim-studio/)

### Inferences
- Most people get "hot reload" from Sideview, Manim Viewer, MarkHoo's LiveView or Manim Cue in VS Code, or from Manim Notebook's file reload in ManimGL. A small custom HTTP server that re-renders on save (as in this project) is equivalent and editor-independent.

### Gaps
- I could not read the READMEs for `manim-preview` (PyPI) or `wenhaoquestion/Manim-live-preview`, so I cannot describe their features.
- GitHub searches for "manim live reload" and "manim hot reload" returned nothing, possibly because of rate limiting.

## Presentation GUIs: manim-slides, manim-presentation, Manim Editor and others

### Takeaway
manim-slides is the single maintained presentation tool. It supports both Manim CE and ManimGL (auto-detected) and offers a Qt presenter (PySide6 recommended) plus conversion to HTML/reveal.js and PowerPoint, an IPython magic and a Sphinx extension. Its predecessors (manim-presentation, Manim Editor) and the smaller reveal.js/pptx exporters are dead.

### Cited Findings
- **manim-slides** (jeertmans): repo 994 stars, MIT, 56 open issues, pushed 2026-11-16. PyPI v5.7.0 (2026-09-14), Python ≥ 3.10. The latest GitHub Release object is v5.6.0 (2026-04-15), so v5.7.0 is on PyPI but not published as a GitHub Release. — [GH API](https://github.com/jeertmans/manim-slides); [PyPI API](https://pypi.org/project/manim-slides/); [GH API releases](https://api.github.com/repos/jeertmans/manim-slides/releases)
- It "requires either Manim or ManimGL" and detects which one is installed. Recommended install: `pipx install -U "manim-slides[pyside6-full]"`. The docs note that the quotes are needed on Windows because of commas. — [installation.md](https://github.com/jeertmans/manim-slides/blob/main/docs/source/installation.md); [README](https://github.com/jeertmans/manim-slides)
- Features from the README and docs index: present with `manim-slides Scene1 Scene2`; `self.next_slide(loop=True)` loops a slide until the presenter continues; offline presenting with Qt, RevealJS or PowerPoint; HTML/RevealJS customisation; IPython magic; Sphinx extension; performance tips for large presentations. Requires "minimal modif. in scenes files" (subclass `Slide`). — [README](https://github.com/jeertmans/manim-slides); [docs](https://manim-slides.eertmans.be/latest/)
- **manim-presentation** (galatolofederico): 173 stars, GPL-3.0, last push 2022-12-15; PyPI 0.2.1 from 2021-06-28. Superseded by manim-slides. — [GH API](https://github.com/galatolofederico/manim-presentation); [PyPI API](https://pypi.org/project/manim-presentation/)
- **Manim Editor** (ManimCommunity/manim_editor): "Web Presenter for Mathematical Animations using Manim", 364 stars, MIT, last push 2024-07-17; PyPI 0.3.8 from 2021-12-19 (Python < 4.0). Abandoned. — [GH API](https://github.com/ManimCommunity/manim_editor); [PyPI API](https://pypi.org/project/manim-editor/)
- Small or dead alternatives: `manim-present` (FoamScience, config-based HTML presentations, 0.1.0 2024-12-11); `manim-revealjs` (1.0.2, 2021-11-27); `manim-pptx` (0.1.6, 2021-10-10); `manim-timeline` (0.0.3, 2024-07-30). — [PyPI API](https://pypi.org/project/manim-present/)
- Live-editing companions: the Alamin-H-M "Manim Slides Preview" VS Code extension (see first section) and `antoniomachuca/MCP-Manim-Slides` (an MCP server for building manim-slides presentations, 3 stars, 2026-09). Manimble (pachterlab, edits Manim slides, 7 stars, pushed 2026-11-13) is a GUI-editor overlap. — [GH API search](https://github.com/search?q=manim+preview&type=repositories); [earlier notes](forks_plugins_tools.md)

### Inferences
- For a Windows user on Manim CE 0.22, manim-slides with PySide6 is the only realistic presenter. I did not verify whether 5.7.0 was tested against CE 0.22's CLI changes (removed `--write_to_movie` and `--save_as_gif`, new `--format`). Since manim-slides wraps `manim render`, check this before relying on it.

### Gaps
- I did not read the manim-slides changelog for 5.7.0, so I cannot say whether it adds CE 0.22 compatibility.
- I did not compile the manim-slides issue tracker's Windows-specific problems.

## Interactive parameter tweaking (sliders, inspectors) while a scene runs

### Takeaway
Very few tools offer this. Manim CE's own `--enable_gui` gives a DearPyGui panel on the OpenGL live window (optional dependency, rarely documented). manim-marimo and manim-widget tie notebook controls to scenes. Manim Cue offers measurement and inspection, not live parameter editing. JAnim offers real-time refresh. I found no mature "sliders bound to scene variables" tool for Manim CE.

### Cited Findings
- CE 0.22.1 exposes `--enable_gui` ("Enable GUI interaction.") and `--gui_location`. The scene stops DearPyGui (`dpg.stop_dearpygui()`) at the end only when `dearpygui` imported and `enable_gui` is set, and `enable_gui` forces live preview (OpenGL). — [local CE 0.22.1] `render --help`; `scene/scene.py` around lines 1507 and 1596; `_config/render_session.py` line 63
- manim-marimo re-renders a ManimGL scene whenever a marimo notebook value (for example a slider) changes. — [README](https://github.com/peter-gy/manim-marimo)
- manim-widget is "truly interactive" in Jupyter and marimo through browser rendering with manim-web. — [README](https://github.com/rambip/manim-widget)
- Manim Cue: frame at a chosen time, timeline navigation, wipe or overlay frame comparison, coordinate measurement in scene units. — [Marketplace](https://marketplace.visualstudio.com/items?itemName=behackl.manim-cue)
- `mdda/manim-interactive` and `pprunty/manim-interactive` appear in ecosyste.ms listings, but I did not inspect them. — [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fmdda%2Fmanim-interactive)

### Inferences
- What CE's DearPyGui panel exposes (I believe it is mainly custom widgets that scenes register, plus playback controls) needs checking in the source or docs before recommending it. I did not read that code.
- For tweaking parameters on Windows today, the practical routes are: (a) constants at the top of the scene plus render-on-save with low-quality frames, (b) marimo with manim-marimo (ManimGL only), or (c) moving to an engine built for it (JAnim, or the non-Manim Motion Canvas).

### Gaps
- I did not verify the contents of the CE DearPyGui panel (widgets and controls).
- I did not inspect the mdda and pprunty manim-interactive repos.
- I did not do the YouTube, Reddit or Discord workflow survey because of the tool budget. I have no community sentiment data on which preview tool people prefer in 2026.
