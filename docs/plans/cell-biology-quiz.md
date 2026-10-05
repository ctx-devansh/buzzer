# Spec: sample game "Cell Biology: Cells and Division"

Status: agreed in design discussion. Revised after the first Goldfish test (critic items 1–9,
each checked against the code). Not yet implemented.
Branch: `feature/new-sample-games`. Owner's T6 **classroom** game.

## Problem

T6 (see `instructions.md`) asks each team member for two new, distinctly named quiz files under
`sample_games/`. This one is the classroom game: intro-college biology, professional tone, about
13 questions. It must:

- include at least one question of **every supported type**
- use both `ACCURACY` and `COMPLETENESS` grading
- ship as `"version": 1`
- import cleanly via the Admin UI, the Host UI, or the API

The deliverable is one new JSON file. No source code changes.

## Technical Plan

### What "supported" and "imports cleanly" mean in this codebase

Checked against the code on `main` at `357e463`:

- **Importer:** `authoring_service.import_game_bundle` (`backend/app/services/authoring_service.py`)
  requires `format == "buzzer/game"` and `version == SUPPORTED_IMPORT_VERSION` (= 1). It checks
  `game` with `GameCreate` and every question with `QuestionCreate(**q)` (both in
  `backend/app/schemas/admin.py`). Any failure rejects the whole file with a 422. A `course_id`
  in the file is discarded.
- **`extra="forbid"`** on both schemas. A question may contain only `type`, `grading_type`, `prompt`,
  `config`, `answer_data`, `time_limit_seconds`, `points_value` (and `order_index`, which this file
  omits, since array position sets the order). `game` may contain only `title`, `description`,
  `max_players`.
- **Limits:** title 1–255 chars, description ≤ 5000, `max_players` 1–500, `prompt` 1–2000 chars,
  `time_limit_seconds` 2–300, `points_value` 0–100000. Prompts go through `bleach.clean` on import
  (`authoring_service.sanitize_prompt`), which escapes `&`, `<` and `>` to `&amp;`, `&lt;`, `&gt;`.
  So prompts must not contain **`&`, `<` or `>`**: write "and" instead of "&". Options, items and
  accepted answers are not sanitised, but they follow the same rule for consistency.
- **Supported types:** the `type` regex accepts five: `multiple_choice`, `true_false`,
  `fill_in_the_blank`, `multi_select`, `put_in_order`. `put_in_order` is a team (T7) type, so
  "every supported type" includes it. T7's canvas type is **not** implemented yet. When it
  lands, this file needs a canvas question to stay compliant (see Open items).

### Structural rules per type (enforced by `QuestionCreate.validate_structure`)

| Type | ACCURACY needs | COMPLETENESS needs |
|---|---|---|
| `multiple_choice` | `config.options` (≥ 2) and `answer_data.answer_points`, the same length, non-negative numbers | `config.options` (≥ 2); `answer_data: {}` |
| `true_false` | `answer_data.answer_points` with exactly the keys `"true"` and `"false"`; `config: {}` | `config: {}`, `answer_data: {}` |
| `fill_in_the_blank` | `acceptedAnswers` (non-empty strings), `answerPoints` (same length, ≥ 0), `editDistance` (int ≥ 0); `config: {}` | `config: {}`, `answer_data: {}` |
| `multi_select` | `config.options` (≥ 2) and `answer_points`, the same length (negatives allowed) | `config.options` (≥ 2); `answer_data: {}` |
| `put_in_order` | `config` has **only** `items` (3–6 distinct strings, compared trimmed and lower-cased, ≤ 200 chars each), listed in **scrambled** display order. `answer_data.correct_order` is a permutation of the item indices in correct sequence and must **not** be the identity | the same `config`; `correct_order` may be omitted |

### Scoring rules the validator does *not* catch (`game_service.calculate_score`)

If one of these is wrong, the file still imports but players get marked wrong. The file must
satisfy all of them:

1. **MC / TF ACCURACY:** a player counts as correct only when `points == points_value`, so the right
   option's points must **equal** `points_value`. Wrong options get `0.0`.
2. **multi_select ACCURACY:** score = sum of the picked `answer_points`, floored at 0. Correct means
   score ≥ `points_value`. So `points_value` = **sum of the positive points**.
3. **FITB ACCURACY:** the player's text is lower-cased and whitespace-collapsed, then matched to each
   accepted answer (also normalised) by Levenshtein distance ≤ `editDistance`. A tolerance > 0 on
   a short answer accepts wrong answers ("g" is distance 1 from "s", "45" is distance 1 from "46").
   So every ACCURACY FITB in this file uses `editDistance: 0`. The flip side: with distance 0, any
   phrasing not listed scores zero. "46 chromosomes" is 12 edits from "46", and hyphens and extra
   words count as edits. So each FITB ACCURACY question both **narrows its prompt** (e.g. "Answer
   with a number.") and **lists the natural variants** (with a unit, hyphenated, spelled out).
4. **put_in_order ACCURACY** gives partial credit by pairs: `points_value × c / t`, where `t = n(n−1)/2`
   and `c` counts item pairs in the correct relative order. The display scramble should have
   **c ≤ floor(t/2)**, the same rule the host editor applies, so a player who locks in without
   moving anything earns at most about half.

### File conventions (match `sample_games/cs_first_day.json`, `data_structures.json`)

Content:
- Points are written as floats (`1.0`).
- multi_select ACCURACY scores **+1.0** for each correct option and **−1.0** for each distractor.
- Single-answer ACCURACY questions are worth **1.0**.
- COMPLETENESS questions are worth **1.0** and have `answer_data: {}`.
- `max_players: 150`.

Layout (doesn't affect function, but fixes one canonical file):
- 2-space indent, UTF-8, LF line endings, trailing newline.
- **Non-ASCII characters are written literally.** The em dash in Q1 is the character itself
  (—), not the JSON escape sequence (backslash, `u`, `2014`), as in `cs_first_day.json`.
- **Key order inside each question:** `type`, `grading_type`, `prompt`, `config`, `answer_data`,
  `time_limit_seconds`, `points_value`. Inside a FITB `answer_data`: `acceptedAnswers`,
  `answerPoints`, `editDistance`.
- **Arrays of strings (`options`, `items`, `acceptedAnswers`) go one element per line.** Number
  arrays (`answer_points`, `answerPoints`, `correct_order`) stay on one line, e.g.
  `"answer_points": [0.0, 1.0, 0.0, 0.0]`.
- The TF `answer_points` object spans several lines, one key per line (`"true"` first), as in
  `cs_first_day.json`.
- Empty objects are written as `{}`.

## Alternatives

- **Four mitosis phases instead of five (drop Prometaphase).** Some courses teach four phases.
  Rejected because the target is intro college, and the standard intro text (Campbell) teaches
  five. If the instructor teaches four, change Q7 to four items with a scramble re-checked
  against rule 4.
- **The whole cell cycle (G1, S, G2, M, Cytokinesis) as the put_in_order question.** Unambiguous,
  but it overlaps with Q5 (S phase). Rejected.
- **A COMPLETENESS multi_select instead of Q13 (COMPLETENESS put_in_order).** That would give a
  richer host chart. A COMPLETENESS `put_in_order` with no `correct_order` shows only
  "N / M answered" and no bars. Rejected, because Q13 is the only coverage of that combination,
  and a self-ranking has no correct order to store.
- **FITB with a typo tolerance of 1 on Q5/Q9.** More forgiving, but it awards points for wrong
  answers (rule 3). Rejected in favour of explicit variants.
- **Bumping `version`.** No new format features are used, so the file stays at 1.

## Detailed Implementation

### File

Create **`sample_games/cell_biology_cells_and_division.json`**. Don't modify any existing file in
`sample_games/`. The starter files don't count toward T6.

Top level, in this key order: `format`, `version`, `game`, `questions`.

```
format:  "buzzer/game"
version: 1
game.title:       "Cell Biology: Cells and Division"
game.description: "An intro-college review of cell structure, the cell cycle, mitosis, and
                   meiosis. Most questions are graded for accuracy; a few check in on how
                   confident you feel."   (one line in the file)
game.max_players: 150
```

### Questions, in array order

Every question below lists all its fields. `config: {}` / `answer_data: {}` are written out
explicitly even when empty, as in the existing files. Option and item strings are exact.

**Q1 — `multiple_choice`, `COMPLETENESS`, 1.0 pts, 20 s**
- prompt: `Before we start: how confident do you feel about cell division right now?`
- options: `Very confident — I could explain it to a classmate`, `Fairly confident`,
  `Somewhat unsure`, `Not confident yet`
- answer_data: `{}`

**Q2 — `multiple_choice`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `Which organelle is the main site of ATP production in eukaryotic cells?`
- options: `Golgi apparatus`, `Mitochondrion`, `Ribosome`, `Lysosome`
- answer_points: `[0.0, 1.0, 0.0, 0.0]`

**Q3 — `true_false`, `ACCURACY`, 1.0 pts, 15 s**
- prompt: `Prokaryotic cells lack a membrane-bound nucleus.`
- answer_points: `{"true": 1.0, "false": 0.0}`

**Q4 — `multi_select`, `ACCURACY`, 3.0 pts, 30 s**
- prompt: `Which of these structures are found in typical plant cells but NOT in animal cells? Select all that apply.`
- options: `Cell wall`, `Mitochondria`, `Chloroplasts`, `Ribosomes`, `Large central vacuole`
- answer_points: `[1.0, -1.0, 1.0, -1.0, 1.0]` (positives sum to 3.0 = `points_value`)
- Note: plant cells do have mitochondria and ribosomes, so both are real distractors.
  Don't add centrioles, which are debatable.

**Q5 — `fill_in_the_blank`, `ACCURACY`, 1.0 pts, 25 s**
- prompt: `During interphase, DNA is replicated in the ___ phase. (Answer with the phase's letter.)`
- acceptedAnswers: `["S", "S phase", "S-phase", "synthesis", "synthesis phase", "DNA synthesis", "DNA synthesis phase"]`
- answerPoints: `[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]`
- editDistance: `0`
- Note: the prompt asks for the letter, but full names are still accepted. Matching ignores
  case and extra whitespace, so "s", "S Phase" and "  S  phase " all match.

**Q6 — `multiple_choice`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `In which phase of mitosis do sister chromatids separate and move toward opposite poles?`
- options: `Metaphase`, `Prophase`, `Anaphase`, `Telophase`
- answer_points: `[0.0, 0.0, 1.0, 0.0]`

**Q7 — `put_in_order`, `ACCURACY`, 1.0 pts, 45 s**
- prompt: `Put the phases of mitosis in the order they occur.`
- config.items (display order, exact): `["Anaphase", "Prophase", "Telophase", "Metaphase", "Prometaphase"]`
- answer_data.correct_order: `[1, 4, 3, 0, 2]`
  - Check: maps to Prophase, Prometaphase, Metaphase, Anaphase, Telophase. ✓
  - Not the identity. ✓
  - The display order's ranks are `[3, 0, 4, 2, 1]`, giving c = 4 of t = 10 pairs in order, and
    4 ≤ floor(10/2) = 5. ✓
- `config` must contain no key other than `items`.

**Q8 — `true_false`, `ACCURACY`, 1.0 pts, 15 s**
- prompt: `Meiosis produces two genetically identical diploid daughter cells.`
- answer_points: `{"true": 0.0, "false": 1.0}` (the statement is false: meiosis produces four
  genetically distinct haploid cells)

**Q9 — `fill_in_the_blank`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `How many chromosomes does a typical human somatic (body) cell contain? (Answer with a number.)`
- acceptedAnswers: `["46", "46 chromosomes", "forty-six", "forty six", "forty-six chromosomes", "forty six chromosomes"]`
- answerPoints: `[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]`
- editDistance: `0`

**Q10 — `multi_select`, `ACCURACY`, 3.0 pts, 30 s**
- prompt: `Which of these events occur in meiosis but NOT in mitosis? Select all that apply.`
- options: `Crossing over between homologous chromosomes`, `Separation of sister chromatids`,
  `Synapsis (pairing of homologous chromosomes)`, `DNA replication before division begins`,
  `Separation of homologous chromosomes`
- answer_points: `[1.0, -1.0, 1.0, -1.0, 1.0]` (positives sum to 3.0)
- Note: sister chromatids separate in mitosis *and* meiosis II, and DNA replicates before both,
  so neither is "meiosis only". The capitalised "NOT" stays in the prompt.

**Q11 — `multiple_choice`, `ACCURACY`, 1.0 pts, 20 s**
- prompt: `What is the failure of chromosomes to separate properly during cell division called?`
- options: `Crossing over`, `Cytokinesis`, `Apoptosis`, `Nondisjunction`
- answer_points: `[0.0, 0.0, 0.0, 1.0]`

**Q12 — `fill_in_the_blank`, `COMPLETENESS`, 1.0 pts, 30 s**
- prompt: `In a word or two, which cell-division concept is still the most confusing to you?`
- config: `{}`, answer_data: `{}`

**Q13 — `put_in_order`, `COMPLETENESS`, 1.0 pts, 40 s**
- prompt: `Rank these topics from the one you feel most confident about to the one you feel least confident about.`
- config.items: `["Meiosis", "Organelles", "Mitosis", "The cell cycle and checkpoints"]`
- answer_data: `{}` (no `correct_order`, since a self-ranking has no right answer)

### Coverage summary (must hold after any edit)

| Type | ACCURACY | COMPLETENESS |
|---|---|---|
| multiple_choice | Q2, Q6, Q11 | Q1 |
| true_false | Q3, Q8 | — |
| fill_in_the_blank | Q5, Q9 | Q12 |
| multi_select | Q4, Q10 | — |
| put_in_order | Q7 | Q13 |

13 questions: 10 ACCURACY, 3 COMPLETENESS. Maximum score = 8×1.0 (single-answer ACCURACY:
Q2, Q3, Q5, Q6, Q7, Q8, Q9, Q11) + 2×3.0 (multi_select) + 3×1.0 (COMPLETENESS) = **17.0**.

### Verification

1. **Offline validation.** Write a throwaway script (`validate_game.py`) in the session
   scratchpad; don't commit it. It takes the JSON path as its only argument and should:
   - load the file with `json.loads(raw, object_pairs_hook=...)`, using a hook that raises on a
     repeated key in any object (plain `json.loads` silently keeps the last duplicate), and assert
     `format == "buzzer/game"` and `version == 1`
   - construct `GameCreate(**game)` and `QuestionCreate(**q)` for every question (from
     `app.schemas.admin`, the importer's own validators)
   - assert **all four scoring rules** above:
     1. MC/TF ACCURACY: the max of `answer_points` (list values for MC, dict values for TF) ==
        `points_value`
     2. multi_select ACCURACY: the sum of the positive `answer_points` == `points_value`
     3. every FITB ACCURACY has `editDistance == 0`
     4. put_in_order ACCURACY: concordant pairs of the display order ≤ floor(t/2)
   - assert the coverage table: the set of types equals all five supported types, and both
     grading modes are present
   - assert no `prompt`, option, item or accepted answer contains `&`, `<` or `>`
   - assert the layout rules that can be checked mechanically:
     - each question's keys appear in the specified order (`list(q) == [...]`)
     - the raw text has no `\u` escapes and ends with exactly one `\n`

     Don't compare the raw text against `json.dumps(...)` output, even with whitespace collapsed.
     `json.dumps(indent=2)` wraps number arrays one element per line, and collapsing that gives
     `[ 0.0, 1.0 ]`, while the file has `[0.0, 1.0]`, so a correct file fails. The parse,
     duplicate-key and key-order checks already cover content and order. Check indentation and
     array wrapping by eye against `cs_first_day.json`.

   **How to run it.** Use whichever of these works:
   - **Local:** run with `backend/` on `PYTHONPATH`. Importing `app.schemas.admin` needs the
     backend's dependencies (pydantic, email-validator, …) installed locally, e.g.
     `pip install -r backend/requirements.txt` in a venv.
   - **Docker fallback:** no local setup needed. The backend container mounts only `./backend` at
     `/app`, so mount the game and the script in too:
     `docker compose run --rm --no-deps -v "$PWD/sample_games:/sample_games:ro" -v "<scratchpad>:/check:ro" backend python /check/validate_game.py /sample_games/cell_biology_cells_and_division.json`
2. **Real import, API.** With the stack up (`docker compose up`), get an admin token (README
   "Import a course roster" shows the login call), then run
   `curl -X POST http://localhost:8000/api/admin/games/import -H "Authorization: Bearer $TOKEN" -F "file=@sample_games/cell_biology_cells_and_division.json"`.
   Expect `201`. The game lands unattached, and `GET /api/admin/games/{id}/questions` should
   return 13 questions in the order above.

   **Then delete this copy:** `curl -X DELETE http://localhost:8000/api/admin/games/{id} -H "Authorization: Bearer $TOKEN"`,
   expecting `204`. Import always creates a new game, and hosts can't delete games (admin only),
   so without this step two copies are left behind. Delete it now, before it has any sessions.
3. **Real import, UI.** Import the same file once through the Host app's games page, attached to
   a course you host (as admin, any course). This is the copy you keep and play in step 4.
4. **Play-through.** Create a room for the step-3 game, then run
   `python scripts/simulate_players.py --room <CODE> --game-json sample_games/cell_biology_cells_and_division.json --fitb-words "G1,M,47,23,mitosis,meiosis,checkpoints"`.

   How the simulator answers each type (`scripts/simulate_players.py`, `_make_answer`):
   - **put_in_order:** submits `correct_order` with probability `accuracy`, otherwise a random
     permutation. A question with no `correct_order` (Q13) always gets a random permutation.
   - **fill_in_the_blank:** a "correct" answer is drawn from `acceptedAnswers`. Otherwise the
     answer comes from the `--fitb-words` pool, which defaults to `DEFAULT_FITB_WORDS`
     (programming language names) when the flag is omitted. Q12 has no accepted answers, so it
     always draws from the pool.

   **Why `--fitb-words` is passed.** It isn't needed for questions to get answers: the default
   pool already covers that. It's there because the default words are nowhere near the right
   answers, so they can't test the exact-match rule (rule 3). This pool contains near-misses:
   - `47` is 1 edit from `46` (Q9)
   - `G1` and `M` are other cell-cycle phases (Q5)

   None of these words appears in any `acceptedAnswers` list. The pool also makes Q12's word
   cloud on-topic. If you change the pool, keep that property.

   With these settings, **every question should receive answers.** Advance through all 13 on the
   host and check:
   - Q7 shows the "Players who placed each item correctly" bars, with non-zero counts
   - Q13 shows only the "N / M answered" line, with N > 0 and no bars. Missing bars are
     expected for COMPLETENESS put_in_order without `correct_order`, not a defect.

   **Per-question score check (the real pass/fail).** "Every total ≤ 17.0" alone is too weak: it
   passes even if a question wrongly scores 0 for everyone. Download the session scores CSV from
   the host GameOver screen or the host `/sessions` page (or `GET /api/game/sessions/{session_id}/export`).
   Its columns are `Player, Q1 … Q13, Total`, with one row per player who answered anything.
   Cells are floats rounded to 4 dp by `export_service._pts`, so they read `0.0`, `1.0`, `0.4`, and
   an unanswered cell is `0.0`. **Parse every cell with `float()` and compare numbers, never
   strings.** Check:
   - **Every ACCURACY column (Q2–Q11) has at least one cell numerically equal to that question's
     full `points_value`** (3.0 for Q4/Q10, 1.0 otherwise). Q7 needs a full 1.0, not just partial
     credit. A column with no full-credit cell means the server didn't score the file's answer key
     as intended.
   - **Q5 and Q9 reject the near-misses.** Don't use the CSV for this: a skipped question is also
     `0.0`, so a zero cell doesn't prove a wrong answer was rejected. Use the host GameOver card
     for each question instead. Its "N correct" must be **less than** its answered count. The
     simulator's console log shows which players submitted a pool word (`G1`, `M`, `47`, …) for that
     question. If every answer was marked correct even though pool words were submitted, the key
     accepts a wrong answer.
   - **Every COMPLETENESS column (Q1, Q12, Q13) contains only values numerically equal to 0 or
     to its `points_value` (1.0), with at least one 1.0.**
   - every `Total` equals the sum of its row's Q cells (within 0.01) and is ≤ 17.0

   This doesn't depend on luck. The simulator's default mix is 20 players, with fast players
   answering correctly 75% of the time and normal players 60%. So a column with no full-credit
   cell, or a Q5/Q9 question where nobody submitted a pool word, is vanishingly unlikely by chance. If one still
   happens, rerun the simulation once before treating it as a defect.

   **What this does not prove:** the simulator reads its "correct" answers from the same JSON, so
   a biologically wrong key would still score full marks. The step-1 rule checks and the authored
   notes under each question (Q4, Q8, Q10) are what guard the content.

   **If a question gets no answers or the run errors:** first rerun step 1. If the file passes
   there, the file isn't the problem. Record the failing question and the simulator output, and
   report it as an app/simulator bug rather than editing the file around it.

### Open items

- **Prometaphase.** Confirm with the course's terminology. If four phases are taught, use
  `items ["Telophase", "Prophase", "Anaphase", "Metaphase"]` with `correct_order [1, 3, 2, 0]`
  (c = 2 of 6, ≤ 3 ✓, not the identity ✓), and keep `points_value`/time unchanged.
