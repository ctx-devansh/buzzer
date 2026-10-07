# Satvik Utkoori (utkoori): Individual Document (T10)

My work on Buzzer: the frontend context hierarchy (T3), the frontend side of the host/admin restructuring design (T4), the Pin the Spot question type (T7), my two sample games (T6) and image support (T8). Every AI session I ran is logged in `ai_log/`. Session logs are cited below by file name. Devansh's sessions are not included.

---

## 1. Repository and Codebase Organization

### How the repository is laid out

Buzzer is a monorepo with one backend, three browser apps, and shared infrastructure:

| Path | What it is |
|---|---|
| `backend/app/` | FastAPI + python-socketio application. `routers/` (REST), `websocket/` (Socket.IO gateway), `services/` (business logic), `models/` (SQLAlchemy/MySQL), `schemas/` (Pydantic wire contract and per-question-type validation), `common/` (auth dependencies, exceptions, logging, rate limiting), `migrations/` (Alembic) |
| `frontend/host/` | The instructor app: game, question and roster management (`pages/manage/`) and the projector screens for a live game (`pages/game/`) |
| `frontend/player/` | The phone app: join by room code, answer questions |
| `frontend/admin/` | The administrator app: users, courses, access grants, guests, all-hosts sessions; it links out to the host app for authoring |
| `nginx/` | One origin for all of it in Docker: `/api` and `/socket.io` go to the backend, `/host`, `/player`, `/admin` serve each app's `dist/` |
| `tests/` | `unit/` (pure functions, no stack), `integration/` (REST + Socket.IO against the running stack), `e2e/` (Playwright against nginx) |
| `sample_games/`, `scripts/` | Game JSON files (T6) and tooling: `simulate_players.py`, `make_pin_images.py` |
| `docs/` | Design documents, one per feature |

The three frontends share no code on purpose. Each has its own `lib/api.ts`, `components/ui/` and types, which have drifted apart. A fix in one app has to be copied by hand to the others. I ran into this in T7 and T8: Pin the Spot has a canvas and a geometry helper in each app (`PinCanvas.tsx` / `PinBoard.tsx`, two `lib/pinTheSpot.ts`), and T8 added an `imageUrl` helper to each.

### How the components relate

There are two transports and one business layer. REST (`routers/`) handles everything outside a live game: authoring, rosters, room creation, downloads. Socket.IO (`websocket/gateway.py`) drives the game once a room exists. Both call into `services/`, which owns the rules: `game_service.py` (access checks, scoring, summaries), `state_service.py` (the Redis contract for live rooms), `authoring_service.py` (question CRUD, export/import), and, after my work, `pin_the_spot.py` and `image_service.py`.

Two rules shape the backend:

- **Role checks live only on the server.** `/api/admin/*` is gated by `require_admin`. `/api/host/*` is gated by `assert_host_can_use_course` / `assert_host_can_use_game`, which ADMIN passes. Every frontend route guard only checks that a token exists.
- **Game visibility is one rule in three places.** A non-admin can use a game only if it is attached to a course they HOST *and* they have a `user_game_access` row. `assert_host_can_use_game`, `visible_games_query` and `create_room` must agree.

State is split between MySQL (persistent: questions, sessions, `session_scores`, and, from T8, `images`) and Redis (ephemeral: room state, the current question, who has answered, answer distributions). `state_service.restore_from_mysql` rebuilds Redis if it is lost.

### Data flow in one round

1. **The host starts a question.** The host's `GameLayout` (the only socket owner in the host app) emits `host_advance`. `gateway._on_host_advance_impl` loads the next question from MySQL, stores the current-question record in Redis, starts a server-side timer task, and broadcasts `new_question` to the room. The payload is built by `_question_payload`, which deliberately omits `answer_data`, so the answer key never reaches a phone. After T8 it also carries `promptImageId`, and `config` carries image ids. Bytes never go over the socket; clients load `/api/images/{id}`.
2. **Phones render it.** The player's `GameLayout` routes to `QuestionPage`, which has one branch per question type. The host's `QuestionPage` shows the prompt, the prompt image and the answered count; the players don't see the prompt (except for Pin the Spot).
3. **A player answers.** The phone emits `submit_answer {question_id, answer_data, answer_time_ms}`. `gateway.on_submit_answer` validates the shape for the type (for Pin the Spot, `pin_the_spot.is_valid_tap`: exactly `{x, y}`, finite, in [0, 1]) and calls `game_service.record_answer`. That calls `calculate_score`, writes a `SessionScore` row to MySQL and updates the Redis distribution hash. The player gets `answer_received`; the host gets `answer_status` with the live count.
4. **The host shows results.** A second `host_advance` moves the phase from QUESTION to RESULTS. The gateway builds the reveal (`_answer_reveal`) and the distribution, and emits `question_results` to the room, plus a personal copy to each player with `yourPoints` / `yourIsCorrect`. The host's `ResultsPage` draws bars, a word cloud or a Pin the Spot board.
5. **The game ends.** After the last question, `host_advance` emits `game_over`, with separate host and player summaries built from MySQL. The HTML report and CSV export are built from the same tables later.

The server drives navigation throughout: pages emit events and wait. `GameLayout` turns the server's next event into a route change.

### The context files I wrote

The team built the context hierarchy as nested `CLAUDE.md` files, which Claude Code loads automatically as it reads into a directory. Devansh wrote the backend ones. **I wrote the 13 frontend ones** (`frontend/CLAUDE.md`, and `src/`, `pages/`, `components/`, `lib/` for each of host, player and admin) on Oct 1–2 (commits `d2f26c7`, `6a64641`, `e1790a8`). I kept them current as later work changed those directories, for example `fa6afb2` for Pin the Spot and the T8 step 9 commit for images.

What I learned writing them:

- **Writing "Gotchas" forced me to read code I would have skimmed.** For example: the frontends share nothing; one `localStorage.token` key is shared across all three apps under nginx, so "Play Again" on the phone signs a host out in the same browser; `TimerBar` must be remounted per question with `key={questionId}`; and the player ignores most `sync_state` fields on reconnect.
- **The "adding a question type touches N places" notes paid off directly in T7.** The frontend and backend docs list every place a new type must be added: four reveal builders, `calculate_score`, the validators, three host pages, four player spots and the editor. That list became the T7 files table, and it is why Pin the Spot didn't miss a reveal builder.
- **The docs have to be maintained, not written once.** `.claude/rules/context-sync.md` makes each change re-check the nearest `CLAUDE.md`. After T8 I updated 18 context files. A stale context file is worse than none, because the AI trusts it.

---

## 2. Design Process (Elephant/Goldfish)

My design documents:

- [docs/design-pin-the-spot.md](design-pin-the-spot.md) (T7)
- [docs/design-t6-sample-games.md](design-t6-sample-games.md) (T6)
- [docs/design-image-support.md](design-image-support.md) (T8)

I also produced the frontend side of [docs/design-host-admin-restructure.md](design-host-admin-restructure.md) (T4) in my Oct 1 sessions.

### How the Elephant produced each document

For each feature I followed the same loop, mostly through the repo's skills:

1. **Load context.** For T3/T4 I first had Claude explain the project structure and then explore the admin/host split, role enforcement, frontend routing and the backend endpoints, aided by the frontend context files (`ai_log/2026-10-01_13-41-05_8b03d330.md`, `ai_log/2026-10-01_14-03-09_3c1f5b5a.md`).
2. **Design discussion.** With `/design-discussion` the Elephant loaded only the relevant context docs and proposed a design in prose. The `sycophant-challenge` rule made it critique its own proposals, and the `no-code-during-design` rule kept code out of the conversation. It ended with numbered questions for me to decide. For T8: public or authenticated image URLs, per-course or per-game libraries, whether the prompt image shows on phones, whether a played canvas can be replaced, and full or reduced scope. I answered "1) they are acceptable, 2) yes, 3) host-only, 4) as you proposed, 5) no" (`ai_log/2026-10-05_14-26-14_b174064a.md`). For T6: "1) A 2) it works 3) keep the starter files 4) yes" (`ai_log/2026-10-05_21-46-02_6735be16.md`). Those answers are recorded in each spec's "Decisions" section (D1–D4 for T7, S1–S10 for T6, decisions 1–5 for T8).
3. **Write the spec.** `/write-spec` turned the agreed design into the document: problem, decisions, data model, validation, a files-touched table, a test plan, numbered implementation steps, alternatives considered, and a self-critique of risks.

### What the Goldfish found that the Elephant missed

The Goldfish was `/goldfish-test` in a fresh session (after `/clear`). It read only the spec and the context hierarchy, with no access to the conversation that produced it. It explained the feature back (comprehension), listed holes (critic), and said which implementation steps could start (readiness). Every spec has a findings table. Representative findings:

**T7, Pin the Spot (G1–G28, two passes):**

- **G1:** the spec never said whose aspect ratio the canvas uses, so the client and server could disagree about where a tap landed. This became decision D6: every canvas draws into the *stored* aspect from `config`.
- **G20:** the report embedded `image_url` unescaped, and an `https` URL can contain `"`. Fixed with `html.escape(..., quote=True)`.
- **G17:** the player's verdict relied on `points > 0`, which reads wrong when `points_value` is 0. This became D9: partial credit (◐) is decided by distance, everywhere.

**T6, sample games (G1–G10, two rounds):**

- **G1:** a classroom true/false question was factually false for a repository's very first commit. Two rounds of rewording later, it became the merge-commit statement.
- **G5:** the generator wrote COMPLETENESS `answer_data` differently from what `--check` expected.

**T8, image support (four passes, plus 18 first-pass findings):**

- **Finding 1:** re-encoding every upload made export/import non-idempotent: hashes changed, so images were never reused, and quality dropped on every round trip. This became the idempotence contract (re-encode only images that carry metadata) with its own unit test.
- **G2-2:** MySQL compares `CHAR` ids case-insensitively, but where-used compared them in Python, so an upper-case id could let a used image be deleted. This became the canonical-lowercase-UUID rule.
- **G3-1:** `process_upload` is CPU-bound and ran in the same event loop as Socket.IO, so one big upload would freeze every live game. It now runs in a worker thread.
- **G4-1:** a route using `get_db` holds a pooled DB connection until *after* the response is sent. The public image route would hold one per slow phone, starving answer recording at question start. It now opens its own short session.

The pattern across all three: **the Elephant designed the happy path well and missed interactions** between the new feature and existing machinery (the update path, the report, the event loop, connection pooling, database collation). A reader with no shared history asks "what happens when…?" about exactly the things the Elephant considered settled.

### How the documents changed

Each Goldfish pass produced a revision commit before any code: for example `d9986e5` (T7, "Revise Pin the Spot design after second Goldfish pass"), `aa5d3fe` and `b91bf2e` (T6), and `51cc1d2` (T8, three passes folded in). The changes were rarely cosmetic. They added decisions (D5–D9 in T7, decisions 6–7 in T8), named functions and orderings (T8's merge → image checks → played guard → validation), and new tests. The specs grew. `design-image-support.md` is long because each Goldfish answer had to be written down as a rule the implementer couldn't misread.

### Did it change how I implemented?

Yes, in three ways:

- **Implementation became mechanical, in a good sense.** Each spec has numbered steps, and each step became one or more commits (`T8 step 1` … `T8 step 10`). When the code disagreed with the plan, the spec was updated in its own commit first. In T8 that happened for the question numbering (R1) and the GIF metadata rule (R2).
- **The test plan came from the spec**, not from the code I happened to write. T7's "update rejects the same payloads as create" symmetry test, for example, came straight from the spec.
- **Closing with `/mean-review` mattered.** In T8 the adversarial review found a real race: library writes returned 200 before `get_db` committed, so the page's reload could read the old row. That was the hidden cause of an end-to-end test I had been treating as flaky. It also found that static GIFs kept embedded comments. The findings were recorded in the spec (section 13) before they were fixed.

---

## 3. AI Tools Used

### Claude Code (the only AI tool I used)

I used Claude Code in the VS Code extension for every task, with the repo's skills (`design-discussion`, `write-spec`, `goldfish-test`, `mean-review`, `context-hierarchy`) and rules. All sessions are logged automatically in `ai_log/`; each file holds one prompt, the tools Claude used, and its reply. I used no other AI tool, so there are no exported sessions in `docs/`.

**T3 / T4: understanding the codebase and the restructuring design**

- *Asked:* "explain the overall structure of this project" (`ai_log/2026-10-01_13-41-05_8b03d330.md`). Then: "explore the codebase, aided by the frontend context files. How do the admin and host interfaces work, how is role-based access enforced, how are the frontend routes structured, and where do the relevant backend endpoints live?" (`ai_log/2026-10-01_14-03-09_3c1f5b5a.md`). Then I asked for the frontend design document: problem, files touched, alternatives, steps (`ai_log/2026-10-01_19-47-02_eff50e51.md`).
- *Used:* the exploration answers became the basis of the frontend `CLAUDE.md` files and the T4 design.
- *Helped:* it found the real enforcement points (`require_admin`, `assert_host_can_use_*`) far faster than I could have by grepping, and explained that the frontend guards only check a token.
- *Fell short:* its first summaries were broad. The useful detail came from specific follow-up questions.

**T7: Pin the Spot**

- *Asked:* `/design-discussion /write-spec` for the canvas question type with the T7 rules pasted in, "dont implement yet" (`ai_log/2026-10-05_15-36-10_e800de98.md`). Then two `/goldfish-test` passes, each followed by "fix the gaps" (`ai_log/2026-10-05_15-44-10_60be6a16.md`, `ai_log/2026-10-05_15-55-56_60be6a16.md`, `ai_log/2026-10-05_15-58-47_e0aedd99.md`). Then "lets implement t7 based on this design doc" (`ai_log/2026-10-05_16-36-41_e0aedd99.md`).
- *Used:* the spec, then backend scoring/validation, both canvases, the editor's target picker, the integration and e2e tests, and the context-doc updates.
- *Helped:* the canvas maths (letterboxing into a stored aspect, DPR scaling, pointer capture, aspect-corrected distance) and keeping one scoring module shared by all four reveal builders.
- *Fell short:* my very first T7 attempt started from a prompt without the design doc attached, and Claude designed a different feature (an "estimate" question) that I had to have it delete ("wait delete the doc you just made. I didn't attach my design doc", `ai_log/2026-10-05_11-05-56_eff50e51.md`). In that early session I also let it go straight from spec to code ("Go ahead and implement", `ai_log/2026-10-05_11-31-37_2ec64102.md`), and AI-written Python then failed the CI lint job ("the linting test is failing in the pipeline", `ai_log/2026-10-05_13-10-42_b174064a.md`).

**T6: sample games**

- *Asked:* "ok we need to do step t6 using the elephant goldfish model" and `/write-spec` (`ai_log/2026-10-05_17-42-20_e0aedd99.md`). Later: "lets just redo t6 following the elephant goldfish model and commit it on the t7-redo branch" (`ai_log/2026-10-05_21-40-50_6735be16.md`), then two Goldfish rounds and "now lets implement based on the doc" (`ai_log/2026-10-05_22-05-23_81b1b2cf.md`).
- *Used:* the question content for both games, `make_pin_images.py` (draws the Pin the Spot images and computes their targets from the drawing's coordinates), the round-trip import test, and the README's per-type JSON reference.
- *Helped:* generating images from code, so targets are exact rather than eyeballed, and a `--check` mode so CI notices drift.
- *Fell short:* it was wrong about the rules at least once. I had to push back on whether each game, or only one, must cover the new types ("I thought each of the games had to cover it", `ai_log/2026-10-05_12-44-02_b174064a.md`). The Goldfish also found a question whose stated answer was factually wrong (G1). AI-written quiz content needs a subject-matter check.

**T8: image support**

- *Asked:* the requirements table with "Images are stored entirely in the database" (`ai_log/2026-10-05_14-22-07_b174064a.md`) and my answers to its design questions (`ai_log/2026-10-05_14-26-14_b174064a.md`). Then four `/goldfish-test` passes with "fix the holes" after each (`ai_log/2026-10-05_22-41-18_9001da5a.md` through `ai_log/2026-10-05_22-56-21_1d490eda.md`). Then "implement t8 based on this doc" (`ai_log/2026-10-06_00-43-55_1d490eda.md`), which also ran `/mean-review`.
- *Used:* the full implementation in 11 spec steps: model and migration, Pillow pipeline, routes, references, export/import v2, report, library page, editor, live-game rendering, docs and e2e tests. Also a live round on :8080 with simulated players.
- *Helped:* before writing the code it checked the spec against reality. It confirmed that the installed FastAPI (0.142) runs `get_db` cleanup after the response, which turned the G4-1 finding into a verified fix. During the review it wrote a probe that logged the network traffic of a flaky e2e test, and found a real race instead of raising a timeout.
- *Fell short:* one Goldfish pass tested the *committed* spec while my revisions were still uncommitted, so it mostly repeated the previous pass. It also took the old branch's code as a starting point, which risked carrying over assumptions from an older Pin the Spot (the spec's "porting rule" exists for this reason).

**Process and Git**

- *Asked:* "Before we move on, can you check if the elephant goldfish model was followed properly for t6,t7, and t8?" (`ai_log/2026-10-05_19-02-28_6735be16.md`), "did we approach t6-t8 with the right approach in the right order on our redo?" (`ai_log/2026-10-05_22-17-21_81b1b2cf.md`), "Did we follow the elephant goldfish process on t6-t8" (`ai_log/2026-10-06_00-45-10_1d490eda.md`), branch and push questions, and MR descriptions.
- *Helped:* auditing the process from the git history (spec commit → Goldfish revision → first code commit) gave an honest answer I could act on.
- *Fell short:* push status was a repeated source of confusion ("you didnt push t6 branch", `ai_log/2026-10-05_12-13-33_2ec64102.md`; "are you sure the latest t7-redo branch was pushed", `ai_log/2026-10-06_00-56-34_1d490eda.md`). The second time, a branch had new automatic log commits after the push. I learned to ask it to compare local and remote commit ids rather than accept "pushed".

**Overall assessment.** Claude Code was most valuable for exploring an unfamiliar codebase, turning a decided design into a precise spec, and adversarial review. It was weakest when I gave it less context than I thought I had (a missing attachment, an ambiguous rule), and when I let it move from design to code in one breath.

---

## 4. Best Practices Learned

### Design before code, and test the design with a stranger
My clearest lesson. In my first pass at T6 and T7 I went from a spec straight to implementation in the same session, without a Goldfish test, and I later redid both properly (`ai_log/2026-10-05_15-17-02_e800de98.md`: "we need to redo t6 and t7 because I didn't follow the elephant goldfish model"). The redone versions are better, not just compliant. The Goldfish found 28 holes in Pin the Spot, several of which (aspect ratio, report escaping, verdict logic) would have been user-visible bugs. A spec that only makes sense to the session that wrote it is not a spec.

### Version control
- **Feature branches, atomic commits, no pushes to `main`.** T8 is 23 commits on `feature/t8-image-support`, each a numbered spec step, a design change, or a single review fix. That made the review findings easy to fix and easy to read.
- **Update the document first, in its own commit**, when implementation proves the plan wrong. The history then shows *why* the code changed.
- **Verify remote state, don't assume it.** `git rev-list --left-right --count branch...origin/branch` answers "is it pushed?" exactly. Automatic `ai_log` commits mean a branch can move after you push it.
- **Branch for a redo rather than rewriting history.** A fresh branch from `main` (`feature/t7-redo`) kept the earlier work recoverable without force-pushing.

### CI/CD
- The pipeline's lint job (`ruff check` and `ruff format --check`, pinned to 0.15.21) caught AI-written code that wasn't formatted. Running exactly the CI commands locally before pushing is cheaper than a red pipeline.
- Pinning the linter's version matters: an unpinned ruff can start failing every MR on its own.
- Tests that need the stack say so (`--fast` for timer cases, e2e last in `pytest.ini`), so "all green" means something.

### Working in an unfamiliar codebase
- Build the map first: the context hierarchy turned "where does scoring live?" into a one-file read. It is also what a fresh AI session needs.
- Look for the "this logic exists in N places" warnings. Buzzer encodes correctness in five places per question type, and missing one silently scores a question as zero. Treat those lists as checklists.
- Read the gotchas *before* the change. `get_db` committing after the response is documented in `services/CLAUDE.md`, and it still bit me in T8 (review finding R10).

### Role-based design
- Authorization belongs on the server. Frontend guards are UX only (`getRole()` is display-only).
- Be deliberate about what an error code leaks. An image from another course returns **404**, not 403, so a host can't probe other courses' libraries. A course you can't host returns 403.
- Define what a role means for each new resource. For T8 we decided that "host of a course" means the whole course library, including images used in other hosts' games, and wrote that down as decision 6 rather than leaving it implicit.

### Testing strategy
- Three layers with different jobs: unit tests for pure rules (scoring tables, the image pipeline's idempotence), integration tests for behaviour across REST and Socket.IO (access control, create/update symmetry, atomic import rollback), and e2e for what a person sees (the phone shows image tiles but not the prompt image).
- Test what the spec promises, including the unhappy paths: 403s, 409s, rejection of SVG and decompression bombs, "nothing is left behind after a failed import".
- **A flaky test is a finding until proven otherwise.** The T8 e2e test that failed one run in three was a real commit-after-response race in production code. Raising the timeout would have hidden it.
- Re-run the full suite after review fixes. Changing behaviour without re-verifying just trades one bug for another.

### Effective AI use
- Give it the full context explicitly (attach the design doc, paste the rules). It can't know what you meant to attach.
- Separate the sessions: the Elephant designs, a fresh Goldfish reviews, a mean-review attacks the code. Each catches what the previous one rationalized.
- Ask it to audit its own work against evidence ("check the git history", "compare local and remote"), not to reassure you.
- Keep the human decisions human: I answered the design questions (public URLs, host-only prompt images, course-wide libraries). The AI's job was to make each choice's consequences explicit.
