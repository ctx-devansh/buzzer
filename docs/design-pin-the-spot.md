# Design: Pin the Spot question type

| | |
|---|---|
| Task | T7 (new question type), with T8 canvas integration |
| Type key | `pin_the_spot` |
| Setting | Party |
| Owner | Satvik Utkoori (utkoori) |
| Reviewer / Goldfish | Devansh Gupta (dgupta57) |
| Status | Implemented; revised after Goldfish review (section 15) |

## 1. Problem

Buzzer has four question types, and all of them ask the player to pick or type an answer. None of them lets a player *point at* something. T7 requires one new type whose interaction surface is an HTML canvas, and T8 requires that uploaded images can be used on that canvas.

Pin the Spot shows the player an image and asks them to tap one point on it. Examples:

- "Where was this photo taken?" on a world map
- "Tap Bascom Hall" on a campus map
- "Find the cat hiding in this photo"

The idea comes from MapTap: the interaction is the subject. You point at where something is instead of naming it. It suits a party because it needs no specialist knowledge, a near miss still earns points, and the reveal (everyone's taps drawn on the image) is a shared moment for the room.

### Goals

- A player taps a point on an image on their phone and is scored by how close they were.
- Admins **and** hosts can create and edit Pin the Spot questions. Both use the host app's question editor (`/host/games/:id/questions`): since T4 the admin app has no question editor and links there.
- The type works with both grading modes, ACCURACY and COMPLETENESS.
- Questions survive export and import.
- The host screen shows answer progress during the question and every tap at reveal.

### Non-goals

- Polygon or irregular target regions (see Alternatives, A1).
- More than one target per question.
- Drawing, dragging, or any input other than a single point.

## 2. How the question works

### Player flow

1. The question opens. The player's phone shows the prompt and the image drawn on a canvas, scaled to fit the screen with the full image visible. (Other types hide the prompt on phones; this one shows it because the player is looking down at the image, not up at the screen.)
2. Tapping the image drops a pin. Tapping again, or dragging, moves it. Taps outside the image area (the letterbox bars) are ignored.
3. The player presses **Lock in** to submit. The submission is final, matching the existing one-answer-per-question rule.
4. If the timer ends before the player locks in, no answer is recorded. This matches how the existing types handle a player who doesn't answer.
5. If the image can't be loaded (for example, a linked image that has gone), the canvas shows "Image failed to load" and the player can't place a pin or lock in. Like a player who doesn't answer, they score nothing.
6. **Results screen.** The player sees the same canvas, read-only, with their own pin and the revealed target and circles. The pin comes from the answer the phone sent (`lastAnswerData` in the player's `GameLayout`), not from the server, so after a page reload it is missing and only the target is drawn. The verdict depends on the grading type:
   - **ACCURACY:** the verdict comes from the server's `is_correct` flag, never from the points. Inside `r_full` shows "Correct". Between the two circles (points > 0, not correct) shows "Partially correct" in amber (◐). Beyond `r_zero` shows "Incorrect".
   - **COMPLETENESS:** the screen shows "Answer recorded!".
7. **Game-over recap.** Each Pin the Spot row shows "Pin placed", the points and the same ✓/◐/✗ marking, taken from the stored `isCorrect` (the player summary also carries `playerAnswer`).

### Host flow

- **While the question is open:** the host screen shows the image, the prompt and an answer count ("31 of 40 answered"). It does **not** show where people tapped, because players in the room would copy the crowd (see A4).
- **At reveal:** every tap is drawn as a dot. The target is marked, with the full-credit circle (r_full) and the zero-credit circle (r_zero) around it.
- **Game-over card:** the same board (every tap plus the circles), built from the per-question distribution in the host summary. That distribution is rebuilt from MySQL, not Redis. The card's shared "correct %" counts only taps inside `r_full`, so it can be low while the average points are high. This is intended: "correct" means a full-credit tap.

### Author flow (host app question editor)

1. Choose a local image file, or paste an image URL. A file is downscaled in the browser (longest side at most 1280 px, JPEG) and stored as a `data:` URL. An `http(s)` URL is kept as-is. Either way, the editor measures the image's width and height, and the server trusts those numbers.
2. Click the image to place the target. Click again to move it.
3. Set the full-credit radius and the zero-credit radius with two sliders. Both circles are drawn on the image as live previews.
   - The sliders start at r_full = 0.05 and r_zero = 0.20.
   - r_full ranges from 0.005 to 0.5. r_zero ranges from 0.02 to the image's diagonal, √(1 + aspect²), rounded down to 2 decimal places.
   - Moving one slider pushes the other so that r_full < r_zero always holds (a gap of at least 0.01). The editor therefore can't produce the server's "r_full ≥ r_zero" 422.
   - Choosing a new image clamps the radii to the new diagonal.
4. **COMPLETENESS with no target.** When grading is COMPLETENESS, a **Remove target** button clears the target, and the editor then saves `answer_data: {}`. While there is no target, the sliders are hidden. Clicking the image places a target again. ACCURACY can't be saved without a target ("Click the image to place the target").
5. **Editing an existing question.** The editor loads the stored `image_url`, width and height into the form and sends them back **unchanged**, byte for byte, unless the author picks a new image. It never re-downscales or re-encodes a stored image. This is what lets a prompt-only edit of a played question pass the guard in section 4.
6. `points_value` is entered directly, as for `put_in_order`. It is not derived from the answer data.
7. Save. The server runs the same validation on create and on update (see section 4).

## 3. Data model

Positions and radii are fractions of the image, not pixels, so scoring is the same on every screen size.

- `x` and `y` run from 0 to 1 across the image's width and height, with (0, 0) at the top left.
- Radii are fractions of the image **width**.
- Distance is measured with the vertical difference scaled by the image's aspect ratio, so the circles stay round on wide or tall images (see A6). The width and height are stored **in the question's `config`**, not looked up from an image record, so a question's scores can't change if an image is later replaced.

### Question `config` (sent to players)

```json
{
  "image_url": "data:image/jpeg;base64,/9j/4AAQ…",
  "image_width": 1280,
  "image_height": 853
}
```

T8 (image storage) does not exist yet, so the image is referenced by `image_url`, decided on 2026-10-05: either an `http(s)://` URL or a `data:image/{png,jpeg,gif,webp};base64,` URL. When T8 lands, `image_id` can be added as an alternative to `image_url` without changing scoring (it only needs the stored width and height).

**`data:` URLs are the recommended form.** An `http(s)` URL is accepted but weaker in four ways:

- The linked image can disappear, which leaves the question unplayable (see section 2, player flow step 5).
- The image can be replaced by one with a different shape. Scores still use the stored width and height, so they stay stable, but the drawing would no longer line up with them.
- Browsers block an `http://` image on a page served over `https`, as mixed content.
- An export holding a URL is only as portable as that URL.

The guarantee that "scores can't change" covers scores only; for a URL image it doesn't cover what is drawn.

### Question `answer_data` (never sent to players)

Required for ACCURACY. Optional for COMPLETENESS: either `{}` (an opinion question, e.g. "tap where you grew up", with no target) or all three fields.

```json
{
  "target": { "x": 0.42, "y": 0.61 },
  "r_full": 0.05,
  "r_zero": 0.20
}
```

### Player submission

```json
{ "x": 0.40, "y": 0.63 }
```

### Database

No new table and no migration. `questions.type` is a `String(50)`, not an enum, and the type uses the existing `config` and `answer_data` JSON columns.

Images are inside `config`, so a question can be large. The server caps `image_url` at 1,500,000 characters, and nginx's request-body limit (`client_max_body_size` in `nginx/nginx.dev.conf`) is raised from the 1 MB default to 10 MB.

- **Creating or updating one question** always fits: one image is at most about 1.5 MB.
- **Importing a game** is one request, so the 10 MB limit is shared by every image in the game. At the 1.5M-character cap, about six images fit. An editor-downscaled JPEG is typically 100–300 KB as a `data:` URL, so a normal game holds a few dozen. A file over the limit gets nginx's 413, not the "Question N invalid" error. This limit is accepted for a class-sized deployment. Raise `client_max_body_size` if games with many large images are needed.

## 4. Validation

Question validation is a single shared function, `validate_pin_the_spot` in `schemas/admin.py`, called by **both** the create path (`QuestionCreate.validate_structure`, which also covers import) and the update path (`authoring_service.update_question`, on the merged stored + requested values). This was checked: before this change `QuestionUpdate` had no structural validation at all, and only `put_in_order` was re-validated on update.

The validator rejects a question unless:

- `config` has exactly `image_url`, `image_width` and `image_height`. The URL is `http(s)://` or a `data:image/{png,jpeg,gif,webp};base64,` URL (no SVG, no `javascript:`), at most 1,500,000 characters. Width and height are integers from 1 to 20,000.
- `answer_data` (when present; see section 3) has exactly `target`, `r_full` and `r_zero`. `target` has exactly `x` and `y`, numbers from 0 to 1.
- 0 < r_full < r_zero ≤ the image's diagonal in width units, √(1 + aspect²). A circle larger than the diagonal can't add anything. This does **not** stop a generous author from giving most taps full credit; that is the author's choice, not a data error.
- Booleans are rejected where numbers are expected (`True` is an `int` in Python).

On update, a question that already has recorded answers can't change its `type` or `config` (the image), because the recorded taps are positions on that image (409, same rule as `put_in_order`).

- **"Change" means "not equal".** The merged `config` (the stored value, overridden by the request's `config` if one is sent) is compared with the stored `config` by value. Resending an identical `config`, which the editor does on every save, is allowed. Only a different image URL, width or height counts as a change. This check runs before validation, so the 409 wins over a 422.
- **Target and radii stay editable after play, with no rescoring.** Recorded `session_scores` keep the points they were given. From then on, the game-over card and the HTML report for **past** sessions draw the **current** target and circles over taps that were scored against the old ones, so a tap can look misplaced against its points. This is accepted. Fixing a wrong target for future sessions matters more than an exact historical picture. An author who wants both should create a new question.

The server rejects a submission unless it is exactly `{x, y}` with finite numbers (not booleans) from 0 to 1. Python's `json` accepts `NaN`, so finiteness is checked explicitly. Anything else returns an error and is not scored.

## 5. Scoring

### ACCURACY

Let (tx, ty) be the target, (px, py) the tap, and aspect = image height ÷ image width.

```
dx = px − tx
dy = (py − ty) × aspect
d  = sqrt(dx² + dy²)

if d ≤ r_full:            score = points_value
else if d ≥ r_zero:       score = 0
else:                     score = points_value × (r_zero − d) ÷ (r_zero − r_full),
                                  rounded half-up to 2 decimal places
```

Rounding is to 2 decimal places, as `put_in_order` does, not to whole points: the editor's default `points_value` is 1, and whole-point rounding would turn every partial score into 0 or 1. The result is clamped to `points_value`. A tap counts as **correct** (`is_correct`) only inside the full-credit circle.

**Edge tolerance.** Both edge tests compare with a tolerance of `EDGE_EPSILON = 1e-9`: `d ≤ r_full + ε` is full credit, and `d ≥ r_zero − ε` is zero. Without it, float subtraction puts a tap exactly on a circle a hair outside it (`0.55 − 0.5` is `0.05000000000000004`), and the "exactly on the edge" rows below would fail. The partial-credit step is done in `Decimal` (half-up), after stripping single-precision read-back noise from `points_value` with `round(points_value, 6)`.

Worked examples with points_value = 1000, r_full = 0.05, r_zero = 0.20 on a square image:

| Tap distance d | Points | Why |
|---|---|---|
| 0.03 | 1000 | Inside the full-credit circle |
| 0.05 | 1000 | Exactly on the full-credit edge |
| 0.125 | 500 | Halfway between the two circles |
| 0.20 | 0 | On the zero-credit edge |
| 0.40 | 0 | Outside the zero-credit circle |

Scoring is a pure function, `score(tap, answer_data, aspect, points_value)` in `backend/app/services/pin_the_spot.py`. It returns `(points, is_correct)`, where `points` is a float with at most 2 decimal places, not an integer. It reads no database or Redis state, so it can be unit tested directly. `game_service._score_pin_the_spot` is a thin wrapper around it: it checks the tap, works out the aspect from `config`, handles COMPLETENESS, and turns a malformed legacy question into 0.

### COMPLETENESS

Any valid tap earns full points, and `is_correct` is **true**, as with every other type under COMPLETENESS. A target, if set, has no effect on scoring and is only drawn at reveal. An invalid tap still scores 0 with `is_correct` false: validity is checked before the COMPLETENESS short-circuit. This applies as a backstop, because the gateway rejects invalid taps before scoring.

## 6. Canvas rendering (player app)

- **Fit:** draw the image to fit the canvas without cropping, and record the drawn image's offset and size so taps can be converted to image coordinates.
- **Sharp on phones:** size the canvas backing store by `devicePixelRatio`, and redraw on resize and orientation change.
- **Input:** use pointer events, which cover touch and mouse. Convert the tap position to canvas coordinates, then to image coordinates from 0 to 1. Ignore taps outside the drawn image.
- **Marker:** a map pin whose **tip** is the chosen point and whose head sits above it, so a thumb doesn't hide the head. The player can drag to fine-tune, and the pin follows the finger. (This settles the open question; no magnifier.)
- **Theming (T9):** canvas drawing can't use CSS classes. The drawing helpers read colors from CSS custom properties (`--pin-marker`, `--pin-target`, …) with `getComputedStyle`, falling back to fixed colors. T9 defines the properties; until then the fallbacks are used.
- **Accessibility:** the canvas gets an `aria-label` with the prompt. As a nice-to-have, arrow keys nudge the marker and Enter locks it in.

## 7. Real-time and host view

- On each valid submission the server stores the point with the player's answer in MySQL, as it does for other types, and increments the question's existing Redis answer-distribution hash under the key `"x,y"` (each rounded to 4 decimal places). The host's answer count already updates live through `answer_status`.
- The distribution hash is sent to the host **only at reveal**, as the existing `answerDistribution` field of `question_results`. At the 250-player limit that is at most 250 keys, small enough to send without binning. Two taps that round to the same key are counted together, and the host draws a bigger dot for a repeated spot.
- **After a Redis restart:** `state_service.restore_from_mysql` does **not** rebuild distribution hashes, for any question type. That limitation already existed and this type doesn't change it. A reveal straight after a Redis flush can therefore show fewer taps on the live host board. The game-over card and the HTML report don't depend on Redis: they rebuild the taps from `session_scores` in MySQL (`tap_key` over each stored answer), so they are always complete.
- Reveal payload, identical in all four reveal builders: ACCURACY → `{type: "pin_the_spot", target, rFull, rZero}`; COMPLETENESS → `{type: "completeness"}`, plus `target`, `rFull` and `rZero` when a target is set.
- The HTML session report draws the image, the circles and every tap as an inline SVG.
- The host canvas uses the same drawing code as the player canvas, plus dots for every tap and the two target circles.

## 8. Export and import

- Export writes the question's `config` and `answer_data` as they are. Because the image is inside `config` (a `data:` URL, or a public URL), a version 1 export is already portable; no format change is needed.
- Importing a Pin the Spot question whose image is missing or invalid fails with the existing "Question N invalid: …" error. It never creates a question without its image.
- Unmodified version 1 files keep importing, as T6 requires. If T8 later moves images to `image_id` and bumps to version 2, `image_url` questions must keep importing.

## 9. Files touched

Confirmed against the code on 2026-10-05.

| Area | File(s) | Change |
|---|---|---|
| Question type list | `backend/app/schemas/admin.py` | `pin_the_spot` in the `type` pattern of `QuestionCreate` and `QuestionUpdate`; no migration (`type` is a string) |
| Validation | `backend/app/schemas/admin.py` (`validate_pin_the_spot`), `backend/app/services/authoring_service.py` (`update_question`) | Shared validator on create, import and update; played-question guard |
| Type rules (single source) | `backend/app/services/pin_the_spot.py` (new) | Pure, no I/O: `is_valid_tap`, `tap_key`, `tap_distance`, `score`, `reveal`, `EDGE_EPSILON`. Every other backend file below calls these instead of copying the rules |
| Scoring and recording | `backend/app/services/game_service.py` | `_score_pin_the_spot` (wraps `pin_the_spot.score`), `"x,y"` distribution keys, reveal in both summary builders, host summary distribution rebuilt from MySQL |
| Submission and reveal | `backend/app/websocket/gateway.py` | Submission validation; `_answer_reveal` branch |
| Session report | `backend/app/services/report_service.py` | Reveal branch, tap keys, SVG chart, type badge |
| Body size | `nginx/nginx.dev.conf` | `client_max_body_size 10m` |
| Player | `frontend/player/src/lib/pinTheSpot.ts`, `frontend/player/src/components/PinCanvas.tsx`, `pages/game/{QuestionPage,ResultsPage,GameOverPage}.tsx`, `types/game.ts` | Canvas, pin, Lock in; result view |
| Host live game | `frontend/host/src/lib/pinTheSpot.ts`, `frontend/host/src/components/PinBoard.tsx`, `pages/game/{QuestionPage,ResultsPage,GameOverPage}.tsx`, `types/game.ts` | Image while open; taps and circles at reveal and in the game-over card |
| Editor | `frontend/host/src/pages/manage/QuestionEditorPage.tsx` | Image picker, target placement, radius sliders |
| Simulated players | `scripts/simulate_players.py` | Tap near the target with `--game-json`, at random otherwise |
| Tests | `tests/unit/test_pin_the_spot.py`, `tests/integration/test_pin_the_spot.py`, `tests/integration/engine/scoring.py`, `tests/e2e/test_pin_the_spot_ui.py` | See section 11 |
| Context docs | nested `CLAUDE.md` files for each directory above | New type listed alongside `put_in_order` |
| Not touched | `backend/app/services/state_service.py` | Reuses the existing `session:{id}:dist:{qid}` hash. `restore_from_mysql` is deliberately left alone (see section 7) |

## 10. Dependencies

- **T8 image API (Devansh).** No longer blocking: images live in `config.image_url`. When T8 lands, its picker can fill `image_url` (or a new `image_id`) plus the width and height.
- **T4 host game management.** Done; the editor lives in the host app's `QuestionEditorPage`.

## 11. Test plan (T5)

Unit tests (`tests/unit/test_pin_the_spot.py`, no stack needed): the scoring table, aspect ratio, rounding, create/update validator verdicts, submission edge cases, and reveal parity across the four builders.

Integration tests against the live stack (`tests/integration/test_pin_the_spot.py`):

- **Scoring:** a tap inside r_full gets full points, a tap halfway between the circles gets half, a tap beyond r_zero gets 0, and a tap exactly on each edge matches the table in section 5.
- **Aspect ratio:** on a 2:1 image, taps the same visual distance from the target horizontally and vertically score the same.
- **COMPLETENESS:** any valid tap gets full points.
- **Create validation:** rejected for a missing image, coordinates outside 0–1, r_full ≥ r_zero, or a negative radius.
- **Update validation:** the same invalid payloads are also rejected on **update**. This is the test that catches the create/update asymmetry.
- **Submission validation:** rejected for a missing x, a string value, NaN, or a value outside 0–1.
- **Access:** a host from another course can't create or edit the question. (Player access is decided per room by `authorise_player`, the same for every type, so it isn't retested here.)
- **Played-question guard:** once answered, the image and type can't change (409); the target and radii can.
- **Export/import:** a game containing the type round-trips with the same target, radii and image.
- **Clean-up:** deleting the game removes its rows in MySQL and its keys in Redis. (Unchanged generic path: the type adds no tables and only uses the existing `session:{id}:dist:{qid}` hash.)

Browser tests (`tests/e2e/test_pin_the_spot_ui.py`, Playwright against `:8080`): authoring in the host editor (file upload, click to place the target, prompt-only edit keeps the image) and a play-through (tap, move, Lock in, partial credit, host boards, game-over recap).

## 12. Implementation steps

Each step is one or more atomic commits on `feature/pin-the-spot`. This document is the branch's first commit.

1. Add the type key and schemas (no migration needed).
2. Add the shared validator and wire it into create **and** update. Add the validation tests.
3. Add the scoring function and the scoring tests.
4. Accept submissions over the socket, store them, update the Redis answer count, and send points at reveal.
5. Build the player canvas: fit, coordinate conversion, marker, Lock in.
6. Build the host view: answer count while open, dots and circles at reveal.
7. Build the editor in the host app's `QuestionEditorPage` (used by hosts and admins).
8. Add export/import support and its round-trip test.
9. Teach `simulate_players.py` to tap near the target when given `--game-json`, and at random otherwise. Play a full round with simulated players at `localhost:8080`.
10. Apply theme tokens to all new screens and check both themes.

If implementation shows this plan is wrong, update this document in its own commit first, then change the code.

## 13. Alternatives considered

- **A1. Polygon target regions.** More expressive: you could make "tap France" match the whole country. Rejected for now because the editor needs a polygon drawing tool and scoring needs point-in-polygon tests. A circle with falloff covers the party use cases.
- **A2. Hit or miss.** Simpler, but a tap 1 pixel outside the target would score the same as one on the other side of the map. That's harsh and less fun at a party. The banded partial credit follows Guess the Correlation.
- **A3. Pixel coordinates.** Rejected because the same tap would land at different pixel positions on different phones and score differently.
- **A4. Showing the heat map live on the host screen.** Rejected because the host screen is visible to the whole room, so players would tap where the crowd is. Taps are shown only at reveal.
- **A5. An SVG or DOM image with click handlers.** Rejected because T7 requires a canvas. The canvas also makes it easy to draw hundreds of dots at reveal.
- **A6. Measuring distance without the aspect ratio.** Rejected because on a wide image the "circle" would be stretched into an oval, and vertical misses would be punished less than horizontal ones.
- **A7. Gaussian falloff instead of linear.** Smoother, but harder to explain to players and to the TA. Linear falloff is easy to state and to check by hand.

## 14. Open questions

- ~~Should the marker sit above the finger, or should a magnified view appear?~~ Pin with its tip at the point, drag to adjust (section 6).
- Should a player who placed a marker but didn't lock in before the timer ended get scored on that marker? Still no, to match the other types.
- ~~Which export format for images does T8 settle on?~~ Not needed for now (section 8).
- ~~Should r_zero have a default?~~ Yes: the editor starts at r_full = 0.05 and r_zero = 0.20.
- Images sent over the socket: every `new_question` carries the `data:` URL to every player (about 100–300 KB after downscaling). Fine for a class; worth revisiting with T8 (send a URL instead).

## 15. Goldfish review findings

The Goldfish review was a fresh Claude Code session (after `/clear`) on 2026-10-05, using the `goldfish-test` skill. It read only this document and the nested `CLAUDE.md` context docs for the backend schemas, services, websocket code and models, and for the host and player frontends. It read no source code and had no access to the design discussion.

**Timing.** The review ran **after** implementation, not before it as the process intends. The revision history already said "Implemented". As a result, several findings were places where the code had moved past this document, not decisions still to make. Each gap below was settled by checking what the code does and recording that here. Where that behaviour is a deliberate trade-off, the trade-off is now stated. No code was changed in this revision.

**Comprehension.** The reader's explanation matched the intended feature: the tap-and-drag pin, Lock in, aspect-corrected linear falloff, 2-dp rounding, `is_correct` only inside `r_full`, the image in `config`, the shared create/update validator, the played-question guard, and taps hidden from the host until reveal. Nothing was misunderstood at that level.

**Holes found, and how they were resolved:**

| # | Finding | Resolution |
|---|---|---|
| 1 | §5 said scoring "returns an integer", which contradicts 2-dp rounding | §5: returns `(points, is_correct)` with a 2-dp float, clamped to `points_value` |
| 2 | §9 put scoring in `game_service`, but the rules live in the pure module `services/pin_the_spot.py` that all four reveal builders call | §5 and §9 name the module and its functions. `_score_pin_the_spot` is described as a wrapper |
| 3 | The "exactly on the edge" rows in the §5 table need a float tolerance that wasn't specified | §5: `EDGE_EPSILON = 1e-9` on both edges, with the reason |
| 4 | The played-question guard didn't say what "change" means. The editor resends the whole question, and might re-encode the image | §4: compared by value, so an identical resend is allowed. §2 author flow step 5: the editor resends the stored image unchanged |
| 5 | Editing the target or radii after play redraws old taps against new circles | §4: accepted on purpose, with no rescoring. A new question is the way to keep both |
| 6 | `is_correct` under COMPLETENESS was unstated | §5: true for any valid tap. An invalid tap is false (backstop only) |
| 7 | Where the player's own pin comes from at results was unstated | §2 player flow step 6: from client state (`lastAnswerData`), so it is lost on reload. The game-over recap uses the server's `playerAnswer` |
| 8 | The player result screens weren't specified | §2 player flow steps 6–7: Correct / Partially correct ◐ / Incorrect from `is_correct`, "Answer recorded!" for COMPLETENESS, "Pin placed" in the recap |
| 9 | There was no editor flow for a COMPLETENESS question without a target | §2 author flow step 4: a **Remove target** button for COMPLETENESS only, saving `{}` with the sliders hidden |
| 10 | `restore_from_mysql` wasn't mentioned | §7 and §9: it rebuilds no distribution hash for any type (an existing limitation, kept). The game-over card and the report rebuild taps from MySQL |
| 11 | The host's game-over card and its "correct %" weren't described | §2 host flow: the board comes from the MySQL-built distribution, and "correct %" counts only full-credit taps, on purpose |
| 12 | How `points_value` is set was unclear | §2 author flow step 6: entered directly, as for `put_in_order` |
| 13 | "Importing a game with images works" overstated the 10 MB limit | §3: about six maximum-size images per import (a few dozen typical ones), and an oversized import gets a 413 |
| 14 | §3 and §8 over-stated how safe `http(s)` images are, and didn't say what happens when an image fails to load | §3 lists the four weaknesses and recommends `data:` URLs. §2 player flow step 5: "Image failed to load", with no way to submit |
| 15 | Strict `r_full < r_zero` with free sliders could produce a 422, and the slider ranges weren't given | §2 author flow step 3: slider ranges, the sliders push each other apart, and the radii are clamped to the diagonal on an image change |

**Process note.** Running the Goldfish test before implementation would have turned findings 4, 5, 7, 9 and 15 into design decisions made up front. In this order they could only be written down after the code already existed.

## 16. Revision history

| Date | Change |
|---|---|
| 2026-10-05 | First draft |
| 2026-10-05 | Revised before implementation: `image_url` in config (T8 not built), 2-dp rounding, diagonal radius bound, optional COMPLETENESS target, host-app editor, pin marker, played-question guard, confirmed file list |
| 2026-10-05 | Implemented (steps 1–10 except sample games, which are left to each member's T6 files) |
| 2026-10-05 | Revised after Goldfish review: 15 findings resolved (section 15). Covers the `pin_the_spot.py` module, edge tolerance, the guard's equality rule, COMPLETENESS `is_correct`, player result views, the no-target editor flow, slider bounds, the Redis-restore limitation, the import size limit and `http(s)` image caveats. No code changes |
