# GUI-based, non-code and interactive alternatives to Manim for math and science explainers (as of Nov 2026)

Research budget: about 15 searches. Most pricing figures come from third-party aggregators (Toolradar, BityClips, Capterra, G2) that disagree with each other, so treat them as indicative and check vendor pages. Tools I could not verify inside the budget are listed under Gaps, with notes from prior knowledge clearly marked as unverified.

## Q1. Which tools do educational YouTubers use (Kurzgesagt, TED-Ed, Veritasium, minutephysics)?

### Takeaway
The only big channel with a well-documented pipeline is Kurzgesagt: illustrations drawn in Adobe Illustrator, animated in Adobe After Effects, and more recently some Cinema 4D. I found no primary sources naming the software used by TED-Ed, Veritasium or minutephysics. Across the industry, Illustrator plus After Effects is the default for illustrated explainers, and Manim is the niche choice for the 3Blue1Brown style of precise math.

### Cited Findings
- Kurzgesagt animates in Adobe After Effects and has begun experimenting with Cinema 4D (from a transcript of their "How to Make a Kurzgesagt Video in 1200 Hours" video). — [Rosetta transcript](https://rosetta.to/u/kurzgesagt/how-to-make-a-kurzgesagt-video-in-1200-hours); [Gigazine](https://gigazine.net/gsc_news/en/20200217-science-animation-making)
- Kurzgesagt's illustrators work in Adobe Illustrator, and an animator (Stephan) animates the art in After Effects. Scenes are split into hundreds or thousands of parts and imported into AE. — [Toolfarm](https://www.toolfarm.com/?p=77543)
- Kurzgesagt sells an official Skillshare class, "Motion Graphics with Kurzgesagt", that teaches After Effects animation of Illustrator assets at 60 fps. — [Skillshare](https://www.skillshare.com/en/classes/motion-graphics-with-kurzgesagt-part-1/631970755)
- A 2014 list on the channel's YouTube page (quoted in an Adobe forum post) named Illustrator CS6, After Effects CS6 and Avid Pro Tools 10. This is historical. — [Adobe Community](https://community.adobe.com/questions-652/how-to-animate-like-kurzgesagt-on-youtube-using-illustrator-flash-776370)
- minutephysics: Henry Reich makes his own animations, often as time-lapse drawings. The episode list includes a tutorial on "using After Effects to Simulate the Universe", which shows he has used AE at least once. — [LiveScience](https://livescience.com/55121-youtube-channel-minute-physics.html); [TheTVDB episode list](https://www.thetvdb.com/series/minutephysics/allseasons/official)
- TED-Ed pairs educators with independent animators and studios, so tools vary from video to video. Generic guides on the "TED-Ed style" recommend After Effects. — [GraphicMama](https://graphicmama.com/blog/how-cartoon-animation-ted-ed/)

### Inferences
- For "illustrated science" explainers (Kurzgesagt, TED-Ed), the standard stack is vector art in Illustrator, animation in After Effects, and sometimes C4D or Blender for 3D. Manim's niche is precise, mathematically defined motion such as graphs, transforms and equation manipulation.
- Kurzgesagt's figure of roughly 1,200 hours per video shows how much manual labor the GUI keyframe approach takes for rich illustrated work.

### Gaps
- I found no primary source on the tools Veritasium's animators use (Veritasium credits several freelance animators) or on TED-Ed's per-studio tools.
- I found no 2025–2026 interview confirming Kurzgesagt's current tools beyond After Effects, Illustrator and C4D.

## Q2. How do GUI tools handle LaTeX equations and precise mathematical motion?

### Takeaway
LaTeX in GUI tools is mostly bolted on. The usual routes are: render LaTeX to PDF/SVG and import it as vectors (After Effects, Illustrator, Inkscape), use a dedicated plugin (AnyTex for AE/Premiere, LaTeX Text Generator for Blender), or use a built-in equation editor (Keynote supports LaTeX/MathML). None of these gives Manim-style automatic glyph matching between equations (TransformMatchingTex). Precise motion means expressions (AE), drivers or Geometry Nodes (Blender), or procedural tools (Cavalry, a free GUI procedural motion tool). In practice these become semi-code workflows.

### Cited Findings
- **After Effects, AnyTex** (by Streamline, sold on aescripts): animates LaTeX formulae "of any complexity" in a handwriting style inside AE and Premiere Pro. It is Windows-only, users call it expensive, and one user reported poor animation quality in the trial on AE 2022 (unresolved). — [aescripts Streamline author page](https://aescripts.com/authors/streamline/); [aescripts forum](https://aescripts.com/forums/discussion/2547/anytex)
- **After Effects, free workaround:** compile LaTeX to PDF, import the PDF into AE as a composition, then animate the vector paths. Adobe forum users have suggested this since 2019, because no font lets you type equations directly. — [Adobe Community](https://community.adobe.com/t5/after-effects-discussions/type-math-equations-in-after-effects/td-p/10816932)
- **After Effects, math expressions:** the open-source tl_math plugin (crazylafo) lets you write math expressions and GLSL inside AE. — [GitHub AE_tl_math wiki](https://github.com/crazylafo/AE_tl_math/wiki)
- **Blender, LaTeX Text Generator** (extensions.blender.org, by katterkie/kstrenkova): makes 3D text objects from LaTeX (equations, formatted text, tables) and is aimed at "technical visualizations and math animations". It is GPL, needs no external LaTeX install, and v1.1.0 (May 2026) supports Blender 4.2 LTS and newer. — [Blender Extensions](https://extensions.blender.org/add-ons/latex-text-generator/); [GitHub](https://github.com/kstrenkova/mathematical-equations)
- **Blender, Blender_math_anim** (free): plots math expressions with parameter sliders and supports sin, cos, exp and similar functions. — [docs](https://westneighbor.github.io/Blender_math_anim/usage_functions/)
- **Blender, other add-ons:** a "Math Formula" extension exists on extensions.blender.org. Animatext (paid, Superhive/Blender Market) does procedural, math-driven text and object animation, not LaTeX. Mathsurf (paid) generates and animates parametric surfaces. — [Math Formula](https://extensions.blender.org/add-ons/math-formula); [Animatext](https://superhivemarket.com/products/animatext-procedural-animations); [Mathsurf](https://superhivemarket.com/products/mathsurf%E2%80%93parametric-surface-generator&animator-for-blender/docs)
- **Keynote:** has native math typesetting (since 2018) through an equation dialog that takes LaTeX or MathML. The output is a PDF image in STIX fonts, so it behaves as an image, not as editable text. — [Apple Support](https://support.apple.com/it-ch/guide/keynote/tan72a69d01f/14.0/mac/1.0); [U. Oregon guide](https://pages.uoregon.edu/noeckel/Keynote.html)
- **Keynote Magic Move** automatically animates the differences between two slides. Apple Education publishes math lessons built with it, for example breaking shapes apart and re-forming them, and manipulating formulas to solve for x. — [MacMost](https://macmost.com/how-to-animate-in-keynote-using-magic-move.html); [Apple Education: formula video](https://education.apple.com/resource/250011577); [Apple Education: Transformations of Functions](https://education.apple.com/resource/250012657)
- **PowerPoint Morph** animates movement, color changes and words or characters moving between slides. It needs PowerPoint 2019, Microsoft 365 or the web version. — [Microsoft Support](https://support.microsoft.com/en-us/PowerPoint/training/use-the-morph-transition-in-powerpoint)
- **Final Cut Pro:** an Apple Discussions thread asks for a LaTeX plugin, which suggests there is no native support. — [Apple Discussions](https://discussions.apple.com/thread/255702792?page=1)
- **GeoGebra:** exports animated GIFs from a slider (File > Export > Graphics View as Animated GIF) and supports a scripted ExportImage() command for GIF or multi-page PDF. — [GeoGebra demo](https://www.geogebra.org/m/zkx7cc4p); [Digital Mathematics blog](https://digitalmathematics.blogspot.com/2020/10/maths-gifs-parabolas.html)
- **Desmos:** native export is a static image only (Share > Export Image). The third-party GIFsmos tool turned Desmos sliders into GIFs (2015) and may no longer work. Screen recording is the practical route. — [Aperiodical](https://aperiodical.com/2015/07/gifsmos/); [OSU ASC](https://ascode.osu.edu/desmos-easy-and-powerful-online-tool-graphing-and-visual-representations-mathematics)
- **Manim vs After Effects:** Manim's positions and relationships come from code ("no 'close enough' positioning") and are reproducible. AE suits ad-hoc creative work, live-action compositing and particles. These sources promote Manim-based products, so they are not neutral. — [QuantumSketch](https://blog-quantumsketch.pages.dev/manim-vs-generative-video/); [Open Source Alternatives](https://www.opensourcealternatives.to/item/manim)

### Inferences
- Keynote and PowerPoint (Magic Move, Morph) are the cheapest no-code way to get Manim-like "equation morphs", but equations are images (Keynote) or OMML objects (PowerPoint). They interpolate whole objects, not glyph by glyph, unless the creator splits the equation into separate pieces by hand.
- Blender has become the strongest free GUI option for math once LaTeX and plotting add-ons are installed. Precise motion still needs drivers, Python or Geometry Nodes.

### Gaps
- I did not verify current AnyTex pricing, other AE LaTeX tools (e.g. "LaTeX for AE"/"Mathfx"-type scripts), or whether AE's Motion Tools, Duik or Overlord help with math. From prior knowledge (unverified): Overlord (Battle Axe) transfers Illustrator layers to AE, Duik is a free rigging toolkit, and Motion Tools Pro is a free/paid keyframe utility. None is math-specific.
- I did not verify the PowerPoint equation editor's LaTeX input mode, which Microsoft 365 is believed to support (unverified).
- I did not find a Blender add-on called "Math Anim" by that name. The closest match is Blender_math_anim.

## Q3. Pricing, licensing, platform and status in 2026 (catalog)

### Takeaway
The free or open-source options are Blender (5.0 released Nov 2025), GeoGebra, Desmos, Inkscape, Synfig, OpenToonz, Krita and DaVinci Resolve (free tier). Mid-priced options are Cavalry (free Starter, paid tier about $20–24/mo), Jitter (free, paid from about $12–19/mo) and Rive (free, paid from about $14/mo, unverified). Adobe is the most expensive: After Effects about $22.99/mo, Creative Cloud Pro about $69.99/mo. Whiteboard tools like VideoScribe run about $25–43/mo. AI generators are mostly freemium with usage caps.

### Cited Findings
**Adobe After Effects / Illustrator (Win/Mac, subscription)**
- After Effects single app costs about US$22.99/mo (annual plan billed monthly). Creative Cloud Pro (which replaced All Apps in 2025, with a price rise) costs about $69.99/mo and includes 4,000 Firefly credits a month. The teams price for AE is about $37.99/mo. Adobe raised prices in 2023 (+9%) and 2025 (+6.1%). I found no confirmed 2026 increase; a 5–8% rise in 2026–27 is a forecast only. — [design-offset](https://design-offset.com/adobe-after-effects-pricing); [Toolradar CC pricing](https://toolradar.com/tools/adobe-creative-cloud/pricing); [CO/AI](https://getcoai.com/news/adobe-raises-creative-cloud-prices-14-with-new-ai-powered-pro-plan/); [pricey.jp](https://www.pricey.jp/web/articles/4660)

**Cavalry (Scene Group; procedural 2D motion design; Win/Mac)**
- It has a free "Starter" plan ("Free forever", no credit card). The Professional plan is listed at $20.16/mo billed monthly (Toolradar, citing the vendor page, Oct 2026). BityClips lists Pro from $24/mo. — [Toolradar](https://toolradar.com/tools/cavalry/pricing); [BityClips](https://bityclips.com/tool/cavalry/pricing)

**Jitter (browser-based, Figma-like motion design)**
- It has a free plan with watermark and resolution limits (third-party sources say 720p30, 3 workspace files, export to video, GIF or Lottie). Paid prices conflict: Studio $12/editor/mo (Toolradar reading the official page, Oct 2026) versus Pro $15–19/mo elsewhere. Annual billing is about 34% cheaper. — [Toolradar compare](https://toolradar.com/compare/jitter-vs-motionity); [Jitter Help](https://help.jitter.video/en/articles/14809073-choose-a-paid-plan-that-s-right-for-you); [MakerStack](https://makerstack.co/reviews/jitter-review/); [BityClips](https://bityclips.com/tool/jitter/pricing)

**Rive (interactive, state-machine vector animation; web editor plus runtimes)**
- It is free, with Pro from about $14/mo according to one aggregator (unverified). — [BityClips (via Jitter search)](https://bityclips.com/tool/jitter/pricing)

**Blender (free, GPL; Win/Mac/Linux)**
- Blender 5.0 was released on 18 Nov 2025, adding HDR and wide-gamut color, ACES workflows and an overhauled Video Sequencer. Grease Pencil gained motion blur, per-point corner types and a new Pen tool in Edit Mode. A 5.0.1 point release followed. — [Blender dev release notes: Grease Pencil 5.0](https://developer.blender.org/docs/release_notes/5.0/grease_pencil/); [It's FOSS](https://itsfoss.com/news/blender-5-0-release/); [CG Channel](https://www.cgchannel.com/?p=171940); [Neowin](https://www.neowin.net/software/blender-501/)

**Keynote (free, Apple only) / PowerPoint (Microsoft 365 subscription)**
- Keynote has native LaTeX/MathML equations and Magic Move. PowerPoint Morph requires 2019, M365 or the web version. — [Apple Support](https://support.apple.com/it-ch/guide/keynote/tan72a69d01f/14.0/mac/1.0); [Microsoft Support](https://support.microsoft.com/en-us/PowerPoint/training/use-the-morph-transition-in-powerpoint)

**GeoGebra / Desmos (free, web)**
- GeoGebra exports animated GIFs from sliders. Desmos exports static images only. — see Q2 sources.

**VideoScribe (Sparkol; whiteboard animation; desktop)**
- Prices vary by source: about $25–43/mo monthly, about $168/yr annual, with a one-off purchase option (about $665) and a free trial. A mid-2026 review says it renders locally and lacks the AI generation features of newer tools. — [Capterra](https://www.capterra.com/p/182209/VideoScribe/pricing/); [G2](https://g2.com/products/videoscribe/pricing); [Tekpon](https://tekpon.com/software/videoscribe/pricing/); [Tool Directory](https://tooldirectory.ai/tools/videoscribe-animated-video-maker); [VideoScribe pricing](https://www.videoscribe.co/pricing/)

**NotebookLM Video Overviews (Google; free with tiered caps)**
- It offers three formats. "Explainer" is structured and in-depth, in 80+ languages. "Brief" was added in Oct 2025. "Cinematic" launched in Mar 2026 and turns uploaded documents into fully animated, narrated videos. Explainer and Brief use Nano Banana illustrations in six styles: Watercolor, Papercraft, Anime, Whiteboard, Retro Print and Heritage. Sources disagree on whether Cinematic is paywalled. Cinematic and custom styles are limited to users 18+. One blog (unverified) lists daily caps of Free 3, Plus 6, Pro 20 and Ultra 100–200. — [Google blog](https://blog.google/technology/google-labs/video-overviews-nano-banana/); [Google support](https://support.google.com/notebooklm/answer/16454555); [9to5Google](https://9to5google.com/2025/10/13/notebooklm-video-overviews-styles/); [Analytics Vidhya](https://www.analyticsvidhya.com/blog/2026/03/notebooklm-cinematic-video-overviews/); [buildfastwithai](https://www.buildfastwithai.com/blogs/notebooklm-cinematic-video-overview-full-guide-2026)

**AI tools that generate Manim behind the scenes (2025–2026)**
- Hosted: Codewords "Educational Manim Video Generator" (Claude writes the script, Perplexity adds examples, then it outputs Manim code; you need your own Manim setup to render). Anim Lab AI (prompt to Manim code to rendered video in about 1 minute for (a+b)^2). Manim AI (solo developer, covered Apr 2026). CortexSolver and LVM Video Engine (Hugging Face spaces). — [Codewords](https://www.codewords.ai/templates/educational-manim-video-generator); [ScriptByAI](https://www.scriptbyai.com/math-educational-video); [TrendHunter](https://www.trendhunter.com/trends/manim-ai); [CortexSolver](https://cortexsolver-main.hf.space/)
- Open source and research: Manim-Studio, rohitg00/manim-video-generator (MIT), TheoremExplainAgent (TIGER-AI-Lab), Code2Video, Manimator, and LLM2Manim (arXiv 2604.05266, Apr 2026, "pedagogy-aware"). A Jan 2026 paper (arXiv 2601.13453) notes "Manim code hallucinations" and LaTeX issues in LLM-generated Manim. — [creativeainews](https://www.creativeainews.com/blog/manim-studio-prompt-to-math-animation/); [sourcepulse](https://www.sourcepulse.org/projects/28985781); [TEA](https://sharedcontext.ai/plugins/external/TIGER-AI-Lab/theoremexplainagent-tea); [arXiv 2604.05266](https://arxiv.org/abs/2604.05266); [arXiv 2601.13453](https://arxiv.org/pdf/2601.13453); [arXiv 2502.19400 (TheoremExplainAgent)](https://arxiv.org/pdf/2502.19400)
- A text-to-clip tool, EduViz, produces short silent math clips that download as GIF or WebP. — [There's An AI For That](https://theresanaiforthat.com/ai/eduviz/)
- QuantumSketch (a vendor of Manim-based AI) argues that Manim beats generative video for math because generative models cannot guarantee correct geometry or text. This is a vendor claim. — [QuantumSketch](https://blog-quantumsketch.pages.dev/manim-vs-generative-video/); [QuantumSketch 2026 list](https://blog-quantumsketch.pages.dev/best-ai-math-animation-tools-2026/)

### Inferences
- Notable 2026 trend: "GUI or AI front end, Manim back end". LLM agents write Manim code, which gives non-coders Manim's precision. Code hallucinations and LaTeX errors remain the known failure modes.
- Generative video models (Sora, Veo, Runway) and NotebookLM suit B-roll and conceptual illustration, not exact equations or plots. Treat their output as non-authoritative for mathematical content.

### Gaps (not verified within budget; prior-knowledge notes marked unverified)
- **DaVinci Resolve / Fusion:** not verified. Prior knowledge (unverified): the free Resolve includes the Fusion node compositor, Studio is a one-time ~$295, and Resolve 20 shipped in 2025.
- **Apple Motion / Final Cut Pro:** not verified. Prior knowledge (unverified): one-time $49.99 and $299.99 (Mac only). Apple also launched a Creator Studio subscription bundle in early 2026; its status and pricing were not checked.
- **Lottie/LottieFiles, Canva, Animaker, Vyond, Doodly, Explain Everything, Mathcha, Inkscape, Synfig, OpenToonz, Krita, Moho, Toon Boom, Apple Grapher, Mathematica, Synthesia, HeyGen, Sora, Veo, Runway, Desmos Studio:** current 2026 pricing and status were not checked. Prior knowledge (unverified):
  - Free/open source: Inkscape, Synfig, OpenToonz and Krita. Inkscape has a built-in LaTeX render extension (pdflatex required). Synfig and OpenToonz are 2D animation tools with no math tooling.
  - Paid 2D/character animation: Moho (Lost Marble; Debut and Pro, perpetual licenses) and Toon Boom Harmony (subscription). Both are character-animation tools rarely used for equations.
  - Commercial animation and whiteboard tools: Vyond and Animaker are template-driven business animation tools (Vyond was $50+/mo). Doodly is a whiteboard tool. Explain Everything is an interactive whiteboard that records lessons. Canva has basic animation and a LaTeX "Math equations" app.
  - Math tools: Mathcha is a web WYSIWYG math editor with diagram export, not animation. Apple Grapher (bundled with macOS) can animate parameters and export movies. Mathematica's Manipulate/Animate can export video and has native typesetting (expensive license). Desmos Studio is the Desmos PBC entity (graphing calculator); I found no native video export.
  - AI video: Synthesia and HeyGen produce AI avatar presenter videos (subscription) that can front an explainer but not build math animations. Sora 2, Veo 3.x and Runway Gen-4 produce cinematic B-roll; OpenAI announced shutting down the standalone Sora app in 2026 (status unverified).
- No Reddit threads came back from searches comparing Manim and AE, so community sentiment is not represented.

## Q4. Pros and cons of GUI tools vs code-based (Manim)

### Takeaway
GUI tools win on artistic freedom, illustration quality, compositing, iteration speed for non-programmers, and industry-standard handoff (AE/Illustrator). Manim wins on mathematical exactness, reproducibility, version control, cost (MIT, free), and automatic equation and glyph transforms. Hybrid workflows are common: render Manim or LaTeX output, then composite in AE, Resolve or Premiere. Blender plus add-ons, Cavalry, and AE expressions sit in the middle.

### Cited Findings
- Manim is MIT-licensed and free. AE costs about $22.99/mo per seat. Manim's Python and LaTeX setup "can be non-trivial" on Windows and older Linux. — [QuantumSketch](https://blog-quantumsketch.pages.dev/manim-vs-generative-video/); [Medium/TDS](https://medium.com/data-science/how-to-create-slick-math-animations-like-3blue1brown-in-python-457f74701f68)
- Manim has been described as "a programmable After Effects for mathematicians". AE is preferred for live-action compositing, particles and non-math motion graphics. — [Open Source Alternatives](https://www.opensourcealternatives.to/item/manim)
- Kurzgesagt-style GUI production is labor-intensive (about 1,200 hours per video, according to the channel's own account). — [Gigazine](https://gigazine.net/gsc_news/en/20200217-science-animation-making)
- GUI LaTeX support is plugin-dependent: Windows-only and costly in AE (AnyTex), an add-on in Blender, image-only in Keynote. — see Q2 sources.
- LLM-generated Manim has known hallucination and LaTeX failure modes. — [arXiv 2601.13453](https://arxiv.org/pdf/2601.13453)

### Inferences
- Rough recommendation map:
  - **Precise math (graphs, proofs, equation derivations):** Manim, or AI-to-Manim generators with human review.
  - **Illustrated science stories:** Illustrator plus After Effects (or Affinity, Inkscape, Blender as free substitutes).
  - **Teachers with no budget:** Keynote Magic Move or PowerPoint Morph, plus GeoGebra GIFs and screen recording of Desmos.
  - **Free 3D or 2D with math:** Blender with LaTeX Text Generator, plus drivers or Geometry Nodes.
  - **Quick narrated summaries:** NotebookLM Video Overviews. Accuracy for math is unverified.
- Interactive output (Rive, Jitter/Lottie, GeoGebra, Desmos applets) is a distinct advantage over Manim's video-only output when the goal is explorable explainers rather than YouTube videos.

### Gaps
- I found no quantitative survey of tool usage among educational YouTubers.
- I found no independent (non-vendor) head-to-head comparison of Manim and GUI tools from 2025–2026.
