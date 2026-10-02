# backend/app/

**Purpose.** The FastAPI + Socket.IO application: a Host displays quiz state on a big screen,
Players answer from their phones, in real time, per course/session. This directory is the whole
backend app package — see the leaf directories' own `CLAUDE.md` for detail.

**Contents (subdirectories — each has its own `CLAUDE.md`).**
- `routers/` — REST endpoints (FastAPI `APIRouter`s): admin CRUD, host-scoped authoring /
  rosters / session downloads (`/host/*`), auth, host/game resource discovery + room lifecycle,
  health check. Thin — delegates business logic to `services/`.
- `services/` — the business-logic layer shared by `routers/` and `websocket/`: auth/JWT, room
  and session lifecycle, answer scoring, CSV/HTML export, roster CSV parsing, Redis-backed
  ephemeral game state, first-admin bootstrap.
- `websocket/` — the realtime half: a python-socketio ASGI app driving in-game events (join,
  host-advance state machine, submit answer, lock/unlock) once a room exists.
- `models/` — SQLAlchemy ORM models: the persistent (MySQL) schema — users, courses/rosters,
  games/questions, sessions/scores.
- `schemas/` — Pydantic request/response models: the API's wire contract, kept deliberately
  separate from `models/` so internal shape never leaks (e.g. `QuestionPublic` omits answer
  keys). Also the sole home of per-question-type structural validation.
- `common/` — cross-cutting infra used by both `routers/` and `websocket/`: auth dependencies,
  typed exceptions + handlers, structlog setup, rate limiting.

**Top-level files (not yet covered by a nested CLAUDE.md — see Gotchas).**
- `main.py` — FastAPI app assembly: mounts routers, mounts the `websocket/` Socket.IO ASGI app,
  registers exception handlers, configures logging, runs `services/bootstrap.py` on startup.
- `config.py` — `Settings` (env-driven config: dev/prod flags, JWT keys, Redis/DB URLs, CORS,
  room limits, stress-test key).
- `database.py` — SQLAlchemy async engine/session setup (`Base`, `AsyncSessionLocal`, `get_db`).
- `redis_client.py` — Redis connection/client factory (`get_redis`).
- `migrations/` — Alembic migration environment and versioned scripts (`versions/`); the schema
  history behind `models/`.

**How it fits in.** Two parallel transports (`routers/` over HTTP, `websocket/` over Socket.IO)
share one business-logic layer (`services/`) and one persistence layer (`models/` for MySQL via
`database.py`, `services/state_service.py` for Redis via `redis_client.py`). `schemas/` and
`common/` are the shared contract/infrastructure layer both transports depend on.

**Gotchas.**
- Scoring/answer-reveal logic for each question type is defined in **three** places that must
  stay in sync: `services/game_service.py::calculate_score`, `services/report_service.py::_answer_reveal`,
  and `websocket/gateway.py::_answer_reveal` — plus the structural validation in
  `schemas/admin.py::QuestionCreate.validate_structure`. A new question type touches all four.
  See the gotchas in `services/CLAUDE.md`, `websocket/CLAUDE.md`, and `schemas/CLAUDE.md`.
- Several FKs are `NOT NULL` without cascade delete (`game_sessions.game_id`,
  `session_scores.user_id`) — `routers/admin.py`'s `delete_game`/`delete_user` manually delete
  dependent rows first. Don't assume ORM cascade alone handles deletes; see `models/CLAUDE.md`.
- `main.py`, `config.py`, `database.py`, `redis_client.py`, and `migrations/` don't yet have their
  own nested `CLAUDE.md` — this file's directory list above is the current coverage; per the root
  `CLAUDE.md`'s T3 directory list, only the six subdirectories above were in scope for this pass.
