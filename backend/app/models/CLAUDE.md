# backend/app/models/

**Purpose.** SQLAlchemy 2.0 declarative ORM models (`Mapped`/`mapped_column`) — the MySQL schema
definition. Every table alembic migrates in `../migrations/versions/` should trace back to a
class here.

**Contents.**
- `user.py` — `User`: local accounts, OAuth2 (netid) accounts, and GUEST accounts share one
  table, distinguished by `role` (`ADMIN`/`USER`/`GUEST`) and which of `netid`/`username`+
  `password_hash`/`email` are populated.
- `course.py` — `Course`, `CourseRoster` (one row per enrolled student, upserted from Canvas CSV
  — see `../services/roster_service.py`), `UserCourseAccess` (per-user `HOST`/`PLAYER` role on a
  course, composite PK `user_id`+`course_id`).
- `game.py` — `Game` (a quiz), `Question` (belongs to a game; `type` +
  `grading_type` (`ACCURACY`/`COMPLETENESS`) + freeform `config`/`answer_data` JSON columns hold
  all per-type-specific shape — validated at the Pydantic layer in `../schemas/admin.py`, not
  here), `UserGameAccess` (which users may host a given game, composite PK). `Game.course_id` is
  a nullable FK to `courses` (NULL = "unattached", ADMIN-only) with a `course` relationship
  (`lazy="selectin"`) and a `course_name` property that `GameResponse`/`MyGameItem` read.
- `session.py` — `GameSession` (one played instance of a `Game` in a `Course`, keyed by
  `room_code`; `status` is `LOBBY`/`IN_PROGRESS`/`COMPLETED`/`ABANDONED`), `SessionScore` (one row
  per player-question answer: points, correctness, timing, raw `answer_data`).
- `__init__.py` — empty; models are imported directly from their modules, not re-exported here.

**How it fits in.** This is the persistent (MySQL) half of game state; `../services/state_service.py`
holds the parallel *ephemeral* (Redis) representation used during an active game for low-latency
reads. `../services/state_service.py::restore_from_mysql` is the bridge that rebuilds Redis state
from these tables if Redis is lost. `../schemas/` defines the API-facing (Pydantic) shapes that
wrap these models for requests/responses — they are deliberately separate so DB columns can differ
from wire format (e.g. `Question.answer_data` is never serialized to players).

**Gotchas.**
- `Game.course`'s `lazy="selectin"` only fires on a SELECT. A `Game` the request just **created**
  or **re-pointed** (`course_id` assigned) has no loaded `course`, and serialising `course_name`
  would lazy-load outside the greenlet (`MissingGreenlet`) or return a stale `None`. Those write
  paths do `await db.refresh(game, ["created_at", "course"])` / expire + refresh explicitly.
- `Question.config`/`answer_data` and `SessionScore.answer_data` are untyped JSON — their actual
  shape varies by `Question.type` and is enforced only by Pydantic validators in
  `../schemas/admin.py::QuestionCreate.validate_structure` and, for `put_in_order` updates, by
  `../services/authoring_service.py::update_question` — not by the DB or ORM layer.
- Several FKs are `NOT NULL` without `ON DELETE CASCADE` (e.g. `game_sessions.game_id`,
  `session_scores.user_id`) — deleting a `Game` or `User` requires manually deleting/reassigning
  dependent rows first (see the gotcha in `../routers/CLAUDE.md` re: `admin.delete_game`/
  `delete_user`). Don't assume SQLAlchemy's cascade config alone handles it.
- `Course.sessions`/`Game.sessions` back-populate `GameSession` but are lazy-loaded — the
  websocket gateway deliberately avoids touching `GameSession.scores` via the ORM relationship
  mid-async-handler (uses raw `select()` instead) to dodge `MissingGreenlet` errors; see the
  comment in `../websocket/gateway.py`'s `_on_host_advance_impl`.
