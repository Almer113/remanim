# S4: what timeline edits look like in code

**Question:** can a timeline with overlapping clips be written as readable,
plain Manim, and how does each timeline edit map to code?
**Bar (PLAN.md):** a written recommendation with code samples for each
timeline edit.
**Verdict: yes.** Overlaps need no new engine: one `play()` per group of
overlapping clips, each clip with its own `run_time`, delays written as
`Succession(Wait(d), anim)` behind a three-line helper. Anchors between
groups use `TimedScene.at(t)`, which our narrated scenes already use.

Probe: five two-object scratch scenes (a square and a circle, each moved
or faded in one `play()`), sampled at 0.25 s steps with the S1 frame
engine, which matches real renders frame for frame. The scratch file was
deleted; the table below is the result.

## What Manim CE 0.22 actually does (measured)

| Code | Result |
|---|---|
| `self.play(a.animate(run_time=1).shift(UP*2), b.animate(run_time=2).shift(UP*2))` | Each keeps its own length; the play lasts 2 s; `a` holds after 1 s |
| Same, with `run_time=2` on `play()` | `play`'s run_time **overrides** both: both take 2 s |
| `a.animate.shift(...).set_run_time(1)` | Silently does nothing to timing. Don't generate it |
| `Succession(Wait(0.5), FadeIn(b, run_time=1))` inside a play | `b` is not on screen until 0.5 s, then fades in over 1 s |
| `AnimationGroup(x, FadeIn(b), lag_ratio=0.5)` | `b` is added at once at opacity 0, fades from 0.5 s. Same picture, less exact to edit |

So CLAUDE.md's note "animations inside one play() all get play's
run_time" is only true when `play()` is given a `run_time`. Without one,
each animation keeps its own. (CLAUDE.md is updated to say so.)

## Recommendation

**Absolute anchors between groups, overlaps inside a group.**

```python
from manim_kit import *

def clip(anim, start=0.0, length=None):
    """An animation placed on its play()'s local timeline."""
    if length is not None:
        anim.run_time = length
    return Succession(Wait(start), anim) if start else anim


class Example(TimedScene):
    def construct(self):
        self.at(0.5)
        self.play(FadeIn(title, run_time=0.8))
        self.at(1.5)
        self.play(                                   # one group: clips overlap
            clip(Create(axes), length=1.2),
            clip(Write(label), start=0.6, length=0.8),
            clip(blob.animate.shift(RIGHT), start=0.9, length=1.0),
        )
        with self.say("Here is the graph."):
            self.at(4.0)
            self.play(Create(curve, run_time=1.5))
```

- `at(t)` is the timeline's absolute time. A clip's start on screen is the
  group's `at()` plus the clip's `start`. Both are literals, so both are
  tier 1 (S5).
- A clip with no delay is written plainly (`Create(axes, run_time=1.2)`).
  `clip()` only appears when a clip starts later than its group.
- `clip()` goes in `manim_kit.py` (original code, no licence attached).
- Never put `run_time=` on a `play()` that holds clips of different
  lengths: it would silently stretch them all.

Why absolute anchors rather than plain sequential `play`/`wait`:
- The GUI's timeline is absolute. With `at()`, moving one clip changes one
  number and nothing else moves, as in an NLE.
- Narration (`say()` / `line()`) is already scheduled on absolute time and
  doesn't block (manim-voiceover's `voiceover()` makes later marks drift).
- Sequential code stays valid: a scene with no `at()` is just a timeline
  whose groups touch end to start. The GUI reads both. It **writes** `at()`
  only for scenes that subclass `TimedScene`, and for scenes made in the
  GUI (which do by default).

## Each timeline edit, in code

| GUI edit | Code change |
|---|---|
| Move a group | Change its `self.at(t)` literal |
| Move a group that has no `at()` (sequential scene) | Change the `self.wait(d)` before it; if there is none, insert `self.wait(d)` |
| Move a clip within its group | Change `start` in `clip(...)`; add `clip(..., start=)` if it had none; remove it when back to 0 |
| Trim / stretch a clip | Change its `run_time=` / `length=` |
| Make two clips in different groups overlap | Merge the two `play()`s into one; the later clip gets `clip(..., start=)` |
| Pull clips apart again | Split the `play()`; each part gets its own `at()` |
| Easing | `rate_func=` on the clip (`smooth`, `linear`, `there_and_back`, ...) |
| Ripple (shift everything after) | Rewrite every later `at()` literal by the same amount. One edit per `at()` |
| Move a narration line | Move the `at()` before its `with self.say(...)`. Lines never overlap: `say()` starts at max(now, end of the previous line), so the GUI shows the real start, not the requested one |
| Land a visual on a word | `a, b = self.line(...)` then `self.at(a + 0.6)` (already in manim_kit) |

All of these are edits of literals or whole statements, so they use the
S2 machinery: byte splices, verified by replay.

## What this model can't do (yet)

- **One long motion under several groups** (a camera drift across three
  `play()`s). `play()` blocks until its longest clip ends, so a clip can't
  outlive its group. Options for Phase 4: drive it with a time-based
  updater (already the documented pattern), or a small kit helper that
  attaches one to a `ValueTracker` for a set time range. Needs its own
  spike; not tested here.
- **Clips that start before their group's anchor.** Not possible by
  construction. The GUI moves the anchor earlier and adds `start` to the
  others.
- **Bookmarks** (`wait_until_bookmark`) in `voiceover()` scenes: read-only
  on the timeline; the GUI shows them as markers.

## Frame-level quirks the GUI must expect

From S1 (measured in real renders):
- A non-frozen `play()` or `wait()` of `d` seconds writes
  `len(arange(0, d, 1/fps))` frames, with the clock adding `1/fps` per
  frame. Float rounding sometimes gives one frame more than `d * fps`
  (1.5 s at 15 fps gives 23 frames = 1.533 s).
- A frozen `wait()` (nothing time-based on screen) advances `int(d*fps)`
  frames.
- A cached `play()` advances the clock by exactly `d`, so a partly cached
  render can drift one frame from a clean one.

So: the timeline snaps to frames, shows the real (rendered) times from the
trace rather than the sum of literals, and treats ±1 frame as equal when
comparing the code's intended time with what rendered.
