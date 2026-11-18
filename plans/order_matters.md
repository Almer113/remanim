# Order matters: AB ≠ BA

**Purpose:** a short (~45 s) narrated video that exercises `manim_kit.py` in a
fresh project context, using `style.py`, not the 2016 recreation look.

**Kit features covered:** `TimedScene` (`say` with captions, `at`, `TARGET`),
`Blob` (moods, `blink`, `look_at`), `SpeechBubble` and `ThoughtCloud` with
`fill_color=BG`, `ClippedGrid` (rect and ellipse frames, `chain_matrices`, a
custom `matrix_of`, `vectors`), `bmatrix`, `rotation`.

**Audience:** someone who has seen a 2×2 matrix but never thought about
multiplication order.

## Maths (checked)

- R = rotate 90° = [[0, −1], [1, 0]], S = shear = [[1, 1], [0, 1]].
- Rotate then shear: S·R = [[1, −1], [1, 0]]; î → (1, 1), ĵ → (−1, 0).
- Shear then rotate: R·S = [[0, −1], [1, 1]]; î → (0, 1), ĵ → (−1, 1).
- S·R ≠ R·S. Matrices act right to left, so S·R means "R first".

Watch-out: `chain_matrices` interpolates each step linearly, so a 90°
rotation would shrink the grid by 1/√2 halfway through. The rotation stage
uses a custom `matrix_of` that turns properly (`rotation(θ)`). If that is
awkward, it's a gap to fix in the kit.

## Colour ledger

| Thing | Colour |
|---|---|
| R (rotation), its label and matrix | `ACCENT` (blue) |
| S (shear), its label and matrix | `ACCENT_2` (orange) |
| î / ĵ arrows | `GOOD` (green) / `BAD` (red) |
| grid lines | `MUTED`; the axes stay white |
| text | `FG`; inactive panel dimmed to `MUTED` |
| bubbles and clouds | `fill_color=BG` (not black) |

## Beats (one Scene each, `TimedScene` with `TARGET`)

| # | Scene | ~s | On screen (region) | Narration (spoken → caption) |
|---|---|---|---|---|
| 1 | `Question` | 7 | Blob bottom-left, speech bubble: "Does the order matter?"; title "Order matters" (title) | "Rotate, then shear. Or shear, then rotate. Same result?" |
| 2 | `RotateThenShear` | 12 | left box grid: rotate 90° (label "R" blue), then shear (label "S" orange); î ends at (1,1). Small "R first, then S" note under it (left) | "First rotate a quarter turn, then shear. The green arrow lands here." |
| 3 | `ShearThenRotate` | 12 | left panel dims; right box grid does S then R; î ends at (0,1) (right) | "Now the other way: shear first, then rotate. It lands somewhere else." |
| 4 | `CompareMatrices` | 9 | both panels fade; S·R = [[1,−1],[1,0]] ≠ R·S = [[0,−1],[1,1]] (main) | "As matrices, S R and R S really are different." → "As matrices, SR and RS really are different." |
| 5 | `Takeaway` | 7 | Blob happy with thought cloud holding a small rotating grid (ellipse clip); footer text "SR = do R first" | "Read a product right to left: S R means R happens first." → "Read right to left: SR means R happens first." |

Total ≈ 47 s. Captions: one line each, ≤ 70 characters, on screen for at least
len/15 + 0.3 s.

## Check plan

`check_layout.py` and `frames.py` per beat; join with `tools/concat.py`. Note
anything in the kit that was awkward, missing or buggy, as the test's
findings.
