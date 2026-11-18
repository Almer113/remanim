# Manim workspace

Math and explainer animations made with Manim Community Edition 0.22.1, plus
the tools built around them. Working rules for Claude are in `CLAUDE.md`.

## Map

| Path | What it is |
|---|---|
| `*.py` in this folder | The videos: `pythagoras.py`, `order_matters.py`, `gradient_descent.py`, `eola_preview.py` (recreation study), `test_scene.py` (install smoke test) |
| `style.py` | Shared palette, text sizes, screen regions |
| `manim_kit.py` | Reusable parts: timed narration, captions, Blob, bubbles, clipped grids |
| `eola_common.py` | Recreation-only layer (CC BY-NC-SA) |
| `edge_tts_service.py` | Text-to-speech service for narration |
| `preview_server.py` | Live preview with code-linked timeline, for AI-driven work |
| `tools/` | Layout check, frame sheets, audio check, joining, comparison, timeline recording |
| `plans/` | One plan per video |
| `studio/` | The Manim Studio GUI project. Start with `studio/PLAN.md` |
| `docs/` | Write-ups of what we learned |
| `reports/`, `research_notes/` | Research surveys and the notes behind them |
| `reference/` | Downloaded reference material for the recreation |
| `media/` | Everything rendered (videos, caches, review frames). Don't wipe it |

## Why the videos sit in the top folder

The preview server watches this folder, the tools import `style.py` and
`manim_kit.py` from it, and Manim writes output to `media/videos/<file name>/`.
Moving the video files would break all three for no gain.
