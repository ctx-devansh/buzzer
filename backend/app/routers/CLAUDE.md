# backend/app/routers/

**Purpose.** FastAPI `APIRouter`s — the HTTP-facing edge of the backend. Each file owns one
resource area and is thin: validate/authorize, call a service or ORM query, return a schema.
Business logic (scoring, room state, CSV parsing) lives in `../services/`, not here.

**Contents.**
- `admin.py` — CRUD for courses, rosters (upload/patch), games, questions (incl. reorder,
  JSON import/export of a full game), local user accounts, course/game access grants, guest→real
  account merging, and admin-only session listing/export/report. All routes gated by
  `require_admin`. `POST /admin/games` accepts an optional `course_id` (404 if missing);
  `PUT /admin/games/{id}` can attach an unattached game (`course_id` settable only while NULL,
  409 otherwise). Admin creates/imports are **not** auto-granted to anyone.
- `host.py` — `/host/*`: the host-owned subset of the admin authoring routes (games, questions,
  reorder, export/import, roster list/import/patch, own-session list, HTML report). Gated by
  `require_user` + `game_service.assert_host_can_use_course/game`; ADMIN passes every check.
  `POST /host/games` and `/host/games/import` (multipart `file` + form `course_id`) auto-grant
  the creator. `PUT /host/games/{id}` takes `HostGameUpdate` (no `course_id` → 422). No game
  delete and no multipart roster route, deliberately.
- `auth.py` — login (password or dev-only netid), OAuth2 callback (reads Traefik-injected
  `X-Auth-Request-User`/`-Email` headers), temp-token exchange, guest join, refresh, logout.
  Sets/clears the `refresh_token` httpOnly cookie. Rate-limited via `slowapi` (`../common/rate_limit.py`).
- `game.py` — host-facing resource discovery (`my-courses`, `my-games?course_id=` — same
  visibility rule as `/host/games`, filter-only — `my-active-sessions`),
  room lifecycle (create/ping/get), guest reconciliation, and session score export. Delegates
  room/session logic to `../services/game_service.py` and `../services/state_service.py`.
- `health.py` — unauthenticated `/health` check: pings MySQL and Redis, counts active
  rooms/players from Redis.
- `__init__.py` — empty; routers are wired up wherever `app/main.py` includes them.

**How it fits in.** This is the synchronous REST half of the backend; the other half is the
realtime layer in `../websocket/` (Socket.IO), which handles in-game events once a room exists.
Routers here create/manage rooms and sessions; the websocket gateway drives gameplay inside them.

**Gotchas.**
- **Shared logic lives in services, not in either router.** `admin.py` and `host.py` differ only
  in their gate; question create/update/delete/reorder, game export/import
  (`services/authoring_service.py`), roster list/upsert/patch (`services/roster_service.py`) and
  the session-list row builder (`services/session_list_service.py`) are called from both. Don't
  copy a route body from one router into the other.
- `GET /host/games?course_id=` is a **gate** (403 for a course the user can't host, also for a
  nonexistent one; ADMIN gets 404), while `GET /game/my-games?course_id=` only filters.
- Several endpoints do local, duplicated authorization checks (`user.role != "ADMIN" and
  session.host_user_id != user.id`) instead of a shared dependency — `game.py`'s
  `delete_session`, `list_session_guests`, `merge_guest_for_session`, `export_session_scores`
  all repeat this pattern.
- `admin.delete_game` and `admin.delete_user` manually pre-delete dependent rows
  (`session_scores`, `game_sessions`) before deleting the parent — SQLAlchemy's default cascade
  can't handle the NOT NULL FK columns involved. Don't "simplify" these away.
  `delete_game` also clears each deleted session's Redis state (`state_service.delete_room_state`,
  after a flush): per-session keys have no TTL and a COMPLETED session never clears them, so
  without this they outlive the game (`tests/integration/test_pin_the_spot.py` checks both stores).
- The `buzzer/game` bundle format (`version: 1`) lives in `services/authoring_service.py`
  (`SUPPORTED_IMPORT_VERSION`). A game's course **never** travels in the file: export omits it and
  import discards any `course_id` in the bundle — the host route's form field is the only source.
- Guest-merge logic is duplicated between `admin.merge_guest` and `game.merge_guest_for_session`
  (same steps, different auth gate) — a bug fix in one likely needs the other too.
