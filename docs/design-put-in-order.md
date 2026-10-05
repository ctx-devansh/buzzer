# Design: "Put in Order" question type (`put_in_order`)

Status: agreed in design discussion. Revised after the first Goldfish test (critic items 1–13)
and again after the second (critic items 1–12 plus two notes) and the final clarification
rounds, each checked against the code.
Not yet re-tested or implemented.
Branch: `feature/put-in-order`.

## Problem

Buzzer needs a classroom question where players see 3–6 items in a scrambled order and arrange
them into the correct sequence (stages of mitosis, events on a timeline, and so on). It must work
end to end like the existing types (`multiple_choice`, `true_false`, `fill_in_the_blank`,
`multi_select`): authoring in the host editor, validation, live play, scoring, per-question
results, game-over screens, the HTML session report, and tests.

Scoring rules (from the requirement):

- **ACCURACY.** With `n` items there are `t = n(n−1)/2` item pairs (3, 6, 10, 15 for n = 3..6).
  Let `c` be the number of pairs the player put in the same relative order as the correct
  sequence. A perfect order (`c == t`) scores exactly `points_value`. Otherwise
  `score = min(round_half_up(points_value × c ÷ t, 2 decimal places), points_value)`. With the
  default `points_value = 1` the score is therefore a 2-decimal value between 0 and 1.
- **COMPLETENESS.** Any *valid* submission earns full `points_value`.
- **No answer.** A player who does not lock in before the timer ends gets 0, the same as other
  types. This needs no new code because unanswered players never reach `calculate_score`.

## Technical Plan

### Data shape (no DB migration)

`questions.type` is a free string checked by a Pydantic regex. `questions.config` and
`questions.answer_data` are freeform JSON. The type key is `put_in_order`.

| Field | Shape | Notes |
|---|---|---|
| `config.items` | `list[str]`, 3–6 items, each 1–200 chars | **Display order, already scrambled.** `config` is sent to players as-is in the `new_question` payload (`websocket/gateway.py::_question_payload`), so it must never be the correct order. Items are **not** bleach-sanitised (consistent with MC `options`); React escapes them, and the HTML report must pass them through `_esc`. |
| `answer_data.correct_order` | `list[int]`, a permutation of `0..n-1` | Required for ACCURACY. Optional for COMPLETENESS in the API (hand-written JSON, imports), but the host editor always sends it (except when re-saving an unchanged question that was stored without one; see the editor's `buildPioPayload` case 2). The indices into `config.items`, listed in the correct sequence. `answer_data` itself is never sent to clients; `correctOrder` reaches them only through the answer reveal, after answers are locked. |
| Player submission (`submit_answer.answer_data`) | `{"orderedIndices": list[int]}` | The player's final order, as a permutation of `0..n-1` (indices into `config.items`). |
| `points_value` | float, as today | Authored directly in the editor for both grading types. It is *not* derived from per-option points the way MC/MS do it. |

Worked example: the author types the correct order `[Prophase, Metaphase, Anaphase, Telophase]`.
The editor scrambles it to `config.items = [Telophase, Prophase, Anaphase, Metaphase]` and stores
`answer_data.correct_order = [1, 3, 2, 0]`, because Prophase is at index 1, Metaphase at 3,
Anaphase at 2 and Telophase at 0.

### Scrambling

The **host editor** does the scrambling at save time. The author always types the items in the
correct order. On save, the editor shuffles them and writes the scrambled `config.items` plus
the matching `correct_order`. Every player in every session starts from that same stored order.
No player gets a separate reshuffle.

**The scramble is fixed for the question's lifetime.** Stored submissions (`orderedIndices` in
`session_scores.answer_data`) are indices into `config.items` *as it was at play time*, and every
reader (host game-over, player recap, HTML report) re-reads the *current* `config.items`. A
reshuffle would therefore silently corrupt every past session's answers and distribution. Two
rules prevent that:

1. **Editor: reshuffle only when the items change.** `questionToForm` remembers the loaded
   `config.items` and `correct_order`. On save, if the author's correct-order list equals
   `correct_order.map(i => config.items[i])` exactly (same strings, same order), `buildPioPayload`
   resends the stored `config.items` and `correct_order` **verbatim**. It scrambles only when the
   item list was edited. Editing just the prompt, time limit, points or grading type never
   reshuffles.
2. **Backend: a played question's items are frozen** (409). See "Update path" under Validation.

The editor keeps reshuffling until the scramble has **at most `floor(t/2)` concordant pairs**
(so a player who locks in without moving anything earns at most about half). For n = 3 the
allowed scrambles are exactly the three permutations with ≥ 2 inversions. The backend enforces
only the weaker rule that `correct_order` is **not the identity**. That keeps hand-written JSON
and imports flexible while still blocking "display order == answer".

### Scoring

Add this to `game_service.calculate_score`, after the existing COMPLETENESS short-circuit:

1. Read `sub = answer_data.get("orderedIndices")` and `correct = question.answer_data.get("correct_order", [])`.
   If `sub` is not a list, or any element fails `type(x) is int` (this excludes `bool`; see
   below), or `sorted(sub) != list(range(len(correct)))`, or `len(correct) < 2`,
   return `ScoreResult(0, False)`. The gateway rejects such submissions earlier anyway; this is
   defence in depth.
2. `rank = {item: pos for pos, item in enumerate(correct)}`.
3. `c = count of (i, j) with i < j and rank[sub[i]] < rank[sub[j]]`, `t = n(n−1)/2`.
4. If `c == t`: `points = points_value`, unchanged. This matters when `points_value` has more than 2
   decimal places (e.g. `pv = 0.125`): rounding it to 2 decimal places would give 0.13, while COMPLETENESS
   awards exactly 0.125.
5. Otherwise:
   `points = min(float((Decimal(str(round(points_value, 6))) * c / t).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)), points_value)`.
   - `round(points_value, 6)` comes first because `points_value` is a single-precision MySQL
     `FLOAT` and can read back as e.g. `0.15000000596`. Without it, a result that sits exactly
     on a .005 boundary would be decided by float noise instead of the half-up rule. Six places
     is far below any authored precision and well above float32 noise for `pv ≤ 100000`.
   - This rounds **half-up to 2 decimal places**. Python's built-in `round(x, 2)` uses banker's
     rounding and works on the binary float, so for example `pv = 0.15, n = 4, c = 1` (raw
     0.025) gives 0.02 instead of 0.03. Going through `Decimal(str(...))` avoids both problems.
   - The `min` clamp is still needed for a `points_value` with more than 2 decimal places. With
     `pv = 0.059, n = 6, c = 14`, the raw score 0.05507 rounds to 0.06, which is more than `pv`.
     The result must never exceed `pv`, because host histograms and the Canvas CSV use
     `Σ points_value` as the maximum.
6. `is_correct = (c == t)`.

**Type of `points`:** `ScoreResult.points_awarded` is a `float`, the same as every other type
(`session_scores.points_awarded` is a `Float` column). Partial scores have at most 2 decimal places
(`0.83` for one adjacent swap at n = 4, pv = 1). A perfect score is `points_value` exactly.

COMPLETENESS needs no new scoring code. The existing branch (`answer_data` non-empty →
full points) is correct *because* the gateway rejects invalid submissions before scoring
(see Validation).

### Validation

**"Int" means `type(x) is int` everywhere in this feature.** In Python `bool` is a subclass of
`int`, so `isinstance(True, int)` is true, and `sorted([True, 0, 2]) == [0, 1, 2]` passes a
permutation check. The three integer checks (the authoring validator on `correct_order`, the
gateway on `orderedIndices`, and `calculate_score`) all use `type(x) is int`, which rejects
`True`/`False`. JSON `true` from a socket client arrives as a Python `bool`, so this matters at
the gateway, not only in theory.

**Authoring (create *and* update).** Write one helper,
`validate_put_in_order(grading_type, config, answer_data)` in `schemas/admin.py`, that raises
`ValueError` when:

- `config` holds any key other than `items` (`set(config) != {"items"}`). This is stricter than
  MC/MS, which ignore extra keys, because `config` is sent to players verbatim and a stray key
  (e.g. an answer) would leak. Imports with extra keys fail with 422.
- `config.items` is not a list of 3–6 elements, or any element is not a `str`
- any item is empty after `strip()`, or longer than 200 characters after `strip()`
  (`1 ≤ len(item.strip()) ≤ 200`). The stored value stays raw, unstripped; all three item checks
  (blank, length, duplicates) look at the stripped string.
- items are duplicates, compared as `item.strip().lower()`. Use `lower()`, not `casefold()`: the
  editor's client-side check uses `trim().toLowerCase()`, and `casefold()` would disagree with
  it on characters like `ß`.
- ACCURACY and `answer_data.correct_order` is missing, or is not a list whose elements all pass
  `type(x) is int` and which forms a permutation of `range(len(items))`
- ACCURACY and `correct_order == list(range(len(items)))` (the identity)

COMPLETENESS questions may omit `correct_order`. If one is present, it is still checked as a
permutation (with the same `type(x) is int` rule), but the identity rule is not applied.

**Error messages.** Authors see these in the editor, either from a create-path Pydantic 422 via
`validationMessage`, which strips the `"Value error, "` prefix, or from an update-path
`VALIDATION_ERROR` `message`. The `ValueError` texts are fixed as follows, checked in this order
(the first failure wins):

| Rule | `ValueError` text |
|---|---|
| extra key in `config` | `Put in Order config may only contain "items"` |
| `items` not a list of 3–6 | `Put in Order needs between 3 and 6 items` |
| an item is not a string | `Every item must be text` |
| an item is blank after strip | `Every item needs text` |
| an item is over 200 chars after strip | `Each item must be at most 200 characters` |
| duplicate items | `Items must be different` |
| `correct_order` missing (ACCURACY), or present but not a permutation of the item indices with `type(x) is int` (either grading type) | `Correct order is missing or invalid: it must list each item index exactly once` |
| identity `correct_order` (ACCURACY) | `Display order must differ from the correct order` |

The editor's client-side checks reuse the exact texts `Every item needs text` and
`Items must be different`, so the author sees the same words whichever side catches it. Unit
tests assert the texts.

Wire the helper up in two places:

- **`QuestionCreate.validate_structure`:** call it when `type == "put_in_order"`, and add
  `put_in_order` to the `type` regex on both `QuestionCreate` and `QuestionUpdate`. Imports are
  covered automatically: `authoring_service.import_game_bundle` builds every question through
  `QuestionCreate(**q)` (`authoring_service.py:245`) and turns failures into `BundleError` → 422.
- **Update path, `services/authoring_service.update_question`** (route:
  `PUT /api/host/games/{game_id}/questions/{question_id}`, `routers/host.py:215`; the admin
  router calls the same service). `QuestionUpdate` has **no** structural validator today
  (verified at `schemas/admin.py:210`; `backend/app/schemas/CLAUDE.md` wrongly says it does, and is
  corrected as part of this feature), so an update could store a broken question. A validator on
  `QuestionUpdate` would be the wrong place anyway, because it sees only the partial body and can't
  check the merged values. The new order of operations is:
  1. Load the question (as today).
  2. Compute the **merged** values *without touching the ORM object*:
     `new_type = body.type if body.type is not None else question.type`, and likewise for
     `grading_type`, `config`, `answer_data`. Read the stored JSON as `question.config or {}`
     and `question.answer_data or {}` (and the same for the merged values) before any `.get`.
     Both columns are `nullable=False, default=dict` (`models/game.py:68–69`), but a
     hand-edited row could still hold JSON `null`. This is what makes "a missing key compares as
     `None`" (step 3) hold without an `AttributeError`.
  3. **Played-question guard (409).** If **either** the stored `question.type` **or** `new_type`
     is `"put_in_order"`, and the question has at least one `session_scores` row (the same
     `select(func.count())` query that `delete_question` uses), and any of these differ from the
     stored values: `new_type`, `new_config.get("items")`, `new_answer_data.get("correct_order")`,
     then raise
     `ConflictError("This question has recorded answers from a past session, so its items "
     "cannot be changed. Create a new question instead.")`. Prompt, time limit, points value,
     order index and grading type stay editable. Changing the grading type is safe: past
     `points_awarded` are stored, not recomputed.
     - The "new type" half of the guard blocks turning a **played** MC/TF/FITB/MS question into
       `put_in_order`. Without it, the old `{selectedIndex}` rows would reach the
       `orderedIndices` readers. Turning a played question into any *other* non-`put_in_order`
       type remains allowed (today's behaviour; see Open risks).
     - Comparison semantics: a missing key compares as `None`. Because the editor omits
       `correct_order` when the stored question has none (see the editor section), a prompt-only
       edit of such a question compares `None == None` and passes.
  4. **Structural validation (422).** If `new_type == "put_in_order"`, call
     `validate_put_in_order(new_grading_type, new_config, new_answer_data)`. On `ValueError`,
     raise `ValidationFailedError(str(exc))`.
  5. Only then assign the fields onto the ORM object (the existing `if body.x is not None`
     block, unchanged).

  Steps 3 and 4 run before any assignment, so a rejected update never leaves a modified ORM
  object in the session. (`get_db` would roll it back anyway, `database.py:33`, but the object
  shouldn't be put in an invalid state in the first place.) This deliberately fixes the update
  path for this type only; the other types keep today's behaviour.

**New exception, `common/exceptions.py`.** Services must not import FastAPI
(`services/CLAUDE.md`), so `HTTPException` is not an option. Add:

```python
class ValidationFailedError(BuzzerError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__("VALIDATION_ERROR", message, status.HTTP_422_UNPROCESSABLE_ENTITY)
```

The existing `buzzer_error_handler` already maps any `BuzzerError` to its `status_code`, so
neither router needs a change. The response body is `{"error": "VALIDATION_ERROR", "message": ...}`.
Pydantic's own 422 uses `detail` instead. **No frontend change is needed:**
`frontend/host/src/lib/api.ts` (`toApiError`) already reads a string `detail`, a BuzzerError's
`message`, or a 422 `detail` list. Do not rewrite the error parsing.

**Submission (`websocket/gateway.py::on_submit_answer`).** Add a branch next to the existing
`multi_select` check, before `game_service.record_answer`. It applies to **both** grading types:
`orderedIndices` must be a list whose elements all pass `type(x) is int`, with
`sorted(orderedIndices) == list(range(len(question.config.get("items", []))))`. Use `.get`, like
the `multi_select` check (`gateway.py:1145`), so a bad DB row without `items` rejects the
submission instead of raising `KeyError`.
Otherwise call `_emit_error(sid, "put_in_order answer must include orderedIndices as a permutation of the item indices")`
and return without recording anything. The player can still submit a valid answer afterwards.

**Defensive readers.** Every reader of a stored `orderedIndices` must **skip** a row (or show no
answer for it) if its answer is not a list of `type(x) is int` forming a permutation of
`range(len(current config.items))`. Such rows should not exist given the guard, but they can arrive
through hand-edited DB rows or legacy data. The readers are the `get_host_question_summary`
distribution, the report distribution, the player recap (`describePlayerAnswer`), and the player
`ResultsPage` `describeAnswer`. Skipped rows still count toward "answered", because that comes from
the row's existence, not from parsing it.

**Other code paths that read `answer_data`: checked, no change needed.**

- `scripts/seed_demo.py` lists its own question types (`type_labels`, line ~226) for the demo
  game it seeds. It doesn't need `put_in_order`, so it's left unchanged. The sample game in
  `sample_games/cs_first_day.json` carries the demo question instead.
- `state_service.restore_from_mysql` restores only cumulative scores and the next question. It
  does not rebuild the Redis answer distributions, so it has no per-type branch to extend.
- `export_service.build_session_csv` and `build_canvas_csv` write `points_awarded` only. Neither
  renders a submitted answer, so `orderedIndices` never appears in a CSV. (They **do** need a
  rounding change for fractional points; see "CSV rounding" below.)
- `build_export_bundle` copies `config` and `answer_data` verbatim; `import_game_bundle` validates
  through `QuestionCreate` (above).

**CSV rounding (`export_service.py`).** `build_canvas_csv` writes the per-student total as an
unrounded `sum(q_scores)` (`export_service.py:182`) and "Points Possible" as an unrounded
`sum(q.points_value …)` (`:159`), so `0.83 + 0.67 + …` can print as `2.4999999999999996` in a
gradebook upload. The per-question cells are raw too. On top of that, `points_awarded` and
`points_value` are `sa.Float()` columns (migration `003_float_points.py`), which on MySQL is a
4-byte single-precision `FLOAT`, so a stored `0.83` probably reads back as `0.8299999833…`
(confirm with `SHOW COLUMNS FROM session_scores` while implementing). Fix: add a module-level
helper `_pts(x) = round(float(x), 4)` and apply it to **every** points cell, every total, and
"Points Possible", in both `build_canvas_csv` and `build_session_csv` (`:53`). It rounds to 4 dp,
not 2, so a 3-dp `points_value` such as `0.125` survives unchanged.

### Answer reveal

Client-safe shapes, with `correctOrder` being the stored `correct_order` passed through
(indices into `config.items`):

| Question | Reveal |
|---|---|
| ACCURACY | `{"type": "put_in_order", "correctOrder": [...]}` |
| COMPLETENESS, `correct_order` stored (always the case for editor-saved questions) | `{"type": "completeness", "correctOrder": [...]}` |
| COMPLETENESS, no `correct_order` (hand-written JSON or import) | `{"type": "completeness"}`, the same as every other type |

The COMPLETENESS variant carries `correctOrder` because the host chart needs it (see "Answer
distribution"). Adding a field keeps every existing `reveal.type === 'completeness'` check
working. Players see the suggested order only after answers are locked, so nothing leaks. In
the TypeScript types the `completeness` variant gains an optional `correctOrder?: number[]`.

**Decision: add a branch to each existing copy instead of refactoring.** The reveal logic is
duplicated in four places today, and all four get a `put_in_order` branch:

1. `websocket/gateway.py::_answer_reveal` — live results screen
2. `services/game_service.py::get_player_question_summary` — player game-over recap
3. `services/game_service.py::get_host_question_summary` — host game-over (~line 657)
4. `services/report_service.py::_answer_reveal` — HTML session report

A unit test (see Tests) asserts all four produce identical output, so a missed copy fails CI.

### Answer distribution (host results chart)

For each answer, write one distribution key per item: `f"{item_index}@{position}"`, meaning
"this item was placed at this 0-based position". That is n increments per answer, the same
loop pattern `multi_select` uses for its per-index keys.

**Write the keys under both grading types.** The COMPLETENESS chart reads the same `i@p` counts
(see below), so the three writers must not skip COMPLETENESS answers. Today's distribution code
already branches on question type only: `record_answer` computes `dist_key` from
`question.type` (`game_service.py:~458–481`), and `get_host_question_summary` loops over scores by
`q_type`. The `put_in_order` branch goes there, keyed on **type alone**. Don't copy the shape of
the neighbouring reveal blocks, which check `grading_type == "COMPLETENESS"` first; a write
skipped for COMPLETENESS would surface only when the integration test's distribution assertion
fails. The integration scenario's `PIO_COMPLETENESS` question asserts the host distribution for
this reason.

Add matching branches in:

- `game_service.record_answer` — live Redis distribution, via `state.increment_answer_dist`
- `game_service.get_host_question_summary` — distribution rebuilt from MySQL `session_scores`
- `report_service._extract_answer_key`, plus the chart code — the report. `_extract_answer_key`
  currently returns a single key per answer, so for `put_in_order` the report code that calls it
  must handle several keys per answer. Either add a `put_in_order`-specific path in
  `build_session_report` or generalise the helper to return a list. Implementer's choice; keep
  the other types' output unchanged.

**Chart: the same bars for both grading types, mirroring the existing types.** Every other type
draws count bars for ACCURACY and the *same* bars with neutral colouring (`correct: null`) for
COMPLETENESS (host `ResultsPage.buildBars` fallback, the report's `_render_bar_chart`).
`put_in_order` does the same:

- One bar per position `p` in `0..n-1`, listed in correct order.
- Label: `` `${p + 1}. ${items[correctOrder[p]]}` ``.
- Count: `dist[`${correctOrder[p]}@${p}`] ?? 0`, i.e. the number of players who placed that item
  in its correct slot. An item nobody placed correctly shows a zero-length bar with count 0,
  like an unpicked MC option.
- Colour: ACCURACY uses `correct: true` (the green "correct" style). COMPLETENESS uses
  `correct: null` (neutral).
- Caption under the chart heading: "Players who placed each item correctly" for ACCURACY,
  "Players who placed each item at this position" for COMPLETENESS.
- If the reveal has no `correctOrder` (COMPLETENESS question without a stored `correct_order`),
  draw no bars and show only the "N / M answered" line.
- **Bar widths reuse the existing renderers unchanged.** Host `ResultsPage` `AnswerBarChart`
  scales by the largest count (`ResultsPage.tsx:121`). The report `_render_bar_chart` scales by
  `max_count` (`report_service.py:164`). Host `GameOverPage` `AnswerBar` scales by `totalPlayers`
  (`GameOverPage.tsx:60`). None of them divides by the sum of the distribution, which would be
  wrong here because each answer adds `n` counts. Nothing may introduce a sum-based width.
- **No per-bar percentage.** `put_in_order` bars show a count only. (Host `GameOverPage`
  `AnswerBar` already shows only a count; there is no per-bar "%" in any renderer today.) The
  host GameOver footer's "% responded" / "% response rate" is `totalAnswered / totalPlayers`
  (`GameOverPage.tsx:92`) and stays unchanged and valid for this type.
- **Test hooks:** each bar rendered from `buildPioBars` gets `data-testid="pio-bar-<p>"`, and its
  count gets `data-testid="pio-bar-<p>-count"`, on both host `ResultsPage` and `GameOverPage`.
  This is the **one** change to the renderers ("unchanged" above refers to their width
  scaling). The bar objects gain an optional `testId?: string`, which `buildPioBars` sets to
  `pio-bar-<p>`. `ResultsPage` `AnswerBarChart` (bar type at `ResultsPage.tsx:115`) and
  `GameOverPage` `AnswerBar` render `data-testid={testId}` on the bar row and
  `data-testid={`${testId}-count`}` on the count, only when `testId` is set. Other types don't
  set it, so their DOM is unchanged.

**Trap:** host `buildBars` has a completeness fallback (`ResultsPage.tsx:195`) that reads
`config.options`. A COMPLETENESS `put_in_order` reveal has `type: "completeness"`, so the code
must branch on the **question type** (`currentQuestion.type === 'put_in_order'`) *before* that
fallback, not on `reveal.type`. The report has the same trap: `build_session_report` must check
`q.type == "put_in_order"` before choosing `_render_bar_chart`/`_render_word_cloud`.

The host bar builder lives in a new shared helper, `frontend/host/src/lib/putInOrder.ts`:
`buildPioBars(reveal, distribution, items)`. Both `ResultsPage` and `GameOverPage` use it, so the
live chart and the game-over chart cannot drift apart. The colour is derived from `reveal.type`:
`'put_in_order'` means ACCURACY (`correct: true`), `'completeness'` means neutral (`correct: null`).
There is no separate grading-type argument.

**Payload sources.** Everything below already exists **except two additive player fields**,
`yourIsCorrect` and `isCorrect` (see "Partial-credit display"):

| Consumer | Items from | Distribution / answer from |
|---|---|---|
| Player `ResultsPage` | `currentQuestion.config.items` (kept from `new_question`) | `lastAnswerData.orderedIndices`, `questionResults.answerReveal`, `questionResults.yourIsCorrect` (new) |
| Player `GameOverPage` | `config` in each `get_player_question_summary` row (`game_service.py:577`) | that row's `playerAnswer` (`{"orderedIndices": [...]}`), `answerReveal` and `isCorrect` (new) |
| Host `ResultsPage` | `currentQuestion.config.items` | raw `questionResults.answerDistribution` dict (`"{i}@{p}"` keys, used as-is) |
| Host `GameOverPage` | `config` in each `get_host_question_summary` item | that item's `answerDistribution` and `answerReveal` |

The host's live `answerDistribution` is built in `gateway._on_host_advance_impl` from
`state.get_answer_dist` (`state_service.py:218`), which returns the Redis hash with keys untouched
and only the values int-cast. So `"{i}@{p}"` keys reach the host exactly as `record_answer` wrote
them; there is no per-type post-processing.

## Alternatives

- **Server shuffles per session/player.** Store items in the correct order, shuffle when the
  question opens, and map each submission back. This is stronger against students sharing
  "move X to the top", but it breaks the invariant "indices always refer to `config.items`" that
  the reveal, distribution, report and game-over code all rely on. Rejected as out of proportion
  for a classroom tool.
- **Client reshuffles per player.** Cheapest option, but the client doesn't know the answer, so a
  random reshuffle can land on the correct order. That hands out free full marks to 1/6 of
  players at n = 3. Rejected.
- **Drag and drop (`@dnd-kit` or custom pointer events).** This matches "drag" literally, but it
  adds a dependency or fragile iOS touch code, it fights page scrolling, and it is harder to
  drive from Playwright. Rejected in favour of pick-and-place (below).
- **Refactor the reveal into one `reveal_for(question)` helper first.** Cleaner, and it would also
  fix the existing missing `multi_select` reveal in the report. But it touches working code for
  every type. Rejected for this feature's scope; the parity test is the guard instead. Worth
  doing as a separate change.
- **Exact-match-only scoring, or scoring by position.** Not the requirement. Pairwise
  (Kendall-style) scoring gives partial credit that degrades smoothly.

## Detailed Implementation

### Backend

| File | Change |
|---|---|
| `backend/app/common/exceptions.py` | Add `ValidationFailedError(BuzzerError)` (422, code `VALIDATION_ERROR`). |
| `backend/app/schemas/admin.py` | Add `put_in_order` to both `type` regexes. Add `validate_put_in_order(...)` (`type(x) is int`, 200-char item limit) and call it from `QuestionCreate.validate_structure`. |
| `backend/app/services/authoring_service.py` | `update_question`: compute merged values, then the played-question guard (`ConflictError`, 409), then `validate_put_in_order` (`ValidationFailedError`, 422), and only then assign (see Validation → Update path). No FastAPI imports. `import_game_bundle` needs no change. |
| `backend/app/services/game_service.py` | `calculate_score` branch (see Scoring). `record_answer` distribution keys. Reveal branch (both shapes, including COMPLETENESS + `correctOrder`) in the player game-over summary. `get_player_question_summary` also selects `SessionScore.is_correct` and adds `"isCorrect": bool(r.is_correct)` to every row (False when unanswered; all types get it, only `put_in_order` reads it). Reveal and distribution branches in `get_host_question_summary`. Update the `calculate_score` docstring. |
| `backend/app/websocket/gateway.py` | `_answer_reveal` branch. Submission validation in `on_submit_answer` (`type(x) is int`). In `_on_host_advance_impl`, the per-question score query also selects `_Score.is_correct`, and the personal `question_results` payload gains `"yourIsCorrect": bool` (False when the player has no row). `_question_payload` needs no change, because items travel in `config`. |
| `backend/app/services/report_service.py` | `_answer_reveal` branch. Distribution-key handling. A `type_badge` entry ("Put in Order"). A `q.type == "put_in_order"` check before the generic chart choice, then `_render_bar_chart`-style bars as in "Answer distribution" (green for ACCURACY, neutral for COMPLETENESS, none without `correctOrder`). A "Correct order: A → B → C" line **whenever the reveal has `correctOrder`, under both grading types**, the same rule as host `ResultsPage`. (This deliberately differs from FITB, whose report line appears only for ACCURACY, `report_service.py:206`.) The chart captions are the **same strings** as the host's ("Players who placed each item correctly" / "Players who placed each item at this position"). **Every item text goes through `_esc`.** |
| `backend/app/services/export_service.py` | `_pts` rounding helper on every points cell, total and "Points Possible" in `build_canvas_csv` and `build_session_csv` (see "CSV rounding"). |
| `backend/app/services/state_service.py` | No change (see Validation → Other code paths). |
| `backend/app/models/` | No change. |

### Player app (`frontend/player/src`)

- **`types/game.ts`:**
  - Add `'put_in_order'` to the question `type` union.
  - Add `{ type: 'put_in_order'; correctOrder: number[] }` to `PlayerAnswerReveal`, and an
    optional `correctOrder?: number[]` to its `completeness` variant.
  - Allow `orderedIndices` in the answer-data type, and `items?: string[]` in the question
    `config` type.
  - Add `yourIsCorrect: boolean` to `PlayerResultsPayload`, and `isCorrect: boolean` to the
    game-over summary item type.
- **`pages/game/QuestionPage.tsx`:** a new branch. Without it the player sees
  "Unsupported question type."
  - Local state:
    - `order: number[]`, initialised to `[0..n-1]`, i.e. the order of `config.items`
    - `picked: number | null`
  - Render a numbered vertical list of full-width `<button>` rows, one per position, each
    showing `config.items[order[pos]]`.
  - **Pick and place, with insert semantics:**
    - Tapping a row when nothing is picked sets `picked = pos`. The row is highlighted and gets
      `aria-pressed="true"`, and a hint reads "Tap where it goes".
    - Tapping a *different* row `dest` removes the item at `picked` and inserts it at `dest`; the
      other items shift. Concretely: `next = [...order]; const [item] = next.splice(picked, 1);
      next.splice(dest, 0, item)`. The moved item ends at index `dest` in the final array, whether
      it moved up or down. Example: `[a,b,c,d]`, pick 0, tap 2 → `[b,c,a,d]`. Then `picked = null`,
      and the moved row gets a brief highlight.
    - Tapping the picked row again cancels: `picked = null`.
  - A "Lock in" button calls `submit({ orderedIndices: order })`. It is enabled whenever the
    question is open, since any order is a valid submission.
  - **Locked and submitted states** (same pattern as the existing branches, which use
    `submitted` and `questionLocked`):
    - Every row button and the Lock-in button get `disabled={submitted || questionLocked}`, with
      the same `opacity-50 cursor-not-allowed` classes the MC/TF branches use. Row `onClick` also
      returns early in that state.
    - A `useEffect` on `questionLocked` sets `picked = null` when the lock arrives, so no row
      stays highlighted.
    - `order` and `picked` are plain `useState` initialisers and reset **on remount**, exactly
      like the existing `submitted` and `startTimeRef`. Every question arrives through a
      results → question route change, which remounts the page (see the `QuestionPage` gotcha in
      `frontend/player/src/pages/CLAUDE.md`). No question-id effect: resetting only some of the
      component's state that way would be half a fix. Making the page robust to two
      back-to-back `new_question`s is a separate change for all types.
    - After submit, show "Answer submitted — waiting for results…". When locked without a
      submission, show the shared `lockedMsg`.
  - Include `TimerBar`, like the other branches.
  - Give rows stable test hooks: `data-testid="pio-row-<pos>"` and `data-testid="pio-lock-in"`.
- **Partial-credit display (both player pages).** Today both pages treat any `points > 0` as
  correct (`ResultsPage.tsx:43`, `GameOverPage.tsx:66`). That would show "Correct!" / ✓ for an
  almost-reversed order worth 0.17 of 1 point. For `put_in_order` **ACCURACY only** (decided by
  `type === 'put_in_order'` and `answerReveal.type === 'put_in_order'`), the outcome is read from
  the server's correctness flag, **not** from comparing points with `pointsValue`:
  - `isCorrect` → "Correct!" / ✓ (green)
  - `!isCorrect && points > 0` → **"Partially correct"** / **◐** (amber, e.g. `text-amber-400`)
  - otherwise → "Incorrect" / ✗

  This rule replaces only the `isCorrect` computation. In the recap, the existing `noAnswer`
  branch (`GameOverPage.tsx:65`, rendered first at `:83`) keeps precedence, so an unanswered
  question still shows "●" / "No answer", never ✗.

  `isCorrect` is `questionResults.yourIsCorrect` on ResultsPage and `item.isCorrect` in the recap.
  Both are the stored `session_scores.is_correct` (`c == t`), added to the payloads by this feature
  (see the backend table). Comparing points to `pointsValue` would be wrong: the `min` clamp makes a
  non-perfect order score exactly `pv` in some cases (e.g. `pv=0.059, n=6, c=14`; `pv=0.07, n=6,
  c=14`; `pv=0.01, n=4, c=5`), and `pv=0` is allowed (`ge=0`). Rejecting pv values with more
  than 2 dp would not close the gap. The `answer_received.isCorrect` field is not used, because it
  is stale or missing when the player didn't answer this question or reconnected.
  COMPLETENESS and all other types keep today's logic. Matching MC/MS partial points to this is
  out of scope (see Open risks).

  **When the correct order is shown.** The two player pages follow different rules on purpose:
  - Live `ResultsPage`: the "Correct order: …" line shows **whenever `answerReveal.correctOrder`
    is present**, including after a perfect answer (see the ResultsPage bullet below).
  - Game-over recap: the "Correct: …" line keeps the existing recap rule,
    `showCorrectAnswer = !isCompleteness && !isCorrect` (`GameOverPage.tsx:67`), with
    `isCorrect = item.isCorrect`. So it shows for partial and incorrect answers and never for
    COMPLETENESS. The recap is a compact list, and for a perfect order the line would repeat the
    player's own answer. Don't "fix" one rule to match the other.
- **`pages/game/ResultsPage.tsx`:**
  - `describeAnswer`, `put_in_order`: "You answered: A → B → C", built from
    `lastAnswerData.orderedIndices` mapped through `currentQuestion.config.items`.
  - A new "Correct order: A → B → C" line, shown whenever `answerReveal.correctOrder` is present
    (ACCURACY and editor-saved COMPLETENESS). It is built from `correctOrder` mapped through
    `currentQuestion.config.items`, mirroring how fill-in-the-blank shows its accepted answers.
    The e2e test asserts this line.
  - While here, also add the missing `multi_select` branch: "You answered: X, Y".
- **`pages/game/GameOverPage.tsx`:**
  - `describePlayerAnswer`: the player's order, item texts joined with "→".
  - `describeCorrectAnswer`: `correctOrder` mapped to item texts, joined with "→". It is shown
    under the recap rule above (partial and incorrect only).

### Host app (`frontend/host/src`)

- **`types/game.ts`:** add a `put_in_order` variant to `AnswerReveal`, matching the backend
  shape exactly, plus the optional `correctOrder` on the `completeness` variant. Add
  `put_in_order` to the type union. Add `items?: string[]` to **both** question `config` types
  (the `QuestionPayload` one at line 34 and the summary-item one at line 85); host `QuestionPage`,
  `ResultsPage` and `GameOverPage` all read `config.items`.
- **`lib/putInOrder.ts` (new):** `buildPioBars(reveal, distribution, items)`
  returns the bars described in "Answer distribution" (or `[]` without `correctOrder`), and
  `correctOrderText(reveal, items)` returns "A → B → C". Both host pages use them.
- **`pages/game/QuestionPage.tsx`:**
  - `typeLabel`: "Put in Order".
  - Show `config.items` on the big screen in display order, labelled with **letters**
    (A, B, C…, via `String.fromCharCode(65 + i)` like the `optionLabel` helpers in
    `ResultsPage`/`GameOverPage`), **not numbers**. Numbering a scrambled list "1. 2. 3." would
    read as positions.
  - While `questionLocked`, the item list is hidden **together with the prompt**: render it inside
    the existing `{!questionLocked && …}` block (`QuestionPage.tsx:73`).
- **`pages/game/ResultsPage.tsx` `buildBars`:** add a `put_in_order` branch that calls
  `buildPioBars`. It must check `currentQuestion.type === 'put_in_order'` *before* the
  completeness fallback (see the trap in "Answer distribution"). Also show the bar caption and
  the "Correct order: …" line.
- **`pages/game/GameOverPage.tsx`:** `typeLabel` entry. `QuestionCard` for `put_in_order`
  shows **the same bars as ResultsPage** (via `buildPioBars`, from the item's `config.items` and
  `answerDistribution`), **the same caption above the bars** as ResultsPage ("Players who placed
  each item correctly" / "Players who placed each item at this position", chosen by
  `answerReveal.type`), plus the "Correct order: …" line when `correctOrder` is present, plus
  the existing correct/answered counts. Its "N correct · X% accuracy" counts **perfect orders
  only**, because `correctCount` comes from `session_scores.is_correct`, which is `c == t`.
  Partial scores do not count as correct there.
  - **Same trap as `buildBars`:** `QuestionCard` must branch on `type === 'put_in_order'`
    **before any `answerReveal.type` check**. Otherwise a COMPLETENESS `put_in_order` card (reveal
    `type: "completeness"`) falls into the generic completeness path that reads `config.options`.
  - **Number formatting on this page** (see "Points display" below): render `pointsValue`
    (`GameOverPage.tsx:129`, currently raw `{pointsValue}`) with `toLocaleString()`. Compute the
    summary `avg` (`:260–261`) without `Math.round` and render it with `toLocaleString()`, so an
    average of 2.4 points no longer shows as "2". `high` and "Max possible" already use
    `toLocaleString()`.
- **`pages/manage/QuestionEditorPage.tsx`:**
  - Add `put_in_order` to the `QuestionType` union and to `typeLabel`.
  - Form state `pioItems: string[]` holds the items **in correct order**. It defaults to three
    empty strings. A new `put_in_order` question uses `defaultForm`'s `pointsValue` of **1**, the
    same as every other type, so partial scores fall between 0 and 1 (e.g. 0.83). No type-specific
    default is needed. The UI lets the author add rows up to 6, remove rows down to 3, and move
    rows with ▲/▼, which is only for authoring.
  - Each item input has `maxLength={200}`, matching the backend limit.
  - Test hooks for the e2e test: `data-testid="pio-item-<i>"` on each item input,
    `pio-add-row` on the add button, and `pio-remove-row-<i>` / `pio-up-<i>` / `pio-down-<i>` on
    each row's buttons.
  - **Client-side checks before save.** The editor disables Save and shows an inline message under
    the item list when any row is blank after `trim()` ("Every item needs text") or two rows are
    equal as `item.trim().toLowerCase()` ("Items must be different"), matching the server's
    `strip().lower()`. These are the
    likeliest mistakes, since a new question starts with three empty rows. The server 422 stays as
    the backstop. If it fires, the editor's existing error display shows it: a create-path
    Pydantic error goes through `validationMessage` (`frontend/host/src/lib/api.ts:16`), which
    already strips the `"Value error, "` prefix and drops `body` from the location, so the user
    sees just the `ValueError` text. An update-path `VALIDATION_ERROR` shows its `message`.
  - `questionToForm`: rebuild `pioItems` as `correct_order.map(i => config.items[i])`. For
    COMPLETENESS without `correct_order` (imports only), use `config.items` as-is. It also keeps
    the loaded pair in form state as `pioStored: {items, correct_order} | null` (`null` for a
    new question).
  - **Whitespace:** item inputs are not trimmed while the author types. `buildPioPayload` compares
    `trim()`med strings on **both** sides. On a match it resends the **stored** strings verbatim,
    whitespace included. On a mismatch (a real edit) it saves the trimmed new strings. This way an
    imported item like `"Prophase "` never triggers a reshuffle, and a 409 on a played question.
  - `buildPioPayload(pioItems, pioStored, gradingType)` →
    `{config: {items}, answer_data: {correct_order?}}`, with three cases checked in this order:
    1. `pioStored` is set **and has a `correct_order`**, and trimmed `pioItems` equals trimmed
       `pioStored.correct_order.map(i => pioStored.items[i])`: return `pioStored.items` and
       `pioStored.correct_order` **unchanged**. Nothing is reshuffled.
       **Exception:** when `gradingType === 'ACCURACY'` and the stored `correct_order` is the
       identity (`[0, 1, …, n−1]`), skip case 1 and fall through to case 3. The backend accepts an
       identity order for COMPLETENESS (imports only, since the editor never produces one), so
       resending it on a switch to ACCURACY would always fail with 422 ("Display order must differ
       from the correct order"). With the fresh scramble the save succeeds if the question is
       unplayed. If it has been played, the guard returns 409; see Open risks.
    2. `pioStored` is set **with no `correct_order`** (an imported COMPLETENESS question), and
       trimmed `pioItems` equals trimmed `pioStored.items`: return `config.items = pioStored.items`
       verbatim and **omit `correct_order`** (`answer_data: {}`). Never dereference the missing
       `correct_order`.
    3. Otherwise (a new question or edited items): scramble with Fisher–Yates, reshuffling until
       concordant pairs ≤ `floor(t/2)`, and send both fields.
  - **`correct_order` is always sent, under both grading types, except in case 2 above.** Sending
    it normally protects a later COMPLETENESS → ACCURACY switch: without it, `questionToForm`'s
    `config.items` fallback would treat the scramble as the "correct" order and silently lose the
    author's order. Case 2 is the exception: inventing a `correct_order` the stored question doesn't
    have would make the played-question guard see `None → [...]` and return 409 on a prompt-only
    edit. Switching such a question to ACCURACY without touching the items fails validation with
    a 422 (ACCURACY requires `correct_order`). The author has to re-enter the items to get a
    scramble, which returns 409 if the question has been played. That is acceptable for an
    import-only edge case.
  - `formToPayload`: for `put_in_order`, `points_value = form.pointsValue` under both grading
    types.
  - In `QuestionForm`, show the points field for `put_in_order` even under ACCURACY.
  - A 409 from the played-question guard shows the server's `message` in the editor's existing
    error display.

### Other

- **Points display (one rule, all UIs).** Every points value shown on screen, per-question or
  total, goes through `Number.prototype.toLocaleString()` with no options. That shows at most 3
  fraction digits, so float32 read-back (`0.8299999833…` → "0.83") and float-sum noise never
  appear, and 0.125 still shows as "0.125". Payloads are **not** rounded; only display and the
  CSV exporters (`_pts`) are. Status per page, checked against the code:
  - Player `ResultsPage`: `+{yourPoints.toLocaleString()} pts` and the total (`ResultsPage.tsx:76,
    82`). Already compliant, no change. `yourPoints` comes from MySQL via `_on_host_advance_impl`.
  - Player `GameOverPage` recap: `+{item.pointsAwarded.toLocaleString()}` (`:112`) and the final
    score (`:144`). Already compliant.
  - Host `GameOverPage`: `high` and "Max possible" are compliant. `pointsValue` (`:129`) and `avg`
    (`:260–261`) change, as listed under the host `GameOverPage` bullet.
  - HTML report: already formats `max_possible` and `avg` with `:g` and `round(avg, 1)`
    (`report_service.py:488, 518, 536, 544`), which hides the same noise. The `put_in_order`
    branch prints no points values (only counts and item text). No change.
  The MySQL read-back itself was not verified, because the Docker stack wasn't running when this
  was written. The rule makes the answer irrelevant.
- **`scripts/simulate_players.py`:** answer `put_in_order` with a random permutation. When
  `--game-json` is given, submit the correct order with probability `accuracy`. Update the
  header docstring.
- **Sample game:** append one `put_in_order` question (ACCURACY, `points_value` 1) to
  `sample_games/cs_first_day.json`. Use a CS-flavoured sequence to fit the file, e.g. the
  compile pipeline "Lexing → Parsing → Type checking → Code generation". Use exactly
  `config.items = ["Parsing", "Code generation", "Lexing", "Type checking"]` and
  `answer_data.correct_order = [2, 0, 3, 1]`. That maps back to Lexing, Parsing, Type checking,
  Code generation, and the display order has 3 concordant pairs (≤ `floor(6/2)`).
- **Context hierarchy** (per `.claude/rules/context-sync.md`): update
  - `backend/app/schemas/CLAUDE.md`: fix line 9. Only `QuestionCreate` carries
    `validate_structure`; `QuestionUpdate` has no validator (`put_in_order` updates are validated
    in `authoring_service.update_question`).
  - `backend/app/CLAUDE.md`: line 40 says reveal logic lives in "three" places; it is now four
    (gateway, report, and two in `game_service`), guarded by the parity test
  - `backend/app/services/CLAUDE.md`: reveal now has four copies, there's a new type, and
    `export_service` rounds points with `_pts`
  - `backend/app/websocket/CLAUDE.md`: new submission check, `yourIsCorrect` in the personal
    `question_results`
  - `frontend/player/src/pages/CLAUDE.md`: drop the "ResultsPage lacks multi_select" note once
    it's fixed. Add that `put_in_order` ACCURACY shows "Partially correct" / ◐ from
    `yourIsCorrect` / `isCorrect`, and the two different correct-order rules
  - `frontend/host/src/pages/CLAUDE.md`: line 91 ("touches the host in three places") gains the
    `buildPioBars` helper in `lib/putInOrder.ts` and the question-type branch before the
    completeness fallback in `buildBars`
  - `frontend/host/src/lib/CLAUDE.md`: list the new `putInOrder.ts` (`buildPioBars`,
    `correctOrderText`)
  - `backend/app/common/CLAUDE.md` (line 13–14): add `ValidationFailedError` (422,
    `VALIDATION_ERROR`) to the list of `BuzzerError` subclasses
  - `backend/app/models/CLAUDE.md` (lines 38–40): question JSON is enforced by
    `QuestionCreate.validate_structure` **and**, for `put_in_order` updates, by
    `authoring_service.update_question`
  - `backend/app/schemas/CLAUDE.md` (lines 32–36): the gotcha calling `validate_structure` the
    "single place" for per-type validation; `put_in_order` validation lives in the shared
    `validate_put_in_order` helper, called from there and from `update_question`. The reveal
    builders now also include the two in `game_service` (four total). This is in addition to the
    line 9 fix above.
  - `frontend/player/src/CLAUDE.md` (line 30): drop "`ResultsPage` already lacks `multi_select`"
  - `frontend/host/src/pages/CLAUDE.md` (lines 96–97): `formToPayload` derives ACCURACY
    `points_value` on the client **except for `put_in_order`**, where it is authored directly

### Tests

**Unit, `tests/unit/test_put_in_order.py`.** Pure functions, no Docker, following
`tests/unit/test_auth.py`'s setup.

- `calculate_score` table, using `MagicMock` questions:
  - identity order at n = 3, 4, 5, 6 → full points, `is_correct=True`
  - reversed order → 0
  - one adjacent swap → `round_half_up(pv·(t−1)/t, 2dp)`, e.g. `pv=1, n=4` → 0.83
  - `pv=1, n=6, c=1` → 0.07
  - `pv=1, n=3, c=1` → 0.33, and `c=2` → 0.67
  - `pv=0.15, n=4, c=1` → **0.03** (half-up regression; `round(0.15*1/6, 2)` gives 0.02)
  - `pv=0.029999999329447746` (float32 read-back of 0.03), `n=4, c=1` → **0.01**. The exact
    value 0.005 rounds half-up to 0.01. Without the `round(pv, 6)` step the noisy 0.004999…
    gives 0.00, so this case fails if that step is dropped.
  - `pv=0.125`, perfect order → **0.125** exactly (no rounding to 0.13)
  - `pv=0.059, n=6, c=14` → **0.059** (clamped; the raw score 0.05507 rounds to 0.06) **and
    `is_correct=False`**. This is the case where points equal `pv` without a perfect order.
  - `pv=0`, any non-perfect order → 0 with `is_correct=False`; perfect order → 0 with
    `is_correct=True`
  - `pv=1000, n=4, c=5` → 833.33
  - the result is a `float` with at most 2 decimal places (or `pv` itself) in every case
  - COMPLETENESS with any permutation → full points
  - `{}` → 0
  - non-permutation submission → 0
  - `[True, 0, 2]` (bool posing as int) → 0
- `QuestionCreate`:
  - accepts n = 3 and n = 6, and a 200-char item
  - rejects n = 2 and n = 7, duplicate items (including case/whitespace variants), blank items,
    a 201-char item, a non-string item, and a `config` with any key besides `items`
  - accepts `"  " + 200 chars + "  "` (length is checked after `strip()`)
  - rejects `correct_order` that is the wrong length, has repeats, is out of range, contains
    non-ints, contains a bool (`[True, 0, 2]` for n = 3), or is the identity (ACCURACY)
  - accepts COMPLETENESS without `correct_order`
- `validate_put_in_order` gives the same verdicts when called directly; this is the helper the
  update path uses.
- **Reveal parity:** for one ACCURACY question, one COMPLETENESS question with `correct_order`
  and one COMPLETENESS question without it (all `put_in_order`),
  `gateway._answer_reveal`, `report_service._answer_reveal`, and the two `game_service` reveal
  branches produce identical dicts. Import `app.websocket.gateway._answer_reveal` directly. That
  works without Docker: `tests/unit/test_auth.py:39` already imports `app.main`, which imports the
  gateway (`main.py:18`). `settings` has defaults, the DB engine and Redis connect lazily, and the
  root `pytest.ini` sets `pythonpath = backend`. The two `game_service` copies are inline
  `if/elif` chains in the query loops today (`get_player_question_summary` ~line 545,
  `get_host_question_summary` ~line 657). Pull each chain, unchanged for the other types, into a
  module-level function with these names and this signature:
  - `_player_summary_reveal(q_type: str, grading_type: str, answer_data: dict, points_value: float) -> dict`
  - `_host_summary_reveal(q_type: str, grading_type: str, answer_data: dict, points_value: float) -> dict`

  Each loop then calls its function with the row's fields. The parity test calls both with the
  same fields it gives the `Question`-based `gateway._answer_reveal` / `report_service._answer_reveal`
  (a `SimpleNamespace` with `type`, `grading_type`, `answer_data`, `points_value`). The extraction
  is behaviour-neutral, and the existing integration scenarios cover the other types' reveals.
- **CSV rounding:** with mocked `db` results holding float32-style values (`0.8299999833106995`,
  `0.6700000166893005`, `0.125`), `build_canvas_csv` (both modes) and `build_session_csv` write
  no points cell, total or "Points Possible" with more than 4 decimal places, and `0.125` stays
  `0.125`.

**Integration, `tests/integration`.** Runs against the Docker stack on :8000.

**What the harness can and cannot do** (checked against `tests/integration/`; the plan below
is built on these facts):

- `engine/orchestrator.run_game(base_url, host_token, player_tokens, room_code, scenario)` plays
  **any existing room**. It does not create a game. `scenario.questions` is used only for the
  question count and log lines, and `player_scripts[i].responses[q]` supplies each answer
  (`None` = skip). `test_host_admin_restructure.py::completed_sessions` already uses it this way on
  a game built through the REST API. So a played session for any game, including an imported
  one, needs only `create_room` + `create_guest_tokens` + `run_game` with a `GameScenario` whose
  `questions` list has the same length and order as the game's questions.
- `run_game` blocks on `answer_received` for every submitting player. A rejected submission
  produces only an `error` event (`gateway._emit_error`), so rejected answers **cannot** go
  through a scenario; the run would hang until `_EVENT_TIMEOUT`.
- `run_game` waits for each `question_results` but throws the payloads away, and returns only the
  players' `game_over` payloads.
- The tests have **no database access** (no MySQL driver or connection in `tests/integration`).
  "No `session_scores` row was written" can only be proved through observable behaviour: the
  next valid submission gets an `answer_received` **without** `alreadyAnswered` (the gateway's
  `has_answered` check would otherwise short-circuit, `gateway.py:1117`), and the game-over recap
  shows that valid answer as the stored `playerAnswer`.
- There is no single-question GET. "Follow-up GET" below means
  `GET /api/host/games/{game_id}/questions` and picking the question by id.
- `conftest.create_questions` posts through `/api/admin/games/{id}/questions` (so it goes through
  `QuestionCreate`) and returns the new ids in order. The `game_setup` fixture creates an
  unattached course + game as admin. Admin may run it, and that is how `test_game_flow` works today.

**Engine, `engine/scoring.py`:**
- Widen the types to `float`: `QuestionSpec.points_value: float`, `compute_question_score -> float`,
  `compute_player_score -> float`, `GameScenario._expected_scores: list[float]` and
  `expected_scores -> list[float]`. Don't "fix" fractional values with `int()`. Update the
  `QuestionSpec.type` comment.
- `compute_question_score`: a `put_in_order` branch that mirrors the backend exactly. Validate
  `orderedIndices` (`type(x) is int`, permutation, else 0), then COMPLETENESS → `points_value`,
  then ACCURACY: count concordant pairs, `c == t` → `points_value`, otherwise
  `min(float((Decimal(str(round(pv, 6))) * c / t).quantize(Decimal("0.01"), ROUND_HALF_UP)), pv)`.
  It must come **before** the existing `grading_type == "COMPLETENESS"` short-circuit, so an
  invalid order isn't credited. (Rejected orders never reach scoring in practice; this keeps the
  mirror honest.)
- Add `expected_is_correct(q, response) -> bool | None`: for `put_in_order` it returns `c == t`
  under ACCURACY, `True` under COMPLETENESS (the backend's COMPLETENESS branch returns
  `is_correct=True`, `game_service.py:359`), and `False` for `None`. For every other type it
  returns `None`, meaning "not asserted". `compute_expected_summary` adds it to each entry as
  `"isCorrect"`.
- **`_build_reveal` has the same trap as host `buildBars`:** it returns `{"type": "completeness"}`
  before any type branch. The `put_in_order` check must come **first**: ACCURACY →
  `{"type": "put_in_order", "correctOrder": [...]}`; COMPLETENESS with `correct_order` →
  `{"type": "completeness", "correctOrder": [...]}`; COMPLETENESS without it → falls through to
  the existing `{"type": "completeness"}`.
- The engine has no `multi_select` branch. Leave that alone.

**Orchestrator, `engine/orchestrator.py`:** `run_game` gains an optional keyword argument
`results_sink: list | None = None`. When it is given, after each question the orchestrator appends
`{"host": <host question_results payload>, "players": [<each player's question_results payload,
in player_tokens order>]}`. Those are the payloads it already awaits and currently discards. The
return value and every existing caller stay unchanged. `run_game_with_timer_expiry` doesn't change.

**`test_game_flow.py`** (the two exact comparisons must change, or every partial score fails on
float32 read-back):
- `_assert_player_outcome`: line 113 (`yourFinalScore`) and line 135 (per-question
  `pointsAwarded`) compare with `pytest.approx(expected)`, not `==`. The default tolerance
  (rel 1e-6) covers float32 read-back (relative error ~6e-8) and float-sum noise, and stays exact
  enough to catch a wrong score: 0.83 vs 0.84 is about 1e-2.
- `_assert_player_outcome`: when `expected["isCorrect"] is not None`, assert
  `actual_q["isCorrect"] == expected["isCorrect"]`.
- `_assert_answer_matches`: add an `orderedIndices` branch (exact list equality).
- `_assert_reveal_content`: the `completeness` early return (line 220) first checks that
  `actual.get("correctOrder") == expected.get("correctOrder")` (both `None` for non-pio
  questions, so existing types are unaffected). Add a `put_in_order` branch asserting
  `correctOrder` equality. Order matters, so compare lists, not sets.
- `test_game_scenario` passes `results_sink=[]` to `run_game` (not to the timer variant) and, for
  each **`put_in_order`** question `q`, asserts against `sink[q]`:
  - each player's `yourPoints == pytest.approx(compute_question_score(...))`, and `yourIsCorrect`
    `== expected_is_correct(...)` (`False` for a skipped player)
  - the host's `answerDistribution` equals the expected `{"i@p": count}` dict, built from the
    submitted orders (one key per item per answer)
  - the host `answerReveal` equals `_build_reveal(q)`
  These live-payload checks cover `put_in_order` only; extending them to other types is
  possible but out of scope.

**Scenario, `scenarios/all_question_types.py`:** a **new** `GameScenario` named
`put_in_order_scoring`, added to `SCENARIOS`, rather than extra questions in `ALL_TYPES` (which
would need new responses for all of its players). Two questions, each with 4 items and
`points_value=1`:
- `PIO_ACCURACY`: `config.items = ["C", "A", "D", "B"]`, `correct_order = [1, 3, 0, 2]`
- `PIO_COMPLETENESS`: same items and `correct_order`, `grading_type="COMPLETENESS"`

Four players, each giving the same response to both questions:

| Player | `orderedIndices` | ACCURACY | COMPLETENESS |
|---|---|---|---|
| perfect | `[1, 3, 0, 2]` | 1, `isCorrect` true | 1 |
| one adjacent swap | `[3, 1, 0, 2]` | 0.83, false | 1 |
| reversed | `[2, 0, 3, 1]` | 0, false | 1 |
| no answer | `None` | 0, false | 0 |

Totals 2, 1.83, 1, 0 give a strict ranking, so `_assert_ranking_order` checks it.

**Edge scenario (optional), `scenarios/edge_cases.py`:** `timer_expiry_put_in_order`, an
`EdgeScenario` with `requires_fast=True, uses_timer_expiry=True`, `PIO_ACCURACY`, one player
answering perfectly and one never answering. It only runs under `--fast`. (The plain "no answer →
0" case is already covered by the scenario above and needs no `--fast`, because `run_game`
advances manually.)

**New file, `tests/integration/test_put_in_order.py`**, for what scenarios can't express. It
reuses `conftest` helpers (`create_questions`, `create_room`, `create_guest_tokens`) and the
`Api`/`Cleanup` pattern from `test_host_admin_restructure.py`. Each fixture deletes its games on
teardown.

- **Rejected submissions** (`test_invalid_orders_are_rejected_then_valid_accepted`): a standalone
  async test that drives `engine/socket_client.TestSocketClient` directly, with one host and one
  guest, and a game with one `PIO_ACCURACY` question.
  - Steps: join the room, wait for `sync_state`, host `host_advance`, wait for `new_question`.
  - For each bad payload in order, emit `submit_answer` and `wait_for("error")`, and assert that the
    message is the `put_in_order` one. Bad payloads: `[0,0,1,2]` (duplicate), `[0,1,2]` (missing),
    `[0,1,2,9]` (out of range), `"0123"` (non-list), `[True,0,2,3]` (JSON `true`).
  - The bool case must be `[True,0,2,3]`: it sorts to `[0,1,2,3]` (because `True == 1`), so only
    the `type(x) is int` rule rejects it. `[True,0,1,2]` would be caught by the plain permutation
    check and wouldn't test the bool rule.
  - Then emit the valid `[3,1,0,2]` and `wait_for("answer_received")`. Assert that it has **no**
    `alreadyAnswered`, `pointsAwarded == pytest.approx(0.83)` and `isCorrect is False`. This proves
    that none of the rejected payloads was recorded.
  - Advance to results and to game over. The recap's `playerAnswer` is
    `{"orderedIndices": [3,1,0,2]}`.
- **Module fixture `played_game`** (scope `module`):
  1. Create a course + game as admin, with an `MC_ACCURACY` question and the `PIO_ACCURACY` and
     `PIO_COMPLETENESS` questions via `create_questions`.
  2. Play one session with `run_game` and one guest answering all three.
  3. **Then** add an unplayed `MC_ACCURACY` question.
  4. Yield all the ids.

  Questions added after the session have no `session_scores` rows, so they count as unplayed.
- REST tests (all through `/api/host/...` with the admin token, which passes both host gates):
  - `POST` returns 422 for an identity `correct_order`, for 2 items, and for a `config` with an
    extra key
  - a `PUT` that makes a valid, **unplayed** `put_in_order` question invalid returns 422 with
    `error == "VALIDATION_ERROR"`. Use a fresh question created in the test, so the shared
    fixture isn't mutated. A follow-up GET shows it unchanged.
  - on the played `PIO_ACCURACY`: a prompt-only `PUT` returns 200, and `config.items` and
    `correct_order` are unchanged. A `PUT` changing `config.items`, `correct_order`, or `type`
    returns 409.
  - type-change guard: the played `MC_ACCURACY` question `PUT` to `type: "put_in_order"` with valid
    items returns 409. The same change on the unplayed MC question returns 200.
  - importing a bundle (`POST /api/host/games/import`, form field `course_id`) with an identity
    `correct_order` returns 422
  - **Item 1 regression** (its own setup):
    1. Import a bundle with one COMPLETENESS `put_in_order` question and **no** `correct_order`.
    2. Find its id via the questions list, and play one session through `run_game`. The
       scenario's single `QuestionSpec` mirrors the imported question, and the one guest
       answers `[0,1,2,3]`.
    3. `PUT` a new `prompt`, `config.items` verbatim and `answer_data: {}`. It returns 200; the
       follow-up GET shows the items unchanged and still no `correct_order`.
    4. The same `PUT` with an added `correct_order` returns 409.
    5. Delete the imported game on teardown.

**E2E (Playwright), `tests/e2e/test_put_in_order_ui.py`.** Runs against nginx on :8080 after
`npm run build`, reusing the `env`, `page_as` and `cleanup` fixtures from `tests/e2e/support.py`
and `conftest.py`.

**Structure: two independent test functions**, so a failure in one can't cascade and nothing
depends on pytest's run order:
- `test_put_in_order_authoring`: step 1 below
- `test_put_in_order_play_through`: steps 2–4 in one function, sharing one game, room and session

All items use the **literal texts** `"A"`, `"B"`, `"C"`, `"D"` (correct order A, B, C, D), so the
expected strings below are item texts, not the host's letter labels.

**Editor selectors.** `QuestionEditorPage.tsx` has no `data-testid`s today. The `put_in_order`
form adds:
- `data-testid="pio-item-<i>"` on each item input
- `pio-add-row` on the add-row button
- `pio-remove-row-<i>`, `pio-up-<i>` and `pio-down-<i>` on each row's buttons

The type picker, prompt field and Save button are found with the role/placeholder selectors
`test_host_admin_ui.py` already uses (`get_by_role`, `get_by_placeholder("Question text…")`).

1. **Authoring** (`test_put_in_order_authoring`, its own game via `cleanup`):
   - The host opens the game's question editor and picks "Put in Order".
   - They click `pio-add-row` once (the form starts with 3 rows), fill `pio-item-0` … `pio-item-3`
     with `A`, `B`, `C`, `D`, and save.
   - Fetch the question via the API and check that `config.items` is a permutation of the
     authored items, that it is not in the authored order, and that
     `correct_order.map(i => items[i])` equals the authored order.
   - Reopen the question in the editor and check that `pio-item-0..3` hold A, B, C, D (the
     authored, correct order).
   - Edit only the prompt and save again. Fetch via the API: `config.items` and `correct_order`
     are identical to the first save (no reshuffle).

**Setup for `test_put_in_order_play_through`.** One game with two questions, both created
**through the API** (`POST /api/host/games/{game_id}/questions`) with fixed data, so the tap
targets are known without parsing a random scramble. Both are ACCURACY with `points_value` 1:
- Q1, prompt `"Order the letters (1)"`: `config.items = ["B", "D", "A", "C"]`,
  `correct_order = [2, 0, 3, 1]`
- Q2, prompt `"Order the letters (2)"`: `config.items = ["C", "A", "D", "B"]`,
  `correct_order = [1, 3, 0, 2]`

Both map back to A, B, C, D, are non-identity, and have 3 concordant pairs. UI authoring is
covered by the authoring test. In the game-over recap the two rows are told apart by their
prompt text.

**Tap sequences.** The player page shows only the display order, so the test computes its clicks
with a small helper in the test file, `taps_to_reach(start, target) -> list[tuple[int, int]]`.
`start` is the initial on-screen order, always `list(range(n))`, and `target` is the desired final
list of item indices. For each `pos` in `0..n-1`, find the current index `k` of `target[pos]`. If
`k != pos`, record the tap pair `(k, pos)` and apply the same insert (`splice(k,1)`,
`splice(pos,0,…)`) to a local copy. With insert semantics, earlier positions are never disturbed,
so this needs at most `n−1` pairs. Each pair is two clicks: `pio-row-k`, then `pio-row-pos`.
- Q1 target: `[2, 0, 3, 1]` (its `correct_order`)
- Q2 target: `[3, 1, 0, 2]`, i.e. Q2's `correct_order` with positions 0 and 1 swapped (one
  adjacent swap → `c = t−1` → 0.83 at n = 4)

2. **Play-through, Q1 (perfect):**
   - Start a room from the host page and join it from a player page.
   - On the player page, all 4 items render.
   - Tap the same row twice: the highlight clears (cancel works).
   - Apply `taps_to_reach(list(range(4)), [2, 0, 3, 1])` as pick-and-place clicks, then lock in.
   - The player results screen shows full points and the line
     "Correct order: A → B → C → D".
   - The host results page renders 4 bars (`pio-bar-0` … `pio-bar-3`), each with
     `pio-bar-<p>-count` text "1", under the "placed correctly" caption.
3. **Play-through, Q2 (partial credit):**
   - The host advances to Q2. The player applies
     `taps_to_reach(list(range(4)), [3, 1, 0, 2])` (B, A, C, D: one adjacent swap from correct)
     and locks in.
   - The player results screen shows **"Partially correct"**, "+0.83 pts", and the
     "Correct order: A → B → C → D" line.
4. **Game over (after Q2):**
   - The recap row with prompt "Order the letters (1)" shows ✓ and "A → B → C → D", with no
     "Correct:" line.
   - The recap row with prompt "Order the letters (2)" shows ◐, "B → A → C → D", and
     "Correct: A → B → C → D".

## Open risks

- **The scramble is the same in every session, for the question's lifetime**, so students can
  share "move X to the top". Re-saving does *not* reshuffle (by design, to protect history). For
  a fresh scramble the author creates a new question.
- **A played, imported COMPLETENESS question with an identity `correct_order` can't become
  ACCURACY.** Resending the stored order fails with 422 (identity rule), and the editor's fresh
  scramble (the case 1 exception) changes `config.items`, so the played-question guard returns
  409. The author must create a new question. This is the same import-only class of dead end as
  `buildPioPayload` case 2; it can't be fixed without either relaxing the guard or accepting an
  identity order under ACCURACY, and both are worse.
- **Items of a played question can't be fixed.** A typo in an item after the question has been
  played needs a new question (409 otherwise). That's the price of keeping past reports correct.
- **The other types still have the underlying problem.** Reordering a played MC or multi-select
  question's options corrupts its history in the same way, and its type can still be changed.
  Out of scope here; the `put_in_order` guard could be generalised later.
- **Pick-and-place is less discoverable than drag.** The hint text and the move highlight carry
  that.
- **Editing a question that is open in a live room.** Before anyone has answered there is no
  `session_scores` row, so the played-question guard passes and the host can change the items.
  Players then submit indices against the old display order. MC has the same risk today.
- **A player who reconnects mid-question loses their local order** and starts again from the
  display order. Acceptable.
- **Points columns are single-precision `FLOAT`** on MySQL. The exporters round to 4 dp to hide
  this, and scoring rounds `pv` to 6 dp before the half-up step, but a migration to `DOUBLE` is
  out of scope. The unit tests use exact `MagicMock` pv values, so they don't exercise the noisy
  read-back.
- **Four reveal copies remain.** The parity test catches drift but doesn't remove it.
- **"Partially correct" is `put_in_order`-only.** MC/MS answers with partial points still show
  "Correct!", because the player pages treat any `points > 0` as correct. The inconsistency is
  deliberate and in scope only for this type. Aligning the others is a separate change.
- **Fractional scores and float totals.** Partial scores are 2-decimal floats, and running totals
  are summed as Python floats (`state_service.update_player_score`), so a total can come out as
  `1.5000000000000002`. Per-question points read from MySQL may also carry float32 noise
  (`0.8299999833…`). Both are handled by the "Points display" rule (Detailed Implementation →
  Other). Multi-select already has the same behaviour.
- **"Between 0 and 1" holds only at the default.** `points_value` is still editable, and scores
  scale with it (pv = 10 gives 8.33 for one swap).
