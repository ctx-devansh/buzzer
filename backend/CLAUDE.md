# backend/

**Purpose.** The Python/FastAPI backend for Buzzer: a Host-facing REST + realtime service, a
MySQL schema managed by Alembic, and dev tooling. See `app/CLAUDE.md` for the application
package itself.

**Contents.**
- `app/` — the FastAPI + Socket.IO application package. See `app/CLAUDE.md` for its full
  breakdown (`routers/`, `services/`, `websocket/`, `models/`, `schemas/`, `common/`, plus
  `main.py`/`config.py`/`database.py`/`redis_client.py`/`migrations/`).
- `requirements.txt` — Python dependencies.
- `alembic.ini` — Alembic config pointing at `app/migrations/`.
- `Dockerfile` — backend container build.
- `scripts/generate_keys.py` — generates an RS256 keypair for `JWT_PRIVATE_KEY`/
  `JWT_PUBLIC_KEY` so JWTs survive a restart in dev (see `app/services/CLAUDE.md`'s note on
  `auth_service.py`'s ephemeral-key fallback).
- `logs/` — runtime log output (not source).

**How it fits in.** One of three top-level app areas in the repo (`backend/`, plus
`frontend/host`, `frontend/player`, `frontend/admin`). The frontends talk to `app/routers/` over
HTTP and `app/websocket/` over Socket.IO.

**Gotchas.**
- Without running `scripts/generate_keys.py` and setting `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`,
  JWTs are signed with an ephemeral in-memory key regenerated on every restart — all outstanding
  tokens are invalidated silently.
- Schema changes must go through `alembic revision --autogenerate` / `alembic upgrade head`
  against `app/models/` — hand-editing `app/migrations/versions/` files after the fact will drift
  from what `alembic revision --autogenerate` would produce next time.
