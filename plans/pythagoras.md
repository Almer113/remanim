# Pythagorean theorem — short explainer

**Goal:** show what a² + b² = c² means geometrically and *why* it's true, using
the classic rearrangement proof. **Audience:** general / early high school.
**Length:** about 60–70 s. **Narration:** none for now. Short on-screen captions
in the footer carry the words (manim-voiceover isn't set up yet).

## Maths (checked)

- Right triangle with legs a, b and hypotenuse c (opposite the right angle).
- Rearrangement proof: a square of side a + b holds four copies of the triangle.
  - Arrangement 1: the triangles sit in the corners, leaving a tilted square of
    side c in the middle. Its corners are right angles because the two acute
    angles of the triangle sum to 90°. Uncovered area = c².
  - Arrangement 2: the triangles pair into two a × b rectangles, leaving an
    a × a square and a b × b square. Uncovered area = a² + b².
  - Same big square, same four triangles, so the uncovered areas are equal:
    c² = a² + b².
- Example: a = 3, b = 4 → 9 + 16 = 25 = 5², so c = 5.

Triangle used in the drawings: a = 1.5, b = 2 (a 3-4-5 shape), so beat 4 can
reuse the same triangle.

## Colour ledger

| Thing | Colour (style.py) |
|---|---|
| side a, a², square on a | `ACCENT` (blue) |
| side b, b², square on b | `ACCENT_2` (orange) |
| side c, c², square on c | `GOOD` (green) |
| the four triangles | grey fill (`MUTED`), white edges |
| captions | `FG`, `CAPTION_SIZE`, footer region |

## Beats (one Scene each, in `pythagoras.py`)

1. **Intro** (~8 s). Title "The Pythagorean theorem" in the title region. A right
   triangle draws in the main region, with a right-angle mark and labels a, b, c
   coloured per the ledger. Caption: "In any right triangle…"
2. **Squares** (~14 s). A square grows on each side (a², b², c²), each labelled
   inside. Then the claim: the formula appears as a² + b² = c², using matching
   colours. Caption: "…the two small squares together equal the big one."
3. **Proof** (~28 s).
   - Left: big (a + b) square with four triangles in arrangement 1 and the green
     c² gap. Caption: "Four copies of the triangle in a square of side a + b."
   - Then a copy on the right slides the triangles into arrangement 2, revealing
     blue a² and orange b². Caption: "Rearrange them…"
   - Then "= " between the two pictures. Caption: "Same square, same triangles,
     so the leftover areas match." The formula ends highlighted.
4. **Example** (~10 s). The 3-4-5 triangle with unit grids in the squares
   (9, 16, 25 cells), then 9 + 16 = 25. Caption: "Try it: 3, 4, 5."
5. **Outro** (~5 s). The formula centred, large. Caption: "a² + b² = c²: true
   for every right triangle."

## Narration (v2)

- **Voice:** Edge TTS `en-US-AndrewNeural` at rate -5%, through manim-voiceover
  and `edge_tts_service.py`.
- **Captions:**
  - One caption per spoken line, at most about 70 characters, one line.
  - Hard cuts between captions, so two are never on screen at once.
  - Each caption stays up at least `len / 15` seconds (15 characters per second
    is a comfortable reading speed) plus 0.3 s, even if the voice finishes sooner.
  - Captions use the written form (a², "a and b"). The spoken text spells things
    out ("A squared", capital letters so the voice says "ay", not "uh").

| Beat | Spoken line | Synced animation |
|---|---|---|
| Intro | Here's one of the most famous facts in all of mathematics. | title |
| | Take any right triangle: a triangle with one ninety-degree corner. | triangle draws; right-angle mark at "ninety" |
| | Its two shorter sides are called the legs, A and B. | a, b labels on the letters |
| | The longest side, across from the right angle, is the hypotenuse, C. | c label |
| Squares | Now, build a square on each side of the triangle. | figure moves left |
| | One on A, one on B, and one on C. | each square on its letter |
| | The theorem says the two smaller squares, together, | a² + b² flies over |
| | have exactly the same area as the big one. | = c² |
| | In symbols: A squared plus B squared equals C squared. | circumscribe |
| | But why should that be true? | — |
| Proof | Here's a beautiful way to see it. | outline |
| | Take four copies of our triangle, | triangles |
| | and fit them inside a square whose side is A plus B. | braces |
| | The space left in the middle is a square with side C, | green gap |
| | so its area is C squared. | c² label |
| | Now take the same big square and the same four triangles, | copy right |
| | and slide the triangles into a new arrangement. | triangles move |
| | This time, the empty space is two squares: A squared, and B squared. | a², b² on cue |
| | Both pictures use the same square and the same four triangles, | = sign |
| | so the empty space must be the same too. | — |
| | C squared equals A squared plus B squared. | formula + circumscribe |
| Example | Let's check it with real numbers: legs of three and four. | triangle + squares |
| | Count the little squares: nine here, sixteen here, | grids, 9, 16 on cue |
| | and twenty-five on the hypotenuse. | 25 |
| | Nine plus sixteen is twenty-five, | equations |
| | so the hypotenuse is exactly five. | c = 5 |
| Outro | A squared plus B squared equals C squared. | formula |
| | It's true for every right triangle, of any size or shape. | — |

## Output

Each beat is checked with `tools/check_layout.py` and `tools/frames.py`. Then
all five are rendered at 1080p and joined into
`media/pythagoras_full.mp4`. 480p previews come first.
