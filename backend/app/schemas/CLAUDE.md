# backend/app/schemas/

**Purpose.** Pydantic v2 request/response models — the API's wire contract, kept separate from
the ORM models in `../models/` so internal DB shape (nullable FKs, JSON blobs) never leaks
directly to clients and so player-facing responses can omit fields (answer keys, grading type).

**Contents.**
- `admin.py` — schemas for every admin-only resource: courses, roster entries/upload/import,
  games, questions (only `QuestionCreate` carries a `model_validator` — `validate_structure`
  — that enforces per-question-type shape of `config`/`answer_data`, e.g. `multiple_choice` needs
  `answer_points` matching `options` length; `QuestionUpdate` has **no** validator, since it sees
  only a partial body. `put_in_order` rules live in the module-level `validate_put_in_order`
  (and `pin_the_spot` rules in `validate_pin_the_spot`: exact config/answer_data keys, http(s)
  or PNG/JPEG/GIF/WebP data URL ≤ 1,500,000 chars, 0 < r_full < r_zero ≤ image diagonal;
  COMPLETENESS may omit the target),
  called from `validate_structure` and, on the merged values, from
  `../services/authoring_service.py::update_question`. `../models/game.py` stores question data
  as untyped JSON, so these are the only structural checks), users, access grants, and the admin
  session list/export item. `GameResponse` carries `course_id`/`course_name`; `GameCreate` and
  `GameUpdate` take an optional `course_id`; `HostGameCreate` requires it; `HostGameUpdate` has
  **no** `course_id` on purpose (with `extra="forbid"`, a host sending it gets a 422).
- `auth.py` — login/token request-response pairs: `LoginRequest` (username+password OR dev-only
  netid, enforced by a `model_validator`), `TokenResponse`/`TempTokenResponse`/`RefreshResponse`,
  `GuestJoinRequest`.
- `game.py` — player/host-facing game schemas: `QuestionPublic` (deliberately omits
  `answer_data`/`grading_type` — the client-safe question shape), room create/info schemas, host
  resource-list items (`MyCourseItem`, `MyGameItem` — which also carries `course_id`/`course_name`), and `ScoreResult` (internal, used by
  `../services/game_service.py::calculate_score`, not a route response model).
- `__init__.py` — empty.

**How it fits in.** Routers in `../routers/` use these as FastAPI `response_model`s and request
bodies; the websocket gateway (`../websocket/gateway.py`) builds its own raw dict payloads instead
of importing these (Socket.IO events aren't typed by Pydantic here) — payload shape there must be
kept in sync with these schemas by hand where they overlap (e.g. `QuestionPublic` vs.
`gateway._question_payload`).

**Gotchas.**
- `QuestionCreate.validate_structure` is where per-question-type answer validation lives for
  creates and imports (for `put_in_order` it delegates to the shared `validate_put_in_order`
  helper, which `update_question` also calls). Adding a new `type` requires a new branch here,
  the `type` regex on both `QuestionCreate` and `QuestionUpdate`, *and* matching logic in
  `../services/game_service.py::calculate_score` and the **four** reveal builders
  (`../websocket/gateway.py::_answer_reveal`, `../services/report_service.py::_answer_reveal`,
  and `_player_summary_reveal` / `_host_summary_reveal` in `../services/game_service.py`).
  Missing one silently lets malformed questions through or scores them as always-zero.
- Integer checks in `validate_put_in_order` use `type(x) is int`, not `isinstance`: `bool` is an
  `int` subclass, and `sorted([True, 0, 2]) == [0, 1, 2]`.
- `ScoreResult` (in `game.py`) is not an HTTP response model — it's an internal transfer object
  between `game_service.calculate_score` and its caller. Don't assume every class in this
  directory is a route schema.
- `extra="forbid"` is used on almost all input schemas (`CourseCreate`, `GameCreate`,
  `QuestionCreate`, etc.) — new client fields need an explicit schema field, not just a matching
  dict key, or the request is rejected with a 422. **Exception:** `auth.py`'s `GuestJoinRequest`
  has no `model_config` at all, so it silently ignores unknown fields instead of rejecting them —
  inconsistent with the rest of the package. Worth fixing to `extra="forbid"` for consistency, or
  documenting why it's deliberately lax.
