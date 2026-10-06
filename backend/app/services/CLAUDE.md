# backend/app/services/

**Purpose.** Business logic layer, called by routers (`../routers/`) and the websocket gateway
(`../websocket/gateway.py`). No FastAPI/Socket.IO imports here — these are plain async functions
over SQLAlchemy sessions and the Redis client, so both transports share one implementation.

**Contents.**
- `authoring_service.py` — question list/create/update/delete/reorder (with `bleach` prompt
  sanitising), the `buzzer/game` export bundle builder, and the bundle importer
  (`import_game_bundle(db, raw, course_id, uploaded_by)`; raises `BundleError`, which routers
  map to 422). Export writes version 1 unless a question uses a library image, then version 2
  with each image embedded once (409 if a referenced image row is gone). Import of version 2
  checks every image, reuses the course's oldest row with the same `sha256`, rewrites the
  references and refuses images when `course_id` is None (the admin route); version 1 files
  may not carry image references. Nothing commits on failure: the `BundleError` reaches
  `get_db`, which rolls back the flushed image rows too.
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
- `image_service.py` — the course image library (T8, `docs/design-image-support.md`):
  `process_upload` (pure; format from the bytes, ≤ 5 MB and ≤ 40 MP checked from the header,
  metadata stripped by re-encoding only images that aren't clean by an allowlist; idempotent,
  so an export re-imports byte for byte), `process_upload_async` (worker thread via
  Starlette's `run_in_threadpool`, the one framework import here: it is CPU-bound and this
  process serves Socket.IO), `clamp_radii`, `question_image_refs`,
  `usage_map`/`where_used` (one scan of the course's questions plus one grouped answer count;
  there is no link table), `validate_question_images` (ownership; overwrites a Pin the Spot
  `image_id`'s size), and the library operations: list, upload, replace (409 for a played
  canvas; resizes and clamps unplayed canvases), delete (409 while used; FK race → 409), and
  the public GET's two reads (head, then bytes only for a 200).
- `export_service.py` — builds session-score CSVs: a raw per-question export and a
  Canvas-gradebook-formatted one (SIS Login ID matching, optional per-question columns,
  roster-only filtering). Every points cell, total and "Points Possible" goes through `_pts`
  (round to 4 dp): points columns are single-precision `FLOAT`, and `put_in_order` partial
  scores (e.g. 0.83) would otherwise print float noise. Answers never appear in the CSV.
- `game_service.py` — the core game/session logic: room code generation, host access checks
  (`assert_host_can_use_course/game`, plus `visible_games_query`, its list-side twin), session lifecycle (create/start/complete/abandon),
  player authorization against the course roster (`authorise_player`), answer scoring
  (`calculate_score` — one branch per question type × grading type; `put_in_order` scores
  pairwise, half-up to 2 dp, clamped to `points_value`; `pin_the_spot` delegates to
  `pin_the_spot.py`), `record_answer` (persists
  to MySQL + updates Redis in one call; `put_in_order` writes one `"{item}@{position}"`
  distribution key per item, `pin_the_spot` one `"x,y"` (4 dp) key per tap, under both grading
  types), and leaderboard/summary builders for
  GAME_OVER payloads (their reveals are `_player_summary_reveal` / `_host_summary_reveal`; the
  player summary also carries `isCorrect`, and drops `config.image_url` for `pin_the_spot`).
- `pin_the_spot.py` — pure rules for Pin the Spot (no DB/Redis): `is_valid_tap`, `tap_key` /
  `parse_tap_key`, `aspect`, `answer_key`, `tap_distance`, `score`, `reveal`, `EDGE_EPSILON`, and
  `half_up_points` (the half-up-to-2-dp helper `put_in_order` also uses). `calculate_score`,
  `record_answer`, the host summary, the report and all four reveal builders call it.
- `authoring_service.py` `update_question` — for `put_in_order` (stored or requested type) it
  checks the *merged* values before assigning anything: a question with `session_scores` rows
  can't change `type`, `config.items` or `correct_order` (409, `ConflictError`), then
  `validate_put_in_order` must pass (422, `ValidationFailedError`). `pin_the_spot` mirrors it: a
  played question can't change `type` or `config` (the image; compared by value, so an identical
  resend passes), target/radii/grading stay editable with no rescoring, then
  `validate_pin_the_spot` on the merged type. Other types keep the unvalidated update path.
  For **every** type, the image checks (`validate_image_keys`, then
  `image_service.validate_question_images`) run right after the merge, so an image 422 comes
  before any played guard's 409, and a stale Pin the Spot size is overwritten before the guard
  compares. `prompt_image_id` left out keeps the stored value; `null` clears it.
- `report_service.py` — generates a standalone, self-contained HTML session report (aggregate
  stats only, no PII) with inline CSS and hand-rolled bar-chart/word-cloud/histogram renderers,
  plus an inline-SVG board for `pin_the_spot` (`_render_pin_board`; the image URL is
  `html.escape(..., quote=True)`d because the `https` check allows `"`). Library images (T8)
  are embedded as `data:` URLs from one query: prompt images, thumbnails on MC bars (the report
  draws no multi-select bars), and `image_id` canvases; a missing row is left out (canvas:
  "Image missing").
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
- `game_service.calculate_score` and the four reveal builders (`report_service._answer_reveal`,
  `websocket/gateway.py::_answer_reveal`, `game_service._player_summary_reveal` and
  `_host_summary_reveal`) independently encode "what counts as correct" per question type —
  there is no single source of truth. A new question type needs updates in all of them (plus
  the Pydantic validators in `../schemas/admin.py`).
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
- Write a JSON column by assigning a new dict (`q.config = {**q.config, …}`), never by editing
  it in place: SQLAlchemy doesn't track changes inside `Question.config`.
- **`get_db` commits after the response is sent.** A service that changes a row a constraint can
  reject (e.g. `uq_roster_course_netid`) must `await db.flush()` itself and turn the
  `IntegrityError` into a `BuzzerError`; otherwise the client gets a 200 for a write that then
  fails to commit, and the connection is dropped. Read anything needed for the error message
  *before* the flush — a session whose flush failed refuses attribute access until rollback.
  `roster_service.patch_roster_entry` is the worked example.
