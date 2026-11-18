# Manim: History and Core Versions (ManimGL, ManimCE, ManimCairo)

Research date: 14 November 2026. Live pages fetched for GitHub, PyPI and the docs show their state on that date. Older material is flagged as such.

## 1. Origins and key milestones (creation, open-sourcing, 2020 fork, ManimGL rename, PyPI names)

### Takeaway
Grant Sanderson started Manim in early 2015 as a personal Python graphics library for 3Blue1Brown. Developers forked it into Manim Community Edition in mid-2020. In early 2021 Grant merged his OpenGL `shaders` branch into master, and that version became "ManimGL". The pre-OpenGL code lives on as the `cairo-backend` branch and the `manimlib` PyPI package. Today the PyPI names are `manim` (Community), `manimgl` (Grant's) and `manimlib` (legacy Cairo).

### Cited Findings
- 3Blue1Brown began in early 2015 as a personal programming project. Grant wanted to practise coding and wrote a Python graphics library that became Manim. His first video went up on 4 March 2015. — [Wikipedia: Manim](https://en.wikipedia.org/wiki/Manim)
- Manim was "initially developed by Grant Sanderson in early 2015" and is MIT-licensed. Wikipedia gives no date for the open-sourcing. The repo has been public on GitHub at github.com/3b1b/manim. — [Wikipedia: Manim](https://en.wikipedia.org/wiki/Manim)
- The 3b1b FAQ says Manim began as a personal bundle of code, not a professionally maintained public tool. Nearly all channel animations are made with it. Clips are edited together in ordinary video-editing software, and the FAQ advises against syncing narration inside Manim. — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- In a demo with Ben Sparks, Grant described Manim as "a custom Python library... very bespoke". — [How I animate 3Blue1Brown (Ben Sparks demo) transcript](https://rosetta.to/u/3blue1brown/how-i-animate-3blue1brown-a-manim-demo-with-ben-sparks)
- Official ManimCE FAQ timeline:
  - Because it was built for personal use, Manim was hard for others to install.
  - In late 2019 Grant started faster OpenGL rendering on a `shaders` branch.
  - In mid-2020 developers forked the code into the community edition.
  - In early 2021 Grant merged `shaders` into master, and that version is ManimGL.
  - The pre-OpenGL version survives as the `cairo-backend` branch.
  — [docs.manim.community FAQ: Installation / Differences between versions](https://docs.manim.community/en/stable/faq/installation.html)
- PyPI names:
  - ManimCE is `manim`.
  - ManimGL is `manimgl`, with docs at 3b1b.github.io/manim.
  - ManimCairo, the old pre-OpenGL ManimGL, had its latest release published as `manimlib`. Rendering some of Grant's old projects may need the exact version from when the project was made.
  — [ManimCE FAQ](https://docs.manim.community/en/stable/faq/installation.html)
- The 3b1b/manim README says the fork happened in 2020. It aimed for more stability, better testing and friendlier onboarding. The README says the pip package is `manimgl`, "not `manim` or `manimlib`", and warns that mixing the install instructions of the two versions causes problems. — [GitHub 3b1b/manim](https://github.com/3b1b/manim)
- You can tell which version a scene targets from its import line:
  - `from manim import ...` means ManimCE.
  - `from manimlib import *` means ManimGL.
  - `from manimlib.imports import *` means early ManimCairo.
  — [ManimCE FAQ](https://docs.manim.community/en/stable/faq/installation.html)
- ManimCE is double-licensed under MIT. Copyright is held by 3blue1brown LLC (LICENSE) and by the Manim Community Developers (LICENSE.community). — [GitHub ManimCommunity/manim](https://github.com/ManimCommunity/manim)
- Wikipedia cites a source dated 19 May 2020 for the community project, which fits a mid-2020 fork. — [Wikipedia: Manim](https://en.wikipedia.org/wiki/Manim)
- ManimGL release timeline on PyPI:
  - 1.0.0 is listed on PyPI.
  - 1.2.0: 16 October 2021
  - 1.3.0: December 2021
  - 1.4.0: January 2022
  - 1.5.0: February 2022
  - 1.6.0 and 1.6.1: April 2022
  - 1.7.0 and 1.7.1: 23 October 2024
  - 1.7.2: 13 December 2024
  — [PyPI manimgl history](https://pypi.org/project/manimgl/#history)

### Inferences
- "ManimGL" was originally a nickname for the OpenGL `shaders` code. It became the official name once it was merged and published as `manimgl` on PyPI, which happened in 2021.
- The motivation was Grant's own workflow: practising code and making precise, programmatic math visuals for his videos. I found no direct quote of Grant giving his reasons beyond "personal project" and "bespoke".

### Gaps
- I could not confirm the exact date the GitHub repo went public. It is generally believed to have been public from early on, around 2015–2016, but I have no citation.
- I did not get Grant's stated motivation in his own words. The IAPS interview (Jan 2025) and Lex Fridman #118 cover it, but the excerpts I could reach did not include his answer.
- I did not find the exact date or first commit of the ManimCommunity fork. It is mid-2020 per the FAQ.

## 2. Technical differences: ManimGL vs ManimCE

### Takeaway
ManimGL renders with OpenGL in real time. It has an interactive preview window and IPython workflow: `self.embed()`, the `-se <line>` flag, and `checkpoint_paste()`, which Grant uses with Sublime Text. It keeps experimental features and does not document breaking changes. ManimCE uses Cairo as its default (stable) renderer and also has an OpenGL renderer. It adds documentation, tests, semantic-versioned releases and a reworked API. The two are not code-compatible.

### Cited Findings
- ManimGL is described as "more experimental features", and breaking changes between releases are not documented. ManimCE is "more stable, better tested, and better documented". — [ManimCE FAQ](https://docs.manim.community/en/stable/faq/installation.html)
- ManimGL interactive features (official quickstart):
  - Calling `self.embed()` at the end of a scene opens an IPython terminal after the animation, and `play` works as shorthand for `self.play`.
  - Running bare `manimgl` opens a window and an IPython shell together.
  - Window controls: scroll to move, `z` plus scroll to zoom, `s` plus the mouse to pan, `d` plus the mouse to rotate the 3D view, `q` to quit.
  - Configuration lives in `custom_config.yml` in the project and `manimlib/default_config.yml`.
  — [ManimGL quickstart](https://3b1b.github.io/manim/getting_started/quickstart.html)
- `checkpoint_paste()` re-runs copied code in the embedded shell. `checkpoint_paste(skip=True)` runs it without animating, and `checkpoint_paste(record=True)` renders the result to file. `manimgl scene.py MyScene -se 15` drops into interactive mode at line 15. The 3b1b/videos repo ships `sublime_custom_commands` with keybindings such as `manim_checkpoint_paste` that send highlighted code to the terminal; this needs the Terminus package. — [3b1b/videos mirror](https://code.amethyst.name/public-mirrors/3b1b-videos/src/commit/4df71d9ef3ad43c2008fa3b3f7abb53e2e3ab3eb); [community skill guide (non-official)](https://tessl.io/registry/skills/github/calesthio/OpenMontage/manimgl-best-practices)
- The imports differ (`from manim import *` vs `from manimlib import *`), and so do the CLI commands (`manim` vs `manimgl`). Tutorials written for one generally break on the other. — [QuantumSketch blog, May 2026 (secondary)](https://blog-quantumsketch.pages.dev/manim-ce-vs-manimgl/)
- ManimCE added tests, documentation and semantic versioning, and puts out predictable PyPI releases. ManimGL has the real-time interactive OpenGL window. — [QuantumSketch blog (secondary)](https://blog-quantumsketch.pages.dev/manim-ce-vs-manimgl/)
- ManimCE's core rewrite ("experimental" branch):
  - A tracker issue says the codebase was "very entangled" and that both renderers, mainly the OpenGL one, were "unmaintainable".
  - The goal is renderer-independent mobjects, with renderer-specific code moved into renderer classes.
  - The tracker targeted v0.20.0 for most tests passing on experimental and v0.21.0 for its release.
  — [search summary of ManimCommunity tracker issue](https://github.com/ManimCommunity/manim/wiki/Roadmap); [migration guide](https://jasongrace2282.github.io/manim-experimental-migration)
- An unofficial migration guide for the experimental branch (August 2024) says that branch makes OpenGL the default and removes Cairo. It also merges `OpenGLMobject` into `Mobject` and adds a renderer protocol for custom renderers. — [Manim experimental migration guide](https://jasongrace2282.github.io/manim-experimental-migration)
- ManimCE roadmap wiki (last edited January 2022, so old):
  - Main would be frozen for bugfixes, with work on an abstract renderer, a renderer-agnostic Scene and a shared Mobject class.
  - The `opengl_compatibility` / `ConvertToOpenGL` metaclass would be removed.
  - It records an experimental C++ OpenGL backend idea called "Maki".
  — [ManimCE Roadmap wiki](https://github.com/ManimCommunity/manim/wiki/Roadmap)
- ManimCE v0.22.0 (8 October 2026):
  - A single `format` option replaces several older output flags.
  - Video encoding is configurable.
  - A new `Manager` class coordinates rendering.
  - `--custom_folders` and `--flush_cache` were removed.
  v0.21.0 (10 August 2026) added Typst support for text and math via `manim[typst]` and parallel encoding of partial movie files. v0.19.0 (January 2025) switched `SceneFileWriter` from an ffmpeg subprocess to PyAV (`av`). — [ManimCE releases](https://github.com/ManimCommunity/manim/releases)
- Recent ManimGL work (August–September 2026) includes z-indexing handled in the renderer, VideoMobject and Sprite (#2521, 9 September 2026), dvisvgm failure handling, and a docs/CLI flag sync. — [3b1b/manim commits](https://github.com/3b1b/manim/commits/master)

### Inferences
- The `Manager` class in v0.22.0 and the PyAV switch in v0.19.0 suggest that pieces of the experimental-branch refactor are landing on main step by step. I found no confirmation of a single "experimental merged / 1.0" event.
- The following API differences come from prior knowledge and were not re-checked in this session:
  - ManimCE splits `Tex` (LaTeX text mode) from `MathTex` (math mode). ManimGL's `Tex` is math mode, and `TexText` handles text.
  - ManimCE renamed `ShowCreation` to `Create`.
  - ManimCE uses a `manim.cfg` / `config` object and `-p -ql` style quality flags. ManimGL uses YAML config and flags such as `-w` and `-o`.
  - ManimCE has a pytest-based graphical-unit-test suite and a plugin system (for example `manim-slides` and `manim-voiceover`, found via `manim plugins`). ManimGL has neither formally.

### Gaps
- I did not fetch an official side-by-side API mapping. The specific claims about Tex vs MathTex, ShowCreation vs Create, config and plugins come from prior knowledge, not from sources found this session.
- I could not confirm the current state of ManimCE's `--renderer=opengl` flag on main, or whether the experimental branch has been released or merged as of November 2026.

## 3. Current status (late 2026): versions, stars, activity, dependencies, Windows

### Takeaway
ManimCE is under active development with frequent releases, the latest being v0.22.1 (27 October 2026), and has about 42.5k stars. ManimGL has about 96.5k stars and saw an active master branch through August–September 2026. Its last PyPI release, though, is 1.7.2 from December 2024, so people who want current ManimGL install from git. There is no ManimCE 1.0 yet.

### Cited Findings
- 3b1b/manim (ManimGL), November 2026: about 96.5k stars, 7.9k forks, 958 watchers, 469 open issues and 50 open PRs, about 6,478 commits, MIT license. — [GitHub 3b1b/manim](https://github.com/3b1b/manim)
- ManimGL's most recent master commits run 15 August to 9 September 2026 (e.g., "Add VideoMobject and Sprite (#2521)" on 9 September 2026). — [3b1b/manim commits](https://github.com/3b1b/manim/commits/master)
- The latest `manimgl` on PyPI is 1.7.2 (13 December 2024). Before that came 1.7.0 and 1.7.1 in October 2024, and the gap back to 1.6.1 (April 2022) is about 2.5 years. — [PyPI manimgl](https://pypi.org/project/manimgl/#history)
- ManimGL requirements: Python 3.10+, FFmpeg and OpenGL, with LaTeX optional. Linux needs Pango dev headers. On Windows, install FFmpeg and MiKTeX, then `pip install manimgl`. macOS uses `brew install ffmpeg mactex`. — [GitHub 3b1b/manim README](https://github.com/3b1b/manim)
- ManimCommunity/manim, November 2026: about 42.5k stars, 3.3k forks, MIT license. It has a Docker image (`manimcommunity/manim`) and an online Jupyter environment at try.manim.community. Most developers use `uv`. — [GitHub ManimCommunity/manim](https://github.com/ManimCommunity/manim)
- ManimCE releases:

  | Version | Date | Notes |
  |---|---|---|
  | v0.19.0 | 20 January 2025 | |
  | v0.19.1 | 1 December 2025 | |
  | v0.19.2 | 17 January 2026 | Python 3.14 support; minimum Python raised to 3.11 |
  | v0.20.0 | 20 February 2026 | `MathTex` rewrite, `Mobject.always`, `--seed` |
  | v0.20.1 | 27 February 2026 | |
  | v0.21.0 | 10 August 2026 | Typst support |
  | v0.22.0 | 8 October 2026 | |
  | v0.22.1 | 27 October 2026 | Pillow 13 fixes |

  The release page shows no years. I inferred them from version order and the docs version. — [ManimCE releases](https://github.com/ManimCommunity/manim/releases); [docs show v0.22.1](https://docs.manim.community/en/stable/faq/installation.html)
- ManimCE's recommended install path uses `uv`:
  1. `uv python install`
  2. `uv init manimations && cd manimations && uv add manim`
  3. `uv run manim checkhealth`

  LaTeX is optional: MiKTeX on Windows, MacTeX on macOS, TeX Live on Linux, or a TinyTeX subset. Typst comes bundled through `uv add "manim[typst]"`. On Windows, if a Microsoft Visual C++ error appears, install the C++ Build Tools ("Desktop development with C++"). macOS needs `brew install cairo pkg-config`. Linux builds ManimPango from source and needs Pango and Cairo dev headers. — [ManimCE uv install docs](https://docs.manim.community/en/stable/installation/uv.html)
- Since v0.19.0, ManimCE uses PyAV instead of calling an external ffmpeg subprocess. — [ManimCE releases](https://github.com/ManimCommunity/manim/releases)
- In January 2025 a community developer on r/manim said there was momentum on the experimental branch but "no concrete timeline". — [r/manim v0.19.0 thread (mirror)](https://lr.us.psf.lt/r/manim/comments/1i5s5eb/manim_community_v0190_has_been_released/m8c1c9t/?context=3)

### Inferences
- Because ManimCE uses PyAV, a separate system FFmpeg install is likely no longer required. The uv install page does not list FFmpeg. ManimGL still requires FFmpeg.
- Star counts favour ManimGL (about 96.5k vs 42.5k), but that reflects the 3Blue1Brown brand and the age of the repo, not current user share.
- ManimCE ships roughly every 1–3 months. ManimGL's PyPI releases are rare and irregular even though its git history is active.

### Gaps
- No public release, date or roadmap for ManimCE 1.0 was found. Whether the experimental branch has merged is unconfirmed.
- I did not get exact contributor counts or the last-commit date for ManimCE.
- I could not determine whether a ManimGL release after 1.7.2 exists on GitHub Releases. PyPI shows none.

## 4. Community: Discord, docs, governance, sponsors, Summer of Code

### Takeaway
ManimCE is community-governed, with an elected Steering Council and an OpenCollective for funding. Its community runs through the Discord (manim.community/discord), r/manim, @manimcommunity on Twitter, and the docs at docs.manim.community. ManimGL has no formal governance: it is Grant's project, with docs at 3b1b.github.io/manim.

### Cited Findings
- ManimCE community channels: Discord at manim.community/discord, Reddit r/manim, Twitter @manimcommunity, and the website manim.community. Help is offered through Discord and Reddit, and bugs go to GitHub issues. — [GitHub ManimCommunity/manim](https://github.com/ManimCommunity/manim)
- Governance and funding (as of January 2022, old): "A new governance scheme is in effect" with an elected Steering Council. Funding goes through OpenCollective, and the only cost listed was the domain. Paid developers were a "distant goal". — [ManimCE Roadmap wiki](https://github.com/ManimCommunity/manim/wiki/Roadmap)
- A GitHub Sponsors link appears in the repo's navigation, but the README names no sponsors. — [GitHub ManimCommunity/manim](https://github.com/ManimCommunity/manim)
- Grant's version is "a testing ground for new ideas while making videos". — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)

### Inferences
- ManimCE seems to run on volunteers, with a small OpenCollective budget and no corporate sponsor I could find.

### Gaps
- I found no evidence that ManimCE has taken part in Google Summer of Code, under NumFOCUS or otherwise. I also found no grants and no current sponsor list.
- I did not find Discord member counts or the current Steering Council membership.

## 5. Which should a newcomer pick?

### Takeaway
Every official source points newcomers to ManimCE (`pip install manim` / `uv add manim`): the ManimCE docs, Grant's own 3b1b FAQ, and the ManimGL README's framing. Pick ManimGL only to match Grant's exact code or interactive workflow. Pick ManimCairo or `manimlib` only to render old (2019-and-earlier) 3b1b projects.

### Cited Findings
- The ManimCE docs recommend "the community maintained version especially for beginners". They suggest ManimGL if you want an exact match to Grant's work and don't need stability or documentation, and ManimCairo mainly for projects from 2019 and earlier. — [ManimCE FAQ](https://docs.manim.community/en/stable/faq/installation.html)
- Grant's FAQ says "Anyone looking to get started with Manim should probably start with this Community Edition." It also suggests Desmos or GeoGebra for people who want a GUI, and scripting Blender or After Effects for mostly non-mathematical animation. — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- The ManimGL README says the community fork aims for more stability, better testing and friendlier onboarding. It also warns that code in older 3b1b/videos scenes may not run on the latest version. — [GitHub 3b1b/manim](https://github.com/3b1b/manim)
- A secondary 2026 blog says: use ManimCE for tutorials and community help, and ManimGL to follow 3b1b videos or for the interactive OpenGL preview. — [QuantumSketch blog](https://blog-quantumsketch.pages.dev/manim-ce-vs-manimgl/)
- On r/manim, the answer to running both was to keep them in separate virtual environments. — [r/manim thread (mirror)](https://reddit.birdcat.cafe/r/manim/comments/1jmhb7a/is_it_possible_to_have_manim_community_and)

### Inferences
- The consensus is clear and consistent across sources, including Grant himself: ManimCE for learning, ManimGL for 3b1b-style live iteration once you are comfortable reading source code.

### Gaps
- I did not reach an r/manim or Discord thread with broad community sentiment. The consensus above comes from official docs and the FAQ, not from polling users.
