# Spec: Pin the Spot question in "Cell Biology: Cells and Division"

Status: agreed in design discussion (2026-10-06). Revised after the first Goldfish test
(critic items C1–C9), the second (items 1–8) and the third (C1–C8), each checked against the code. Image chosen and step 1 completed (option A radii). Not yet implemented.
Branch: `feature/new-sample-games`. Revises the owner's T6 classroom game, whose original spec
is [`cell-biology-quiz.md`](cell-biology-quiz.md). That spec remains the authority for every
question this one doesn't change (Q1, Q3–Q13) and for the scoring rules 1–4 it defines.

## Problem

T6 (`instructions.md`) requires that at least one game per member "includes questions using
each of the team's new question types (T7)". The team's T7 types are `put_in_order` and
`pin_the_spot` (`docs/design-put-in-order.md`, `docs/design-pin-the-spot.md`). The owner's two
games (`cell_biology_cells_and_division.json`, `absurd_but_true.json`) use `put_in_order` but
neither uses `pin_the_spot`. `cell-biology-quiz.md` already lists this gap under Open items
("When it lands, this file needs a canvas question to stay compliant").

Fix: replace the Cell Biology game's **Q2** with a Pin the Spot question on a real animal-cell
diagram, uploaded to a course image library (T8).

## Technical Plan

### The question

Q2 today is a `multiple_choice` ACCURACY question: "Which organelle is the main site of ATP
production in eukaryotic cells?", answer Mitochondrion. It becomes:

- **type** `pin_the_spot`, **grading_type** `ACCURACY`, **points_value** `1.0`,
  **time_limit_seconds** `25`
- **prompt** (exact): `Tap the organelle where most of the cell's ATP is made.`
- **canvas:** an unlabeled diagram of an animal cell containing exactly one mitochondrion
- **target:** the centre of that mitochondrion

The prompt names the **function**, not the organelle, so the player has to know which organelle
makes ATP *and* recognise it on the diagram. The prompt contains no `&`, `<` or `>`
(`cell-biology-quiz.md`, "Limits"). The apostrophe in "cell's" is fine.

### How Pin the Spot scores (`docs/design-pin-the-spot.md` §6)

- Taps and the target are fractions of the image (x of width, y of height, 0–1).
- Distance is measured in **image-width units**, with the y difference scaled by the image's
  height/width:
  - `d = √(dx² + (dy·h/w)²)`
- **Full points** when `d ≤ r_full`, **zero** when `d ≥ r_zero`, and a straight-line drop in
  between: `points_value × (r_zero − d)/(r_zero − r_full)`, rounded half-up to 2 dp.
- `is_correct` is true only inside `r_full`.
- Validation (`validate_pin_the_spot` in `backend/app/schemas/admin.py`):
  - `0 < r_full < r_zero ≤ √(1 + (h/w)²)`
  - target `{x, y}` with each value in 0..1
  - ACCURACY can't have `answer_data: {}`

### Why the image comes from the course library, and what that implies

The image is uploaded through the host app's course image library and picked as the canvas in
the question editor. The editor then stores `config: {image_id, image_width, image_height}`.
The server fills in the width and height from the image row. Consequences, each checked in
`backend/app/services/authoring_service.py`:

1. **The file becomes version 2.** `build_export_bundle` exports `"version": 2` whenever any
   question refers to a library image. Version 2 adds:
   - a top-level `images` array, one entry per image:
     `{id, filename, content_type, width, height, sha256, data_base64}`
   - a `prompt_image_id` key on **every** question (`null` here)

   A version-1 file containing `image_id` is rejected ("image references need a version 2
   file"). T6 permits the bump: "If your image work (T8) extends the format, you may bump the
   version … your game files must import cleanly into your own application either way."
2. **Only the host app can import it.** `import_game_bundle` refuses a version-2 file with
   images when `course_id is None`, which is what the admin import passes (422: "A game with
   images must be imported into a course; use the host app's import"). The host import
   (`POST /api/host/games/import` with `file` + `course_id`) works.
3. **Import usually gives the image a new id.** `_import_images` reuses an existing image in
   the target course with the same sha256, or inserts a new row, and `_remap` rewrites
   `config.image_id` to that course's id.
   - The imported copy's `config.image_id` **differs from the file's whenever the target course
     doesn't already hold the image**.
   - Importing back into the authoring course reuses the same row, so the id matches there.
   - The round-trip test always imports into a fresh course, so it breaks (see "Test change"
     below).
   - It's also why step 9 must use a **second** course: re-importing into the authoring course
     wouldn't prove the image imports from scratch.
4. **The file is written by the exporter, not by hand.**
   - `json.dumps(indent=2, ensure_ascii=False)` splits number arrays one element per line, and
     adds `prompt_image_id` to every question. That breaks the layout rules in
     `cell-biology-quiz.md` ("File conventions → Layout"): one-line number arrays, the exact
     key list.
   - `json.dumps` writes **no trailing newline**.
   - `config` and `answer_data` are SQLAlchemy `JSON` columns on **MySQL 8.0** (native JSON).
     MySQL reorders object keys: shorter keys first, then by byte order. Expected effects:
     - FITB `answer_data` probably comes back as `answerPoints`, `editDistance`,
       `acceptedAnswers`.
     - Q2's `answer_data` probably comes back as `r_full`, `r_zero`, `target`.
     - Not confirmed at runtime; observe it on the first export.
   - **This spec supersedes those layout rules for this file**: the exporter's output is the
     canonical layout, **byte for byte**. Don't add back the trailing newline or reorder keys
     by hand.
   - The content rules (float points, ±1.0 multi-select, values per question) still apply.

### Image requirements

The author sources the image before implementation:

1. **No labels.** A labeled diagram gives the answer away. Crop or paint out any labels.
2. **Exactly one mitochondrion.** Scoring has one target. A correct tap on a second mitochondrion
   would score 0. Paint out any extras.
3. **Licence: waived by the owner (2026-10-06).** The owner decided not to check the chosen
   image's licence, and takes responsibility for that. Reviewers shouldn't re-raise it. The
   original guidance is kept below for reference.

   Original guidance: prefer **public domain or CC0** (e.g. from Wikimedia
   Commons), which need no credit. CC-BY or CC-BY-SA is acceptable only with attribution
   carried **inside the game file**, because the JSON gets shared without this spec:
   - Append a short credit to `game.description`, e.g.
     ` Diagram: <title> by <author>, <licence>, via Wikimedia Commons.`
   - Make the change in the host app's game edit form before exporting.
   - `game.description` allows up to 5000 characters, survives the round trip, and the
     integration test compares it.
   - Either way, record the source URL, author and licence in this spec (Detailed
     Implementation, step 1).
   - Upload the file as `animal_cell.png`, which becomes `images[0].filename` in the export.
   - **The PNG itself is not committed.** The game JSON embeds the image (`images[0]`) and is
     the source of truth (Risk 3). Keep the local copy outside the repo, or delete it after
     step 10.
4. **Format and size:** **PNG, longest side 800–1280 px**, under 500 KB. This keeps the
   **pixel size** fixed from your file to the stored image, so the step-1 measurements stay
   valid. The stored bytes may still differ from your local file.
   - The host app's `prepareUpload` (`frontend/host/src/lib/imageFile.ts`) uploads a PNG with
     longest side ≤ 1280 px as-is. It downscales a larger one, and always re-encodes a JPEG at
     quality 0.9.
   - The server's `process_upload` then re-encodes any PNG carrying metadata outside
     `image_service.CLEAN_INFO_KEYS`, e.g. an ICC profile or a text "Software" chunk, which most
     image editors write. It uses `optimize=True` and keeps the same pixel size. Re-encoding is
     idempotent, so the round trip still holds.
   - Optional: strip metadata before uploading (e.g. "export without colour profile"), so the
     export holds exactly the edited file.
   - Upload cap: 5 MB (`image_service.MAX_UPLOAD_BYTES`).
   - The image is embedded as base64 (×1.33) in the file and in every import request
     (nginx `client_max_body_size 10m`).
5. **Landscape or square, and readable on a phone.**
   - Require **height ≤ width**. The player's `PinCanvas` caps the board at 60% of the window
     height, which is 384 px on a 360×640 phone. A portrait image would hit that cap and be
     drawn narrower than the screen.
   - The 8% threshold below assumes the board is drawn at full width.
   - The mitochondrion's longest side should be at least 8% of the image width (about 29 px on
     a 360 px-wide phone), and it must not look like a vesicle or ER.
6. **Clear space around it.** Nothing that isn't cytoplasm may come within the chosen `r_zero`
   of the mitochondrion's centre. That includes other organelles, the plasma membrane, the
   nuclear envelope and cytoskeleton lines. If the diagram is crowded, edit the neighbours away,
   or pick a different diagram.
   - **Exception: free-ribosome dots count as cytoplasm** (owner decision, 2026-10-06). Small
     dots scattered through the cytosol are background texture. Tapping one is tapping
     cytoplasm, so they don't count toward N.

### Radii

Pin the Spot scores with circles, but a mitochondrion is elongated. Measure everything in
image-width units. Set the radii in the editor once the image is chosen, then record them in
this spec:

- **r_full = ½ the mitochondrion's short side**, snapped down. Full credit then lands only on
  the organelle itself, never on cytoplasm or a neighbour beside its short sides.
- **r_zero = the largest step value below N − 0.005** (option A, owner decision 2026-10-06).
  - N is the distance from the target to the nearest edge of anything that isn't cytoplasm
    (requirement 6).
  - The 0.005 margin covers the allowed target-placement error (step 5).
  - So no part of a neighbour ever scores.
  - r_zero must also satisfy the editor limits below (≥ r_full + 0.01, ≥ 0.02). If it can't,
    the image fails requirement 6.
- **Accepted trade-off: the tips of the mitochondrion may score 0.**
  - An earlier draft required r_zero ≥ ½ the long side, so every tap on the organelle would
    score something.
  - Three candidate diagrams failed that rule. In each, the mitochondrion sits between the
    nucleus and the membrane, and both are closer to its centre than its own tips. A circle
    can't cover the tips without covering them too.
  - With option A, the middle of the organelle scores full or partial credit, and the
    outermost part of each end scores 0. The chosen image loses about 19% of the length this
    way (step 1).
  - Students aiming at "the mitochondrion" tap near its middle, so this rarely matters.
- **Editor limits** (`frontend/host/src/lib/pinTheSpot.ts`):
  - step `R_STEP = 0.005`
  - r_full from `0.005` to `0.5`
  - r_zero at least `0.02`
  - minimum gap `R_GAP = 0.01` (r_zero ≥ r_full + 0.01)

  Do the requirement-6 check against these numbers in step 1, before opening the editor.
- **Snapping:** round both **down** to the step. r_full stays on the organelle, and r_zero
  stays below N − 0.005.
- **Distances** in this spec use the scoring formula's aspect-scaled distance, in image-width
  units: `√(dx² + (dy·h/w)²)`, with dx and dy as fractions.

### Test change: `tests/integration/test_sample_games.py`

**Current behaviour.** The test imports every `sample_games/*.json` into one course through the
host route, exports it, and asserts that each question's `config` is `==` to the file's.

**Why it fails here.** Consequence 3: Q2's `config.image_id` changes on import, so the test
fails on this file.

**Change.** Make the comparison treat image references by **content**, not id. When the bundle
has an `images` array:

- For each question, compare `config` with `image_id` removed. Separately check that the
  exported `config.image_id` names an exported image, and the file's `config.image_id` names a
  file image, whose decoded `data_base64` bytes are equal.
- `prompt_image_id` isn't in today's `QUESTION_KEYS`, so it's currently never compared. The
  version-2 branch asserts the key is **present on both sides** for every question, then
  compares it the same way: by bytes when non-null, both `None` otherwise.
- If the file has a non-empty `images` array but the export has none, the test **fails**. It
  must not fall back to the version-1 comparison.
- Apply the same rule to `config.option_image_ids`, element by element (by bytes, or both
  `null`). This file doesn't use it, but it's the same helper and keeps future version-2
  files covered.
- Also assert `exported["version"] == bundle["version"]`.
- Version-1 files keep the exact comparison they have today.

Comparing **bytes** is the right check:

- `process_upload` stores an already-clean image unchanged. An exported image is always clean,
  because it went through `process_upload` on upload, so it round-trips byte for byte.
- The file's `sha256` field is ignored on import (recomputed), so comparing that field would
  prove nothing.

This file's tests belong to the teammate who wrote `docs/design-t6-sample-games.md`. Tell them
before changing it. The test's docstring says to report a failing file to its owner, not to
edit the file. Here the file is correct and the test doesn't understand version 2.

Logistics:
- **Same MR, test commit first.** The test change and the new game file land in the same MR,
  with the test commit before the file commit. Version-1 files pass the changed test, so
  neither commit leaves `main` red.
- **If the teammate objects**, fall back to the `data:` URL alternative (see Alternatives),
  which keeps the file at version 1 and needs no test change. That needs a revision of this
  spec first.
- **Leftover images.** Each run leaves the image in the throwaway test course. That's
  harmless; the course itself is already left behind, since there's no course DELETE route.

**A second test imports this file and needs no change.**
`tests/integration/test_images.py::test_sample_games_still_import` imports every
`sample_games/*.json` into `two_courses["a"]` through the host route and expects 201.
- It passes unchanged: the host route is used and a course is given.
- It leaves the image in course A's library. No later test in that file counts course A's
  images, so that's harmless.

**Stale design doc.** `docs/design-image-support.md` §4.7 (line 237) says "the existing
`sample_games/` files don't change" and that `test_sample_games.py` "keeps passing unchanged".
Both stop being true with this change. Add a dated note under that bullet pointing here.
Don't rewrite the T8 history.

## Alternatives

- **Keep Q2 and add a 14th question targeting a different organelle (e.g. the Golgi).** No
  overlap with Q2, but it renumbers Q3–Q13 and makes the game longer. Rejected; it's the fallback
  if no diagram with a single mitochondrion can be found (see Risks).
- **Keep Q2 as is and add "tap the mitochondrion".** Tests the same fact twice. Rejected.
- **A diagram drawn in code with `scripts/make_pin_images.py`.** The target comes from the
  drawing's own coordinates, and `--check` keeps the file in sync. Rejected:
  - Organelles drawn from Pillow primitives aren't recognisable without labels.
  - It means editing a teammate's script.
  - Its `write()` reformats the whole JSON file.
- **Embed the diagram as a `data:` URL in `config.image_url` (stays version 1).** Rejected by
  the owner in favour of the library upload, which lets the editor place the target and radii
  visually. Trade-off: version 1 would keep admin import working and avoid the test change.
  Keep it in mind if the version-2 costs grow.
- **An external `https://` URL in `config.image_url`.** Rejected: the game breaks when the link
  dies or the classroom network blocks the host.
- **Mitosis-stage "slide" or cell-cycle wheel images.** Considered in discussion. The owner
  chose organelles, which cover the half of the game that has fewer questions.

## Detailed Implementation

Do these in order. Steps 2–9 come after this spec is Goldfish-tested.

**1. Source the image** (see "Image requirements").
- Edit it (crop or paint out labels and any extra mitochondria) and save it as
  `animal_cell.png`.
- Measure in pixels in an image editor, then convert. Positions are fractions (x ÷ width,
  y ÷ height). Lengths and distances are in image-width units (px ÷ width, using the
  aspect-scaled distance from "Radii").
- Fill in this record before implementing.

**Record (completed 2026-10-06).** Measured by script on the exact upload file. The
mitochondrion is the connected non-white region at its location. Its sides come from its
principal axes. N is the nearest pixel of any structure of 400 px or more outside it, so
ribosome dots are excluded (requirement 6).

| Field | Value |
|---|---|
| Source | Made by the owner. A flat greyscale animal-cell diagram (nucleus with nucleolus, rough ER, smooth ER, Golgi, vesicles, lysosomes, one mitochondrion) |
| Licence | Waived by owner (requirement 3) |
| Upload file | `animal_cell.png`: 8-bit greyscale PNG (mode L), no metadata, 409 KB. Converted from the owner's RGBA original with `optimize=True` |
| Pixel size | 1254 × 1254 (square, h ≤ w ✓) |
| Mitochondrion centre (x, y) | (0.3236, 0.6435), i.e. pixel (405.8, 806.9) |
| Short side / long side | 115 px = 0.0916 / 218 px = 0.1738, long axis tilted ≈ 44° |
| Long side vs. width | 17.4% ≥ 8% ✓ |
| N, nearest non-cytoplasm edge | 95 px = **0.0760** (nuclear envelope). Next is the plasma membrane at 105 px = 0.0837. The nearest ribosome dot is at 89 px = 0.0711 and is excluded |
| r_full = ½ × 0.0916, snapped down | **0.045** (56 px) |
| r_zero = largest step < N − 0.005 = 0.0710 | **0.070** (88 px) |
| Check r_zero ≥ r_full + 0.01 | 0.070 ≥ 0.055 ✓ pass |
| Check r_zero < N − 0.005 | 0.070 < 0.0710 ✓ pass |
| Tip loss (accepted, see "Radii") | 21 px at each end, 19% of the length, scores 0 |

- Still to do: check by eye at a 360×640 viewport that the mitochondrion is recognisable
  (step 9 covers this on the device).

**2. Start the stack.**
- `docker compose up -d`, then `docker compose run --rm backend alembic upgrade head`.
- Serve the host app with `npm run dev:host`, or `npm run build` and use `localhost:8080/host`.
- Sign in as an admin (or a host of the course you'll use).

**3. Import the current game into an authoring course.**
- Host app → **Games** (`/games`) → **Import JSON** → choose a course → choose
  `sample_games/cell_biology_cells_and_division.json` (still version 1, so it imports).
- Use a course you keep for authoring. The image will live in its library.

**4. Upload the image.** Host app → **Courses** (`/courses`) → that course → **Images**
(`/courses/:id/images`) → upload `animal_cell.png`. Open the full-size view to confirm.

**5. Edit Q2** (Games → the game's questions, `/games/:gameId/questions`).
- **Question type** → **Pin the Spot**. Changing an unplayed question's type is allowed
  (`update_question` returns 409 only for a *played* question). If the editor refuses anyway,
  delete Q2, add a new Pin the Spot question, and move it to position 2 with the arrows.
- Prompt, grading, points and time exactly as in "The question".
- Canvas: choose the library image with the image picker. **Don't paste a URL**: that stores
  `image_url`, not `image_id`.
- Click the centre of the mitochondrion to place the target. Set the sliders to the step-1
  r_full and r_zero, then save.
- Compare the saved values with the step-1 record:
  - **Target offset** o = aspect-scaled distance from the saved target to the step-1 centre.
    It must be **≤ 0.005**. If it's larger, re-place the target.
  - **Clearance from the saved target:** r_zero < N − o. A click off-centre brings the
    zero-credit circle o closer to a neighbour.
  - r_full and r_zero equal the step-1 values (within 1e-9).
- Record the saved values here:
  - target `TBD`
  - o `TBD`
  - r_full `TBD`
  - r_zero `TBD`

**6. Export and replace the file.**
- In the editor, click **Export JSON** and save the download over
  `sample_games/cell_biology_cells_and_division.json`.
- **Don't play the authoring copy.** Once a session has answers, Q2's image and type are frozen
  (409), so a later image swap would need a fresh import.

**7. Review the change by meaning, not by text.** The text diff is noisy by design. Expected
noise, none of which is a defect:
- number arrays reformatted one element per line
- object keys reordered by MySQL (consequence 4)
- "No newline at end of file" at the end
- `data_base64` as one very long line

The real check is semantic. Parse the old file (`git show HEAD:sample_games/cell_biology_cells_and_division.json`)
and the new one, and assert:
- `format` is unchanged and `version` is 2
- `game` is dict-equal to the old file's (plus the credit sentence if requirement 3 needed
  one)
- Q1 and Q3–Q13 are dict-equal to the old file on the 7 original keys (`type`,
  `grading_type`, `prompt`, `config`, `answer_data`, `time_limit_seconds`, `points_value`)
- every question has `prompt_image_id` equal to `null`
- Q2 matches step 5, with `config.image_id == images[0].id`. Compare `target.x`, `target.y`,
  `r_full` and `r_zero` to the recorded values **within 1e-9**, not as exact text: they come
  back from a MySQL JSON double.
- `images` has exactly one entry, and `images[0].width`/`height` equal the step-1 pixel size
  (re-encoding keeps the size; a mismatch means the upload was scaled and the measurements are
  invalid)

Any failed assertion is a defect to investigate.

**8. Change the test** as described in "Test change". Then, with the stack up, run
`pytest tests/integration/test_sample_games.py`. All files should pass, this one included.

**9. Play-test a fresh copy.**
- Import the exported file into a **second** course through the host app. This also proves it
  imports from scratch.
- Create a room, then run
  `python scripts/simulate_players.py --room <CODE> --game-json sample_games/cell_biology_cells_and_division.json`,
  adding the `--fitb-words` flag from `cell-biology-quiz.md`. With `--game-json`, the simulator
  taps near the target, otherwise anywhere on the image.
- Join yourself from a phone-sized browser (DevTools device mode, **360×640** viewport) and
  check:
  - Q2 shows the diagram with no labels, and the mitochondrion can be found.
  - Tapping its centre gives 1.0 and reads "Correct".
  - A tap between r_full and r_zero gives partial points.
  - A tap on the very end of the mitochondrion (past 88 px from its centre) gives 0. That's
    expected per "Radii", not a defect.
  - A tap on the nucleus gives 0.
  - The reveal draws the target and all taps.
- If the diagram doesn't work at phone size:
  1. Change the image or radii in the **authoring copy** (unplayed) and update this spec.
  2. As admin, delete the previous play-test copy from the second course (host app → Games →
     Delete; hosts can't delete games). Otherwise every retry leaves a game behind.
  3. Repeat steps 6–9.

**10. Commit.** One logical change per commit:
1. the docs: this spec, the Open-items note in `cell-biology-quiz.md`, and the dated note in
   `docs/design-image-support.md` (see "Stale design doc")
2. the test change
3. the game file, e.g. "Replace Cell Biology Q2 with a Pin the Spot organelle question"

In the MR description, note that the file is version 2 and must be imported through the host
app.

### Coverage summary after the change (replaces the table in `cell-biology-quiz.md`)

| Type | ACCURACY | COMPLETENESS |
|---|---|---|
| multiple_choice | Q6, Q11 | Q1 |
| true_false | Q3, Q8 | — |
| fill_in_the_blank | Q5, Q9 | Q12 |
| multi_select | Q4, Q10 | — |
| put_in_order | Q7 | Q13 |
| pin_the_spot | Q2 | — |

Still 13 questions: 10 ACCURACY, 3 COMPLETENESS. Q2 is still worth 1.0, so the maximum score is
still **17.0**.

**No COMPLETENESS Pin the Spot question, on purpose.** `design-pin-the-spot.md` §9 says
"(ACCURACY and COMPLETENESS questions)". This spec reads that as "the game as a whole has both
modes", not "every type needs both modes", which matches T6's grading-modes row. The game meets
it with Q1, Q12 and Q13.

### Verification

1. **Offline validation.** Rewrite the throwaway validator from `cell-biology-quiz.md`
   Verification step 1 (it was never committed, so it may be gone), with these changes. Compare
   Q2's target and radii to the step-5 values within 1e-9.

   **Keep:**
   - the duplicate-key `object_pairs_hook`
   - `GameCreate` and `QuestionCreate(**q)` for every question (`QuestionCreate` accepts
     `prompt_image_id` and a Pin the Spot `config.image_id`)
   - the per-question key-order check, now **8 keys**: the 7 original ones followed by
     `prompt_image_id`. Top-level key order stays the exporter's, so this holds.
   - the no-`\u`-escapes check (still true, because the exporter uses `ensure_ascii=False`)
   - the no-`&`/`<`/`>` check
   - scoring rules 2–4 unchanged
   - scoring rule 1 (MC/TF max = `points_value`) on **Q3, Q6, Q8, Q11**

   **Change:**
   - `version == 2` (not 1)
   - the set of types must be all **six**, and both grading modes present

   **Drop:**
   - the trailing-newline check (consequence 4)
   - the FITB `answer_data` inner key-order rule (MySQL reorders keys)
   - the by-eye check of one-line number arrays

   **Add (Pin the Spot):**
   - `images` has exactly one entry
   - `sha256(b64decode(images[0].data_base64)) == images[0].sha256`
   - Q2's `config` keys are exactly `{image_id, image_width, image_height}`, with no
     `image_url`
   - `config.image_id == images[0].id`
   - `image_width`/`image_height` equal `images[0].width`/`height`, and both equal the step-1
     pixel size
   - Q2's `answer_data` has exactly `target{x, y}`, `r_full` and `r_zero`, with
     0 < `r_full` < `r_zero`, and matches the values recorded in step 5
2. **Integration:** `pytest tests/integration/test_sample_games.py` passes for every file (step 8).
3. **Admin import is refused, as expected:** `POST /api/admin/games/import` with this file →
   422 "A game with images must be imported into a course". This confirms the behaviour, not a
   bug to fix.
4. **Play-through:** step 9, plus the per-question score-CSV checks from `cell-biology-quiz.md`
   step 4. For the CSV check, Q2 is an ACCURACY column that needs at least one cell equal to
   1.0.

## Risks (self-critique)

1. **A suitable image may not exist as-is.** Most free diagrams are labeled and show many
   mitochondria, so expect to edit one. If none can be made to work, fall back to the Golgi
   variant from Alternatives. That variant needs its own spec revision, because it renumbers
   the questions.
2. **The test change touches a teammate's test.** Without it, `test_sample_games.py` fails on
   this file. Agree the change with them first. The other test that imports every sample game,
   `test_images.py::test_sample_games_still_import`, passes unchanged.
3. **The app becomes the source of truth for this file.** Hand-editing the exported JSON later
   is possible but awkward (huge base64 line, layout). Any content change should go through the
   authoring copy and a re-export. If the authoring course or game is deleted, the next change
   starts from a re-import of the committed file.
4. **The admin import refuses the file.** Anyone following the README's admin-import path, or
   `cell-biology-quiz.md` verification step 2, gets a 422. Step 3 of Verification above
   documents this as expected.
5. **Mitochondria vs. look-alikes.** At phone size, a mitochondrion can resemble a vesicle or
   smooth ER. Only the step-9 phone check catches this.
6. **Nothing re-checks the target later.** Unlike `make_pin_images.py --check`, no tool
   verifies the target still sits on the mitochondrion. The test change only proves the image
   and numbers round-trip.
7. **Repo size.** A ~500 KB image becomes ~670 KB of base64 in the JSON. That's acceptable once,
   but don't commit repeated re-exports of a larger image.
