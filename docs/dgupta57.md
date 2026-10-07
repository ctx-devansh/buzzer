# Devansh Gupta (dgupta57)

What I worked on:

- **T3:** the backend context files.
- **T4:** the host/admin restructure.
- **T7:** the "Put in Order" question type.
- **T6:** my two sample games.
- **T9:** the whole light/dark theming task.

## 1. Repository and Codebase Organization

### How the repo is laid out

Buzzer has two halves: a Python backend and three React apps.

- **`backend/app/`** is a FastAPI app with a python-socketio server mounted beside it.
  - `routers/` holds the REST endpoints. They are split by audience (`admin.py`, `host.py`, `game.py`, `auth.py`, ...).
  - `services/` holds the actual logic. Both the REST routers and the socket gateway call into it, so it isn't written twice.
  - `websocket/gateway.py` runs everything that happens live once a room exists.
  - `models/` holds the SQLAlchemy tables (MySQL).
  - `schemas/` holds the Pydantic request and response shapes.
  - `common/` holds shared helpers such as exceptions and auth dependencies.
- **`frontend/`** contains three separate Vite apps:
  - `host` is the big screen. After T4 it also covers game authoring, rosters and session downloads.
  - `player` is the phone UI.
  - `admin` handles users, courses, guests and access grants.

  After T9 all three apps share one `frontend/theme/` folder (design tokens and a Tailwind preset).
- **`tests/`** has three layers:
  - `unit/`
  - `integration/` (REST and Socket.IO against the running Docker stack)
  - `e2e/` (Playwright against the nginx build on :8080)
- **`docs/`** holds the design docs, and `ai_log/` holds the Claude Code session logs.

The backend uses two datastores:

- **MySQL** is the permanent record: users, courses, games, questions, sessions and answers.
- **Redis** holds the live game state: the room, the current question, who has answered and the answer counts. `state_service.py` owns the Redis key layout and can rebuild Redis from MySQL if Redis is lost.

### Data flow in one game round

1. **The host starts the question.** The host app emits `HOST_ADVANCE` over Socket.IO. The gateway moves the room from LOBBY or RESULTS to QUESTION in Redis, starts a server-side timer task and broadcasts `new_question` to the room. Every question payload is built by `_question_payload`, so image ids and type config always travel with it.
2. **A player answers.** The player app emits `SUBMIT_ANSWER`.
   - The gateway first checks the shape of the answer. For `put_in_order` it must be a real permutation of item indices, and booleans are rejected. A bad answer gets an `error` event and nothing is saved.
   - A valid answer goes to `game_service`. It scores the answer, writes it to MySQL, updates the Redis answer counts and notifies the host room (`{room}:host`) so the "answered" count goes up live.
3. **Results.** When the timer runs out or the host advances, the room moves to RESULTS. Everyone gets the answer distribution. Each player also gets a personal message on their `user:{id}` socket room with their own points, correctness and rank.
4. **After the game.** The session is COMPLETED. The host can download the HTML summary and the CSV of scores from GameOver or the Sessions page. Both are built by `report_service` from MySQL.

### Context files I wrote

I ran the `context-hierarchy` skill over `backend/` and checked the output myself before committing it:

- `backend/CLAUDE.md`
- `backend/app/CLAUDE.md`
- `backend/app/{routers, services, websocket, models, schemas, common}/CLAUDE.md`

This was commit `10c3fa7`; the log is [`ai_log/2026-09-21_20-50-36_bd2c6add.md`](../ai_log/2026-09-21_20-50-36_bd2c6add.md). Satvik covered the frontend directories. I also updated these files whenever my own features changed them; the T4, T7 and T9 commits all touch them.

What I learned from writing them:

- **Routers are thin and services do the work.** That is why T4 was mostly a new router (`host.py`) on top of new services (`authoring_service`, `session_list_service`) and not a copy of `admin.py`.
- **The socket rooms have naming rules.** A player's own socket room is `user:{id}`, and the host's is `{room}:host`. Getting either name wrong sends a message to nobody, and nothing errors.
- **The same logic sometimes lives in two places.** For example, `_answer_reveal` exists in both the gateway and `report_service`. Any new question type has to be updated in both.

## 2. Design Process (Elephant/Goldfish)

My design docs:

- [`docs/design-host-admin-restructure.md`](design-host-admin-restructure.md) (T4)
- [`docs/design-put-in-order.md`](design-put-in-order.md) (T7)
- [`docs/design-better-ui.md`](design-better-ui.md) (T9)

I worked the same way for all three:

1. Discuss the design with `/design-discussion` (the Elephant).
2. Write it up with `/write-spec`.
3. Run `/goldfish-test` in a brand new session.
4. Take each finding back to the Elephant, check it against the code, then update the doc.
5. Repeat until the Goldfish had nothing blocking left.

Only after that did I tell Claude to "implement exactly according to the spec".

**What the Goldfish caught that the Elephant missed.** The Elephant knew the codebase well and tended to fill gaps with things it "knew". The Goldfish only had the doc, so it found the places where a reader would have to guess.

- **T4.** The first draft said to "add a filter" to `GET /game/my-games`. The Goldfish pointed out that the endpoint only joins `user_game_access`. Following the doc literally would have shipped the exact access bug the risks section warned about. The fix was §3.3: one visibility rule, written in pseudocode and shared by all three endpoints. The same pass found:
  - an "attach game to course" step that had no endpoint
  - a Sessions filter for an `ACTIVE` status that doesn't exist

  Sections 11–18 of the doc record five Goldfish passes and four design reviews.
- **T7.** The Goldfish showed that re-saving a question re-scrambled its items, which would corrupt past session reports. It also found that my integration test for rejecting booleans didn't really test that rule: `[true,0,1,2]` is rejected anyway, because `True == 1`.
- **T9.** I ran seven Goldfish passes, all listed in the doc's revision log (§9). Real problems they found:
  - `focus:outline-none` utilities silently beat the global focus ring.
  - Replacing Tailwind's palette turns a plain `border` into `currentColor`. There were 51 of them.
  - Transparent uploaded images disappear on dark backgrounds.
  - The dark-mode spinner failed contrast (1.92:1).
  - Room codes and timers on the host screen would have got *smaller*.

  None of these came up in the Elephant discussion. The before and after screenshots of 41 key screens in both themes, with the axe contrast report, are in [`docs/ui/`](ui/README.md).

**Did it change how I implemented?** Yes. Implementation turned into reading and checking, not discovering. When the code did disagree with the spec, I updated the doc first and then the code. One example was the TypeScript TS6310 build error, recorded in commit `4fa5f0b` before the fix in `5125a14`. The downside is time: T9 had more Goldfish passes than implementation commits. By the last few passes the findings were small, so I should have stopped earlier.

## 3. AI Tools Used

I used **Claude Code** for everything, in the VS Code extension and the terminal. Every session is logged in `ai_log/`. I didn't use any other AI tools.

| What | Example logs | How I used it |
|---|---|---|
| Context files (T3) | [`2026-09-21_20-50-36_bd2c6add`](../ai_log/2026-09-21_20-50-36_bd2c6add.md) | `/context-hierarchy` on `backend/`, then I reviewed each file |
| T4 design and Goldfish | [`2026-10-02_01-22-15_3890c101`](../ai_log/2026-10-02_01-22-15_3890c101.md), [`01-10-24_70b7af91`](../ai_log/2026-10-02_01-10-24_70b7af91.md), [`14-48-56_25c99a94`](../ai_log/2026-10-02_14-48-56_25c99a94.md) | Design discussion, then repeated fresh-session Goldfish tests |
| T4 implementation and review | [`2026-10-02_16-56-03_db1b26ad`](../ai_log/2026-10-02_16-56-03_db1b26ad.md), [`2026-10-03_13-08-21_04c90268`](../ai_log/2026-10-03_13-08-21_04c90268.md) | Implemented from the spec, ran `/mean-review` three times and fixed what it found, then asked for Playwright tests |
| Git and CI help | [`2026-10-03_17-21-16_26e466a9`](../ai_log/2026-10-03_17-21-16_26e466a9.md) | Moved commits I had made on the wrong branch without rewriting history; fixed a failing `python-lint` job |
| T7 Put in Order | [`2026-10-03_20-34-01_b77515ce`](../ai_log/2026-10-03_20-34-01_b77515ce.md), [`2026-10-04_17-36-31_c799f3d9`](../ai_log/2026-10-04_17-36-31_c799f3d9.md) | Fed Goldfish findings back into design, then implementation |
| T6 sample games | [`2026-10-04_22-34-20_4be98c76`](../ai_log/2026-10-04_22-34-20_4be98c76.md), [`2026-10-05_01-14-35_332cb312`](../ai_log/2026-10-05_01-14-35_332cb312.md), [`2026-10-06_13-48-47_0691570f`](../ai_log/2026-10-06_13-48-47_0691570f.md) | Wrote a spec for each game ([cell biology](plans/cell-biology-quiz.md), [absurd but true](plans/absurd-but-true-quiz.md)) and ran several Goldfish passes, then had Claude build the JSON. The Goldfish caught real content bugs: a fill-in-the-blank answer that would mark "46 chromosomes" wrong, and a fact already used in an existing sample game. Later I asked Claude to check both games against the T6 criteria. I made the Pin the Spot image myself and checked the tap coordinates by hand |
| T9 theming | [`2026-10-06_19-51-09_34d5df99`](../ai_log/2026-10-06_19-51-09_34d5df99.md), [`2026-10-06_22-12-48_34d5df99`](../ai_log/2026-10-06_22-12-48_34d5df99.md) | One long Elephant session across seven Goldfish rounds, then implementation |

**Where it helped**

- It explored the code quickly. I could ask questions like "should I see a HOST role for users?" and get an answer checked against the actual code.
- The Goldfish passes and `/mean-review` caught real bugs before I shipped them.
- It was good at tedious, wide changes, such as moving every page in all three apps onto theme tokens and writing the screenshot capture script.

**Where it fell short**

- **It said things were done when they weren't.** After the T4 implementation I had to ask whether the integration tests really covered everything, and whether any starter tests had been weakened. Later `/mean-review` passes still found more problems.
- **Its git advice was unsafe for this project.** Twice it suggested a rebase. Rewriting history isn't allowed here, so I pushed back both times ([`2026-10-03_17-22-39`](../ai_log/2026-10-03_17-22-39_26e466a9.md), [`2026-10-04_18-28-45`](../ai_log/2026-10-04_18-28-45_c799f3d9.md)).
- **Its tests left a mess.** They created many test courses, and I had to ask for them to be cleaned up.
- **It assumed things about the toolchain that were wrong.** For example, it assumed bare imports resolve from the importing app. They don't, and the Goldfish caught it. I only trusted claims I had checked against the code.

## 4. Best Practices Learned

- **Design before code works, but only if you verify.** Every Goldfish finding was checked against the code before I changed the doc. Some were wrong, and some miscounted (for example, it said 26 `focus:ring` uses and there were 40).
- **One branch per task and small commits.** The T9 branch has about 30 commits that each do one thing, such as "Add theme token unit tests" or "Migrate admin app to theme tokens". That made the merge request easy to review. Earlier, on T4, I put everything in one big commit and had to fix a wrong-branch commit, which taught me this the hard way.
- **Run CI locally before pushing.** Running `ruff format` and `tsc --noEmit` locally would have saved me the failed `python-lint` pipeline.
- **Role checks belong in one place.** For T4, the "can this host use this game" rule had to agree in three spots: `assert_host_can_use_game`, `visible_games_query` and `create_room`. Putting it in shared services means the admin and host routers can't drift apart.
- **Test behavior, including the failure cases.** Good tests check things like a 403 for a host from another course, or a rejected boolean in an answer. They don't just check for a 200. Tests should also clean up what they create in both MySQL and Redis.
- **Using AI well means steering it.** It works best with a written spec, a narrow request and a habit of asking "did you actually check that?"
