# Creator Toolchains: What 3Blue1Brown and Other Educational YouTubers Use to Animate

Research date: 2026-11-14. "Confirmed" = stated by the creator or their own repo/site. "Inferred/unverified" = my reasoning or background knowledge that I could not source in this session. Search budget was limited (~20 calls), so coverage of the long tail of channels is thin; see Gaps.

## 3Blue1Brown (Grant Sanderson): exact workflow, tools, team

### Takeaway
Grant animates with his own ManimGL (3b1b/manim), installed from source, driven interactively from Sublime Text (Terminus plugin + custom commands) through `manimgl file.py Scene -se <line>` and `checkpoint_paste()`. Manim only produces clips that he edits in conventional video-editing software. By 2026 3Blue1Brown is a small studio with several animators and illustrators, and the videos repo now ships a `CLAUDE.md` for Claude Code.

### Cited Findings
**Engine and version**
- The 3Blue1Brown FAQ calls Manim "a custom open-source Python library I've written" (github.com/3b1b/manim). Grant says his version is "probably best viewed as a testing ground where I try to quickly put new things together while developing videos", and he tells newcomers to "start with this Community Edition." — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- The FAQ points people who prefer a GUI or less friction to Desmos or GeoGebra. It also names Mathematica, matplotlib, Processing, Shadertoy, Blender and After Effects as other programmable or animation tools. — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- The 3b1b/videos repo holds the Manim scenes for 3B1B videos and uses 3b1b/manim, not Community Edition. It tells users to install `manimgl` from source because "the latest published release is out of date." It also warns that older projects may depend on older versions of manim. No version number is pinned. — [3b1b/videos README](https://github.com/3b1b/videos)
- The repo's `CLAUDE.md` says: "This repository uses the 3b1b version of Manim, not ManimCommunity". It tells Claude to use `Tex()` rather than `MathTex()` and describes `stage_scenes.py`, Dropbox for assets and output, and a `custom_config.yml` that renders at 4K/30fps. Its code-style rules say to build VGroups declaratively and to use `.arrange()`/`.next_to()` instead of hand-computed coordinates. — [3b1b/videos CLAUDE.md](https://raw.githubusercontent.com/3b1b/videos/master/CLAUDE.md)

**Interactive workflow**
- `manimgl <file> <Scene> -se <line_number>` opens an interactive iPython session, similar to a debugger, at that line. `checkpoint_paste()` runs whatever code is on the clipboard. If the pasted code starts with a comment, the first run saves the scene state, and later runs with the same comment restore that state before executing. There are `skip` variants (all run_times set to 0) and `record` variants (render to file). — [3b1b/videos README](https://github.com/3b1b/videos)
- Sublime Text setup: install the Terminus package, then copy `sublime_custom_commands` into `Packages/User/`. The suggested keybindings are: `shift+super+r` → `manim_run_scene`, `super+r` → `manim_checkpoint_paste`, `super+alt+r` → `manim_recorded_checkpoint_paste`, `super+ctrl+r` → `manim_skipped_checkpoint_paste`, `super+e` → `manim_exit`, `super+option+/` → `comment_fold`. — [3b1b/videos README](https://github.com/3b1b/videos)
- "How I animate 3Blue1Brown | A Manim demo with Ben Sparks" (Oct 12, 2024, about 54 min) shows the tool and workflow behind the animations, including a hello-world scene and a Lorenz attractor. The accompanying post says the workflow "depends on a couple of Sublime plugins." — [3B1B lesson page](https://www.3blue1brown.com/lessons/manim-demo/); [3B1B Substack, 2024-10-12](https://3blue1brown.substack.com/p/how-i-animate-3blue1brown)

**Editing, audio, music**
- Grant on editing: Manim "is just a tool for making individual clips to be edited together later. You should certainly use traditional video-editing software for as much as you can." — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- Grant on audio: "get a good microphone and learn how to use it." He also admits "an embarrassing number of 3Blue1Brown videos have terrible audio." — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- His livestream setup post lists a Rode lavalier mic, a Focusrite Scarlett Solo interface and OBS. This is for livestreams, not necessarily for regular videos. — [3B1B blog: livestream setup](https://3blue1brown.com/blog/livestream-setup) (as summarized by search results)
- Vincent Rubinetti wrote almost all of the music. Grant wrote the piano pieces for the Linear Algebra and Calculus series. — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)

**Team and collaborators (from FAQ, current at time of fetch)**
- Current team: Grant Sanderson; Paul Dancstep (animation and writing); Ashley Hamer Pritchard (operations); Vincent Rubinetti (music and web development); Aaron Gostein (animation); Nishad Deulkar (animation); Mitchell Zemil (illustration and animation); Claire Vermillion (illustration and animation). — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- Past contributors: James Schloss (Summer of Math Exposition); Quinn Brodsky (filming and research for the barber-pole videos); Dawid Kołodziej (turning long-form videos into shorts); Kurt Bruns (video art); Josh Pullen, River Way and Vivek Verma (written and interactive lessons); Sridhar Ramesh (winding number and Wallis product videos); Ben Hambrecht (Basel problem and Pi Day 2018). — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- Ben Eater built Criblate (criblate.com), the community subtitle and translation site. Ben Eater is not an animator for the channel. — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)
- Grant contributed visuals to the documentary "A Trip to Infinity", which won an Emmy for graphic design and art direction. — [3Blue1Brown FAQ](https://www.3blue1brown.com/faq)

### Inferences
- Several dedicated "illustration and animation" hires suggest that some recent 3B1B visuals are made outside Manim, by hand or in conventional illustration tools. No source says which tools those team members use.
- The `CLAUDE.md` and the Dropbox/4K30 config show that by 2026 the repo is set up for AI-assisted Manim coding. This is the clearest public evidence of how Grant's current pipeline is configured.
- The Pi creatures ship as SVG assets with the manim/videos code (background knowledge, not re-verified this session).

### Gaps
- I found no creator statement naming his editing NLE (Final Cut, Premiere or DaVinci Resolve). It stays unconfirmed. Do not assert one.
- The microphone model for regular (non-livestream) videos was not found.
- I found no source on whether the newer animators use ManimGL, After Effects, Blender or something else.
- The exact ManimGL version Grant runs: install from master/source per the README. I did not verify the latest PyPI release number.

## Summer of Math Exposition (SoME): entrants' tools and statistics

### Takeaway
No official breakdown of the tools SoME entrants used exists. The 3B1B results posts report entry counts and formats, not software.

### Cited Findings
- SoME1 (2021) received more than 1,200 submissions in mixed formats: videos, blog posts, interactive pages, games and notebooks. The results page names no animation software. — [SoME1 results](https://www.3blue1brown.com/blog/some1-results)
- SoME1 winners: "That weird light at the bottom of a mug — ENVELOPES"; "Hiding Images in Plain Sight: The Physics Of Magic Windows" (Matt Ferraro); "The Beauty of Bézier Curves" (Freya Holmér, per background knowledge); "What Is The Most Complicated Lock Pattern?"; "Pick's theorem: The wrong, amazing proof". — [SoME1 results](https://www.3blue1brown.com/blog/some1-results)
- Search summaries put SoME1 at more than 1,300 entries (this conflicts slightly with the "over 1,200" above) and say peer review narrowed SoME2 to a top 105. SoME3 video entries had about 7M combined views, with roughly 100 entries above 10k views. — [3B1B SoME pages via search](https://3blue1brown.substack.com/p/some3-results); [SoME2](https://www.3blue1brown.com/blog/some2)
- Prize information for SoME4 exists. — [SoME4 Prizes](https://3blue1brown.substack.com/p/some4-prizes)

### Inferences
- Freya Holmér's winning Bézier video was made in Unity with Shapes (see below), so a top SoME1 entry was not made with Manim.

### Gaps
- No survey or statistic on tool usage among SoME entries (Manim vs Motion Canvas vs After Effects, etc.) was found.

## Other creators: confirmed and likely toolchains

### Takeaway
Programmatic tools are concentrated among the math and CS explainers: ManimGL (Welch Labs, older Reducible), Manim CE (newer Reducible), Motion Canvas (aarthificial, Polylog's Tomáš Sláma), Unity (Freya Holmér, Sebastian Lague, Primer's current pipeline) and Blender with Python (old Primer). Studio-style channels like Kurzgesagt use Illustrator and After Effects. For many channels I found no creator statement.

### Cited Findings
- **Reducible:** The repo holds the code for the channel's videos. Newer videos use Manim Community Edition and older ones an old 3b1b/manim. The author modified the manim source for the graph-theory videos. — [nipunramk/Reducible](https://github.com/nipunramk/Reducible)
- **Welch Labs (Stephen Welch):** The animations are "scenes generated using the library Manim", specifically the 3Blue1Brown version, not Community. Stephen Welch also mixes overhead hand-drawn graphics with digital animation. — [WelchLabs/videos](https://github.com/WelchLabs/videos) (via search summary)
- **Welch Labs freelance Manim animator role:** requires 3+ years of Python and 1+ year of Manim. Freelancers work from storyboards and "submit animations as pull requests to Welch Labs animation github repo". — [Welch Labs job page](http://www.welchlabs.com/freelance-manim-animator)
- **Welch Labs designer/editor role:** lists Adobe Illustrator, After Effects and Premiere. — [Welch Labs editor job](http://www.welchlabs.com/editor) (via search summary)
- **Vcubingx (Vivek Verma):** The repo holds the source for the channel's videos. The author describes it as messy, for reference only, and not a good way to learn Manim. — [vivek3141/videos](https://github.com/vivek3141/videos)
- **Primer (Justin Helps):** The original pipeline "primer" / "primerpython" was a Python library for building and animating objects in Blender. Its Bobject class adds keyframes, and it runs through the Script Runner add-on with TeX and dvisvgm. Much of its structure comes from manim. The archived repo says the author has moved to **primerunity** and that the old code is unsupported. — [Helpsypoo/primerpython](https://github.com/Helpsypoo/primerpython)
- **Kurzgesagt:** The studio's own "How to Make a Kurzgesagt Video in 1200 Hours" says illustration is done in Adobe Illustrator (about 200 panels on average) and animation in After Effects with rigged characters. It also mentions experiments with Cinema 4D. Gigazine (2020) reports that animation takes 8–12 weeks with 2–3 animators and up to 1,200 hours for a ~9-minute video. — [Kurzgesagt video transcript](https://rosetta.to/u/kurzgesagt/how-to-make-a-kurzgesagt-video-in-1200-hours); [Gigazine 2020](https://www.gigazine.net/gsc_news/en/20200217-science-animation-making/)
- **Kurzgesagt** sells an official Skillshare course on its After Effects and Illustrator motion-graphics workflow. — [Skillshare](https://www.skillshare.com/en/classes/Motion-Graphics-with-Kurzgesagt-%E2%80%93-Part-1/631970755)
- **Freya Holmér:** Her math animations are made in Unity with Shapes, her own vector-graphics library for Unity. Video credits also cite Mathfs, her math library, and custom procedural animation tools. — [acegikmo.com/shapes](https://acegikmo.com/shapes); [search summary of her video transcript](https://patronhunt.com/freya-holmer)
- **aarthificial (Motion Canvas creator):** Motion Canvas is a TypeScript library for animated videos, created by the game-dev YouTuber aarthificial for his own videos. It is MIT-licensed, uses generator-function scenes, has a browser editor backed by Node with live preview, and exports through FFmpeg. — [Medium overview](https://medium.com/@hhartleyjs/animations-in-javascript-with-motion-canvas-2a61fce7d66f) (secondary source)
- **Polylog (Tomáš Sláma, co-creator):** On 4 Oct 2024 he wrote that he is moving from Manim to Motion Canvas, citing "severe MBS (Manim Burnout Syndrome)" and Motion Canvas's live preview. He plans to work with the Polylog team to produce videos faster. He had previously written a Manim tutorial series. — [slama.dev/motion-canvas/1](https://slama.dev/motion-canvas/1/)
- **Artem Kirsanov:** His video "How I Make Science Animations" covers After Effects, Python modules and Blender, including 3D neuron activity and brain models. — [Class Central listing](https://www.classcentral.com/course/youtube-how-i-make-science-animations-205178)

### Inferences
- **Sebastian Lague:** His Coding Adventures are visibly built and rendered in Unity, and his repos are Unity projects (background knowledge, not sourced this session).
- **Veritasium, Numberphile, minutephysics, Vsauce, PBS Space Time, Steve Mould, etc.:** These appear to be live-action channels with conventional NLE editing and (for Veritasium and PBS Space Time) hired motion-graphics animators. I found no creator-confirmed tool lists.
- A practical pattern emerges: solo math creators pick a code tool (ManimGL, Manim CE, Motion Canvas or Unity) for precise animation and still use a conventional editor plus Adobe tools for assembly (Welch Labs states this explicitly).

### Gaps
- No sourced tool information was found for these channels: Mathologer (Keynote is often rumoured; unconfirmed), Numberphile, Veritasium, minutephysics, Zach Star, Steve Mould, Vsauce, Ten Minute Physics, Aleph 0, Domain of Science, Morphocular, Jacob Bryant, Looking Glass Universe, PBS Space Time, Up and Atom, Two Minute Papers, Acerola, StatQuest, Andrej Karpathy, Polymathematic, Mathemaniac, Serpentine Integral, Kuvina Saydaki, and Javis users. They need per-channel follow-up (video descriptions, about pages, Patreon posts).
- The current state of Primer's Unity pipeline (the primerunity repo) was not directly checked.
