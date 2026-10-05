# Design: Pin the Spot question type

| | |
|---|---|
| Task | T7 (new question type) |
| Type key | `pin_the_spot` |
| Setting | Party |
| Owner | Satvik Utkoori (utkoori) |
| Reviewer / Goldfish | Devansh Gupta (dgupta57) |
| Branch | `feature/t7-redo`, from `main` |
| Status | Draft, before Goldfish review. No code yet |

## 1. Problem

The four built-in types (and Devansh's `put_in_order`) all ask a player to pick, type or order
something. None lets a player *point at* something. T7 requires one type whose interaction surface
is an HTML canvas.

Pin the Spot shows an image; the player taps one point on it and is scored by distance to a hidden
target ("Tap Bascom Hall" on a campus map; "Where was this photo taken?" on a world map). It follows
MapTap: the interaction is the subject. It suits a party: no specialist knowledge, a near miss still
scores, and the reveal (every tap drawn on the image) is a shared moment.

**Goals:** tap-to-answer with distance scoring; authorable by hosts and admins in the host editor;
works with ACCURACY and COMPLETENESS; survives export/import; host shows live answer count and every
tap at reveal.

**Non-goals:** polygon targets (A1); more than one target; any input besides a single point; a
course image library (T8 adds `image_id` later, section 10).

## 2. Decisions made in the design discussion (2026-10-05)

- **D1. Image source = `config.image_url`.** An `http(s)://` URL or a
  `data:image/{png,jpeg,gif,webp};base64,` URL, plus `image_width`/`image_height`. T8 is not built on
  this branch; when it lands it adds `image_id` as an *alternative*, without changing scoring.
- **D2. Partial credit rounds half-up to 2 decimal places** (as `put_in_order` does), not whole points.
- **D3. A played question's image is frozen (409)**; target and radii stay editable with no rescoring.
- **D4. Marker = a map pin whose tip is the point**, head above it; drag to fine-tune. No magnifier.

## 3. How the question works

### Player flow
1. The phone shows the **prompt** and the image on a canvas, scaled to fit with the whole image
   visible. (Exception to "players never see the prompt": the player is looking down at the image,
   not up at the projector.)
2. Tap drops the pin; tap again or drag moves it. Taps in the letterbox bars are ignored.
3. **Lock in** submits; final, like every type. Timer ends first → nothing recorded.
4. Image fails to load → "Image failed to load"; no pin, no Lock in; scores nothing.
5. Results screen: the same canvas read-only with the player's pin (from the answer the phone sent;
   lost on reload) and the revealed target + circles. ACCURACY verdict from the server's
   `is_correct`: inside `r_full` "Correct", between circles (points > 0) "Partially correct" ◐,
   beyond "Incorrect". COMPLETENESS: "Answer recorded!".
6. Game-over recap row: "Pin placed", points, ✓/◐/✗ from stored `isCorrect`.

### Host flow
- **Open:** image, prompt, "31 of 40 answered". **No taps shown** (the room would copy the crowd, A4).
- **Reveal:** every tap as a dot (bigger for repeats), target, filled full-credit circle, dashed
  zero-credit circle.
- **Game over card:** same board, built from MySQL; "correct %" counts only taps inside `r_full`.

### Author flow (host app `QuestionEditorPage`, used by hosts and admins)
1. Choose a local file (downscaled in the browser to ≤ 1280 px longest side, re-encoded as a JPEG
   `data:` URL) or paste an `http(s)` URL (kept as-is). The editor measures width/height.
2. Click the image to place the target; click/drag to move.
3. Two sliders, both circles previewed live. Defaults r_full 0.05, r_zero 0.20. r_full 0.005–0.5;
   r_zero 0.02–floor₂(diagonal). Moving one pushes the other so r_full < r_zero (gap ≥ 0.01). A new
   image clamps radii to its diagonal.
4. COMPLETENESS only: **Remove target** → `answer_data: {}`, sliders hidden. ACCURACY can't save
   without a target.
5. `points_value` is entered directly (as `put_in_order`), not derived.
6. Editing resends the stored `image_url`, width, height **unchanged** unless a new image is picked
   (so a prompt-only edit of a played question passes D3's guard).

## 4. Data model

Fractions, not pixels: `x`, `y` ∈ [0,1] across width/height, origin top-left; radii are fractions of
the image **width**; distance scales the vertical difference by aspect (= height ÷ width) so circles
stay round (A6). Width/height live **in config**, so scores never depend on re-fetching the image.

```json
config      { "image_url": "data:image/jpeg;base64,…", "image_width": 1280, "image_height": 853 }
answer_data { "target": {"x": 0.42, "y": 0.61}, "r_full": 0.05, "r_zero": 0.20 }   // or {} (COMPLETENESS only)
submission  { "x": 0.40, "y": 0.63 }
```

**Database:** no migration — `type` is a string and the type uses the existing JSON columns.
`http(s)` URLs are allowed but weaker (can vanish, change shape, be blocked as mixed content, aren't
portable); the editor recommends files.

## 5. Validation

One module-level function `validate_pin_the_spot(grading_type, config, answer_data)` in
`schemas/admin.py`, called from **both** `QuestionCreate.validate_structure` (create + import) and
`authoring_service.update_question` (merged stored+requested values). Rejects unless:

- `config` keys are exactly `image_url`, `image_width`, `image_height`; URL as in D1, ≤ 1,500,000
  chars (no SVG, no `javascript:`); width/height `type(x) is int` in 1..20,000.
- `answer_data` is `{}` (COMPLETENESS only) or exactly `target`, `r_full`, `r_zero`; `target` exactly
  `{x, y}`, numbers in [0,1].
- 0 < r_full < r_zero ≤ √(1 + aspect²) (the diagonal in width units — larger can't add anything).
- Numbers are finite and **not bools** (`True` is an `int`).

`pin_the_spot` joins the `type` regex on **both** `QuestionCreate` and `QuestionUpdate`.

**Update path (the asymmetry T7 warns about).** Today `update_question` validates only
`put_in_order`. Add, for stored **or** requested type `pin_the_spot`, in this order:
1. Merge stored + requested values.
2. **Played guard (D3):** if the question has `session_scores` rows and (`type` changes or the merged
   `config` ≠ stored `config` *by value*) → 409. Runs before validation, so 409 wins over 422.
   Resending an identical config is allowed.
3. `validate_pin_the_spot` on the merged values → 422.
4. Only then assign.

Target/radius edits after play are allowed with **no rescoring**; past reports then draw old taps
against new circles (accepted; a new question keeps both).

**Submission** (gateway): exactly `{x, y}`, finite, non-bool, in [0,1] (Python's `json` accepts
`NaN`, so check finiteness). Otherwise emit `error`, record nothing.

## 6. Scoring

All rules in one pure module **`backend/app/services/pin_the_spot.py`** (no DB/Redis):
`is_valid_tap`, `tap_key` (`"x,y"` at 4 dp), `tap_distance`, `score`, `reveal`, `EDGE_EPSILON = 1e-9`.
`calculate_score` and all four reveal builders call it, so the type's rules exist once.

ACCURACY: `dx = px−tx; dy = (py−ty)·aspect; d = √(dx²+dy²)`.
`d ≤ r_full+ε` → full; `d ≥ r_zero−ε` → 0; else `points_value·(r_zero−d)/(r_zero−r_full)`, half-up to
2 dp in `Decimal` (after `round(points_value, 6)` to strip FLOAT read-back noise), clamped to
`points_value`. `is_correct` only inside `r_full`. ε exists because `0.55−0.5 = 0.05000000000000004`.

| d (square, pv 1000, 0.05/0.20) | Points |
|---|---|
| 0.03 | 1000 |
| 0.05 (edge) | 1000 |
| 0.125 | 500 |
| 0.20 (edge) | 0 |
| 0.40 | 0 |

COMPLETENESS: any **valid** tap → full points, `is_correct` true; validity is checked before the
COMPLETENESS short-circuit, so an invalid tap scores 0 (backstop — the gateway rejects it first).
A malformed stored question scores 0 rather than raising.

**Reveal payload** (identical in all four builders): ACCURACY `{type: "pin_the_spot", target, rFull,
rZero}`; COMPLETENESS `{type: "completeness"}` plus `target/rFull/rZero` when a target is set.

## 7. Real time

- `record_answer` stores the tap in `session_scores.answer_data` and increments the existing Redis
  distribution hash `session:{id}:dist:{qid}` under `tap_key` (both grading types). Live count uses
  the existing `answer_status`.
- Taps reach the host **only at reveal**, as `question_results.answerDistribution` (≤ 250 keys; no
  binning). Repeats share a key → bigger dot.
- Game-over host summary rebuilds the distribution from MySQL. `restore_from_mysql` does not rebuild
  distribution hashes for any type (existing limitation, unchanged).
- **Clean-up fix:** `admin.delete_game` must, after flushing its MySQL deletes, call
  `state_service.delete_room_state` per session (as `DELETE /game/sessions/{id}` already does);
  today those keys outlive the game.

## 8. Rendering

**Player `components/PinCanvas.tsx` + `lib/pinTheSpot.ts`:** fit without cropping (record drawn rect);
backing store × `devicePixelRatio`, redraw on resize/orientation; pointer events + pointer capture,
`touch-action: none`; CSS px → image fraction, letterbox → null; pin tip on point (flips below near
the top edge); colours from CSS custom properties `--pin-*` with fallbacks (T9); `aria-label` = prompt,
arrow keys nudge, Enter locks in. Read-only mode for results.

**Host `components/PinBoard.tsx` + its own `lib/pinTheSpot.ts`** (apps share nothing): same drawing,
plus taps and circles; with `onPick` it is the editor's target picker.

## 9. Export / import and sample games

- Export writes `config`/`answer_data` as stored; a `data:` URL makes the file self-contained, so
  **version 1 is unchanged** and old files keep importing.
- A Pin the Spot question with a missing/invalid image fails import with "Question N invalid: …".
- nginx: `client_max_body_size 10m` (a game import shares one body; ~6 max-size images or a few dozen
  typical 100–300 KB ones). Over that → nginx 413.
- **T6:** at least one of each member's games includes `pin_the_spot` (ACCURACY and COMPLETENESS
  questions); the games themselves are designed in T6's own pass after this lands.

## 10. Dependencies

- **T8 (later):** adds `config.image_id` as an alternative to `image_url` (server fills width/height),
  a picker in the editor, and a 409 on replacing a played canvas. Scoring is unaffected.
- **T4:** done; editor is `QuestionEditorPage`.

## 11. Files touched

| Area | File(s) | Change |
|---|---|---|
| Type + validation | `backend/app/schemas/admin.py` | Type regex (create + update); `validate_pin_the_spot`; branch in `validate_structure` |
| Update path | `backend/app/services/authoring_service.py` | `update_question`: played guard + validation for `pin_the_spot` |
| Rules (single source) | `backend/app/services/pin_the_spot.py` (new) | Pure helpers (section 6) |
| Scoring/recording/summaries | `backend/app/services/game_service.py` | `calculate_score` branch, distribution key, both summary reveals, host summary taps from MySQL |
| Gateway | `backend/app/websocket/gateway.py` | Submission check; `_answer_reveal` branch |
| Report | `backend/app/services/report_service.py` | Reveal branch, tap keys, inline-SVG board, type badge |
| Clean-up | `backend/app/routers/admin.py` | `delete_game` clears Redis per session |
| Body limit | `nginx/nginx.dev.conf` | `client_max_body_size 10m` |
| Player | `frontend/player/src/{lib/pinTheSpot.ts, components/PinCanvas.tsx, pages/game/{QuestionPage,ResultsPage,GameOverPage}.tsx, types/game.ts}` | Canvas, Lock in, results, recap |
| Host live | `frontend/host/src/{lib/pinTheSpot.ts, components/PinBoard.tsx, pages/game/{QuestionPage,ResultsPage,GameOverPage}.tsx, types/game.ts}` | Image while open; taps + circles at reveal and game over |
| Editor | `frontend/host/src/pages/manage/QuestionEditorPage.tsx` | `QuestionType`, `typeLabel`, `buildPinPayload`, `questionToForm`, `formToPayload`, UI |
| Simulated players | `scripts/simulate_players.py` | Tap near target with `--game-json`, random otherwise |
| Tests | `tests/unit/test_pin_the_spot.py`, `tests/integration/test_pin_the_spot.py`, `tests/integration/engine/scoring.py`, `tests/integration/scenarios/all_question_types.py`, `tests/e2e/test_pin_the_spot_ui.py` | Section 12 |
| Context docs | nested `CLAUDE.md` for every touched directory | `.claude/rules/context-sync.md` |

## 12. Test plan (T5)

**Unit (no stack):** scoring table incl. both edges; aspect ratio; 2-dp rounding and FLOAT noise;
validator verdicts (bools, NaN, keys, diagonal); submission edge cases; reveal parity across all four
builders.

**Integration (live stack):**
- Scoring across players (scenario): inside r_full full, halfway half, beyond 0, edges per table;
  2:1 aspect symmetry; COMPLETENESS any valid tap full.
- **Create** rejects: missing image, `javascript:` URL, zero width, ACCURACY without target, target
  out of range, r_full ≥ r_zero, negative radius, r_zero past diagonal.
- **Update rejects the same payloads** — the create/update symmetry test.
- Submission rejects: missing x, string, NaN, out of range, extra key, bool → `error`, nothing scored,
  then a valid tap is accepted.
- Played guard: image/type change → 409; identical resend + prompt edit → 200; target/radii → 200.
- Access: another course's host gets 403 on create/edit; admin routes work.
- Export → import round trip keeps image, size, target, radii; missing image → 422 "Question N".
- Clean-up: deleting the game removes MySQL rows **and** Redis keys.
- HTML report contains the board.

**Browser (Playwright, :8080):** authoring (file upload, click target, sliders, prompt-only edit
keeps the image byte for byte); play-through (tap, drag, Lock in, partial credit, host boards,
game-over recap).

## 13. Implementation steps

Each step is one or more commits on `feature/t7-redo`; this doc (revised after Goldfish) is committed
first.
1. Type key, `validate_pin_the_spot`, create branch; validation unit tests.
2. Update path: played guard + validation; symmetry integration tests.
3. `pin_the_spot.py` + `calculate_score` + four reveal builders; scoring and parity tests.
4. Gateway submission, Redis distribution, reveal payload; submission tests.
5. Player canvas and result views.
6. Host boards (open, reveal, game over).
7. Editor.
8. nginx limit, export/import round trip, report board, `delete_game` Redis clean-up and tests.
9. `simulate_players.py`; play a round at :8080 with simulated players.
10. Theme tokens (T9 hooks), context docs, e2e tests, full suite + `ruff` + `tsc`.

If implementation shows this plan is wrong, update this doc in its own commit first, then the code.

## 14. Alternatives considered

- **A1. Polygon targets** — expressive ("tap France"), but needs a polygon editor and
  point-in-polygon scoring; circle + falloff covers party use.
- **A2. Hit or miss** — a 1-px miss equals the other side of the map; harsh. Banded credit follows
  Guess the Correlation.
- **A3. Pixel coordinates** — scores would differ by screen size.
- **A4. Live heat map on host** — the room copies the crowd; taps only at reveal.
- **A5. SVG/DOM image with click handlers** — T7 requires canvas; canvas also draws hundreds of dots.
- **A6. No aspect correction** — circles become ovals; vertical misses punished less.
- **A7. Gaussian falloff** — harder to explain/check by hand than linear.
- **A8. Wait for T8 `image_id`** — blocks T7; `image_url` works now and `image_id` slots in later (D1).
- **A9. Whole-point rounding** — collapses partial credit at the default `points_value` 1 (D2).

## 15. Risks and open questions (self-critique)

- **Request size.** `data:` URLs put ~100–300 KB in every `new_question` sent to every phone (×250
  players) and in every question save. Accepted for a class; T8's URL-based images fix it.
- **`http(s)` images** can disappear or change shape: scores stay stable (size is stored) but the
  drawing may not line up. Mitigated by recommending files; not prevented.
- **Editing target after play** redraws history against new circles (accepted, D3).
- **Player's own pin is client state** — lost on page reload at results (recap uses the server's copy).
- **Redis restore** doesn't rebuild distributions: a reveal right after a Redis flush can show fewer
  taps live; game-over and report rebuild from MySQL.
- Open: should a placed-but-not-locked pin score when time runs out? Draft keeps **no**, matching
  other types.

## 16. Goldfish review findings

*To fill in after the Goldfish session, before any implementation code.*

## 17. Revision history

| Date | Change |
|---|---|
| 2026-10-05 | First draft, from the user's draft + design discussion (D1–D4, codebase corrections) |
