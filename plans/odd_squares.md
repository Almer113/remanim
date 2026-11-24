# Odd numbers make squares

**Purpose:** a ~1 min narrated video, made **in reManim** (Claude driving
the browser pane) as the exit check of Phase 7 (step F16). It should use
the Phase 7 features on real work, and every place where the studio is
slow, awkward, wrong or missing something goes under "Studio friction" at
the end. That list feeds the exit report (`studio/docs/phase7/exit_report.md`).

**Audience:** anyone who can add. No algebra needed until the last beat,
and there only n and n².

**Studio features it should exercise** (Phase 7 step in brackets):
- the New file dialog with the voice off (A2);
- "+ scene" four times, after the current scene and at the end (B3);
- the `TARGET` field, including "fit" (B4);
- `+ line` in a silent scene, which asks to turn the voice on (B5);
- the mid-sentence warning when a fade-out lands inside a line (C6);
- snapping pause ends to the end of a narration line (C7);
- read-only computed fields (D8);
- scale and move values in the Inspector (D9);
- the canvas/timeline splitter (D10);
- timeline clicks (D11);
- Undo served from the frame cache (E13);
- the scene arrows and PageUp/PageDown (A1);
- export joined at `-ql`, then `-qh`, with the narration check.

## Maths (checked)

- The k-th odd number is 2k − 1: 1, 3, 5, 7, … (k = 1, 2, 3, 4).
- Partial sums: 1 = 1², 1 + 3 = 4 = 2², 1 + 3 + 5 = 9 = 3²,
  1 + 3 + 5 + 7 = 16 = 4². Check further: the first 10 odd numbers
  (up to 19) add to 100 = 10².
- Why: an n × n square of dots grows into an (n + 1) × (n + 1) square by
  adding an L-shaped layer around two sides. The layer has n dots along
  the top, n down the side and 1 in the corner: 2n + 1 dots, which is the
  (n + 1)-th odd number. And (n + 1)² − n² = 2n + 1 agrees.
- So 1 + 3 + 5 + ⋯ + (2n − 1) = n² for every n ≥ 1 (induction, drawn).

Layout: dots of radius 0.09, spacing 0.6, so a 4 × 4 square is 1.98 wide;
the 6 × 6 square in beat 4 uses spacing 0.5 (2.68 wide). The square's
bottom-left dot stays fixed while it grows, so each layer is added on the
top and the right.

## Colour ledger

| Thing | Colour |
|---|---|
| dots already in the square | `ACCENT` (blue) |
| the newest L-shaped layer, and its "+3", "+5", "+7" | `ACCENT_2` (orange) |
| the two sides n of a layer | `ACCENT_2`; their braces and "n" labels `FG` |
| the corner dot, "+1" | `GOOD` (green) |
| the square totals 1, 4, 9, 16 and n² | `GOOD` |
| sums and other text | `FG`; earlier lines dimmed to `MUTED` |

The odd numbers keep orange wherever they appear in an equation, and the
squares keep green.

## Beats (one Scene each, `Beat(TimedScene)` with `TARGET`)

| # | Scene | ~s | On screen (region) | Narration (spoken → caption) |
|---|---|---|---|---|
| 1 | `Sums` | 10 | four lines appear one at a time in a column (main): 1 = 1, 1 + 3 = 4, 1 + 3 + 5 = 9, 1 + 3 + 5 + 7 = 16; then the totals turn green and "= 1², 2², 3², 4²" slides in beside them | "Add up the odd numbers: one, then one plus three, then one plus three plus five." → "Add up the odd numbers: 1, then 1 + 3, then 1 + 3 + 5." / "Every total is a square. Why?" → same |
| 2 | `Layers` | 16 | left: one dot, then an orange L of 3 makes a 2 × 2 square, then 5 makes 3 × 3, then 7 makes 4 × 4, each layer turning blue as the next arrives. Right: the running sum, one term per layer, "+3" etc. in orange | "Start with one dot. Wrap three around it, and you have a two by two square." → "One dot. Wrap 3 around it: a 2 × 2 square." / "Five more make three by three. Seven more make four by four." → "5 more: 3 × 3. 7 more: 4 × 4." |
| 3 | `WhyOdd` | 14 | main: an n × n square (n = 4, dimmed), its next layer in orange with braces "n" on the top row and "n" on the side, the corner dot green with "+1"; then "n + n + 1 = 2n + 1" (right), "an odd number" under it | "Each new layer covers one side, then the other, then the corner." → "Each layer: one side, the other side, the corner." / "That's N plus N plus one: always the next odd number." → "n + n + 1: always the next odd number." |
| 4 | `General` | 12 | left: a 6 × 6 square with its layers alternating blue and orange; right: 1 + 3 + 5 + ⋯ + (2n − 1) = n², each odd term lighting up with its layer | "Keep going, and the first N odd numbers always fill an N by N square." → "The first n odd numbers always fill an n × n square." |
| 5 | `Takeaway` | 8 | the square fades; the equation moves to the middle, n² in green; underneath, small: "1 + 3 + ⋯ + 19 = 100" | "One plus three, all the way to nineteen, is a hundred: ten squared." → "1 + 3 + … + 19 = 100 = 10²." |

Total ≈ 60 s. Captions: one line each, at most 70 characters, on screen
for at least len/15 + 0.3 s. Voice `en-US-AndrewNeural` at −5% (the house
voice), switched on through `+ line` in `Sums`, since the file starts
silent. Spoken text spells out letters with capitals ("N plus N") so the
voice says them.

## How it's built

- In the studio: the file (New file), the five scene classes (+ scene),
  every narration line (+ line), every `TARGET`, the timing (pauses,
  `run_time`s, snapping to line ends), positions, scales and colours.
- In code, as for Euler: the `Beat` base with the house caption look, the
  `get_*` helpers (dot square, L-shaped layer, the sum lines), loops over
  layers, and anything the studio locks (updaters). Each such edit is
  logged with why it had to be code.
- Undo in the studio is used at least once after a timing edit, to check
  E13 on real work.

## Check plan

`check_layout.py` and `frames.py` for each beat; `audio_check.py` on the
scenes and on the joined video; export joined at `-ql` in the studio,
then `-qh` once you approve the low-quality version.

After the video (the rest of F16): the full test suite, the corpus run,
the clip and drag benches against Phase 6, E15's frame-time measurement
(needs the browser pane visible), and the exit report.

## Studio friction (filled in while building)

Each entry: what I tried, what happened, how bad (blocks / slows /
cosmetic), and whether it was fixed on the spot or left open.

Built 2026-11-22, Claude driving reManim in the browser pane (1440×900).
Result: 5 scenes, 53.0 s joined (`media/odd_squares_full_l.mp4`), 9
narration lines, `audio_check.py` ok on every scene and the joined file.

What I did in the studio: created the file (New file dialog, voice off,
`TARGET` 10); added four scenes (+ scene, three "after this scene", one
"at the end"); the first narration line, which asked for the voice and
set it on `Beat` in the same edit; six timing edits (four pauses typed,
one "end of line" button, one deliberately mid-sentence and undone); one
`TARGET` fit; Undo and Redo three times; one scale in the Inspector;
the splitter; a seek by clicking a lane; the export joined at `-ql` with
the narration check. What I did in code: the `Beat` base with the caption
look, the helpers (dot layers, sums, the general equation), every
`construct()` body, the captions on each line, and the sizes after the
first contact sheets (maths at 36 read too small).

| # | What happened | How bad | Done |
|---|---|---|---|
| 1 | **`+ line` has no caption field.** The caption is the spoken text, so "one plus three plus five" would be captioned in words; the house rule wants "1 + 3 + 5". I added `caption=` to all nine lines in code. | slows | open: a caption field in the `+ line` popup (and on the narration clip in the Inspector) |
| 2 | **Edge TTS failed intermittently** ("No audio was received"): two retries on the first line, and once all four attempts in `check_layout.py`. The studio showed "Verifying the edit by replaying the scene…" for ~45 s with no sign it was waiting on the voice service. | slows | open: say "synthesising narration (retry 2/4)" while it waits |
| 3 | **"End at: end of line" was offered on a computed pause** (`self.at((2.4, 6.4, 9.4)[k - 1])`), next to the greyed "computed" field; clicking it was refused. | cosmetic | **fixed:** `Inspector.tsx` hides the buttons when the pause is read-only; checked in the pane |
| 4 | **The Inspector still read "scale 1" after a scale edit.** The edit chained `.scale(0.9)` onto the object's last placement statement (`eq.shift(UP * 0.5)`), but step 9 only read `.scale()` chained on the constructor or a helper call. | cosmetic, misleading | **fixed:** `project.py` also reads the placement / scale / rotate statements (`moves.transform_calls`, each call counted once); unit tests added; the pane shows 0.9 |
| 5 | The undo toast reads "undo: TARGET 13.47 → 12.97": it names the edit being undone, so the arrow points the opposite way to what just happened. | cosmetic | open: "undo: TARGET back to 13.47" |
| 6 | **Layers lists every dot.** In `WhyOdd` all VGroups start expanded (40+ rows of "square · Dot"); the eq was far down the list. The two captions show as unnamed "Text" rows. | slows | open: groups start collapsed; captions hidden or named "caption" |
| 7 | After `+ line` set the voice, the template's comment stayed: `VOICE = "en-US-AndrewNeural"  # set a voice to narrate`. | cosmetic | open: drop or reword the comment when the voice is set |
| 8 | "End at" lists only line ends after the pause starts, so a trailing pause after the last line offers nothing, and "a beat after the line" always means typing. | cosmetic | open: idea, "end of line + 0.5 s" |
| 9 | After `serve.py restart` (to load fix 4) the Undo history was gone, as documented. | note | by design |
| 10 | **The `-qh` export warned "render the low-quality version first"** although the 480p15 export of the same file had passed. The server had restarted at logon in between, and the dialog only remembers exports held in memory. "Export anyway" worked: 5 scenes in about 2.5 min, joined, narration check passed. | cosmetic, misleading | open: also count a low-quality render on disk that is newer than the file |

What worked well, worth keeping:
- **New file → + scene → + line** made a five-scene, narrated skeleton
  without touching the code, and the voice question set `VOICE` on the
  base in the same undo step as the line.
- **Ripple moves `TARGET`** with the pause, and the toast says so
  ("ripple: TARGET 16 → 13.47"); "fit" then trimmed the last 0.5 s.
- **The "end of line" button** put a fade exactly on the end of a line
  in one click (`self.at(13.4) → self.at(11.04)`).
- **The mid-sentence warning** fired on the deliberate case, in the
  toast and on the clip ("FadeOut ends 1.0 s before the line … does");
  Ctrl+Z restored the file.
- **Read-only up front:** the computed `at()` showed "computed" before
  any typing.
- **Undo and Redo took about 1.5 s each**, including the new frame.
- Clicking an empty lane seeked; the splitter gave the canvas 831×467
  instead of 491×276; the export ran all five scenes, joined them and
  checked the narration with no help.
