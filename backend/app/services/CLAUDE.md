# backend/app/services/

**Purpose.** Business logic layer, called by routers (`../routers/`) and the websocket gateway
(`../websocket/gateway.py`). No FastAPI/Socket.IO imports here — these are plain async functions
over SQLAlchemy sessions and the Redis client, so both transports share one implementation.

**Contents.**
- `authoring_service.py` — question list/create/update/delete/reorder (with `bleach` prompt
  sanitising), the `buzzer/game` export bundle builder, and the bundle importer
  (`import_game_bundle(db, raw, course_id)`; raises `BundleError`, which routers map to 422).
  Shared by `routers/admin.py` and `routers/host.py`; callers authorise first.
  `delete_question` refuses (409) a question with `session_scores` rows — those are grade data
  and `question_id` is `NOT NULL` with no `ON DELETE` — and flushes before returning, because
  `get_db` commits only after the response is sent.
- `auth_service.py` — password hashing (bcrypt via passlib), RS256 JWT creation/decoding
  (access/refresh/temp tokens), auto-generates an ephemeral in-memory RSA keypair if
  `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` aren't set (dev convenience — tokens die on restart), and
  user lookup/creation helpers (by username, by netid via OAuth2, guest-by-email).
- `bootstrap.py` — creates the initial ADMIN user on startup from `ADMIN_USERNAME`/
  `ADMIN_PASSWORD` env vars, if none exists yet. Retries (rather than crashes) if the schema
  isn't migrated yet, because a crashed startup under `uvicorn --reload` leaves the container
  looking "Up" while nothing serves.
- `export_service.py` — builds session-score CSVs: a raw per-question export and a
  Canvas-gradebook-formatted one (SIS Login ID matching, optional per-question columns,
  roster-only filtering).
- `game_service.py` — the core game/session logic: room code generation, host access checks
  (`assert_host_can_use_course/game`, plus `visible_games_query`, its list-side twin), session lifecycle (create/start/complete/abandon),
  player authorization against the course roster (`authorise_player`), answer scoring
  (`calculate_score` — one branch per question type × grading type), `record_answer` (persists
  to MySQL + updates Redis in one call), and leaderboard/summary builders for GAME_OVER payloads.
- `report_service.py` — generates a standalone, self-contained HTML session report (aggregate
  stats only, no PII) with inline CSS and hand-rolled bar-chart/word-cloud/histogram renderers.
  Duplicates `_answer_reveal` logic from `../websocket/gateway.py` by design (no player-request
  dependency at report-generation time) — keep both in sync if scoring/reveal rules change.
- `roster_service.py` — parses Canvas gradebook CSV exports (and a pre-mapped row list from the
  frontend's column-mapping wizard) into `course_rosters` upserts, deactivating any netid missing
  from the latest upload; also `list_roster` and `patch_roster_entry` (404 if the entry is not in
  that course, 409 if the new netid is already on its roster), shared by the admin and host
  routers.
- `session_list_service.py` — `list_session_rows(db, status, host_user_id)`: the hand-built
  `AdminSessionItem` rows for `GET /admin/sessions` (`host_user_id=None`) and
  `GET /host/sessions` (`None` for ADMIN, the caller's id otherwise). N+1 per session, as before.
- `state_service.py` — the Redis key schema and all room/player/question-state read/write
  helpers (room TTL, player set, current-question record, per-question answered set, answer
  distribution hashes), plus `restore_from_mysql` to rebuild state after a Redis flush/restart.
- `__init__.py` — empty.

**How it fits in.** Sits between the transport layers (`../routers/`, `../websocket/`) and
persistence (`../models/` for MySQL via SQLAlchemy, Redis via `state_service.py`). Routers and
the gateway both call into `game_service.py`/`state_service.py` for anything touching room or
score state, so this is the one place that logic should be edited.

**Gotchas.**
- **Game visibility is one rule in two functions.** `assert_host_can_use_game` (per game) and
  `visible_games_query` (lists, used by `/game/my-games` and `/host/games`) must agree: ADMIN →
  every game; anyone else → game attached to a course (`course_id IS NOT NULL`) they HOST **and**
  a `user_game_access` row. If they drift, the UI lists games `create_room` rejects.
- `create_room` also rejects a game attached to a *different* course than the room's — for
  ADMIN too (it is a course-identity rule, not an access check).
- `game_service.calculate_score` and `report_service._answer_reveal` /
  `websocket/gateway.py::_answer_reveal` independently encode "what counts as correct" per
  question type — there is no single source of truth. A new question type needs updates in all
  three places (plus the Pydantic validators in `../schemas/admin.py`).
- This is not just a future risk — it's already out of sync for `multi_select`:
  `report_service.py::_answer_reveal` has no `multi_select` branch (falls through to `{}`), and
  its bar-chart/word-cloud renderers and `type_badge` map don't handle `multi_select` either, so
  `multi_select` questions currently render in the HTML session report with no chart and no
  reveal. `game_service.py` and `websocket/gateway.py` both handle `multi_select` correctly —
  only the report generator is missing it.
- `state_service` keys are the entire Redis contract; changing a key format (e.g.
  `session:{id}:dist:{qid}`) breaks `delete_room_state`'s key-pattern cleanup and
  `restore_from_mysql`'s reconstruction unless updated together.
- `game_service.create_room` counts active rooms by scanning `room:*` keys and re-fetching state
  per key — O(n) on every room creation; the `max_rooms` limit depends on this staying correct
  as Redis key naming evolves.
- `auth_service`'s auto-generated JWT keys are silently ephemeral in dev — don't assume tokens
  survive a backend restart unless `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` are actually set.
- **`get_db` commits after the response is sent.** A service that changes a row a constraint can
  reject (e.g. `uq_roster_course_netid`) must `await db.flush()` itself and turn the
  `IntegrityError` into a `BuzzerError`; otherwise the client gets a 200 for a write that then
  fails to commit, and the connection is dropped. Read anything needed for the error message
  *before* the flush — a session whose flush failed refuses attribute access until rollback.
  `roster_service.patch_roster_entry` is the worked example.
