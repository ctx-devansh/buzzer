# backend/app/routers/

**Purpose.** FastAPI `APIRouter`s — the HTTP-facing edge of the backend. Each file owns one
resource area and is thin: validate/authorize, call a service or ORM query, return a schema.
Business logic (scoring, room state, CSV parsing) lives in `../services/`, not here.

**Contents.**
- `admin.py` — CRUD for courses, rosters (upload/patch), games, questions (incl. reorder,
  JSON import/export of a full game), local user accounts, course/game access grants, guest→real
  account merging, and admin-only session listing/export/report. All routes gated by
  `require_admin`. Prompt HTML is sanitized here via `bleach` before it ever reaches the DB.
- `auth.py` — login (password or dev-only netid), OAuth2 callback (reads Traefik-injected
  `X-Auth-Request-User`/`-Email` headers), temp-token exchange, guest join, refresh, logout.
  Sets/clears the `refresh_token` httpOnly cookie. Rate-limited via `slowapi` (`../common/rate_limit.py`).
- `game.py` — host-facing resource discovery (`my-courses`, `my-games`, `my-active-sessions`),
  room lifecycle (create/ping/get), guest reconciliation, and session score export. Delegates
  room/session logic to `../services/game_service.py` and `../services/state_service.py`.
- `health.py` — unauthenticated `/health` check: pings MySQL and Redis, counts active
  rooms/players from Redis.
- `__init__.py` — empty; routers are wired up wherever `app/main.py` includes them.

**How it fits in.** This is the synchronous REST half of the backend; the other half is the
realtime layer in `../websocket/` (Socket.IO), which handles in-game events once a room exists.
Routers here create/manage rooms and sessions; the websocket gateway drives gameplay inside them.

**Gotchas.**
- Several endpoints do local, duplicated authorization checks (`user.role != "ADMIN" and
  session.host_user_id != user.id`) instead of a shared dependency — `game.py`'s
  `delete_session`, `list_session_guests`, `merge_guest_for_session`, `export_session_scores`
  all repeat this pattern.
- `admin.delete_game` and `admin.delete_user` manually pre-delete dependent rows
  (`session_scores`, `game_sessions`) before deleting the parent — SQLAlchemy's default cascade
  can't handle the NOT NULL FK columns involved. Don't "simplify" these away.
- `admin.import_game` / `export_game` define a versioned bundle format
  (`"format": "buzzer/game"`, `version: 1`) — bump `_SUPPORTED_IMPORT_VERSION` deliberately if the
  bundle shape changes, and keep import validation (`GameCreate`/`QuestionCreate`) in sync.
- Guest-merge logic is duplicated between `admin.merge_guest` and `game.merge_guest_for_session`
  (same steps, different auth gate) — a bug fix in one likely needs the other too.
