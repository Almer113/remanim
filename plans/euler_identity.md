# Why e^(iπ) = −1

**Purpose:** a ~75 s narrated video, made **in the studio** (Claude driving
the browser pane) as the first real use of the studio after Phase 6. Every
place where the studio is slow, awkward, wrong or missing something is
logged under "Studio friction" at the end; that list feeds Phase 7.

**Audience:** someone who knows e^x and has heard of i, but finds
e^(iπ) = −1 magic. No calculus beyond "the rate of change of e^t is e^t".

**Studio features it should exercise:** new file from the template, the
code skeleton, dragging objects, timing edits on the timeline, colour and
number edits in the inspector, narration lines (`+ line`), captions,
equation edits, a moving point with an updater, export joined at `-ql`
then `-qh`, the narration check.

## Maths (checked)

- Multiplying by i turns a point a quarter turn about 0:
  1 → i → −1 → −i → 1.
- e^t is the function whose rate of change equals itself: velocity =
  position. On the real line, a point at 1 runs away faster and faster.
- e^(it): by the chain rule, d/dt e^(it) = i·e^(it). So the velocity is
  the position turned a quarter turn: always at right angles to the
  radius, and of length |e^(it)|.
- Starting at 1 (length 1), the velocity is perpendicular and length 1, so
  the point stays on the unit circle and moves at speed 1. After time t it
  has walked an arc of length t, so e^(it) = cos t + i sin t.
- Half the circle has length π, so after t = π the point is at −1:
  e^(iπ) = −1.
- Check with small steps: (1 + iπ/n)^n → e^(iπ). Its length is
  (1 + π²/n²)^(n/2): n = 8 → 1.78, n = 16 → 1.35, n = 64 → 1.08. So the
  step spirals start outside the circle and close in on −1. (n = 4 gives
  2.61, too big for the frame at our scale; start at 8.)

Scale: 1 unit of the complex plane = 1.6 frame units in beats 2–5 (unit
circle radius 1.6; the n = 8 spiral reaches 2.85, inside the safe area
when the plane is centred slightly right).

## Colour ledger

| Thing | Colour |
|---|---|
| the moving point e^(it), its radius | `ACCENT` (blue) |
| velocity arrow, the "i ×" turn | `ACCENT_2` (orange) |
| the arc walked, the length π | `GOOD` (green) |
| −1 (the destination) | `GOOD` once reached, `FG` before |
| plane grid, axes labels | `MUTED`; real and imaginary axes `FG` |
| text | `FG`; inactive parts dimmed to `MUTED` |

The equation keeps these colours wherever it appears: `e`, `i`, `π`
plain `FG` except π in `GOOD` once it means the arc length.

## Beats (one Scene each, `TimedScene` with `TARGET`)

| # | Scene | ~s | On screen (region) | Narration (spoken → caption) |
|---|---|---|---|---|
| 1 | `Hook` | 8 | e^(iπ) = −1 large (main); then shrinks to the title region | "E to the I pi equals minus one. Why on earth would that be true?" → "e^(iπ) = −1. Why on earth would that be true?" |
| 2 | `TimesI` | 12 | complex plane (main, centred right); point at 1 jumps a quarter turn three times: i, −1, −i, each with an orange curved arrow "× i" | "Multiplying by I turns a point a quarter turn around zero." → "Multiplying by i turns a point a quarter turn." |
| 3 | `Velocity` | 14 | left: real line with a point at 1 running right, arrow "velocity = position" growing (left). Right: the plane, point at 1, orange velocity arrow straight up, label "velocity = i × position" (right) | "E to the T grows at its own size. E to the I T moves at its own size, turned a quarter turn." → "e^t moves at its own size; e^(it), turned a quarter turn." |
| 4 | `Walk` | 16 | the plane (main): the point walks the unit circle with its velocity arrow always at right angles, green arc trailing, a timer "t = 0.00" (footer-right); stops at t = π on −1, arc labelled "π" | "Always sideways, always speed one, so it walks around the circle. After time pi, it has walked half way: to minus one." → "Always sideways, speed 1: it walks the circle. After π, it's halfway: at −1." (two lines) |
| 5 | `Steps` | 14 | the plane (main): step spirals (1 + iπ/n)^n for n = 8, 16, 64, each replacing the last, label "n = 8" (top-right of plane); the circle dimmed under them | "Take the walk in small straight steps, and the steps close in on minus one." → "Small straight steps close in on −1 too." |
| 6 | `Takeaway` | 10 | e^(iθ) = cos θ + i sin θ (main), then θ → π morphs into e^(iπ) = −1 with −1 in green | "In general, E to the I theta is cos theta plus I sin theta. Put in pi, and you land on minus one." → "e^(iθ) = cos θ + i sin θ. Put in π: −1." |

Total ≈ 74 s. Captions: one line each, ≤ 70 characters, on screen for at
least len/15 + 0.3 s. Voice `en-US-AndrewNeural` at −5% (the house voice).

## Check plan

`check_layout.py` and `frames.py` per beat; `audio_check.py` on the scenes
and on the joined video; export joined at `-ql` in the studio, then `-qh`
when the low-quality version is approved.

## Studio friction (filled in while building)

Each entry: what I tried, what happened, how bad (blocks / slows /
cosmetic), and whether it was fixed on the spot or left for Phase 7.

Built 2026-11-20, Claude driving the studio in the browser pane (1440×900).

What I did in the studio: created the file (New file), shortened six
pauses and one walk (`run_time`) on the timeline, moved a label made by a
helper, scaled a plane made by a helper, undid an accidental edit, and
exported all six scenes joined at `-ql` with the narration check. What I
did in code: the skeleton (six scenes, the plane, updaters, spirals, the
narration lines), the loop's spacing, the `TARGET`s, and splitting one
`play()` in two.

| # | What happened | How bad | Done |
|---|---|---|---|
| 1 | **The UI crashed** ("Cannot read properties of undefined (reading '4')") when the file was saved outside the studio while a clip was selected: during the re-trace the scene is a stub with no `clips`, and `App.tsx` read `scene.clips[sel.clip]` without the pending check that the code 75 lines later has. The error screen worked (the file was safe, Reload fixed it). | blocks | **Fixed:** `App.tsx` and `Inspector.tsx` guard pending scenes; re-tried the same way, no crash, selection kept |
| 2 | **The ◂ ▸ arrows next to "1/6" reorder scenes**, not navigate them. I clicked ▸ expecting the next scene; it wrote `SCENES = ["TimesI", "Hook", …]` into the file. Undo restored it byte for byte. They sit exactly where prev/next buttons usually are. | slows, surprising | Phase 7: arrows navigate; reorder moves to a menu or drag in the dropdown |
| 3 | **New file uses `window.prompt`**: the browser pane doesn't support it (the click silently did nothing; console: "prompt() is not supported"), and it looks foreign in any browser. | blocks in the pane | Phase 7: an in-app dialog (worked round with a stub here) |
| 4 | **No way to add a scene class.** The template makes one scene; a six-beat video needs six, and a shared base class. | slows | Phase 7: "+ scene" (a copy of the current scene's base, empty `construct`) |
| 5 | **`TARGET` can't be edited.** Shortening pauses left the scene padded to the old `TARGET`; the padding shows as "timed by library code (line None)", locked. Had to edit six `TARGET`s in code. | slows | Phase 7: the TARGET chip edits it; offer "fit to content"; fix "line None" |
| 6 | **A fade-out could land mid-sentence without warning.** Shortening `Walk`'s last pause put `fade_all()` before the narration ended; only the timeline's narration lane showed it. | quality risk | Phase 7: warn when objects leave while a line is still playing, or snap pause ends to the narration end |
| 7 | **A computed `at()` looks editable, then refuses** ("the at() time is computed (1.2 + 3.2 * k) … change it in the code"). Clear message, but only after typing. | cosmetic | Phase 7: show such fields read-only with the reason |
| 8 | The canvas is small at this size when the timeline has many lanes; a 0.3-unit label was a few pixels wide, so I selected it from Layers instead. No way to give the canvas more room. | slows | Phase 7: a draggable splitter between canvas and timeline |
| 9 | Clicking an empty spot in a timeline lane doesn't move the playhead (only the ruler does); clicking a lane's name doesn't select its object. | cosmetic | Phase 7 |
| 10 | Layers said "Nothing selectable on screen" while a frame's objects were still loading. | cosmetic | Phase 7: "loading…" |
| 11 | After a scale edit the inspector still showed "scale = 1"; the helper-made label's shift was written as `0.2419 * LEFT`. | cosmetic | Phase 7: round moves to 2 decimals |
| 12 | `check_layout.py` crashed once on an empty LaTeX SVG while the studio traced the same file (not reproducible; both use their own TeX folders). | watch | left; note if it comes back |
| 13 | The New file button's accessible name is its tooltip, not its label, so assistive tools (and the pane's `find`) don't see "New file". | cosmetic | Phase 7 |

What worked well, worth keeping:
- Timing edits on the timeline were quick and exact; every one was
  verified by a replay, the narration and later clips rippled, and the
  toast showed the code change (`self.at(13.4) → self.at(7.5)`).
- Edits on objects made by helpers went to the right place: a `.shift()`
  or `.scale()` chained on **this** call of `get_label()` / `get_plane()`,
  not inside the helper, and the toast named the other objects that moved
  with it (radius, rule, dot, arrow).
- Outside edits were picked up within seconds ("changed outside the
  studio; reloaded"), keeping the selection.
- Undo of the accidental reorder was byte-exact.
- The narration lane (waveform plus caption) made dead air obvious at a
  glance; that's what found the pacing problems.
