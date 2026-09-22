# backend/app/schemas/

**Purpose.** Pydantic v2 request/response models — the API's wire contract, kept separate from
the ORM models in `../models/` so internal DB shape (nullable FKs, JSON blobs) never leaks
directly to clients and so player-facing responses can omit fields (answer keys, grading type).

**Contents.**
- `admin.py` — schemas for every admin-only resource: courses, roster entries/upload/import,
  games, questions (`QuestionCreate`/`QuestionUpdate` carry a `model_validator` — `validate_structure`
  — that enforces per-question-type shape of `config`/`answer_data`, e.g. `multiple_choice` needs
  `answer_points` matching `options` length; this is the *only* structural validation for question
  data, since `../models/game.py` stores it as untyped JSON), users, access grants, and the admin
  session list/export item.
- `auth.py` — login/token request-response pairs: `LoginRequest` (username+password OR dev-only
  netid, enforced by a `model_validator`), `TokenResponse`/`TempTokenResponse`/`RefreshResponse`,
  `GuestJoinRequest`.
- `game.py` — player/host-facing game schemas: `QuestionPublic` (deliberately omits
  `answer_data`/`grading_type` — the client-safe question shape), room create/info schemas, host
  resource-list items (`MyCourseItem`, `MyGameItem`), and `ScoreResult` (internal, used by
  `../services/game_service.py::calculate_score`, not a route response model).
- `__init__.py` — empty.

**How it fits in.** Routers in `../routers/` use these as FastAPI `response_model`s and request
bodies; the websocket gateway (`../websocket/gateway.py`) builds its own raw dict payloads instead
of importing these (Socket.IO events aren't typed by Pydantic here) — payload shape there must be
kept in sync with these schemas by hand where they overlap (e.g. `QuestionPublic` vs.
`gateway._question_payload`).

**Gotchas.**
- `QuestionCreate.validate_structure` is the single place per-question-type answer validation
  lives — adding a new `type` requires a new branch here *and* matching logic in
  `../services/game_service.py::calculate_score` and the reveal builders in
  `../services/report_service.py` / `../websocket/gateway.py`. Missing one silently lets
  malformed questions through or scores them as always-zero.
- `ScoreResult` (in `game.py`) is not an HTTP response model — it's an internal transfer object
  between `game_service.calculate_score` and its caller. Don't assume every class in this
  directory is a route schema.
- `extra="forbid"` is used on almost all input schemas (`CourseCreate`, `GameCreate`,
  `QuestionCreate`, etc.) — new client fields need an explicit schema field, not just a matching
  dict key, or the request is rejected with a 422. **Exception:** `auth.py`'s `GuestJoinRequest`
  has no `model_config` at all, so it silently ignores unknown fields instead of rejecting them —
  inconsistent with the rest of the package. Worth fixing to `extra="forbid"` for consistency, or
  documenting why it's deliberately lax.
