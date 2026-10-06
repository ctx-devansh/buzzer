# Design: T6 sample games (Satvik)

| | |
|---|---|
| Task | T6 (quiz/game JSON files), Satvik's two games |
| Owner | Satvik Utkoori (utkoori) |
| Branch | `feature/t7-redo` (both T7 types, `put_in_order` and `pin_the_spot`, are on this branch) |
| Status | Revised after two Goldfish rounds (§8). Implementation in progress |
| Related | [instructions.md](../instructions.md) T6, [design-pin-the-spot.md](design-pin-the-spot.md), [design-put-in-order.md](design-put-in-order.md) |

This replaces an earlier T6 design at this path, whose implementation was reverted in `8c26fb3`
so that this design is committed before any T6 code. Nothing below depends on that earlier work.

## 1. Problem

T6 asks each member for two game JSON files under `sample_games/`, imported into the running app:

| Rule | What it means here |
|---|---|
| Quantity | 2 games: one classroom, one party |
| Classroom game | Educational content, professional tone |
| Party game | Fun, broadly accessible |
| Question types | **Each** game has ≥ 1 `multiple_choice`, `true_false`, `fill_in_the_blank`, `multi_select` |
| Grading modes | **Each** game uses both `ACCURACY` and `COMPLETENESS` |
| New types | Across the member's games, each team T7 type (`put_in_order`, `pin_the_spot`) appears at least once |
| Format | Conforms to the game JSON schema in the README; imports cleanly via the UI or API; `"version": 1` |
| Committed | Under `sample_games/`, with new, distinct file names. The 12 starter files don't count |

Rubric R6 also grades the content: "complete and appropriate to its audience".

Two gaps outside the game files: the README's "file format" section shows only a
`multiple_choice` example (so "conforms to the schema in the README" can't be checked for the
other five types), and nothing automatically proves that `sample_games/` imports.

## 2. Decisions (design discussion, 2026-10-05)

- **S1. New content, designed here.** Every question in §5 was designed in the discussion. No
  earlier game file is reused.
- **S2. Classroom topic: Git and version control** (directly relevant to a software-engineering
  course). Rejected alternative: data structures (A2).
- **S3. Party theme: "Game Night Mixed Bag"**: quick trivia, an odd-one-out Pin the Spot round,
  ranking rounds, then no-wrong-answer hot takes.
- **S4. Both T7 types in both games**, more than the minimum, so neither game depends on the
  other to meet the rule.
- **S5. Points:** classroom 1 per question (2 for the ACCURACY multi-select), so a CSV export
  reads as gradebook points; party 1000 per ACCURACY question (900 for the multi-select) and 250
  per COMPLETENESS question.
- **S6. Pin the Spot images are drawn by a script** (`scripts/make_pin_images.py`), not taken
  from photos or maps (A3). The script is the source of truth for every image and target, and
  computes targets from the drawing's own coordinates.
- **S7. The 12 starter files stay** in `sample_games/`. Deleting them earns nothing and touches
  shared content.
- **S8. Free-text answer policy:** list the common variants explicitly; `editDistance` 0 for
  numeric answers and 1 for words of five letters or more. (Scoring lowercases and collapses
  whitespace but keeps punctuation.)
- **S9. Defaults taken when `/write-spec` was run** (the owner can override them at the Goldfish
  stage): odd-one-out uses a **frown** among smiles rather than a wink (A4); classroom Q1 uses
  `git switch -c` rather than `git checkout -b` (A5); the question lists are as drafted.
- **S10. Tests and README:** an integration test imports every `sample_games/*.json` and checks
  the content survives; a unit test runs the generator's `--check`; the README gains a per-type
  format reference.

## 3. Technical plan

1. Write both game files by hand from §5, with a placeholder `config`/`answer_data` on each Pin
   the Spot question (§5.3). Placeholders must never be committed (§5.9).
2. Write the generator (§5.4), run it to fill the pin questions, and do the faithfulness and
   visual checks.
3. Add the tests (§5.5) and the README changes (§5.6).
4. Live check (§5.8), recorded in §8.

## 4. Alternatives considered

- **A1. Reuse earlier game files.** Rejected: their content would predate this design.
- **A2. Data-structures classroom game** (BST traversal pin, complexity ranking). Clear answers,
  but less tied to the course's own workflow (branches, merge requests) than Git. There is also
  already a starter `data_structures.json`.
- **A3. Real photos or maps for Pin the Spot.** Licensing questions, size limits, and targets
  would be placed by hand. Drawn images are reproducible and their targets are exact.
- **A4. A wink as the odd face.** A closed eye is a few pixels on a phone; a frown is readable at
  phone size while still needing a look.
- **A5. `git checkout -b`.** Equally correct; `git switch -c` is the current recommended form.
  Only one may appear among the options, or Q1 would have two right answers.
- **A6. Delete the starter files.** Rejected (S7).
- **A7. One T7 type per game** (the minimum). Rejected (S4).
- **A8. Mark pin questions with an id field in the JSON.** `QuestionCreate` is `extra="forbid"`,
  so an extra key fails import. The generator identifies questions by file, 1-based index and
  prompt prefix instead (§5.4).

## 5. Detailed implementation

Common to every question: keys exactly `type`, `grading_type`, `prompt`, `config`,
`answer_data`, `time_limit_seconds`, `points_value` (in that order). COMPLETENESS questions have
`answer_data: {}`. `fill_in_the_blank` `config` is `{"maxLength": n}`. Top level:
`{"format": "buzzer/game", "version": 1, "game": {"title", "description", "max_players": 150},
"questions": [...]}`. Files are written as `json.dumps(bundle, indent=2, ensure_ascii=False) + "\n"`.

**Shapes verified against the code** (`QuestionCreate.validate_structure`,
`backend/app/schemas/admin.py`; `calculate_score`, `services/game_service.py`; 2026-10-05):
- MC, TF, FITB and MS check `answer_data` only under ACCURACY, so `{}` is valid for COMPLETENESS
  (MC and MS still need ≥ 2 `options`).
- TF `answer_points` must be a dict with exactly the keys `"true"` and `"false"`.
- MC `answer_points` and FITB `answerPoints` must be ≥ 0; **MS `answer_points` may be negative**,
  and `calculate_score` clamps the MS total with `max(0.0, raw)`.
- FITB `editDistance` is a non-negative int (default 0).
- `put_in_order` / `pin_the_spot` are checked by `validate_put_in_order` / `validate_pin_the_spot`.

If the code disagrees with anything here at implementation time, the code wins and this spec is
corrected.

### 5.1 Classroom: `sample_games/git_version_control_classroom.json`

- **Title:** `Git & Version Control: Core Concepts Check`
- **Description:** `An in-class check on branches, fetching, commits, history rewriting, merge
  bases and the merge-request workflow, followed by a short self-assessment. One point per
  question (two for the multi-select).` (one line in the JSON)

| # | Type | Grading | Time | Pts | Prompt | config | answer_data |
|---|---|---|---|---|---|---|---|
| 1 | MC | ACC | 25 | 1 | `Which command creates a new branch called feature and switches to it?` | options `["git branch -d feature", "git switch -c feature", "git merge feature", "git fetch feature"]` | `answer_points [0, 1, 0, 0]` |
| 2 | MC | ACC | 25 | 1 | `What does git fetch do?` | options `["Downloads remote commits and merges them into your current branch", "Uploads your local commits to the remote", "Downloads remote commits without changing your current branch", "Deletes local branches that no longer exist on the remote"]` | `answer_points [0, 0, 1, 0]` |
| 3 | TF | ACC | 20 | 1 | `git commit sends your new commits to the remote repository.` | `{}` | `answer_points {"true": 0, "false": 1}` |
| 4 | TF | ACC | 20 | 1 | `A merge commit records more than one parent commit.` | `{}` | `answer_points {"true": 1, "false": 0}` |
| 5 | FITB | ACC | 30 | 1 | `Which command lists the files you have changed and the files Git is not tracking yet?` | `maxLength 30` | `acceptedAnswers ["git status", "status"]`, `answerPoints [1, 1]`, `editDistance 1` |
| 6 | FITB | ACC | 30 | 1 | `Which file in a repository lists path patterns that Git should not track? (include the dot)` | `maxLength 30` | `acceptedAnswers [".gitignore", "gitignore"]`, `answerPoints [1, 1]`, `editDistance 1` |
| 7 | MS | ACC | 40 | 2 | `Select every command that rewrites existing commit history. Incorrect selections cost a point.` | options `["git rebase", "git revert", "git commit --amend", "git status", "git fetch"]` | `answer_points [1, -1, 1, -1, -1]` |
| 8 | Pin | ACC | 40 | 1 | `The branches main and feature have diverged. Tap the commit that git merge-base main feature returns.` | generator (`commit_graph`) | generator: target (0.275, 0.65), `r_full 0.04`, `r_zero 0.12` |
| 9 | PIO | ACC | 60 | 1 | `Put the steps of a merge-request workflow in order, first step first.` | items `["Open a merge request", "Commit your changes", "Merge into main", "Create a branch", "Get review approval", "Push the branch"]` | `correct_order [3, 1, 5, 0, 4, 2]` |
| 10 | MC | COMP | 25 | 1 | `How confident are you resolving a merge conflict on your own?` | options `["Very confident", "Somewhat confident", "Not yet confident", "I have never had one"]` | `{}` |
| 11 | TF | COMP | 20 | 1 | `I had used git rebase before this course.` | `{}` | `{}` |
| 12 | MS | COMP | 30 | 1 | `Which Git tools have you used? Select all that apply.` | options `["The command line", "VS Code Source Control", "GitHub Desktop", "The GitLab web interface", "Another Git GUI"]` | `{}` |
| 13 | FITB | COMP | 30 | 1 | `In a word or two, which Git topic should we review next class?` | `maxLength 40` | `{}` |

Checks (all by hand during design, 2026-10-05):
- **Facts:** `git switch -c` creates and switches (Git ≥ 2.23); `git fetch` updates
  remote-tracking refs only; `git commit` is local; a merge commit stores two or more parent hashes (Q4; the
  earlier "every commit except the very first" wording was false, since orphan branches and
  unrelated-history merges create further root commits);
  `git rebase` and `git commit --amend` replace commits, `git revert` adds a new one.
- **Q5/Q6 edit distance 1** doesn't reach a wrong command: `git stash` and `git stage` are ≥ 2
  from `git status`.
- **Q9:** 6 items (the maximum), distinct; the display order differs from `correct_order`.
- **Q7:** the positive points sum to 2 = `points_value`, so a perfect pick is correct; the total
  is clamped at 0.
- **Totals:** ACCURACY 10 points, COMPLETENESS 4, so 14 in all.

### 5.2 Party: `sample_games/game_night_mixed_bag_party.json`

- **Title:** `Game Night Mixed Bag`
- **Description:** `A party quiz for any crowd: quick trivia, an odd-one-out hunt, ranking
  rounds, and a few no-wrong-answer hot takes to finish.` (one line)

| # | Type | Grading | Time | Pts | Prompt | config | answer_data |
|---|---|---|---|---|---|---|---|
| 1 | MC | ACC | 20 | 1000 | `Warm-up! How many hearts does an octopus have?` | options `["1", "2", "3", "8"]` | `answer_points [0, 0, 1000, 0]` |
| 2 | TF | ACC | 15 | 1000 | `Botanically speaking, bananas are berries.` | `{}` | `answer_points {"true": 1000, "false": 0}` |
| 3 | Pin | ACC | 25 | 1000 | `Spot the odd one out! Tap the face that is different.` | generator (`odd_face`) | generator: target (0.625, 0.5), `r_full 0.09`, `r_zero 0.15` |
| 4 | FITB | ACC | 25 | 1000 | `What colour is a polar bear's skin under its fur? (one word)` | `maxLength 20` | `acceptedAnswers ["black"]`, `answerPoints [1000]`, `editDistance 1` |
| 5 | MS | ACC | 25 | 900 | `Which of these are mammals? Wrong picks cost you!` | options `["Dolphin", "Penguin", "Bat", "Shark", "Platypus"]` | `answer_points [300, -300, 300, -300, 300]` |
| 6 | PIO | ACC | 30 | 1000 | `Fastest to slowest! Rank these by top speed (diving counts).` | items `["Human", "Garden snail", "Cheetah", "Peregrine falcon", "Grizzly bear"]` | `correct_order [3, 2, 4, 0, 1]` |
| 7 | TF | ACC | 15 | 1000 | `A group of crows is called a "murder".` | `{}` | `answer_points {"true": 1000, "false": 0}` |
| 8 | MC | ACC | 20 | 1000 | `Which letter appears most often in English text?` | options `["A", "E", "T", "S"]` | `answer_points [0, 1000, 0, 0]` |
| 9 | Pin | COMP | 25 | 250 | `No wrong answers: tap where you would hang out at this party.` | generator (`party_room`) | `{}` |
| 10 | PIO | COMP | 30 | 250 | `Rank these pizza toppings, favourite first.` | items `["Pepperoni", "Mushrooms", "Pineapple", "Extra cheese"]` | `{}` |
| 11 | TF | COMP | 15 | 250 | `Hot take: cereal is a soup.` | `{}` | `{}` |
| 12 | MC | COMP | 20 | 250 | `The best game-night snack is…` | options `["Chips & dip", "Popcorn", "Pizza rolls", "Candy"]` | `{}` |
| 13 | MS | COMP | 25 | 250 | `Which of these have you done this year? Pick all that apply.` | options `["Sung karaoke", "Tried a new cuisine", "Pulled an all-nighter", "Learned a dance"]` | `{}` |
| 14 | FITB | COMP | 20 | 250 | `Last one! Describe tonight's vibe in ONE word.` | `maxLength 20` | `{}` |

Checks (by hand, 2026-10-05):
- **Facts:** an octopus has 3 hearts; bananas are botanical berries; polar-bear skin is black;
  "a murder of crows"; E is the most frequent letter in English.
- **Q6 gaps are wide:** peregrine falcon (dive, > 300 km/h) > cheetah (~100–120) > grizzly bear
  (~55) > human (~45 peak sprint) > garden snail (< 0.1). The prompt says diving counts, so the
  falcon isn't a trick.
- **Q4 edit distance 1** also accepts other words one edit from `black`, e.g. `block`, `blank`,
  `back`, `lack`, `slack`, and `black.` (punctuation is kept). Unlikely answers; accepted for
  typo tolerance.
- **Q5:** the positive points sum to 900 = `points_value`.
- **Totals:** ACCURACY 7 × 1000 + 900 = 7,900; COMPLETENESS 6 × 250 = 1,500; 9,400 in all.

Every party prompt is plain text. Q12's `&` is plain text, which the prompt sanitiser doesn't
touch (it applies to prompts only, not options).

### 5.3 Placeholders before the generator runs

Each Pin the Spot question is first written with `config: {"image_url": "<filled by the
generator>", "image_width": W, "image_height": H}` (W × H from §5.4), and for ACCURACY rows
`answer_data: {"target": {"x": 0.5, "y": 0.5}, "r_full": …, "r_zero": …}` with the table's radii.
The placeholder `image_url` isn't a `data:image/png;base64,` URL, so `--check` difference 1
(§5.4) always fires for it and the first run rewrites it. (It would also fail
`validate_pin_the_spot`, which is why a placeholder must never be committed or imported.)

### 5.4 Generator: `scripts/make_pin_images.py`

**Prerequisite:** Pillow ≥ 10.1. It isn't in any `requirements.txt`, so the module docstring
lists `pip install "pillow>=10.1"`, as `simulate_players.py` lists its own prerequisites.

**Paths** are resolved from the script: `ROOT = Path(__file__).resolve().parents[1]`, files
under `ROOT / "sample_games"` (module-level `GAMES_DIR`, so tests can point it elsewhere).

**Interface:**
- `python scripts/make_pin_images.py` renders every image and prints one line per plan row,
  `<file> Q<n> (<key>): updated` or `unchanged`. A row is updated only if `--check` would report
  a difference for it; then its `config` (and, for ACCURACY, `answer_data`) is rewritten from the
  fresh render. Otherwise its stored PNG bytes are left alone. A file is written only if one of
  its rows was updated. Exit 0.
- `--check` writes nothing, prints each difference as `<file> Q<n> (<key>): <reason>`, exits 1 if
  there are any, 0 otherwise.
- **Plan mismatch** raises `PlanError(ValueError)` from `verify_plan()`, which both modes call
  first. A plan file that is missing, isn't valid JSON or has no top-level `questions` list is
  also a `PlanError`. The CLI prints it and exits **2** in both modes, writing nothing.
- Importable without side effects: `render(key) -> (PIL.Image.Image, (x, y) | None)` returns
  the target **rounded to 4 dp** (`None` for an image without a target); `check() -> list[str]`
  (raises `PlanError`); `write() -> list[tuple[PlanRow, bool]]` (`bool` = updated);
  `main(argv: list[str] | None = None) -> int` (`argv` defaults to `sys.argv[1:]`, so tests can
  pass `["--check"]`).
- **`PlanRow`** is a frozen `@dataclass` with fields `file: str` (file name in `GAMES_DIR`),
  `index: int` (1-based), `prefix: str`, `key: str`, `grading: str`, `r_full: float | None`,
  `r_zero: float | None`. `PLAN: tuple[PlanRow, ...]` holds the three rows below.

**Plan table** (1-based index):

| File | Q | Prompt starts with | Key | Grading | `r_full` | `r_zero` |
|---|---|---|---|---|---|---|
| classroom | 8 | `The branches main and feature` | `commit_graph` | ACCURACY | 0.04 | 0.12 |
| party | 3 | `Spot the odd one out` | `odd_face` | ACCURACY | 0.09 | 0.15 |
| party | 9 | `No wrong answers` | `party_room` | COMPLETENESS | — | — |

**Safety:** before anything else, for every row the question at that index must exist (an index
past the end of `questions` is a `PlanError`), have `type == "pin_the_spot"`, the listed grading
type, and a prompt starting with the prefix; otherwise `PlanError` naming the row. All rows are
verified before any file is read for writing, so a `PlanError` leaves every file untouched.

**What it writes per row:** `config` becomes exactly `{"image_url": "data:image/png;base64,<PNG>",
"image_width": W, "image_height": H}`. ACCURACY: `answer_data` becomes `{"target": {"x": tx,
"y": ty}, "r_full": …, "r_zero": …}` from `render` and the table. COMPLETENESS: `answer_data`
becomes `{}` (so a row `write()` updates always passes `--check` afterwards). Nothing else changes. Encoding: `image.save(buf, "PNG",
optimize=True)`, then base64.

**`--check` differences,** in order (the first hit is the row's difference):
1. `config` keys aren't exactly `image_url`/`image_width`/`image_height`, or `image_url` isn't a
   `data:image/png;base64,` URL that decodes to a PNG.
2. The stored width/height or the decoded PNG's size differs from the render's.
3. ACCURACY: `answer_data` != the expected dict (exact `==`). COMPLETENESS: `answer_data != {}`.
4. Pixels: decoded PNG and render, both `.convert("RGB")`, differ by a mean absolute difference
   over all channels > **2.0** (0–255). This tolerates antialiasing changes between Pillow
   versions.

**Colours:** background `#1e293b`, light `#f8fafc`, dark `#0f172a`, line grey `#94a3b8`. Pixel
coordinates, origin top-left; rectangles and ellipses are Pillow `(x0, y0, x1, y1)` boxes. Each
image is drawn **in the order its bullets list the shapes** (later shapes cover earlier ones,
e.g. the couch seat over the backrest, the bowls over the table top).

**`commit_graph`**, 800 × 400:
- Background fill.
- Main lane at y = 260: commits at x = 100, 220, 340, 460, 580. Feature lane at y = 140:
  commits at x = 340, 460, 580.
- Links (line grey, 6 px), drawn first: main 100→580 along y = 260; (220, 260)→(340, 140);
  feature 340→580 along y = 140.
- Commits: circles radius 16, fill light, 3 px dark outline, **no labels**.
- Branch labels: `ImageFont.load_default(size=22)`, light, anchor `"lm"`: `main` at (610, 260),
  `feature` at (610, 140).
- **Target:** the fork commit (220, 260) → (0.275, 0.65).
- **Radii:** `r_full` 0.04 = 32 px covers the commit (16 + 3 px). `r_zero` 0.12 = 96 px ends
  before the nearest other commit centre (120 px on the main lane; 170 px to (340, 140)), so
  tapping a neighbouring commit scores 0. Taps on the links near the fork get partial credit,
  which is accepted.

**`odd_face`**, 800 × 600:
- Background fill. A 4 × 3 grid of faces centred at x ∈ {100, 300, 500, 700}, y ∈ {100, 300, 500}.
- Each face: circle radius 70, fill `#facc15`, 3 px dark outline; eyes are dark filled circles
  of radius 8 at (cx − 25, cy − 20) and (cx + 25, cy − 20).
- Mouth, dark, 6 px: a smile is `arc((cx − 35, cy − 15, cx + 35, cy + 35), 20, 160)`; the odd
  face (row 2, column 3, centre (500, 300)) instead has a frown,
  `arc((cx − 35, cy + 15, cx + 35, cy + 65), 200, 340)`.
- **Target:** (500, 300) → (0.625, 0.5).
- **Radii:** `r_full` 0.09 = 72 px covers the face (70 px + outline). `r_zero` 0.15 = 120 px ends
  before the nearest edge of any other face (200 − 70 = 130 px), so tapping another face
  scores 0.

**`party_room`**, 800 × 500, no target, no text:
- Wall `#334155` (0, 0)–(800, 330); floor `#a16207` (0, 330)–(800, 500).
- Window `#7dd3fc`, (80, 60)–(260, 200), 4 px light outline, light cross bars at x = 170 and
  y = 130 (4 px).
- TV `#0f172a`, (520, 90)–(720, 210), 6 px `#94a3b8` outline; stand `#94a3b8` (605, 210)–(635, 250).
- Couch: backrest rounded rectangle (90, 250)–(370, 310), radius 20, `#6d28d9`; seat rounded
  rectangle (90, 300)–(370, 400), radius 20, `#7c3aed`.
- Snack table: top `#d97706` (470, 360)–(690, 380); legs `#d97706` (490, 380)–(505, 450) and
  (655, 380)–(670, 450); bowls (ellipses) `#f97316` (500, 330)–(570, 362) and `#facc15`
  (590, 330)–(660, 362).

**After the first run**, look at each PNG once: the odd face is findable on a phone-sized view,
no branch label overlaps a link, and the room reads as a room.

**Faithfulness check, run once before committing:** the targets in the written JSON equal
`render`'s, which equal the coordinates above ÷ size: (0.275, 0.65) and (0.625, 0.5).

### 5.5 Tests

- **`tests/integration/test_sample_games.py`**: parametrized over
  `sorted((Path(__file__).resolve().parents[2] / "sample_games").glob("*.json"))`, ids = file
  names, so it covers both new files **and** the 12 starters. It uses the `conftest.py` fixtures
  `base_url` and `admin_token`, and `from .test_host_admin_restructure import Api, Cleanup`
  (`tests/integration/` is a package; `Api(base_url)` prefixes `/api`, so paths below omit it).
  - **Module-scoped fixture:** one course for the whole module, `POST /admin/courses` with
    `{"name": f"T6 sample games {uuid.uuid4().hex[:6]}", "semester": "Test"}` → 201. The course
    is left behind (no course DELETE exists).
  - **Per file:**
    1. `cleanup = Cleanup(api, admin_token)`, created **before** the `try`.
    2. In the `try`: `POST /host/games/import` (admin token),
       `files={"file": (name, bytes, "application/json")}`, `data={"course_id": str(course_id)}`
       → 201, body `{"game_id": int}`; `cleanup.games.append(game_id)` immediately.
    3. `GET /host/games/{id}/questions` → the same `type` sequence as the file.
    4. `GET /host/games/{id}/export` → 200. Compare these keys only:
       `game.title`, `game.description`, `game.max_players`, and for each question (by position)
       `type`, `grading_type`, `prompt`, `config`, `answer_data`, `time_limit_seconds`,
       `points_value`, each with `==`. `order_index` (replaced by array position) and any
       `game.course_id` (discarded by import) are deliberately not compared; a file key outside
       this list is ignored.
    5. `finally: cleanup.run()`.
  - **Why the starters can take the full comparison** (checked 2026-10-05): all 12 pass
    `QuestionCreate`; none has a `game` key besides `title`/`description`/`max_players` or a
    question key besides the seven above; and all 164 starter prompts come back unchanged from
    `sanitize_prompt` (bleach), as do every prompt in §5.1/§5.2 (quotes, apostrophes and `…`
    included).
  - A separate test asserts the glob isn't empty. If a teammate's or starter file fails, stop and
    report it; don't edit someone else's content.
- **`tests/unit/test_pin_images.py`**: `pytest.importorskip("PIL")`; load the script with
  `importlib.util.spec_from_file_location`, **registering it in `sys.modules` before
  `exec_module`** (`@dataclass` resolves its module there). Assert:
  - `check() == []`;
  - `render(...)` sizes and targets: `commit_graph` (800, 400), (0.275, 0.65); `odd_face`
    (800, 600), (0.625, 0.5); `party_room` (800, 500), `None`;
  - on copies in `tmp_path` (`monkeypatch.setattr(module, "GAMES_DIR", tmp_path)`): `write()`
    reports every row unchanged and leaves the bytes identical; swapping party Q3 and Q4 makes
    `check()` and `write()` raise `PlanError` with the file unchanged; a non-JSON and a missing
    plan file each raise `PlanError`; with the swapped copy, `main([])` and `main(["--check"])`
    both return 2 and leave the file unchanged; after `write()` on a copy whose party Q9
    `answer_data` was set to `{"x": 1}`, `check() == []` and Q9's `answer_data == {}`.

### 5.6 README (`README.md`, "Quiz import and export")

- **Import:** Host app → **Games → Import JSON** (needs a course; grants the importer access);
  API `POST /api/host/games/import`, multipart `file` + form `course_id`. One sentence: the
  admin-only `POST /api/admin/games/import` still exists and leaves the game unattached.
- **Export:** Host app question editor → **Export JSON**; API `GET /api/host/games/{id}/export`
  (the admin route also works for admins).
- After the existing example: the top-level rules (`format`, `version` 1), the per-question keys
  (including the optional `order_index`, replaced by array position), and a per-type table of
  `config`, ACCURACY `answer_data`, COMPLETENESS `answer_data` and the player's submission.
  **Every cell is verified against** `QuestionCreate.validate_structure`,
  `validate_put_in_order`, `validate_pin_the_spot` (`backend/app/schemas/admin.py`) and the
  scoring in `game_service.calculate_score` before committing; the code wins any disagreement.
- One line on `scripts/make_pin_images.py` (and `--check`), and add it to the project-structure
  tree.

### 5.7 Starter files and other scripts

No starter file and no other script changes (S7). `simulate_players.py`'s docstring example
(`cs_first_day.json`) stays valid.

### 5.8 Live check (manual)

1. `docker compose up -d`, `npm run build`; at `http://localhost:8080/host`, **signed in as the
   admin** (hosts can't delete games, and step 4 deletes them), import both files into one course.
2. For each game, create a room **in that course** and run
   `python scripts/simulate_players.py --room <CODE> --players 20 --game-json sample_games/<file>
   --base-url http://localhost:8080`. The host may be driven by hand or by a Socket.IO script; if
   scripted, wait ~2 s after each results screen before advancing.
3. Pass if every question shows and is answered; each ACCURACY pin reveal's target and radii
   equal the file and taps cluster around the target; Game Over shows the pin boards.
4. Record the date and outcome in §8, then delete the imported games.

### 5.9 Commits (in order)

1. This spec, **before** the Goldfish test.
2. The Goldfish revisions, as their own commit.
3. Both game files **together with** the generator and its output (so no commit contains a
   placeholder). Before this commit: `--check` exits 0, the faithfulness check has passed, and
   **each file imports with 201** via `POST /api/host/games/import` (by hand with `curl`, or the
   §5.5 integration test run from the working tree); delete the imported games afterwards. A file
   that fails import is never committed.
4. Tests. 5. README. 6. The live-check record in §8.

Run the full `pytest` (root `pytest.ini`) and `ruff check scripts/make_pin_images.py tests` before
the last commit (findings already present in `tests/integration/conftest.py` and
`tests/integration/scenarios/edge_cases.py` are out of scope).

## 6. Out of scope

- Devansh's two games (his own T6 deliverable).
- T8 `image_id` (library images); these files stay `"version": 1` with `data:` URLs.
- The `host_advance` double-advance race (two advances within ~10 ms re-show results).

## 7. Risks (self-critique)

- **The odd face may still be hard on a small phone.** Each face is ~¼ of the phone's width;
  a frown is a large shape change, but if the live check shows trouble, enlarge the mouth.
- **Classroom Q8 is the hardest question.** It needs the idea that the merge base is where the
  branches forked; 40 s and its position late in the ACCURACY block give it room.
- **Index-based plan table.** Reordering questions breaks it; the prefix check makes the script
  exit 2 without writing, and the table needs a manual update.
- **Pillow isn't a declared dependency.** The unit test skips without it, so an environment
  without Pillow silently doesn't check the images.
- **Font rendering differs between Pillow/FreeType versions.** Only `commit_graph` has text, and
  it's a small part of the image, so the 2.0 tolerance should absorb it; if not, re-run the
  generator rather than raising the tolerance.
- **The import test also runs the starter files** (and later, teammates' files). A failure in
  someone else's file blocks the suite; the rule is to stop and ask.

## 8. Revision history

| Date | Change |
|---|---|
| 2026-10-05 | First draft, from the design discussion (S1–S10), committed before the Goldfish test |
| 2026-10-05 | Goldfish revisions. **G1** classroom Q4 was false for a root commit → "except the very first". **G2** answer shapes verified against `validate_structure`/`calculate_score` and listed in §5; commit 3 now requires a 201 import. **G3** import test compares a fixed key list (not `order_index`/`course_id`); starters' round trip and every prompt's sanitiser stability checked. **G4** `Cleanup` created before the `try`, `cleanup.run()` in `finally`. **G5** `write()` sets COMPLETENESS `answer_data` to `{}` (it disagreed with `--check`), with a test. **G6** `main(argv)` signature; exit-2 test case named. **G7** `PlanRow` fields, out-of-range index is a `PlanError`, draw order = listed order. **G8** §5.3 reason corrected. **G9** party Q4 edit-distance list completed. **G10** live check signed in as admin. S9 defaults (frown, `git switch -c`) unchanged |
| 2026-10-05 | Goldfish round 2. Classroom Q4 reworded to the merge-commit statement (the G1 wording was still false for extra root commits). Confirmed `simulate_players.py --game-json` answers `put_in_order` and aims `pin_the_spot` taps at the target, so §5.8 needs no script change |
