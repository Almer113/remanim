# S5: how much of our real code could the studio edit?

**Question:** in the scenes we actually wrote, how much code is plain
enough for a GUI to show and edit, and how much must stay code-only?
**Bar (PLAN.md):** a tier breakdown.
**Verdict: done, and favourable.** About 95% of statements are tier 1 or 2.
Tier 3 is almost all helper logic (conditions, loops inside geometry
helpers) that a motion editor has no reason to touch. On the timeline
side, 99.4% of statements are tier 1 or 2.

Code: `studio/spikes/s5_census.py` (static, reads the AST; no rendering).
Output: `media/studio_spikes/s5/census.json`, with examples per tier.

## Tiers

| Tier | Meaning in the GUI | Example |
|---|---|---|
| 1 | Fully editable: a known Manim / manim_kit / style call whose arguments are literals, constants, arithmetic of those, or plain names | `self.play(FadeIn(title), run_time=0.8)` |
| 2 | Tweakable: the GUI shows it and edits its numbers and strings, but not its structure (reads other objects, indexing, comprehensions, f-strings, numpy, simple loops) | `blob.get_top() + UP * 1.4`, `rule[0]` |
| 3 | Code only: lambdas, updaters, `always_redraw`, `while`, `if` on computed values, nested `def`, `try` | `if (a[2] - level) * (b[2] - level) < 0:` |

## Results

By file:

| File | Statements | Tier 1 | Tier 2 | Tier 3 |
|---|---:|---:|---:|---:|
| test_scene.py | 11 | 100.0% | 0.0% | 0.0% |
| pythagoras.py | 205 | 61.0% | 35.1% | 3.9% |
| order_matters.py | 127 | 68.5% | 26.0% | 5.5% |
| gradient_descent.py | 365 | 58.9% | 32.9% | 8.2% |
| eola_preview.py | 490 | 69.6% | 26.3% | 4.1% |
| **All** | **1198** | **65.0%** | **29.5%** | **5.4%** |

By what the statement is for (all files):

| Purpose | Statements | Tier 1 | Tier 2 | Tier 3 |
|---|---:|---:|---:|---:|
| Timeline (`play`, `wait`, `at`, `say`, `add`, camera) | 527 | 79.9% | 19.5% | 0.6% |
| Object (made, or made and placed, in one statement) | 339 | 67.0% | 30.4% | 2.7% |
| Layout (`shift`, `next_to`, `arrange`, ...) | 50 | 78.0% | 18.0% | 4.0% |
| Style (`set_color`, `set_fill`, `fade`, ...) | 29 | 10.3% | 86.2% | 3.4% |
| Logic (loops, conditions, helper bodies) | 253 | 35.2% | 45.1% | 19.8% |

The purpose split is a rough heuristic (by method names in the statement),
but the pattern is clear: what a motion editor edits (timeline, objects,
layout) is almost all tier 1 or 2. Tier 3 sits in the logic rows.

## What tier 3 actually is

A sample from each file:

- Geometry helpers: `contour_segments` in gradient_descent
  (`if len(pts) == 2:`, saddle-cell cases), `land_color`.
- Plumbing: `Beat.say` caption handling, `fade_all` list comprehensions.
- Nested functions: `def step(n, letter):` inside `get_steps`.
- Conditional expressions: `rt = 0.7 if k < 3 else 0.45`.

None of this is something a user would want to drag or retime. The GUI
shows these lines as read-only code blocks (open in the editor), and the
objects they produce are still selectable and draggable through the
helper's call site (see S2).

Known over-counts in tier 3 (the census is conservative):
- `for level in LEVELS:` (a loop over a named constant) is classed tier 3
  but should be tier 2, like a loop over a literal list.
- A simple conditional expression could be tier 2: the GUI can edit both
  branches' literals without touching the condition.

## Static vs dynamic evidence

The census reads code. S2 and S3 tested the same files by running them:
- **S3:** every on-screen object in 16 scenes resolved to the right line
  (100% of 7,000+ clicks), tier 3 code included.
- **S2:** of 149 objects dragged in order_matters, 137 (92%) moved exactly
  by a verified code edit. The 12 failures are all one pattern
  (`ClippedGrid`, placed by its own arguments), fixable with a pattern
  rule.

So "tier 3" does not mean "the GUI can't touch the result". It means the
GUI can't restructure that line. The objects tier-3 code makes are still
selectable, and usually draggable through the call that uses them.

## Implications for the plan

1. The property panel needs a numbers-and-strings editor for tier 2
   expressions (edit a literal inside `blob.get_top() + UP * 1.4` without
   touching the rest). This covers about 30% of statements and most style
   calls.
2. Tier 3 lines show as code, read-only in the GUI, with "open in editor".
   No need to model lambdas or updaters in Phase 1–3.
3. Loops over a literal list or a named constant can be tier 2 later (edit
   the list). Low priority: they are a small part of the 5.4%.
