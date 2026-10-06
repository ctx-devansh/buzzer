# Design: Pin the Spot question type

| | |
|---|---|
| Task | T7 (new question type) |
| Type key | `pin_the_spot` |
| Setting | Party |
| Owner | Satvik Utkoori (utkoori) |
| Reviewer / Goldfish | Devansh Gupta (dgupta57) |
| Branch | `feature/t7-redo`, from `main` |
| Status | Implemented 2026-10-05; live-checked during T6 (section 17) |

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

- **D1. Image source = `config.image_url`.** An `https://` URL (G10: `http://` rejected) or a
  `data:image/{png,jpeg,gif,webp};base64,` URL, plus `image_width`/`image_height`. T8 is not built on
  this branch; when it lands it adds `image_id` as an *alternative*, without changing scoring.
- **D2. Partial credit rounds half-up to 2 decimal places** (as `put_in_order` does), not whole points.
- **D3. A played question's image is frozen (409)**; target and radii stay editable with no rescoring.
- **D4. Marker = a map pin whose tip is the point**, head above it; drag to fine-tune. No magnifier.

Added after the Goldfish review (section 16):

- **D5. A placed but unlocked pin does not score** when time runs out, matching every other type.
- **D6. Every canvas draws into the stored aspect.** Player canvas, host board, editor and report
  draw the image into a rectangle of aspect `image_height ÷ image_width` from `config` (stretching
  the image if its natural size differs) and convert taps against that rectangle. The server's
  aspect and the client's can therefore never disagree.
- **D7. `grading_type` may change after play**, with no rescoring (as D3 for target/radii, and as
  `put_in_order` already allows). Past rows keep their stored points and `is_correct`.
- **D8. Correct % is the stored `is_correct`**, as for every type (`correctCount` in the host
  summary). For ACCURACY that equals "inside `r_full` at scoring time"; COMPLETENESS reads 100%
  like every other COMPLETENESS question.

Added after the second Goldfish pass (section 16, G18–G28):

- **D9. Partial (◐) is decided by distance, everywhere.** Results screen and game-over recap use
  the same client rule: `isCorrect` false **and** the tap's distance `d < r_zero − ε` (same formula,
  aspect and `EDGE_EPSILON = 1e-9` as the server) → ◐. No target in the reveal → ✗ / "Incorrect".
  Never derived from points.

## 3. How the question works

### Player flow
1. The phone shows the **prompt** and the image on a canvas, scaled to fit with the whole image
   visible (in the stored aspect, D6). (Exception to "players never see the prompt": the player is
   looking down at the image, not up at the projector.) `new_question` already carries `prompt` and
   `config`, so no gateway change is needed; the prompt renders as **plain React text** (`{prompt}`,
   escaped), exactly as the host's `QuestionPage` does.
2. Tap drops the pin; tap again or drag moves it. A tap that *starts* in the letterbox bars is
   ignored; a drag that leaves the image **clamps** the pin to the nearest edge (x, y in [0,1]).
3. **Lock in** submits; final, like every type. Disabled until a pin exists. Timer ends first →
   nothing recorded (D5).
4. While the host has the question **locked**, taps, drags, keys and Lock in are disabled; the
   image and any placed pin stay visible.
5. Image fails to load → "Image failed to load"; no pin, no Lock in; scores nothing.
6. Results screen: the same canvas read-only with the player's pin (from `lastAnswerData`, which
   player `GameLayout` already keeps in `useGame()` when `emitAnswer` is called; lost on reload) and the revealed target + circles. ACCURACY verdict from the server's
   `yourIsCorrect`: true → "Correct"; false and the player's pin is inside `r_zero` (computed
   client-side from the reveal, D9) → "Partially correct" ◐; otherwise "Incorrect". The verdict never
   depends on points, so `points_value` 0 still reads correctly. COMPLETENESS: "Answer recorded!".
7. Game-over recap row: "Pin placed", points, ✓/◐/✗: ✓ from stored `isCorrect`, ◐/✗ by D9 using the
   stored tap (`answerData` in the player summary, already sent) and `config.image_width`/`image_height`
   (kept; only `image_url` is dropped).

### Host flow
- **Open:** image, prompt, "31 of 40 answered". **No taps shown** (the room would copy the crowd, A4).
  While locked the prompt is hidden (existing behaviour) but the image stays. Image fails to load
  → the board shows "Image failed to load" in its place; counts and controls still work.
- **Reveal:** every tap as a dot, target, filled full-credit circle, dashed zero-credit circle
  (target and circles only when the reveal has them). Dot radius = `base · √count`, capped at
  `3 · base`, where `base` = 1% of the drawn width (min 4 CSS px).
- **Game over card:** same board from the host summary, which already carries each question's
  `config` (so the image) and its MySQL-built distribution. Correct % per D8.

### Author flow (host app `QuestionEditorPage`, used by hosts and admins)
1. Choose a local file (downscaled in the browser to ≤ 1280 px longest side, drawn onto a **white**
   background so PNG transparency doesn't turn black, re-encoded with
   `canvas.toDataURL('image/jpeg', 0.85)`; an animated GIF keeps its first frame) or paste an
   `https` URL (kept as-is). If the result exceeds 1,500,000 characters the editor retries at
   quality 0.7 then 0.5, then shows "Image too large" and keeps the previous image. The editor
   measures `naturalWidth`/`naturalHeight` (integers) for width/height. An image whose natural
   size is 0 × 0 (e.g. an SVG URL without dimensions) is refused in the editor with "Image has no
   size; use a PNG, JPEG, GIF or WebP" and the previous image is kept.
   **Picking a new image clears the target** (and clamps radii); ACCURACY can't save until a new
   target is placed.
2. Click the image to place the target; click/drag to move.
3. Two sliders, both circles previewed live. Defaults r_full 0.05, r_zero 0.20. r_full 0.005–0.5;
   r_zero 0.02–floor₂(diagonal), step 0.005. Moving one pushes the other so r_full < r_zero (gap ≥ 0.01). A new
   image clamps radii to its diagonal.
4. COMPLETENESS only: **Remove target** → `answer_data: {}`, sliders hidden. ACCURACY can't save
   without a target.
5. `points_value` is entered directly (as `put_in_order`), not derived.
6. Editing resends the stored `image_url`, width, height **unchanged** unless a new image is picked
   (so a prompt-only edit of a played question passes D3's guard). Likewise `answer_data` (target,
   r_full, r_zero) is resent **exactly as stored** unless the author moves the target or a slider, so
   an off-grid imported radius is never silently snapped.
7. `points_value` defaults as for `put_in_order`.

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
`https` URLs are allowed but weaker (can vanish, change shape, aren't
portable); the editor recommends files.

## 5. Validation

One module-level function `validate_pin_the_spot(grading_type, config, answer_data)` in
`schemas/admin.py`, called from **both** `QuestionCreate.validate_structure` (create + import) and
`authoring_service.update_question` (merged stored+requested values). Rejects unless:

- `config` keys are exactly `image_url`, `image_width`, `image_height`; width/height
  `type(x) is int` in 1..20,000; `image_url` is a `str` of ≤ 1,500,000 chars that is either
  - `https://` followed by a non-empty host (`urllib.parse.urlsplit(...).netloc`), no whitespace;
    scheme matched case-insensitively. Plain `http://` is **rejected**: under HTTPS it is blocked as
    mixed content, so it would only ever work in dev. Or
  - `data:image/(png|jpeg|gif|webp);base64,` (prefix matched case-insensitively) followed by a
    non-empty payload that `base64.b64decode(payload, validate=True)` accepts.

  Everything else (SVG, `javascript:`, other schemes) is rejected.
- `answer_data` is `{}` (COMPLETENESS only) or exactly `target`, `r_full`, `r_zero`; `target` exactly
  `{x, y}`, numbers in [0,1].
- 0 < r_full < r_zero ≤ √(1 + aspect²) (the diagonal in width units — larger can't add anything).
- Numbers are finite and **not bools** (`True` is an `int`).

`pin_the_spot` joins the `type` regex on **both** `QuestionCreate` and `QuestionUpdate`.

**Update path (the asymmetry T7 warns about).** Today `update_question` validates only
`put_in_order`. Mirror its structure:
1. Merge stored + requested values (already done at the top of `update_question`).
2. **Played guard (D3)** — runs when the stored **or** requested type is `pin_the_spot`: if the
   question has `session_scores` rows and (`type` changes or the merged `config` ≠ stored `config`
   *by value*) → 409. Runs before validation, so 409 wins over 422. Resending an identical config is
   allowed. `grading_type`, `answer_data` (target/radii) and prompt are not guarded (D3, D7).
3. Validation dispatches on the **merged** type only: `if new_type == "pin_the_spot":
   validate_pin_the_spot(...)` → 422. Changing an *unplayed* question from `pin_the_spot` to another
   type follows that type's existing path (unvalidated for the built-ins, as today); the client is
   expected to send the new type's `config`/`answer_data` with it.
4. Only then assign.

Target/radius/grading-type edits after play are allowed with **no rescoring**; past reports then draw old taps
against new circles (accepted; a new question keeps both).

**Submission** (gateway): exactly `{x, y}`, finite, non-bool, in [0,1] (Python's `json` accepts
`NaN`, so check finiteness). Otherwise emit `error`, record nothing.

## 6. Scoring

All rules in one pure module **`backend/app/services/pin_the_spot.py`** (no DB/Redis):
`is_valid_tap`, `tap_key` (`f"{x:.4f},{y:.4f}"`, e.g. `"0.4000,0.6300"`; clients split on `,`
and `parseFloat`), `tap_distance`, `score`, `reveal`, `EDGE_EPSILON = 1e-9`.
`calculate_score` and all four reveal builders call it, so the type's rules exist once.

ACCURACY: `dx = px−tx; dy = (py−ty)·aspect; d = √(dx²+dy²)`.
`d ≤ r_full+ε` → full; `d ≥ r_zero−ε` → 0; else `points_value·(r_zero−d)/(r_zero−r_full)`, half-up to
2 dp exactly as `put_in_order` does today in `game_service.py`:
`(Decimal(str(round(pv, 6))) * Decimal(str(fraction))).quantize(Decimal("0.01"), ROUND_HALF_UP)`,
then `min(float(raw), pv)`. Factor that expression into one helper in `pin_the_spot.py` (or a
shared one in `game_service.py` that both types call) — not a second hand-written copy. `is_correct` only inside `r_full`. ε exists because `0.55−0.5 = 0.05000000000000004`.

| d (square, pv 1000, 0.05/0.20) | Points |
|---|---|
| 0.03 | 1000 |
| 0.05 (edge) | 1000 |
| 0.125 | 500 |
| 0.20 (edge) | 0 |
| 0.40 | 0 |

COMPLETENESS: any **valid** tap → full points, `is_correct` true; validity is checked before the
COMPLETENESS short-circuit, so an invalid tap scores 0 (backstop — the gateway rejects it first).
A malformed stored question scores 0 (`is_correct` false) rather than raising, and its reveal is
`{type: "pin_the_spot"}` (ACCURACY) or `{type: "completeness"}` with no target/radii — clients then
draw taps only.

**Reveal payload** (identical in all four builders): ACCURACY `{type: "pin_the_spot", target, rFull,
rZero}`; COMPLETENESS `{type: "completeness"}` plus `target/rFull/rZero` when a target is set.

## 7. Real time

- `record_answer` stores the tap in `session_scores.answer_data` and increments the existing Redis
  distribution hash `session:{id}:dist:{qid}` under `tap_key` (both grading types). Live count uses
  the existing `answer_status`.
- Taps reach the host **only at reveal**, as `question_results.answerDistribution`. No cap and no
  binning: keys ≤ answers ≤ `max_players` (≤ 500), ~20 bytes each. Repeats share a key → bigger dot.
- Game-over host summary rebuilds the distribution from MySQL. `restore_from_mysql` does not rebuild
  distribution hashes for any type (existing limitation, unchanged).
- **Clean-up fix:** `admin.delete_game` today selects only session ids. Change it to select
  `(id, room_code)` pairs **before** the deletes, run the existing MySQL deletes, `await db.flush()`,
  then call `state_service.delete_room_state(redis, room_code, session_id)` for each pair (the same
  call `DELETE /game/sessions/{id}` makes); today those keys outlive the game. A room still live when
  its game is deleted is not notified (unchanged; admin-only action) — its sockets hit errors on the
  next event because the session row is gone.
- **Payload size.** `new_question` and the host `game_over` summary carry `config.image_url`
  (one recipient for the host summary; every phone for `new_question`, accepted in section 15). The
  **player** `game_over` summary currently also carries every question's `config`; for
  `pin_the_spot` it must send `config` **without `image_url`** but **with** `image_width`/
  `image_height` (the recap is text only but needs the aspect for D9), otherwise each phone would
  download every image again at game over.
- **Host reconnect** needs no change: host `sync_state.currentQuestion` is built by
  `_question_payload`, which already includes `config` (the image).

## 8. Rendering

**Player `components/PinCanvas.tsx` + `lib/pinTheSpot.ts`:** fit without cropping into the stored
aspect (D6; record the drawn rect); backing store × `devicePixelRatio`, redraw on
resize/orientation; pointer events + pointer capture, `touch-action: none`; CSS px → image fraction,
letterbox → null on pointer-down, clamped during a drag; pin tip on point, head drawn *below* the
point when the point is within one pin height (≈ 40 CSS px) of the top of the drawn rect; colours
from CSS custom properties `--pin-*` with fallbacks (T9); `tabIndex=0`; `aria-label` = the prompt as plain text;
keyboard: with no pin, the first arrow key places it at (0.5, 0.5); arrows nudge 0.01 (Shift: 0.05),
clamped; Enter locks in only when a pin exists. While interactive the canvas has
`role="application"` (it is a focusable control, not a static picture); read-only it is
`role="img"`. Read-only mode for results.

**Host `components/PinBoard.tsx` + its own `lib/pinTheSpot.ts`** (apps share nothing): same drawing,
plus taps and circles; with `onPick` it is the editor's target picker. Image load failure → a
"Image failed to load" placeholder in the board's box.

**Report (`report_service.py`):** inline SVG sized to the stored aspect; `<image href=…>` with the
stored `image_url` passed through `html.escape(url, quote=True)` (§5's `https` check still allows
`"` and `<`; an unescaped URL could inject attributes into the downloaded report). A `data:` URL
keeps the report self-contained; an `https` URL is referenced and needs the network (accepted). Then taps, target and circles as on the host board.

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
| Scoring/recording/summaries | `backend/app/services/game_service.py` | `calculate_score` branch, distribution key, both summary reveals, host summary taps from MySQL, player summary drops `image_url` |
| Gateway | `backend/app/websocket/gateway.py` | Submission check; `_answer_reveal` branch |
| Report | `backend/app/services/report_service.py` | Reveal branch, tap keys, inline-SVG board, type badge |
| Clean-up | `backend/app/routers/admin.py` | `delete_game` clears Redis per session |
| Body limit | `nginx/nginx.dev.conf` | `client_max_body_size 10m` |
| Player | `frontend/player/src/{lib/pinTheSpot.ts, components/PinCanvas.tsx, pages/game/{QuestionPage,ResultsPage,GameOverPage}.tsx, types/game.ts}` | Canvas, Lock in, results, recap |
| Host live | `frontend/host/src/{lib/pinTheSpot.ts, components/PinBoard.tsx, pages/game/{QuestionPage,ResultsPage,GameOverPage}.tsx, types/game.ts}` | Image while open; taps + circles at reveal and game over |
| Editor | `frontend/host/src/pages/manage/QuestionEditorPage.tsx` | `QuestionType`, `typeLabel`, `buildPinPayload`, `questionToForm`, `formToPayload`, UI |
| Simulated players | `scripts/simulate_players.py` | Tap near target when the answer key is available (via its existing game-JSON input, or a new `--game-json` flag if none exists), random otherwise |
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
- Played guard: image/type change → 409; identical resend + prompt edit → 200; target/radii →
  200; grading-type change → 200 (D7).
- Type change on an unplayed question: `pin_the_spot` → `multiple_choice` with MC config → 200.
- Create rejects `http://` and a `data:` URL with invalid base64.
- Player `game_over` summary has no `image_url` for pin questions; host summary has it.
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
- **`https` images** can disappear or change shape: scores stay stable (size is stored) but the
  drawing may not line up. Mitigated by recommending files; not prevented.
- **Editing target after play** redraws history against new circles (accepted, D3).
- **Player's own pin is client state** — lost on page reload at results (recap uses the server's copy).
- **Redis restore** doesn't rebuild distributions: a reveal right after a Redis flush can show fewer
  taps live; game-over and report rebuild from MySQL.
- ~~Open: does a placed-but-not-locked pin score?~~ Decided **no** (D5).
- `https` images in the report need the network when the report is opened later.
- **Image load time** counts toward answer time (measured from page mount). Answer time doesn't
  affect points, so this is cosmetic; a slow phone simply has less time to tap.

## 16. Goldfish review findings

Goldfish session 2026-10-05 (fresh session; spec + context hierarchy only). Comprehension matched
the intent. Gaps found and how this revision closes them:

| # | Gap | Resolution |
|---|---|---|
| G1 | Canvas aspect source unspecified — client and server could disagree | D6 |
| G2 | How host game-over/report get images; payload size | §7 payload size, §8 report; player summary drops `image_url` |
| G3 | How the player gets and renders the prompt | §3 player 1: already in `new_question`, plain text |
| G4 | Update path when type changes away from `pin_the_spot` | §5 update step 3: validate by merged type |
| G5 | Correct % for COMPLETENESS with a target | D8 |
| G6 | New image kept the old target | §3 author 1: cleared |
| G7 | `delete_game` would need session data after the flush | §7: select `(id, room_code)` first |
| G8 | Unlocked pin at time-out was open | D5 |
| G9 | Grading-type change after play | D7 |
| G10 | URL validation details; `http://` | §5: `https` only, base64 checked |
| G11 | Editor JPEG quality / oversize / transparency | §3 author 1 |
| G12 | `tap_key` format; "≤ 250" vs `max_players` 500 | §6, §7 |
| G13 | Drag off-image, keyboard, pin flip, dot size | §3, §8 |
| G14 | Host lock and image-failure behaviour | §3 player 4, host open |
| G15 | Rounding helper duplication | §6 |
| G16 | Reveal for malformed question | §6 |
| G17 | Verdict relied on points > 0 | §3 player 6 |

Second Goldfish pass, 2026-10-05 (fresh session). Comprehension matched; remaining gaps:

| # | Gap | Resolution |
|---|---|---|
| G18 | Where the player's pin survives `QuestionPage` unmount | §3 player 6: existing `lastAnswerData` |
| G19 | Recap ◐ vs ✗ from a boolean `isCorrect` | D9; summary keeps width/height |
| G20 | `image_url` unescaped in report HTML | §8 report: `html.escape` |
| G21 | Client ε at the `r_zero` edge; missing target | D9 |
| G22 | Host reconnect mid-question gets the image? | §7: already in `sync_state` |
| G23 | CSV export of taps | None needed: CSV holds points only |
| G24 | Imported off-grid radii snapped by sliders | §3 author 6 |
| G25 | Production nginx body limit | None: `nginx.dev.conf` is the only config |
| G26 | Image load eats answer time | §15 |
| G27 | `points_value` default | §3 author 7 |
| G28 | Keyboard focus on canvas | §8 `tabIndex=0` |

## 17. Revision history

| Date | Change |
|---|---|
| 2026-10-05 | First draft, from the user's draft + design discussion (D1–D4, codebase corrections) |
| 2026-10-05 | Goldfish revision: D5–D8, gaps G1–G17 (section 16) |
| 2026-10-05 | Second Goldfish revision: D9, gaps G18–G28 |
| 2026-10-05 | Implemented (steps 1–10). Step 9's live round was played during T6 (`docs/design-t6-sample-games.md` §8): 20 simulated players per game through :8080, every reveal's target and radii equal to the file, taps clustered around each target |
| 2026-10-05 | `mean-review` follow-ups, before the code: editor refuses a 0 × 0 image (§3 author flow); player canvas role is `application` while interactive (§8) |
