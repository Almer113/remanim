# Experiment: recreate the "Essence of linear algebra preview" (3Blue1Brown, 2016)

**Goal:** stress-test our pipeline by recreating a real 3Blue1Brown video as close
to 1:1 as we legitimately can, and record what we learn.
Reference: youtube.com/watch?v=kjBOesZCoqc (5:09, 1080p, ~30 fps). Downloaded to
`reference/` with yt-dlp for private analysis only; not redistributed.

## Ground rules

| Element | Treatment | Why |
|---|---|---|
| Maths visuals, layout, colours, motion, timing | Match as closely as possible | Grant's scene code (3b1b/videos `_2016/eola/chapter0.py`) is CC BY-NC-SA 4.0, so a non-commercial adaptation with attribution is allowed. Our port carries the same license. |
| Narration | Our own script, written from scratch around each section's topic | The voiceover isn't covered by the code license. Used the transcript only for section timing and topics. |
| Pi creature characters | Replaced with an original character ("blob": rounded body, two eyes) | They're 3Blue1Brown's characters. |
| 3Blue1Brown logo intro | Neutral title card | Channel branding. |
| Dieudonné quote | Short excerpt (under 15 words) plus attribution | Keeps the quote brief. |
| Speech/thought bubble lines | Own wording | Same reason as the narration. |
| Chapter titles, equations | As in the source | Factual / mathematical content, from the licensed code. |
| Music | None | Not ours to use. |

## Shot list (reference timings, seconds)

Section boundaries come from `tools/analyze_reference.py` contact sheets,
together with a 10 fps scan for black gaps and change spikes. "Source" is the
class in chapter0.py.

| # | Scene (ours) | Start | End | Source | What's on screen |
|---|---|---|---|---|---|
| 1 | TitleCard | 0.0 | 4.3 | (logo) | neutral title card |
| 2 | OpeningQuote | 4.3 | 12.4 | OpeningQuote | quote paragraph top, green "linear algebra", yellow attribution writes in |
| 3 | UpcomingSeries | 12.4 | 17.0 | UpcomingSeriesOfVidoes | 10 video icons fade in left→right, blue gradient |
| 4 | AboutLinearAlgebra | 17.0 | 27.5 | show_dependencies | "Linear Algebra" left, yellow arrows fan to 5 subjects + vdots |
| 5 | TopicsBubble | 27.5 | 53.1 | to_thought_bubble | student + thought cloud cycles: matmul, det, cross, eigen; then confused "???" + Why?/cross↔Det/"eigen" questions |
| 6 | NumericVsGeometric | 53.1 | 70.8 | NumericVsGeometric + ExampleTransformation | green split lines, two headings, numeric product left, grid transform in a box right |
| 7 | GeometricHelpful | 70.8 | 81.3 | list_geometric_benefits | heading moves left + "is helpful for ...", student with matrix / light bulb / "So therefore..." |
| 8 | NumericToComputations | 81.3 | 85.6 | NumericToComputations | Numeric understanding ↓ Actual computations |
| 9 | LinAlgPyramid | 85.6 | 107.3 | LinAlgPyramid | 3 boxed layers write in, bottom greys out, red arrow to field names cycling |
| 10 | IntimidatingProf | 107.3 | 124.4 | IntimidatingProf | student + professor, name arrow Professor→Coworker, speech bubble, grid thought cloud, "???", student's matmul cloud |
| 11 | SineApproximations | 124.4 | 145.2 | SineApproximations | series top, green note, yellow sin(1), red sin(π/6) |
| 12 | LooseConnectionToTriangles | 145.2 | 154.7 | LooseConnectionToTriangles | sin(x) ↔ triangle, "?" |
| 13 | PhysicsExample | 154.7 | 177.3 | PhysicsExample | projectile parabola, velocity components, professor bubble "sin θ ≈ 0.7-ish" |
| 14 | LinearAlgebraIntuitions | 177.3 | 205.8 | LinearAlgebraIntuitions + Matrices/MatrixMult/Determinants | header + 3 intuitions each with matrix → grid transform |
| 15 | ProfessorsTry | 205.8 | 212.6 | ProfessorsTry | professor speech + det grid in thought cloud |
| 16 | ExampleMatrixMultiplication | 212.6 | 226.7 | NumericalMatrixMultiplication | step-by-step 2×2 product with circled entries |
| 17 | TableOfContents | 226.7 | 247.1 | TableOfContents | blue title, 10 chapters fade in, yellow note + arrow on ch. 3 |
| 18 | SeriesIntoBubble | 247.1 | 261.7 | series_of_videos | chapters morph to icons, student, 3D grid thought cloud |
| 19 | ResourceForTeachers | 261.7 | 270.3 | ResourceForTeachers | 3 students + professor speech bubble |
| 20 | AboutPacing | 270.3 | 272.8 | AboutPacing | "About pacing..." |
| 21 | DifferingBackgrounds | 272.8 | 282.8 | DifferingBackgrounds | label + arrow moves over 3 students |
| 22 | PauseAndPonder | 282.8 | 292.5 | PauseAndPonder | pause symbol + thought cloud |
| 23 | NextVideo | 292.5 | 309.3 | NextVideo | title + blue frame with vector-addition grid |

## Narration (ours; each line starts with its section)

1. — (no voice)
2. — (no voice)
3. A new series is on its way, and it's all about linear algebra.
4. Linear algebra underpins computer science, physics, engineering and statistics. Yet many students finish the course without really getting it.
5. In a typical class you learn recipes. Multiply these matrices. Compute that determinant. Use it to get a cross product. Solve for the eigenvalues. The procedures work, but the reasons stay hidden. Why is multiplication defined like this? What does a cross product have to do with a determinant? And what is an eigenvalue, really?
6. There are two ways to know this subject. One is numeric: you can carry out the operations. The other is geometric: you can picture what those operations do to space.
7. The geometric view tells you which tool fits a problem, why it works, and what the answer means.
8. The numeric view is what gets you the answer.
9. Skip the geometric layer, and the cracks might not show for a while. They show up later, when computer science, engineering, statistics, economics or pure maths start building on top of it.
10. Then you watch a professor, or a coworker, glance at a problem and know the shape of the answer at once. If you assume they're grinding through numbers in their head, it looks like magic, and it's a little discouraging.
11. Here's an analogy. Suppose sine had only ever been shown to you as this infinite sum. It is how calculators get their values, so it isn't wrong. You'd practise plugging in numbers and adding up terms.
12. Somewhere in the back of your mind, you'd know it relates to triangles, but no one ever showed you how.
13. Then physics comes along. Velocities split into sine and cosine parts, and your classmates estimate these values instantly. You'd decide they must be human calculators, and feel slow for needing to add up a series every time.
14. Linear algebra is a lot like that, except the fix is easy. A handful of visual ideas sit under the whole subject. A matrix moves space around. Multiplying matrices means doing one move after another. The determinant measures how much areas stretch. Once these click, the formulas start explaining themselves.
15. To be fair, good teachers do try to share this picture.
16. Yet courses spend most of their time on hand calculation, which computers now do for us. Our job is the concepts.
17. So here's the plan: a short series you can watch in one sitting, from vectors all the way to eigenvalues and abstract vector spaces. Chapter three is the one to look forward to.
18. Videos alone won't teach you the subject. What they can do is give you the right pictures, so the practice you do afterwards actually sticks.
19. Teachers can point students here for a quick visual refresher.
20. A word on pacing.
21. Some of you are reviewing, some are taking the course now, and some haven't started. One speed won't suit everyone.
22. So pause whenever you need to. Thinking it through on your own is where the learning happens.
23. Next up: vectors, and what they really are. See you there.

## Method

- **Timing lock:** each scene has a `TARGET` length taken from the reference.
  Visuals follow the reference's clock with `at(t)` (seconds into the scene).
  Narration is scheduled on the timeline without blocking (`say()` →
  `add_sound(time_offset=...)`), each line starting when the previous one has
  ended. `lock_to_target()` pads the scene to TARGET and warns on overrun.
- **Clipped grids:** linear-transformation grids drawn inside rectangles and
  thought clouds. In the original these were composited in an editor; we clip
  each grid line to the frame shape (rectangle or ellipse) analytically,
  every frame.
- **Comparison:** `tools/compare.py` renders side-by-side frames
  (reference | ours) at the same timestamps, per section and for the whole
  video.
- **Style:** black background. Text uses LaTeX (`Tex`) like 2016-era Manim, not
  Pango `Text`. Manim CE's default colour constants (BLUE_D, GREEN, YELLOW...)
  are the same palette 3b1b used.
- **Learnings** are recorded as we go in `docs/recreation_learnings.md`.
