# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Buzzer** is a Jackbox-inspired real-time party quiz platform. A **Host** displays game state on a large screen while **Players** join and answer questions from their mobile browsers.

## Development Commands

### Docker Environment
```bash
docker compose up
docker compose up --build
docker compose down
docker compose logs -f [service_name]
docker compose exec backend [command]
```

### Backend (FastAPI / Python)
```bash
# Run inside the container or with venv active
alembic upgrade head
alembic revision --autogenerate -m "description"
pytest
pytest --cov=app
ruff check .
ruff format .
```

### Tests (from the repo root, against the running Docker stack)
```bash
pytest                    # unit → integration → e2e (root pytest.ini; e2e must run last)
pytest tests/integration  # REST + Socket.IO against :8000
pytest tests/integration --fast   # also run timer-expiry cases (time_limit_seconds=2)
npm run build && pytest tests/e2e   # Playwright against nginx on :8080 (serves frontend/*/dist)
# one-time e2e setup: pip install -r tests/e2e/requirements.txt && playwright install chromium
```

### Frontend Applications
```bash
npm run dev           # all three apps concurrently
npm run dev:host
npm run dev:player
npm run dev:admin
npm run build
```

### Scripts
```bash
python scripts/seed_demo.py
python scripts/simulate_players.py --room ABCDE1
python scripts/smoke_test_websocket.py
```

## Architecture notes

Per-directory detail lives in the nested `CLAUDE.md` files (this team's context hierarchy);
the host/admin split is specified in [docs/design-host-admin-restructure.md](docs/design-host-admin-restructure.md).

- **Admin app vs. host app.** The admin app is admin-first (Users, Courses, Guests, Sessions).
  Game/question authoring, rosters and session downloads live in the host app (`/games`,
  `/courses/:id/roster`, `/sessions`, GameOver downloads); the old admin routes redirect there.
- **Two API surfaces, one service layer.** `/api/admin/*` is gated by `require_admin`;
  `/api/host/*` (`routers/host.py`) by `assert_host_can_use_course` / `assert_host_can_use_game`
  (ADMIN passes both). Logic past the gate lives in `services/authoring_service.py`,
  `roster_service.py` and `session_list_service.py`; don't copy it into either router.
- **Game visibility is one rule in three places.** A non-admin can use a game only if it is
  attached to a course (`games.course_id`) they HOST *and* they have a `user_game_access` row.
  `assert_host_can_use_game`, `visible_games_query` (`GET /game/my-games`, `GET /host/games`)
  and `create_room` must agree. Change one, change all three. A game can only be run in its own
  course, and hosts can't reassign or delete games (admin-only).
- **Cross-app links** (`frontend/*/src/lib/links.ts`) point at the other app's dev port under
  `npm run dev` and at `/host`, `/admin`, `/player` under nginx (:8080). The token is per-origin,
  so admin→host links only stay signed in on :8080.
- After pulling schema changes run `docker compose run --rm backend alembic upgrade head`.

## Elephant-Goldfish tooling (optional, encouraged)

Project instructions T3/T4 require the Elephant-Goldfish design process from Lecture 4 for the
UI restructuring task: build bottom-up context, discuss a design, write it down, Goldfish-test
it, then implement. This repo ships a working implementation of that process as Claude Code
skills and rules — using them is **encouraged, not required**. Following the same process by
hand, in your own words, earns identical credit; see [instructions.md](instructions.md) T3.

**Context hierarchy.** T3's "README trick" — bottom-up per-directory context docs — can be
built as plain `README.md` files (as T3 describes) or as nested `CLAUDE.md` files (the
`context-hierarchy` skill), which Claude Code loads automatically as it reads into a directory.
Either is graded the same way. The directories T3 asks you to cover:

```
backend/app/routers/       backend/app/services/     backend/app/websocket/
backend/app/models/        backend/app/schemas/      backend/app/common/
frontend/host/src/pages/       frontend/host/src/components/       frontend/host/src/lib/
frontend/player/src/pages/     frontend/player/src/components/     frontend/player/src/lib/
frontend/admin/src/pages/      frontend/admin/src/components/      frontend/admin/src/lib/
```

**Skills for each phase:**

| Phase | Skill | What it does |
|---|---|---|
| Prerequisite | `context-hierarchy` | Build or refresh the context hierarchy, leaves to root |
| 1 — Growing the Elephant | `design-discussion` | Scope a feature, load only the relevant context, discuss design (no code) |
| 2 — Teaching the Elephant | `write-spec` | Turn an agreed design into `docs/plans/<feature-slug>.md` (or `docs/design-<feature>.md` — see T3) |
| 3 — Goldfish Protocol | `goldfish-test` | In a genuinely fresh session: comprehension, critic, and readiness checks against the spec |
| 4 — Implementation | *(no skill — just build it)* | Write the code against the goldfish-tested spec |
| 4 — closing | `mean-review` | Adversarial review of the finished implementation |

Invoke any of these explicitly with `/<name>`, or let Claude pick them up automatically when the
conversation matches. `.claude/rules/` enforces two habits for the whole conversation: the
`no-code-during-design` rule during design/spec/goldfish phases, and the `sycophant-challenge`
rule after any technical proposal. `.claude/rules/context-sync.md` keeps the context hierarchy
from going stale as `backend/` and `frontend/` change.

**Building your own.** These skills and rules are a starting point, not a ceiling. If your team
finds a recurring workflow worth codifying — a review checklist, a scaffolding pattern for new
question types, a consistent way to draft sample game JSON — writing it as your own skill or
rule under `.claude/` is fair game and works in your favor: it's exactly the kind of thoughtful,
deliberate AI usage the grading notes reward, and it's something concrete to point to in your
individual markdown document (T10) and at the TA code review (T11).
