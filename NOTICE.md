# Licences in this repository

Everything here is under the MIT License in [`LICENSE`](LICENSE), except
the files below, which keep their own licences.

| Files | Licence | Source |
|---|---|---|
| `eola_common.py`, `eola_preview.py` | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/): non-commercial use only, credit, share alike | Adapted from 3Blue1Brown's scene code, [3b1b/videos](https://github.com/3b1b/videos) (`_2016/eola/chapter0.py`). A recreation study; the narration is original and the characters, logo and music are not 3Blue1Brown's |
| `studio/tests/corpus/gallery/*.py` | MIT, Copyright (c) 2018-2024 The Manim Community Developers | The Manim Community example gallery (`docs/source/examples.rst`, ManimCommunity/manim v0.22.1), used unchanged as test input |

Anything that imports `eola_common.py` takes on its CC BY-NC-SA licence.
Nothing else in the repository imports it.

The web UI's npm dependencies (React, Vite and their dependencies) are
installed by `npm install` and keep their own licences (MIT, Apache-2.0,
BSD, ISC, MPL-2.0); none are committed here.

reManim is an independent project. It is not affiliated with or endorsed
by the Manim Community or 3Blue1Brown.
