# Design: Host / Admin UI Restructuring (T4) — Frontend

Status: **Ready to implement** — Goldfish-tested five times (§11, §13, §15, §16, §18) and
design-reviewed three times (§12, §14, §17) · Scope: `frontend/host`, `frontend/admin` (plus the
backend API contract they depend on) · Task: T4 in [instructions.md](../instructions.md)

**How to read this.** §1–§2 are the problem and the decisions. §3 is the backend contract, §4 the
frontend plan, §8 the build order, §10 the tests. **Build from §3 and §4** — where §8 or §10 could be
read as disagreeing with them, §4.5 is the page contract and §3 is the API contract. §11–§18 are the
revision history: evidence for T10/T11, not instructions.

Two things will break at runtime if skipped, and neither is visible from the section it belongs to:
**`course_name` is not safe on a `Game` the request just created or just re-pointed** (§3.3's closing
paragraph — `lazy="selectin"` does not cover either case), and **a GUEST gets a 403 from
`/game/my-courses`, not `[]`** (§4.6's rejected branch, not its empty state).

One more to read *before writing the §10 tests*, because it decides how all of them are written:
**§10's fixtures are session-scoped and clean up after themselves.** The suite's only existing
example (`conftest.py::game_setup`) is function-scoped and leaks a course per test by design.

---

## 1. Problem

The admin app (`frontend/admin`) does two different jobs:

1. **Admin work**: user accounts, course creation, granting course/game access, guest merging.
2. **Host work**: editing games and questions, uploading rosters, and downloading session
   results.

The host app (`frontend/host`) only has a login page, a course+game picker on `/home`, and the
live game screens. As a result, an instructor with HOST access to a course cannot edit their own
quizzes, update their roster, or download their results. They have to ask an admin, and the
admin uses endpoints that are all gated by `require_admin`.

T4 asks for the following:

| # | Host capability | Today |
|---|---|---|
| H1 | Download session summary (HTML) for a completed session | Admin-only (`GET /admin/sessions/{id}/report`) |
| H2 | Download per-player scores (CSV) for a completed session | Backend route exists (`GET /game/sessions/{id}/export`, host-or-admin); **no host UI** |
| H3 | View and update the roster (CSV upload, deactivate) for a course where the user has HOST access | Admin-only (`/admin/courses/{id}/roster*`) |
| H4 | Create games; add, edit, delete, and reorder questions and their scoring | Admin-only (`/admin/games*`) |
| H5 | Games are attached to one course at creation, and only that course's hosts and players can reach them | **Not modelled**: `games` has no `course_id`, and any game can be played in any course |

| # | Admin requirement |
|---|---|
| A1 | Admin-first layout: Users, Courses, and access grants come first |
| A2 | Admins keep full host and player capability, placed lower in the navigation |

Constraint: every new capability goes through the existing role/permission system
(`require_user` + `assert_host_can_use_course` / `assert_host_can_use_game`). There are no
client-side-only gates.

## 2. Key decisions (summary)

1. **Host-owned screens move into the host app and are no longer duplicated in the admin app.**
   `GamesPage`, `QuestionEditorPage`, and `RosterPage` are moved from `frontend/admin` to
   `frontend/host` and pointed at a new host-scoped API (`/api/host/...`). The admin app links
   to them instead of keeping its own copies.
2. **The host app gets a management shell.** Non-game routes (`/home`, `/games`, `/courses`,
   `/sessions`) are wrapped in a top-nav layout. The live game routes (`/game/:code/*`) stay
   full-screen with no shell, because they are shown on the projector.
3. **The admin app is reordered to be admin-first.** Users, Courses, Access, and Guests come
   first. A separate "Host tools" group holds Sessions (all hosts, Canvas export) and outbound
   links to the host app's Games and Rosters screens.
4. **Games have a `course_id`.** The host UI always requires a course when creating or
   importing a game. Game lists show and filter by course. The course picker on `/home` filters
   games by the selected course.
5. **Effective game access for a non-admin is HOST on `game.course_id` AND a `user_game_access`
   row.** Creating a game automatically grants access to its creator. ADMIN bypasses both checks,
   as it does today.

## 3. Backend contract this frontend depends on

The frontend cannot be built without these endpoints. They are listed here so both halves are
built against the same contract. Paths are relative to `/api`. "Host-gated" means
`require_user`, followed by `assert_host_can_use_course(course_id)` and/or
`assert_host_can_use_game(game_id)` on the resource. ADMIN passes every check.

### 3.1 Data model change

- `games.course_id INT NULL, FK → courses.id` (new Alembic migration). The column is
  **nullable** so that existing rows and the current `/admin/games` callers keep working. Today
  these callers are `tests/integration/conftest.py`, `scripts/seed_demo.py`, and
  `scripts/smoke_test_websocket.py`, and they create games with no course. T5 forbids weakening
  existing tests.
- A game with `course_id = NULL` is "unattached". **Only ADMIN** can host or edit it.
- `assert_host_can_use_game` for a non-admin requires all three:
  `game.course_id IS NOT NULL`, HOST on `game.course_id`, and a `user_game_access` row.
- `create_room(game_id, course_id)` rejects a game whose `course_id` is non-null and does not
  match `course_id` (403). This enforces H5 for **players** without any player-frontend change,
  because players are already authorised against `session.course_id`
  (`game_service.authorise_player`).
- **That mismatch check is deliberately role-blind**: not even an ADMIN may run course A's game in
  course B. ADMIN's bypass is of the *access* checks (`assert_host_can_use_*`), not of H5's
  course-identity rule, because a session in the wrong course would be scored against the wrong
  roster. A2 ("admins keep full host capability") still holds — an admin can host any game in
  **its own** course, and attach an unattached one first.

### 3.2 Endpoints (new unless marked)

| Method & path | Gate | Used by |
|---|---|---|
| `GET /game/my-courses` *(existing, unchanged)* | require_user. **Already HOST-scoped** — see §3.4 | Host shell, Games, Rosters, Home |
| `GET /game/my-games?course_id=` *(see §3.3 — the query changes, not just the filter)* | require_user | Home picker |
| `GET /host/games?course_id=` | require_user. When `course_id` is **present**, `assert_host_can_use_course(course_id)` runs **before** the query — 403 for a non-admin without HOST on it, and **403 (not 404) for a non-admin naming a course that does not exist**: that function checks existence only in its ADMIN branch, so a missing course looks exactly like a missing `user_course_access` row. ADMIN gets the 404. Course existence is deliberately not leaked to non-hosts. The §3.3 visibility rule then applies to the result set. `course_id=` filters for **every** role; unattached games appear for ADMIN **only when no `course_id` is given** | Games list |
| `POST /host/games` `{title, description, max_players, course_id}` | HOST on `course_id`; inserts a `user_game_access` row for the creator. **Must `await db.refresh(game, ["course"])` after the flush** before returning `GameResponse` — write the attribute-scoped form, *not* the bare `await db.refresh(game)` that `admin.create_game` uses today. See §3.3's closing paragraph | Games list |
| `GET /host/games/{id}` · `PUT /host/games/{id}` | host-gated on game. The body is a **new `HostGameUpdate`** (`title`, `description`, `max_players`, `extra="forbid"`) — *not* `GameUpdate`. Sending `course_id` is a **422**. See §3.5 | Question editor, Games list |
| `GET/POST /host/games/{id}/questions` | host-gated on game | Question editor |
| `PUT/DELETE /host/games/{id}/questions/{qid}` | host-gated on game; `qid` must belong to `id` | Question editor |
| `POST /host/games/{id}/questions/reorder` `{order: [ids]}` (same body as admin) | host-gated on game | Question editor |
| `GET /host/games/{id}/export` | host-gated on game | Question editor |
| `POST /host/games/import` multipart `file`, `course_id` | HOST on `course_id`; auto-grants the creator | Games list |
| `GET /host/courses/{cid}/roster` | HOST on `cid` | Roster |
| `POST /host/courses/{cid}/roster/import` (mapped rows) | HOST on `cid` | Roster |
| `PATCH /host/courses/{cid}/roster/{rid}` | HOST on `cid`; `rid` must belong to `cid` | Roster |
| `GET /host/sessions?status=` | require_user; non-admin sees only `host_user_id == me`. `status` is one exact value from the `session_status` enum, or omitted for all — there is no multi-status alias (see §4.5) | Sessions |
| `GET /host/sessions/{sid}/report` | session host or ADMIN | Sessions |
| `GET /game/sessions/{sid}/export` *(existing, raw per-player CSV)* | session host or ADMIN | Sessions |
| `POST /admin/games` *(existing; accepts optional `course_id`)* | require_admin; a `course_id` that does not exist is a **404** — `create_game` has no existence check today, so without one the FK error surfaces as a 500. Same `db.refresh(game, ["course"])` requirement as `POST /host/games`, **replacing** this route's existing bare `await db.refresh(game)` | `scripts/seed_demo.py` (§8-13), `tests/`, §10 |
| `POST /admin/games/import` *(existing, unchanged)* | require_admin | unchanged callers |
| `PUT /admin/games/{id}` *(existing; `GameUpdate` gains `course_id: int \| None`)* | require_admin; `course_id` is accepted **only while the stored value is `NULL`** — an attempt to change a non-null `course_id` is a **409 Conflict**, because moving a game between courses would orphan its past sessions' roster scoping. After assigning `course_id`, **`db.expire(game, ["course"])`** or the response serialises a stale `course_name: null` — see §3.3's closing paragraph | Host GamesPage "Attach to course", ADMIN only |
| `DELETE /admin/games/{id}` *(existing)* | require_admin | Host Games list, shown to ADMIN only |
| `GET /admin/games` *(existing; add `course_id`, `course_name` to `GameResponse`)* | require_admin | Admin UserDetail grants |

Response shapes for the `/host/*` endpoints match their `/admin/*` equivalents, so the moved
pages only need their path prefix changed. `GameResponse` gains `course_id: int | null` and
`course_name: str | null`. `GET /host/sessions` returns `AdminSessionItem`
(`backend/app/schemas/admin.py`) unchanged — it already carries `session_id`, `status`,
`game_title`, `course_name`, `course_semester`, `room_code`, `created_at` and `player_count`,
which is everything §4.5 needs. The first two matter most and are the easiest to overlook:
`status` is what gates §4.5's download buttons on `COMPLETED`, and the id field is spelled
**`session_id`, and is a `str`** — not `id`, not an int.

**`AdminSessionItem` is `ConfigDict(from_attributes=False)`.** It is not serialised off an ORM
object: `admin.list_sessions` builds the rows by hand in a loop. See §3.3 — that loop is the sixth
entry on the extract-don't-copy list, not something `GET /host/sessions` reimplements.

**There is no host multipart roster route.** The admin app's `POST /admin/courses/{cid}/roster`
(multipart CSV → `process_roster_csv`) has **no consumer**: `RosterPage` parses the CSV in the
browser and posts mapped rows to `…/roster/import`, and nothing under `tests/` or `scripts/` calls
the multipart path either. §4.5 keeps that same wizard, so `/host/*` mirrors only
`…/roster/import`. Do not build a host multipart route for parity with admin.

**A game's course never travels in the file.** `course_id` is a **multipart form field** on
`POST /host/games/import`, alongside `file`. It is never read from the bundle, for three reasons:

- `import_game` validates the bundle's game object with `GameCreate(**game_data)`
  ([`routers/admin.py`](../backend/app/routers/admin.py)), and `GameCreate` is `extra="forbid"`.
  Once `GameCreate` gains `course_id: int | None`, a hand-edited file carrying a `course_id` would
  otherwise construct a game attached to a course the uploader may not host. `import_game`
  therefore **pops `course_id` out of `game_data`** before constructing `GameCreate`, and the host
  route sets it from the validated form field afterwards. The form field is the only path; there
  is no precedence rule to remember, because the file's value is discarded rather than overridden.

  The extracted import service (extraction 4 below) therefore takes `course_id: int | None` as an
  **argument**, and **only the host route passes it** — `POST /admin/games/import` keeps its current
  signature (`file` alone) and passes `None`, so an admin-imported bundle lands unattached. There is
  no optional `course_id` on the admin import route: nothing in §4, §8, §8-12 or §10 calls it, the
  admin app's `/games` route is deleted (§4.2), and `seed_demo.py` attaches its game through
  `POST /admin/games` (§8-13), not through import. Adding the field to both routes for symmetry
  would be one more unexercised path, not parity.
- `export_game` keeps emitting exactly `game: {title, description, max_players}`. The bundle format
  stays `"version": 1` and course-free, so `GET /host/games/{id}/export` →
  `POST /host/games/import` round-trips a game into a *different* course, which is what an
  instructor reusing last term's quiz actually wants.
- **T6 depends on this.** Sample games under `sample_games/` must import cleanly as unmodified
  version-1 files. A required form field satisfies that; a required *bundle* field would break
  every existing file and force a version bump T6 explicitly wants to avoid.

### 3.3 Game visibility: one rule, three endpoints

`GET /game/my-games`, `GET /host/games`, and `assert_host_can_use_game` must all apply the **same**
rule, or the UI will list games that `create_room` then rejects:

- **ADMIN** — every game, attached or not.
- **Non-admin** — `games.course_id IS NOT NULL` **AND** a `user_course_access` row with
  `role = 'HOST'` on `games.course_id` **AND** a `user_game_access` row for the user.

This is a real change to `GET /game/my-games`, not just a new filter.
[`routers/game.py`](../backend/app/routers/game.py)'s `my_games` currently joins `user_game_access`
alone, so today it would list unattached games and games on courses the user has no HOST access to.
In pseudocode:

```
if user.role == ADMIN:            select Game                       (+ optional course_id filter)
else:                             select Game
                                    join UserGameAccess on game_id, user_id = me
                                    join UserCourseAccess on course_id = Game.course_id,
                                         user_id = me, role = 'HOST'
                                    where Game.course_id is not null  (+ optional course_id filter)
```

**Invariant to test (T5):** every game `GET /game/my-games` returns is one `POST /game/rooms`
accepts for that game's own course. Listed ⇒ creatable.

**The `course_id` query parameter is a gate, not only a filter.** `GET /host/games` calls
`assert_host_can_use_course`
([`services/game_service.py`](../backend/app/services/game_service.py)) whenever the parameter is
present, so an unauthorised course is a 403 rather than an empty list. This is deliberate: the
Games page populates its course `<select>` from `/game/my-courses`, so a legitimate client never
sends a course the user cannot host, and a 403 distinguishes "not your course" from "no games
yet". `GET /game/my-games?course_id=` keeps **filter-only** semantics — it is the Home picker's
list endpoint and must stay forgiving.

**Serialising the course name.** `GameResponse` and `MyGameItem` are both `from_attributes=True`,
and every current return path is `return result.scalars().all()` or `return game`. `Game`
([`models/game.py`](../backend/app/models/game.py)) has relationships to `questions`, `sessions`
and `user_access` and **no `course` relationship**, so `course_name` cannot be read off the ORM
object today. Add one to the model:

```
course: Mapped[Course | None] = relationship("Course", lazy="selectin")
```

`lazy="selectin"` is **not optional.** Pydantic serialises after the query has returned and the
awaited scope has closed, so a default-lazy relationship raises
`MissingGreenlet: greenlet_spawn has not been called` on an async session the first time
`GameResponse` touches it. `selectin` issues a second SELECT inside the original await instead.
The alternative — an explicit `selectinload(Game.course)` on every query feeding a `GameResponse`
or `MyGameItem` — works, but has to be remembered at each read site in `routers/admin.py`,
`routers/game.py` and the new `routers/host.py`; the relationship-level setting cannot be
forgotten. `course_name` is then a plain property on the model (`self.course.name if self.course
else None`), which `from_attributes` picks up with no change at any **read** site.

**`lazy="selectin"` covers queried games only — two write paths need an explicit refresh.** The
loader strategy fires as part of a SELECT, so it covers `db.get`, `my_games`, `list_games` and
`GET /host/games`. It does **not** cover a `Game` the same request mutated or created:

- **Created** (`POST /host/games`, `POST /admin/games`): the object is constructed and flushed, so
  `course` is not loaded by the statement that wrote the row. Pydantic's attribute access can then
  fall back to a lazy load on an async session → `MissingGreenlet`, the exact failure this paragraph
  exists to avoid. It also hides itself until the attached-create path runs: a many-to-one lazy load
  with a `NULL` FK short-circuits without emitting SQL, so every existing unattached
  `POST /admin/games` keeps working.

  **What the existing code actually does, because it changes what you write.**
  [`admin.py`](../backend/app/routers/admin.py)::`create_game` is
  `db.add(game)` → `await db.flush()` → **`await db.refresh(game)`** → `await db.commit()`. It does
  re-SELECT the row, so whether `course` comes back loaded depends on whether a bare
  `Session.refresh()` re-applies the mapper's `selectin` strategy — which is exactly the kind of
  thing not to bet a 500 on. Fix, on **both** create paths: write
  `await db.refresh(game, ["course"])`, **replacing** the bare `db.refresh(game)` rather than sitting
  next to it. The attribute-scoped form is correct either way, and `POST /host/games` is specified
  as copying `create_game`'s shape, so the bare call would otherwise be copied too.
- **Re-pointed** (`PUT /admin/games/{id}` setting `course_id`, the §4.5 attach control): `db.get`
  already resolved `course` to `None` — unattached is the only state the control renders on — and
  assigning the FK attribute does not update the loaded relationship. `AsyncSessionLocal` is
  `expire_on_commit=False` ([database.py](../backend/app/database.py)) **and `get_db` commits after
  the route returns**, i.e. after FastAPI has serialised the response, so nothing refreshes it in
  that window. The attach would report success with a blank course name. Fix:
  `db.expire(game, ["course"])` after the assignment.

Both are asserted in §10 on the **response body**, not the status code, because both return 2xx.

**Auto-grant is host-only.** `POST /host/games` and `POST /host/games/import` insert a
`user_game_access` row for the creator. `POST /admin/games` and `POST /admin/games/import` do
**not** — an admin already bypasses both checks, and handing the game to an instructor is the
explicit grant step A1 asks for, done on `UserDetailPage`.

**After this change `POST /admin/games` has no UI caller.** §4.2 deletes the admin app's `/games`
route, and an admin creating a game through the host GamesPage takes the auto-granting `/host` path.
The admin create routes stay for `scripts/`, `tests/integration/` and the §10 cases — so the
consequence below describes the **script and API path only**. It is not a flow an admin can trip
over in the console.

That consequence: a game created through `POST /admin/games` for a course is invisible to that
course's hosts until granted. It is intended (see Alt 7), and the `UserDetailPage` note in §4.5 is
what makes it legible when the grant is the thing that was forgotten.

**Backend files implied** (owned by the backend half of T4, listed so this list is complete):
`backend/app/models/game.py` (`course_id` column, `course` relationship with `lazy="selectin"`,
`course_name` property), new `backend/app/migrations/versions/<rev>_game_course_id.py`,
`backend/app/schemas/admin.py` (`GameResponse.course_id`/`course_name`, `GameCreate.course_id`,
`GameUpdate.course_id` — note `GameUpdate` is `extra="forbid"`, so the field must be added or the
request 422s — plus a **new `HostGameUpdate`** without `course_id`, per §3.5), `backend/app/schemas/game.py` (`MyGameItem.course_id`/`course_name`), new
`backend/app/routers/host.py`, `backend/app/main.py` (mount the router),
`backend/app/routers/game.py` (my-games filter), `backend/app/routers/admin.py` (optional
`course_id`), `backend/app/services/game_service.py` (`assert_host_can_use_game`,
`create_room`), and the matching `CLAUDE.md` files.

Shared logic between `/admin/*` and `/host/*` must be **extracted into a service function and
called from both routers**, not copied. `routers/CLAUDE.md` already records two places where
duplicated logic has drifted (guest merge, auth checks). Six things qualify:

1. question create/update, with its `bleach` prompt sanitisation
2. question reorder
3. roster upsert (`…/roster/import` → `process_roster_rows`)
4. game import
5. the **export bundle builder** — §3.2 lists `GET /host/games/{id}/export`, and `export_game`'s
   bundle construction would otherwise be copied
6. the **session-list row builder**, which is the largest of the six and the easiest to miss
   because §3.2's "returns `AdminSessionItem` unchanged" reads like there is nothing to build.
   There is: `AdminSessionItem` is `from_attributes=False`, and
   [`routers/admin.py`](../backend/app/routers/admin.py)::`list_sessions` assembles each row in a
   hand-written loop — `db.get(Game)`, `db.get(Course)`, `db.get(User)` and a
   `count(SessionScore.user_id.distinct())` **per session** — then returns `list[dict]`. Extract it
   as a service function over `(db, status: str | None, host_user_id: str | None)`: the admin route
   passes `host_user_id=None`, and `GET /host/sessions` passes `None` for an ADMIN and `me` for
   everyone else (§4.6). The N+1 shape is pre-existing and is carried over as-is — moving it is in
   scope, fixing it is not.

### 3.4 `GET /game/my-courses` is the frontend's HOST-course source of truth

Five screens populate a course `<select>` or an empty state from this one endpoint (HostShell,
Home, Games, Courses, Roster), so its exact semantics are part of the contract rather than an
implementation detail. Verified in [`routers/game.py`](../backend/app/routers/game.py)::`my_courses`:

- **Non-admin** — joins `user_course_access` with `role == 'HOST'`. A PLAYER-only user gets `[]`.
- **ADMIN** — a separate branch selecting **every** course, each returned with `"role": "HOST"`.

Two consequences the frontend depends on:

1. **No client-side filtering is needed anywhere.** Every course this endpoint returns is one the
   user may host, which is what makes §3.3's `?course_id=` gate safe: a legitimate client cannot
   send a course it would get a 403 for. Do not add a second filter on top.
2. **§4.6's empty state is correct for an ADMIN**, but for a reason that has nothing to do with
   `assert_host_can_use_course`'s admin bypass — it is the ADMIN branch above. The one case where
   an admin *does* see the §4.6 state is a database with **zero courses**, which is a correct and
   useful thing to show them (the fix is to create a course). §4.6 states the role gate anyway, so
   the message an admin sees points at the admin console rather than at "ask an administrator".

This endpoint is **not** modified by T4. It is documented here because §3.3 changes its sibling
`my-games` and the two are easy to conflate.

### 3.5 `course_id` is not reachable through any `/host` route

§3.2 adds `course_id` to `GameUpdate` so ADMIN can attach an unattached game. That schema must
**not** be reused by `PUT /host/games/{id}`. Today
[`schemas/admin.py`](../backend/app/schemas/admin.py)'s `GameUpdate` has only
`title`/`description`/`max_players`, and [`routers/admin.py`](../backend/app/routers/admin.py)::`update_game`
applies them with three independent `if body.X is not None` blocks. A host route written in that
same shape, against a `GameUpdate` that has meanwhile grown a fourth field, would apply
`course_id` too — handing hosts the course-reassignment power the admin route deliberately guards
with a 409.

So the host route takes its **own** `HostGameUpdate` schema with the three editable fields and
`extra="forbid"`. A host sending `course_id` gets a 422 from Pydantic. This is chosen over
"accept the shared schema and remember to skip the field" precisely because `extra="forbid"`
cannot be forgotten, whereas a skipped `if` block can — the same reasoning as §3.3's
`lazy="selectin"`.

Changing a game's course is therefore an ADMIN-only operation, reachable only through
`PUT /admin/games/{id}`, and only while the stored value is `NULL`.

## 4. Frontend plan

### 4.1 Host app: route map (after)

```
/login                          LoginPage            (unchanged)
── HostShell (top nav, RequireAuth) ──────────────────────────────
/home                           HomePage             "Play": active sessions + create room
/games                          GamesPage            NEW (moved from admin)
/games/:gameId/questions        QuestionEditorPage   NEW (moved from admin)
/courses                        CoursesPage          NEW: my HOST courses → roster
/courses/:courseId/roster       RosterPage           NEW (moved from admin)
/sessions                       SessionsPage         NEW: my sessions + downloads
── no shell (projector) ──────────────────────────────────────────
/game/:code/{lobby,question,results,gameover}   unchanged
*                               → /login             (unchanged)
```

`HostShell` nav items: **Play** (`/home`), **Games**, **Rosters** (`/courses`), **Sessions**,
then a right-aligned **Admin console** link (`/admin/`, shown only when the JWT role is `ADMIN`)
and **Sign out**.

### 4.2 Admin app: route map (after)

```
Sidebar group "Administration" (top)
  Users        /users, /users/:userId    (unchanged; default landing route)
  Courses      /courses                  (create/edit; "Roster" → host app)
  Guests       /guests                   (unchanged)
Sidebar group "Host tools" (below a divider, muted heading)
  ↳ muted sub-label: "open the host app"
  Sessions     /sessions                 (all hosts; Canvas export; unchanged page)
  Games ↗      external link → {HOST_APP_URL}/games
  Rosters ↗    external link → {HOST_APP_URL}/courses
  Host a game ↗ external link → {HOST_APP_URL}/home
  Join as player ↗ external link → {PLAYER_APP_URL}/join
```

Removed admin routes: `/games`, `/games/:gameId/questions`, `/courses/:courseId/roster`. Each
one is replaced with `<ExternalRedirect>` to the matching host-app URL so old bookmarks still
work. The catch-all changes from `/courses` to `/users`.

`ExternalRedirect` takes a **builder**, not a fixed string, so route params survive the hop. It
calls `useParams()` and passes the result to the builder in an effect:

```
<ExternalRedirect to={p => `${HOST_APP_URL}/games/${p.gameId}/questions`} />
<ExternalRedirect to={p => `${HOST_APP_URL}/courses/${p.courseId}/roster`} />
<ExternalRedirect to={() => `${HOST_APP_URL}/games`} />
```

The param names are the existing ones in `admin/src/App.tsx` (`:gameId`, `:courseId`) and the host
app's new routes use the same names, so a bookmark lands on the same resource, not a list page.

The component **renders `null`** while the effect runs — no spinner, no "Redirecting…" copy. The
navigation is immediate and a flash of placeholder text is worse than a blank frame.

There is no separate "Access" page. Course and game grants already live on `UserDetailPage`,
and keeping them there avoids building a second grant UI. The A1 "access grants" requirement is
covered by Users being first in the nav and UserDetail being where grants happen.

### 4.3 Cross-app URLs and the auth token

- Production (nginx) and the Docker stack serve all three apps from one origin (`/host/`,
  `/admin/`, `/player/`). `localStorage.token` is per-origin, so it is **shared**: an admin who
  follows "Games ↗" arrives already signed in.
- In Vite dev mode each app has its own port (5173/5175) and the links need
  `VITE_HOST_APP_URL=http://localhost:5173` / `VITE_PLAYER_APP_URL=http://localhost:5174` to work at
  all. With them set, the link reaches the host app but not the token (separate origins), so it lands
  on the host login page — acceptable for development.

  **Without them it fails silently, and not in the way the default path suggests.**
  `frontend/admin/vite.config.ts` sets `base: '/'` in dev and proxies only `/api`, so there is no
  `/host` route on :5175: `window.location.replace('/host/games')` hits the admin dev server, gets
  the SPA `index.html` fallback, and lands in the admin router — whose `basename` is `/` in dev, so
  `/host/games` matches nothing and falls through to the catch-all §4.2 repoints at `/users`. The
  "Games ↗" link therefore returns the user to the admin app's own Users page with no error and no
  navigation they can see. Both sentences go in the admin `lib/CLAUDE.md`.
- URLs come from `import.meta.env.VITE_HOST_APP_URL ?? '/host'` and
  `import.meta.env.VITE_PLAYER_APP_URL ?? '/player'`, defined once in `admin/src/lib/links.ts`
  and `host/src/lib/links.ts` (`VITE_ADMIN_APP_URL ?? '/admin'`).

### 4.4 Role awareness in the UI (display only)

New `host/src/lib/auth.ts`: `getToken()`, `clearToken()`, and `getRole(): 'ADMIN' | 'USER' |
'GUEST' | null`. `getRole()` base64-decodes the JWT payload's `role` claim without verifying it.
The claim exists: [`services/auth_service.py`](../backend/app/services/auth_service.py)::`create_access_token`
builds its payload with `"role": role`. (Worth citing because if the claim were absent or renamed,
`getRole()` would silently return `null` and the Admin console link and Delete button would never
render for anyone — a failure that reads as a permissions bug, not a typo.)
It is used **only** to show or hide UI (the Admin console link, and the Delete-game button
that calls `/admin/games/{id}`). Every action is still authorised by the server. A forged role
claim only reveals a button that returns 403. `api.ts`, `App.tsx`, `LoginPage`, and
`GameLayout` switch to `getToken()`, which fixes the "no single accessor" gotcha in
`host/src/lib/CLAUDE.md`.

### 4.5 Page behaviour

**HomePage (host)**: same layout, with one change to how games are loaded. Today the page fetches
`/game/my-courses` and `/game/my-games` together in one `Promise.all` on mount. After this change:

- On mount it fetches **only** `/game/my-active-sessions`, and takes the course list from the shell's
  outlet context (§4.6) instead of fetching `/game/my-courses` itself. The games list starts empty.
- With **no course selected**, the Quiz select is disabled with the placeholder "Select a course
  first". No `my-games` request is made.
- When `courseId` changes, fetch `/game/my-games?course_id={courseId}`. The existing
  "auto-select a single game" logic runs on that result. Clear `gameId` first on every course
  change, so a stale selection can never survive into a new course.
- Empty state for a course with no games: "No quizzes for this course yet — create one in Games."
- Its load-failure message changes with its payload. The page's catch today reads "Failed to load
  courses or games. Are you still logged in?"; after this change it loads neither, so it becomes
  "Failed to load your active sessions." The course list's failure is the shell's, and §4.6 owns
  all four of its branches.

The single-course auto-select already in the page still runs, so the common case (an instructor
with one course) reaches a usable Quiz select with no extra click. **It has to move to do so.**
Today it is `if (c.length === 1) setCourseId(c[0].id)` *inside* the mount `Promise.all`
([`HomePage.tsx`](../frontend/host/src/pages/HomePage.tsx)); the courses now arrive from outlet
context **after** mount, so left where it is the branch runs against an empty list on every load and
nothing is ever auto-selected. Make it an effect keyed on the context course list, which also makes
it correct when the shell's Retry refetch resolves. The single-*game* auto-select stays where §4.5
puts it, on the `my-games` result.

**GamesPage (host, moved)**:
- List: a course **filter** `<select>` — not grouping — whose options are "All courses" plus the
  shell's courses (outlet context, §4.6), **defaulting to "All courses"**. Each row shows title,
  course name, and description. ADMIN-only rows with `course_id = null` are labelled "Unattached
  (admin only)".
  - On mount, and whenever "All courses" is selected: `GET /host/games` with **no `course_id`
    parameter**. This is the only request shape that returns unattached games to an ADMIN (§3.2),
    which is why it is the default rather than the first course — and it means the page's first
    request can never 403.
  - Choosing a course refetches `GET /host/games?course_id={id}`, which is **gated**, not merely
    filtered (§3.3). A 403 is unreachable from this page because every option came from
    `/game/my-courses`, all of which the user may host (§3.4); show the server's message inline if
    one arrives anyway.
- Create form: title, description, max players, and a **required** course `<select>`. The
  submit button stays disabled until a course is chosen. When the list filter is set to a specific
  course, that course is the form's initial value; under "All courses" the form starts unselected.
  The two selects are **independent after that**: changing the filter never overwrites a course the
  user has already picked in an open form, and never clears a form. The form's course is a required
  field in its own right, not a view of the filter.
- Import JSON: a file picker plus the same required course select (prefilled from the filter on the
  same rule). Sends `FormData` with `file` and `course_id`, then navigates to the new game's
  question editor.
- Edit title/description/max players inline (`PUT /host/games/{id}`, body `HostGameUpdate` — it
  never carries `course_id`, §3.5).
- **Attach to course**: on rows with `course_id === null`, and **only when
  `getRole() === 'ADMIN'`**, a course `<select>` plus an Attach button calling
  `PUT /admin/games/{id}` with `{course_id}`. On success the row re-renders as attached **from the
  response body's `course_id` and `course_name`** — which is why §3.2 requires the server to expire
  the `course` relationship before returning; without it the row renders attached with a blank
  course name. A 409 (the stored value was not null, §3.2) is shown inline on the row — it should be
  unreachable from a control that only renders on unattached rows, but a stale list makes it
  possible.
- The course cell is **read-only** in every other case: for any non-admin, and for an ADMIN on a
  game that is already attached. No UI anywhere moves a game between courses (§3.5).
- Delete: rendered only when `getRole() === 'ADMIN'`, behind the existing confirm step, and
  calls `DELETE /admin/games/{id}`. Hosts cannot delete games (see §5, Alt 5).

**QuestionEditorPage (host, moved)**: behaves the same as today. The only change is the API
prefix: `/admin/games/...` becomes `/host/games/...`. The header also shows the game's course
name, and the back button goes to `/games`.

One behaviour change beyond the prefix: **when the initial load fails, the page renders only the
error and the back link.** A 403 already shows the server's message today — `api.ts` throws
`Error(detail)`, the page renders `{error && <p …>{error}</p>}`, and `questions` stays `[]` — but it
shows that message *inside the authoring shell*: an empty `<h2>` where the title would be, "No
questions yet. Add one above.", and live Add Question and Export JSON buttons. Track load success
separately from `loading` and suppress all three on failure, so a game the user cannot read never
presents a working editor. This, not the message, is what §8-12's matrix row is really asserting.

**CoursesPage (host, new, small)**: reads the shell's course list (§4.6), with one card per course
(name · semester) and a "Manage roster" button that goes to `/courses/:id/roster`. It is
read-only, because course creation stays an admin task.

**RosterPage (host, moved)**: same CSV upload, column-mapping wizard, and inline edit/deactivate
as today. The prefix changes from `/admin/courses/...` to `/host/courses/...`. A 403 response
renders "You don't have HOST access to this course" instead of a generic error.

**SessionsPage (host, new)**:
- `GET /host/sessions` with a status filter whose default is **Completed**. An ADMIN opening this
  page sees **every** host's sessions (§3.2), which overlaps the admin app's own SessionsPage; that
  is intended — the admin page keeps the Canvas-format export (§9), this one is the generic view.
  The options are
  **All / Completed / Abandoned** only, each passed straight through as `status=` (All omits the
  param). There is deliberately no "Active" option: `session_status` is an enum of four exact
  values with no `ACTIVE` member, so an "Active" tab would need a two-status alias on the
  endpoint — and live sessions are already listed, with Rejoin, on `/home`. This page is for
  finished sessions.
- Each row shows game title, course · semester, room code, date, and player count, keyed by
  `session_id`. The two fields the buttons below depend on are `status` and **`session_id`** (a
  `str`, not `id` and not an int) — see §3.2.
- **Download summary (HTML)** button: `api.download('/host/sessions/{session_id}/report')`. Enabled
  only for `status === 'COMPLETED'`.
- **Download scores (CSV)** button: `api.download('/game/sessions/{session_id}/export')`. Enabled
  only for `status === 'COMPLETED'`.
- Download errors are shown inline on the row.

**GameOverPage (host)**: add the same two download buttons next to "New Game". **No backend change
is needed for the session id.** `RoomInfoResponse` already returns `session_id`
(`backend/app/schemas/game.py`), and `GameLayout` already calls `GET /game/rooms/{code}` for the
game title — it just types the response as `{ game_title: string }` and throws the rest away.
Widen that type to include `session_id` and put it in `GameContext`; nothing else changes.

These buttons carry **no `COMPLETED` status gate**, unlike SessionsPage: reaching this screen means
the server emitted `game_over`, which is what sets the status. They do carry one other gate:
**both buttons are disabled while `sessionId` is null.** That fetch is deliberately non-fatal today
— `GameLayout` calls it `.then(data => setGameTitle(…)).catch(() => {})`, commented "non-fatal —
title stays blank if fetch fails" — so a failed or still-in-flight `GET /game/rooms/{code}` leaves
`sessionId` unset while the rest of the screen renders from the socket's `game_over` payload. Without
the gate the buttons would request `/host/sessions/null/report` at the end of a game the host just
ran. Do **not** make that fetch fatal to fix this; a blank title is a better failure than a dead
Game Over screen.

Note the reconnect gap recorded in
`host/src/pages/CLAUDE.md` — `sync_state` has no `COMPLETED` branch, so a host who refreshes here
loses the whole screen, buttons included. That is pre-existing and out of scope; SessionsPage is
the recovery path, which is exactly why Alt 8 puts the downloads in both places.

**Admin UserDetailPage**: the game-grant picker labels each game as "Title — Course", using the
new `course_name` on `GameResponse`. A grant for a game whose course the user has no HOST access
to is allowed, because the server stores it, but the row shows a yellow note: "No HOST access to
this game's course — grant has no effect until course access is granted." This makes the
intersection rule from §2 decision 5 visible to the admin.

**Admin CoursesPage**: the "Roster" button becomes an external link to
`{HOST_APP_URL}/courses/{id}/roster`.

### 4.6 A signed-in user with no HOST access

All three apps share one origin and one `localStorage.token` (§4.3), and the host app's
`RequireAuth` checks only that a token exists. So the host app's management shell is reachable by
two kinds of user it is not for: a `USER` with only PLAYER access to their courses, and a `GUEST`
who just finished a game (`game_service.authorise_player` treats `GUEST` as a real role, so guests
hold ordinary tokens). Neither is a security problem — every `/host/*` endpoint is gated
server-side — but without this section both land on four independently-empty pages with no
explanation.

**The two arrive through different branches, which is the thing to get right.** Only the
PLAYER-only `USER` gets `[]`. A `GUEST` never reaches this endpoint's body at all:
`require_user` ([common/dependencies.py](../backend/app/common/dependencies.py)) raises
`ForbiddenError("Authenticated account required")` for `role == "GUEST"`, so `/game/my-courses`
answers **403**. The empty state below is therefore the PLAYER-only user's; the guest's message
lives in the rejected branch. That 403 is unambiguous — the GUEST check is `require_user`'s only
`ForbiddenError` — so the shell can branch on the status alone.

`HostShell` loads `/game/my-courses` once and is the **only** caller of it in the host app. When it
returns `[]` *and* `getRole() !== 'ADMIN'`, the shell renders a single explanatory empty state in
place of the routed content:

> You don't have HOST access to any course. Ask an administrator to grant HOST access before
> creating games or managing a roster.

This replaces Games and Rosters, rather than letting each page render its own empty list. Three
deliberate exceptions:

- **`/home` and `/sessions` are never replaced.** Mechanically: the shell calls `useLocation()` and
  renders `<Outlet/>` regardless of the course list when the active path is **exactly** `/home` or
  `/sessions` (an equality check on `pathname`, not a prefix — neither has sub-routes, and the deep
  management routes `/games/:gameId/questions` and `/courses/:courseId/roster` are *not* exempt).

  **The exemption is scoped to the resolved-`[]` state only.** Both rejected branches below — 403 and
  anything-else — replace the routed content on *every* path, `/home` and `/sessions` included. The
  distinction is not arbitrary: `[]` means the user owns host data this shell can still show them
  (their own sessions, their own live rooms), whereas a rejection means the shell does not know what
  they own. A GUEST on `/home` therefore gets the guest message, not a Play screen — which is what
  §8-12's guest row asserts. Nothing is exempt from the in-flight state either, because that state
  renders the routed content anyway.

  Neither page is lifted out of the shell — that would be the obvious alternative and it is wrong,
  because the page would lose the nav and a revoked-access host would have no way to reach it. The
  nav always renders in every one of the four states below, so both stay one click away while
  Games and Rosters show the empty state.

  **Both exemptions rest on the same property**, and `/home`'s case is the stronger one.
  `GET /host/sessions` filters on `host_user_id`; `GET /game/my-active-sessions`
  ([routers/game.py](../backend/app/routers/game.py)) filters on `host_user_id` too, with no
  course-access predicate. So a host whose HOST access was revoked mid-term still owns both sets of
  data, and `/home` is where the active-session list and **Rejoin** live — replacing it would strand
  a session that is live on the projector right now, a worse outcome than hiding a CSV from last
  month. `/home` needs no new empty state for this: §4.5 already specifies its no-course rendering
  (disabled Quiz select, "Select a course first", no `my-games` request), which is exactly right for
  a user with zero HOST courses.

  **That same `host_user_id` filter deliberately excludes current co-hosts**: a TA with HOST on course A does not
  see a session the professor ran in course A, even though T4's H1/H2 wording ("the host can
  download … for a completed session") does not tie the download to who pressed Start. Two reasons
  for taking the narrower rule. First, a session row leads to a per-player score CSV, and spreading
  one instructor's grade data to every TA on the course is a worse default than making them ask.
  Second, `host_user_id == me` is a column predicate inside the existing query, whereas
  "me OR HOST on `session.course_id`" is a per-endpoint authorization check of exactly the kind
  `routers/CLAUDE.md` records as having already drifted twice. Widening it is a §9 follow-up, so the
  narrow rule is a decision, not an omission.
- **`/game/:code/*`** is outside the shell entirely and unaffected.
- **ADMIN never sees the state**, because `my-courses` has an explicit ADMIN branch returning every
  course (§3.4). The one exception is a database with zero courses, where an admin *should* be told
  something — so the role check above swaps in a second message for ADMIN: "No courses exist yet —
  create one in the admin console."

**The shell has four states, not one.** `my-courses` is a single request that five screens now
depend on, and the shell replaces routed content — so an unstated failure branch blanks the whole
management app rather than one page:

- **In flight** — render the nav and the routed content with an empty course list, and **not** the
  empty state above. Pages that need a course show their own "Select a course first" placeholder
  (§4.5), which is already their no-selection state. Rendering the empty state while loading would
  flash "You don't have HOST access to any course" on every slow fetch — the most alarming possible
  message to show a user who does in fact have access.
- **Rejected, 403** — the GUEST case above. Replace the routed content with "This is a guest
  account — sign in with your NetID or university account to host." and **no Retry button**: the
  request cannot succeed for this token, so offering a retry is a lie. `api.ts` throws
  `Error(detail)` and discards the status, so the shell's fetch needs the status — read it off the
  response in the shell rather than widening `api.ts` for one caller.

  **That costs a deliberate copy, so write it deliberately.** A raw `fetch` in `HostShell`
  re-implements three things `api.ts` already owns: the `/api` prefix, the `Authorization: Bearer`
  header, and the `{detail}`-or-`HTTP <status>` error parse. That is the copy-paste drift
  [`frontend/CLAUDE.md`](../frontend/CLAUDE.md) names as its first gotcha, so keep it to this one
  call, and take the token from **`getToken()`** — a raw `localStorage.getItem('token')` here would
  fail §8-1's own grep gate. The alternative, if a second caller ever needs a status, is one line in
  `apiFetch` attaching `res.status` to the thrown error; it is not worth it for one caller today.
- **Rejected, anything else** — replace the routed content with the thrown error's message and a
  **Retry** button that refetches. Keeping all three apart is the point: `[]` means "ask an
  administrator", 403 means "wrong kind of account", a 500 means "try again".
- **Resolved** — the behaviour specified above: `[]` plus non-ADMIN → the empty state (or the
  zero-courses message for ADMIN); otherwise the routed content with the courses in context.

§9 leaves 401 handling out of scope, so an expired token arrives here as **rejected-anything-else**
— the server's message plus Retry, not a redirect, and not the guest message (401 is not 403). That
is precisely why these branches have to be stated: the one request §9's exclusion makes five times
more visible is the one the shell owns.

**The shell owns the course list.** `HostShell` passes the loaded courses to its children through
`<Outlet context={{courses}}>` / `useOutletContext()`. HomePage, GamesPage, CoursesPage and
RosterPage read it from there and **do not fetch `/game/my-courses` themselves** — otherwise the
same list is fetched five times on every navigation, with five independent loading states. This is
the one piece of shared state the shell owns; everything else each page fetches for itself. The
refetch stays **private to the shell**: its only caller is the Retry button above. No page in §4.5
creates or changes a course (CoursesPage is read-only, course creation is admin-side), so no child
has anything to invalidate and an exported `reload()` would be dead code.

## 5. Alternatives considered

| # | Alternative | Why rejected |
|---|---|---|
| 1 | **Let HOST users log into the admin app** and hide admin-only nav items by role. | It does not restructure anything, which is what T4 asks for. It mixes two audiences in one app again, and it puts the "hiding" logic on the client, where it is easy to get wrong. The host app is where instructors already are. |
| 2 | **Keep the admin copies of Games/QuestionEditor/Roster and add ported copies to host.** | It duplicates about 1,600 lines (`QuestionEditorPage` alone is 788). Every new question type (T7) would then need editor changes in two places, on top of the four backend places the root `CLAUDE.md` already warns about. Drift is very likely. |
| 3 | **Shared package (`frontend/shared/`) imported by both apps**, with pages parameterised by API prefix. | This is the cleanest fix for duplication, but each app is built separately (`npm --prefix`) with its own `node_modules`. A shared folder needs Vite `resolve.alias` plus `dedupe` for React and react-router, tsconfig `paths`, Tailwind `content` globs in both apps, and checks that the Docker/nginx builds still work. That is a lot of build risk for a benefit Decision 1 already gets by keeping a single copy. We can revisit this if the player app needs to share editor code for T7 or T8. |
| 4 | **Reuse `/admin/*` endpoints for hosts** by relaxing `require_admin` to "admin or host of this resource". | It would blur the admin/host boundary that T4 asks us to draw. Every admin route would need its own resource-level check, which is easy to forget on one route. A separate `/host/*` router keeps the gating in one place, makes "is this route host-reachable?" clear from the path, and keeps the pre-existing admin tests unchanged. |
| 5 | **Let hosts delete games.** | `delete_game` also deletes `game_sessions` and `session_scores`, which is grade data, and T4 does not require it ("add, edit, delete, and reorder **questions**"). It stays admin-only. ADMIN sees the button in the host app. |
| 6 | **Make `games.course_id` NOT NULL** and backfill. | Existing tests, seed scripts, and smoke tests create games without a course. Requiring it would break them or force edits, and T5 forbids weakening tests. Nullable plus "unattached = admin-only" gives the same guarantee for every game a host can create. |
| 7 | **Course HOST alone grants access to all of that course's games** (drop `user_game_access` for non-admins). | It is simpler, but "granting game access" is an explicit admin task in T4/A1, so game grants have to mean something. The intersection rule keeps grants meaningful and makes H5 strict. |
| 8 | **Put the downloads only on GameOverPage.** | Hosts close the projector tab, and H1/H2 are for "a completed session", which can be days old. Both places get them. |
| 9 | **Drop §4.6's `pathname` exemptions: wrap only the four gated routes (`/games`, `/games/:gameId/questions`, `/courses`, `/courses/:courseId/roster`) in a shared guard element inside the shell's outlet**, so `/home` and `/sessions` are exempt by not being wrapped. | Genuinely cleaner on one axis — the equality-vs-prefix rule and its deep-route caveat disappear, and the nav still renders, so §15's objection to lifting `/sessions` out of the shell does not apply. Rejected on cost, not merit: the four states, the role gate and the course list all still have to live somewhere, so it moves complexity rather than removing it, and it restructures the one section §12/§14/§15/§16 have already converged on. Worth revisiting if a *fifth* route needs the same gate — at that point the guard pays for itself. |

## 6. Risks and self-critique

- **Intersection rule versus co-hosts.** With rule §2 decision 5, a TA with HOST on a course cannot run a
  quiz that another instructor created until an admin grants it. This is deliberate, but it will
  confuse users. The UserDetail note (§4.5) makes it visible. If the team finds this too strict,
  dropping the `user_game_access` check (Alt 7) is a single change in `assert_host_can_use_game`
  plus updated tests.
- **`/game/my-games` semantics change.** Specified in §3.3 — all three read paths share one rule,
  and the "listed ⇒ creatable" invariant is a required T5 test (§10). This was the single easiest
  thing in this design to implement wrongly: the endpoint row in §3.2 reads like a new query
  parameter, and the authorization change behind it is what actually matters.
- **Editing a game that already has completed sessions.** Questions can be edited or deleted
  after a session, which changes what the HTML report shows for that older session.
  Admin has this problem today too. It is out of scope, but worth noting.
- **`seed_demo.py` must attach its game to its course, or the README's first-run flow breaks.** The
  script creates the course and then the game through `POST /admin/games` **with no course**
  (`scripts/seed_demo.py::create_game`), so after §3.1 the demo game is unattached. Being an ADMIN is
  not enough to rescue it: §3.1's admin bypass makes the game hostable through the **API**, but the
  only UI that creates rooms is HomePage, and §4.5 changes it to request
  `/game/my-games?course_id={selected}` and nothing else. §3.3's `course_id` filter applies to the
  ADMIN branch too, so a `NULL` `course_id` is excluded from every request the page can make. A fresh
  clone → `seed_demo.py` → sign in as admin → pick "Demo Course" lands on §4.5's "No quizzes for this
  course yet" with no way to reach the demo game — and that clean-clone path is a submission
  checklist item ([instructions.md](../instructions.md)). **Fix: the script passes `course_id` when
  creating the game** (§8-13). §3.2 already makes the field optional on `POST /admin/games`, and
  `seed_demo.py` is not under `tests/`, so this changes no test and no contract.

  The rejected alternative is to let `?course_id=` return unattached games to an ADMIN. It would also
  work — `create_room` accepts an unattached game for an ADMIN, so "listed ⇒ creatable" survives — but
  it costs §3.3's one-rule-three-endpoints property and contradicts §10's "unattached absent in the
  second" row, to fix in a contract what a one-line script change fixes at the source.
- **Unattached games (`course_id = NULL`)** never appear for non-admin hosts. Existing
  production games (if any) would disappear from host pickers until an admin attaches them. The
  admin-side fix is the `PUT /admin/games/{id}` row in §3.2 (`course_id` settable only while null,
  409 otherwise) plus the ADMIN-only "Attach to course" select on unattached rows in GamesPage.
  `GameUpdate` is `extra="forbid"`, so the schema field is not optional polish — without it the
  request 422s.
- **Dev-mode cross-port links** do not carry the token (§4.3). This is a known limitation and is
  not a bug.
- **JWT role decode** is display-only. If someone later uses `getRole()` for a real decision,
  that is a security bug. The function's comment must say so.
- **Report rendering gap**: `report_service` does not render `multi_select` (see
  `services/CLAUDE.md`). H1 exposes this report to hosts, so they will see it. Fixing it is
  backend work and is tracked separately. It does not block this design.

## 7. Files touched (frontend)

**Host app: `frontend/host/src/`**

| File | Change |
|---|---|
| `App.tsx` | Add `HostShell` layout route wrapping `/home`, `/games`, `/games/:gameId/questions`, `/courses`, `/courses/:courseId/roster`, `/sessions`; use `getToken()` in `RequireAuth` |
| `lib/api.ts` | Add `put`, `patch`, `postForm`, `download` (port from `admin/src/lib/api.ts`) |
| `lib/auth.ts` | **New**: `getToken`, `setToken`, `clearToken`, `getRole` (display-only) |
| `lib/links.ts` | **New**: `ADMIN_APP_URL` |
| `components/HostShell.tsx` | **New**: top nav, the sole `/game/my-courses` fetch, the §4.6 loading / 403 (no Retry) / other-error (with Retry) / empty states, the `/home` + `/sessions` path exemptions, and `<Outlet context={{courses}}/>` |
| `pages/HomePage.tsx` | Filter games by course; take courses from outlet context instead of fetching them; **move the single-course auto-select out of the mount effect into one keyed on the context list** (§4.5); update the load-failure message, which now covers active sessions only; remove its own Sign Out button (moves to the shell); use `getToken`/`clearToken`; **drop the full-screen centring** — the page's root is `min-h-screen flex flex-col items-center justify-center` today, which inside the shell gives a page taller than the viewport with the card pushed below the nav. Shell-relative padding instead. §4.5's "same layout" means the same *content*, not the same splash framing |
| `pages/LoginPage.tsx` | `setToken()` instead of raw `localStorage` |
| `pages/manage/GamesPage.tsx` | **New** (moved from admin; course select; import with course; admin-only delete) |
| `pages/manage/QuestionEditorPage.tsx` | **New** (moved from admin; `/host` prefix; course in header) |
| `pages/manage/CoursesPage.tsx` | **New** (my HOST courses → roster) |
| `pages/manage/RosterPage.tsx` | **New** (moved from admin; `/host` prefix; 403 message) |
| `pages/manage/SessionsPage.tsx` | **New** (my sessions; HTML + CSV download) |
| `pages/game/GameLayout.tsx` | Use `getToken()`; widen the `/game/rooms/{code}` response type and keep `sessionId` in `GameContextValue` (declared in this file) |
| `pages/game/GameOverPage.tsx` | Add the two download buttons |
| `pages/CLAUDE.md`, `components/CLAUDE.md`, `lib/CLAUDE.md` | Update for the new pages, shell, and auth helper (context-sync rule) |

**Admin app: `frontend/admin/src/`**

| File | Change |
|---|---|
| `App.tsx` | Regroup the sidebar (Administration / Host tools); remove `/games`, `/games/:gameId/questions`, `/courses/:courseId/roster` routes and replace them with `ExternalRedirect`; catch-all → `/users` |
| `lib/links.ts` | **New**: `HOST_APP_URL`, `PLAYER_APP_URL` |
| `components/ExternalRedirect.tsx` | **New**: `window.location.replace(url)` in an effect |
| `pages/LoginPage.tsx` | Post-login navigate to `/users` instead of `/courses` |
| `pages/CoursesPage.tsx` | "Roster" button → external link to the host roster |
| `pages/UserDetailPage.tsx` | Show the course on the game-grant picker and grant rows; add the no-HOST-course warning |
| `pages/GamesPage.tsx` | **Delete** (moved to host) |
| `pages/QuestionEditorPage.tsx` | **Delete** (moved to host) |
| `pages/RosterPage.tsx` | **Delete** (moved to host) |
| `pages/SessionsPage.tsx` | Unchanged |
| `pages/CLAUDE.md`, `components/CLAUDE.md`, `lib/CLAUDE.md` | Create or update (context-sync rule) |

**Response interfaces are declared per page.** The admin app has no `types/` directory — each page
declares its own response shapes inline (`admin/src/pages/CLAUDE.md`), and the three moved pages
carry that habit into the host app. So `course_id` / `course_name` must be added to the local
`Game` interface in the moved `GamesPage` **and** `QuestionEditorPage` (which fetches the game for
its header), and to `UserDetailPage`'s game list. The §7 rows above say "course in header" and
"show the course on the game-grant picker"; this is the edit that makes them compile.

**Player app**: no changes. H5 is enforced server-side in `create_room` plus the existing roster
check.

## 8. Implementation steps

Order: the backend contract (§3) lands first, or in parallel behind the same branch, so each
frontend step can be checked against a running stack. Each step below should end with
`npm run build` passing for the affected app.

All of T4 ships as **one merge request** — T1 asks for one branch and MR per task, and `main` never
sits in a half-moved state where the admin app has deleted its pages and the host app has not yet
gained them. The cost is a diff spanning the backend, two frontends and the §10 tests for one
non-author reviewer (T2), so **commit granularity is what makes it reviewable.** Commit in these
groups, in order: **1–2** (host plumbing, then shell and routing), **3** (the page copy, *no other
change*), **4** (re-point APIs), **5–7** (course attachment, roster/courses polish, sessions),
**8–9** (GameOver downloads, Home course filter), **10** (admin restructure), **11** (context
sync). Step 3 must be its own commit with nothing else in it — that is the only thing that keeps
~1,600 moved lines readable as a move rather than as 1,600 new lines.

1. **Host plumbing.** Add `lib/auth.ts` and `lib/links.ts`. Extend `lib/api.ts` with `put`,
   `patch`, `postForm`, and `download`, ported from admin. Replace every
   `localStorage.getItem/setItem/removeItem('token')` in the host app with the helpers
   (`grep -rn "localStorage" frontend/host/src` should then find hits only in `lib/auth.ts`).

   **"Ported", not copied verbatim** — admin's `api.ts` reads `localStorage.getItem('token')` in
   **three** places, because `downloadFetch` and `postForm` each call `fetch` directly rather than
   going through `apiFetch` (deliberately: `download` needs the raw response for
   `Content-Disposition` and the blob, and `postForm` must *not* send
   `Content-Type: application/json`). Keep both bypasses, but route all three token reads through
   `getToken()`, or the grep check above fails on the file you just added. Keep the bypasses
   themselves: the host's `apiFetch` sets `'Content-Type': 'application/json'` unconditionally, so a
   `postForm` built on top of it would break multipart upload.
2. **HostShell + routing.** Create `components/HostShell.tsx` (nav: Play, Games, Rosters,
   Sessions, [Admin console], Sign out). It fetches `/game/my-courses` once, renders all four §4.6
   states (loading, 403-without-Retry, other-error-with-Retry, and the role-gated empty states),
   exempts `/home` and `/sessions` from replacement by `pathname` equality, and exposes the list via
   `<Outlet context={{courses}}>` — courses only, no `reload`. In `App.tsx`, wrap the management routes in
   `<RequireAuth><HostShell/></RequireAuth>` as a layout route, and leave `/game/:code/*`
   outside it. Check that `/home` still works and that the game screens show no nav.
3. **Move pages.** `git mv` is not possible across apps without losing the diff, so copy
   `admin/src/pages/{GamesPage,QuestionEditorPage,RosterPage}.tsx` to
   `host/src/pages/manage/` in **one commit with no edits**. Fix the import paths
   (`../lib` → `../../lib`, `../components` → `../../components`) in the next commit. This keeps
   the history readable.
4. **Re-point APIs.** In the moved pages, replace the `/admin/games` → `/host/games` and
   `/admin/courses` → `/host/courses` prefixes. Fix internal `navigate()` targets (they
   already use `/games/...` and `/courses`, which match the host routes).
5. **Course attachment in GamesPage.** Take the course list from the shell's outlet context (§4.6) —
   **do not fetch `/game/my-courses` here**; the shell is its sole caller. Add the required course
   select to the create and import forms and send `course_id`. Add the course column and the filter
   `<select>` defaulting to "All courses", with the no-param / `?course_id=` request rule from §4.5.
   Make delete ADMIN-only and point it at `/admin/games/{id}`. Add "Attach to course" on unattached
   rows via `PUT /admin/games/{id}`, shown to ADMIN only.
6. **CoursesPage + RosterPage polish.** Build the small CoursesPage. Map a 403 on RosterPage to
   the friendly message.
7. **SessionsPage.** Build the list with a status filter and both download buttons, gated on
   `COMPLETED`.
8. **GameOverPage downloads.** Widen `GameLayout`'s **existing** `GET /game/rooms/{code}` call from
   `api.get<{ game_title: string }>` to include `session_id`, expose it on `GameContextValue` as
   `sessionId`, and add the two buttons. **No backend change** — `RoomInfoResponse` already returns
   `session_id`, and the call already runs and discards it (§4.5, §11). **Do not look for the session
   id on a socket payload**: it is in neither `sync_state` nor `game_over`, and is not being added to
   either. `GameContextValue` is declared in `pages/game/GameLayout.tsx`, not in `types/game.ts`.
9. **HomePage course filter.** Fetch games per selected course, clear a stale `gameId`, handle
   the empty state, and remove the local Sign Out button.
10. **Admin restructure.** Add `lib/links.ts` and `ExternalRedirect`. Regroup the sidebar. Swap
    the removed routes for redirects. Change the catch-all and post-login route to `/users`.
    Change CoursesPage's Roster button to an external link. Add the course labels and warning
    to UserDetailPage. Delete the three moved pages.
11. **Context sync.** Update or create the `CLAUDE.md` files listed in §7.
12. **Manual verification matrix** (Docker stack, same origin), run before writing the §10 tests:
    - USER with HOST on course A only: sees only course A in Rosters and Games. Creating a game
      without a course is impossible in the UI. Opening `/games/{courseB-game}/questions`
      directly shows the server's 403 message **and no editor UI** — no title, no "No questions yet",
      no Add Question, no Export (§4.5). Session downloads work for their own completed
      session, and someone else's session id returns 403.
    - ADMIN: the admin app lands on Users, and the Host tools links open the host app already
      signed in. The host app shows the Admin console link, Delete buttons, and unattached
      games.
    - Room creation with a course-B game in course A fails with the server's 403 message on
      Home.
    - A player on course A's roster cannot join a session for course B (existing behaviour,
      re-checked).
    - GameOverPage with `GET /game/rooms/{code}` failing (block it in devtools): the screen still
      renders from `game_over`, the title is blank, and **both download buttons are disabled** rather
      than requesting `/host/sessions/null/report` (§4.5).
    - A **guest** token (finish a player game, then open `/host/home` in the same browser): the
      shell shows the guest message with **no Retry button**, not "ask an administrator" and not a
      raw `Authenticated account required` (§4.6).
    - A host **mid-game** whose HOST access is then revoked (delete their `user_course_access` row
      while a LOBBY session is open): `/home` still lists the session with a working **Rejoin**, and
      `/sessions` still lists their completed ones, while Games and Rosters show the empty state
      (§4.6).
    - ADMIN attaches an unattached game on GamesPage: the row shows the **course name**, not a blank
      cell, without a manual page refresh (§3.3's closing paragraph). Creating a game with a course
      through the host form likewise returns a row with its course name, rather than a 500.
    - **The README path, from a clean database**: run `scripts/seed_demo.py`, sign in as the admin
      credentials it prints, and on `/home` select "Demo Course" — the demo game **is** in the Quiz
      select and a room can be created (§6, step 13). This is the one matrix row that fails if step 13
      is skipped, and it fails silently, as an empty select rather than an error.
13. **Seed script.** In `scripts/seed_demo.py::create_game`, pass the `course_id` returned by
    `create_course` in the `POST /api/admin/games` body, so the demo game is attached to "Demo
    Course" (§6). Do this alongside the step-1 backend work — it is listed last only to keep the
    existing `§8-12` references to the verification matrix stable. Nothing else in the script
    changes, and no test touches it.

## 9. Out of scope

- Canvas-format export for hosts. Hosts get the raw per-player CSV that H2 asks for. The Canvas
  export stays on the admin Sessions page.
- Merging guest players into real accounts from the host app. `/game/sessions/{id}/guests` and
  `merge-guest` exist, but T4 does not ask for them.
- Unifying `api.ts`/`utils.ts`/`ui/*` across the three apps (see Alt 3).
- Fixing the `multi_select` gap in the HTML report (backend; see §6).
- The host-reconnect `COMPLETED` gap in `sync_state` (pre-existing; see §4.5, GameOverPage).
- **401 handling.** Neither `api.ts` redirects on an expired token — it throws on whatever page is
  open (`host/src/lib/CLAUDE.md`). This change takes that from one host screen to five, so it will
  be more visible, but it is pre-existing and shared by all three apps. Not fixed here; listed so
  nobody detours into it mid-implementation.
- **Co-host access to another host's session downloads.** §4.6 fixes `GET /host/sessions` on
  `host_user_id == me`, so a course co-host cannot download a session they did not start. Widening it
  to "me OR HOST on `session.course_id`" is a one-line query change plus §10 rows; it is deferred for
  the two reasons §4.6 gives (score-data exposure, and the per-endpoint auth check
  `routers/CLAUDE.md` flags). Listed so the narrower rule reads as a decision.
*(Attaching `seed_demo.py`'s game to its course was listed here through §16. It is **in scope** as of
§17 — it is the difference between the README's first-run flow working and not. See §6 and §8-13.)*

## 10. Integration tests (T5 scope for this feature)

T4's deliverables include integration tests, so the cases live here rather than in a separate
document. They go in `tests/integration/`, against the live Docker stack, using the existing
fixtures. Existing tests are not modified (T5), which is the whole reason `course_id` is nullable.

Fixtures needed: an ADMIN, a `host_a` with HOST on course A only, a `host_b` with HOST on course B,
a game attached to A and granted to `host_a`, a game attached to B, and one unattached game.

**Scope and cleanup are part of the spec, because the suite's one worked example is the wrong shape
to copy here.** [`tests/integration/conftest.py`](../tests/integration/conftest.py)::`game_setup` is
**function-scoped**: it creates a course *and* a game per test, deletes the game on teardown, and
leaves the course behind — its own comment says "Courses have no cascade and no DELETE endpoint;
leave them as inert records", which §12 confirmed (there is no `DELETE /admin/courses/{id}`). Copying
that shape for T4 means every one of the ~25 rows below leaks two courses, two users and three games,
and the rows that create rooms leak LOBBY sessions that `create_room` counts against `MAX_ROOMS`
([`game_service.py`](../backend/app/services/game_service.py) scans `room:*` and counts
LOBBY/IN_PROGRESS). [instructions.md](../instructions.md)'s T5 names this failure in advance —
"check whether every deletion path cleans up what its matching creation path set up, in both
datastores" — and it arrives as unrelated-looking resource limits, long after the test that caused it.

So:

- One **session-scoped** `t4_env` fixture builds course A, course B, `host_a`, `host_b`, the
  A-attached-and-granted game, the B-attached game and the unattached game **once**, and every row
  below reads from it.
- A row that **mutates** shared state takes its own function-scoped resource instead: question
  CRUD and reorder (H4), the roster upload and `PATCH` (H3), and the attach-to-course rows, which
  consume the unattached game's one-way NULL → set transition and so need a fresh game each.
- Teardown deletes, in this order: every session the test created
  (`DELETE /game/sessions/{id}` — this is the Redis half, and the only thing that frees a room slot),
  then every game (`DELETE /admin/games/{id}`, which the route's manual pre-delete cascades to
  sessions and scores), then both users (`DELETE /admin/users/{id}`).
- The two courses are knowingly left as inert records, exactly as `game_setup` does — **which is the
  reason they are created once per session rather than once per test.** Name them distinctly
  (`T4 Course A`/`T4 Course B` plus a run tag) so a leaked row is identifiable rather than anonymous.

| Area | Case | Expect |
|---|---|---|
| Visibility | `host_a` `GET /game/my-games` | only A's granted game — no unattached game, no B game |
| Visibility | **listed ⇒ creatable**: for every game `my-games` returns, `POST /game/rooms` with that game and its own `course_id` | 201 for each |
| Visibility | `host_a` `GET /host/games?course_id={B}` | 403 (no HOST on B) |
| Visibility | `host_a` `GET /host/games?course_id={nonexistent}` | **403**, not 404 — `assert_host_can_use_course` checks existence only for ADMIN (§3.2) |
| Visibility | ADMIN `GET /host/games?course_id={nonexistent}` | 404 |
| Visibility | ADMIN `GET /host/games` vs `?course_id={A}` | unattached game present in the first, absent in the second |
| Access | `host_a` HOST on A but **no** `user_game_access` row for an A game → `POST /game/rooms` | 403 (the intersection rule, §2 decision 5) |
| Access | a USER with PLAYER-only access to course A: `GET /game/my-courses`, then `GET /host/games?course_id={A}` | `[]` (PLAYER is not HOST), then 403 — the §4.6 empty state |
| H5 | `host_a` `POST /game/rooms` with a B-attached game and `course_id = A` | 403 |
| H5 | any host, `POST /game/rooms` with the unattached game | 403; ADMIN succeeds |
| H4 | `host_a` full question CRUD + reorder on A's game via `/host/games/{id}/questions*` | 200/204, order persisted |
| H4 | `host_a` same calls against B's game | 403 |
| H4 | `host_a` `PUT /host/games/{id}` with `course_id` in the body | **422** (`HostGameUpdate` is `extra="forbid"`, §3.5), and the stored `course_id` is unchanged |
| H4 | `POST /host/games` | 201 **and** a `user_game_access` row exists for the creator **and the response body carries the course's `course_name`** — not null, and not a 500 from `MissingGreenlet` (§3.3) |
| H4 | `POST /admin/games` with `course_id` | 201 and **no** `user_game_access` row (§3.3); `course_name` present in the body |
| H4 | `POST /admin/games` with a `course_id` that does not exist | **404**, not 500 (§3.2) |
| H4 | ADMIN `PUT /admin/games/{id}` setting `course_id` on an unattached game, then changing it again | 200, then 409. The **200's body carries the new `course_name`**, not the stale null the loaded relationship holds (§3.3) |
| H3 | `host_a` roster GET / CSV upload / `PATCH …/roster/{rid}` on A | 200; a netid missing from the upload is deactivated |
| H3 | `host_a` same on B; and `PATCH` with a `rid` belonging to another course | 403 / 404 |
| H1/H2 | `host_a` `GET /host/sessions/{sid}/report` and `GET /game/sessions/{sid}/export` for their own completed session | 200, `Content-Disposition` with a **quoted** filename (the frontend's regex needs it) |
| H1/H2 | `host_a` same calls for `host_b`'s session | 403 |
| Sessions | `host_a` `GET /host/sessions` | only own sessions; ADMIN sees all; `status=COMPLETED` filters correctly; each row carries `session_id` and `status` (§3.2) |
| Sessions | the extracted row builder (§3.3-6) called from `/admin/sessions` and `/host/sessions` for the same session | byte-identical row, so the admin page's behaviour is unchanged by the extraction |
| Access | ADMIN `GET /game/my-courses` with no explicit `user_course_access` rows | every course, each with `"role": "HOST"` (§3.4) — the admin is not shown §4.6's empty state |
| Sessions | a host whose HOST access to a course was revoked, `GET /host/sessions` for a session they ran | 200 and the session is still listed (§4.6's `/sessions` exemption) |
| Access | the same revoked host, `GET /game/my-active-sessions` with a LOBBY session open | 200 and the session is still listed — the endpoint filters on `host_user_id` with no course predicate, which is what §4.6's `/home` exemption rests on |
| Access | a **GUEST** token, `GET /game/my-courses` | **403** `Authenticated account required` — not `[]`. This is the branch §4.6's guest message renders from (§4.6) |
| Regression | the existing `/admin/*` game and roster suites | unchanged and passing |

## 11. Goldfish-test revisions (2026-10-02)

A fresh session read §1–§9 with only the context hierarchy for company, and found eight points
where it would have had to guess. Each was checked against the code before being written up here.

| Finding | Was | Now |
|---|---|---|
| `/game/my-games` authorization | §3.2 read as "add a filter"; §6 required the intersection rule. `routers/game.py::my_games` joins `user_game_access` alone, so following §3.2 would have shipped the exact bug §6 warned about | **§3.3**: one visibility rule, with pseudocode, shared by all three read paths |
| "Attach to course" | Required by §6/§8-5 with no endpoint in §3.2, and `GameUpdate` is `extra="forbid"` → 422, not a silent no-op | **§3.2** row for `PUT /admin/games/{id}`, 409 on re-attach; schema field called out in §3 and §6 |
| SessionsPage "Active" filter | Four options against an endpoint taking one exact status; `session_status` has no `ACTIVE` member | **§4.5**: All / Completed / Abandoned. Live sessions stay on `/home` |
| GameOverPage session id | "add `session_id` to `GET /game/rooms/{code}` if it is missing" — it is already there; `GameLayout` just discards it | **§4.5**: widen the response type, store it in `GameContext`. No backend change. Status gate explicitly dropped |
| Auto-grant on `/admin/games` | Unstated | **§3.3**: host routes auto-grant, admin routes do not, with the reason |
| `?course_id=` for ADMIN | Ambiguous whether it filters ADMIN, and whether unattached games survive the filter | **§3.2**: filters for every role; unattached only with no filter |
| `ExternalRedirect` | "to the matching host-app URL" — silent on route params | **§4.2**: builder over `useParams()`, with the three call sites |
| HomePage before a course is picked | Only the course-selected case was described, while the page fetches `my-games` unconditionally today | **§4.5**: disabled Quiz select, no request until a course is chosen, `gameId` cleared on change |

Also added: **§10**, the T5 cases for this feature — §8-12 referred to "the T5 tests" that no
document listed. Confirmed sound and left alone: `api.download` throws `Error(detail)` on non-2xx,
so the inline row errors and the RosterPage 403 message work from the ported helper;
`nginx.dev.conf` already has `try_files $uri $uri/ /host/index.html`, so the new deep host routes
need no nginx change; and A1/A2 plus H1–H5 are all covered by §4.

Still true and worth repeating at the T11 review: the admin→host links depend on the shared-origin
token (§4.3), so **A2 is only demonstrable in the nginx build**, not under `npm run dev`.

## 12. Design-review revisions (2026-10-02, second pass)

A second design pass re-read §1–§11 and checked every concrete claim against the code. Seven points
needed changing; the rest held as written.

| Finding | Was | Now |
|---|---|---|
| `?course_id=` gate | §3.2 described a filter, §10 tested for 403 — an implementer following §3.2 fails §10 | **§3.2/§3.3**: `assert_host_can_use_course` runs when the param is present; `my-games` stays filter-only |
| `course_name` serialisation | "add `course_id`, `course_name` to `GameResponse`" — but `Game` has no `course` relationship, and `from_attributes` would lazy-load after the await scope closed (`MissingGreenlet`) | **§3.3**: `course` relationship with `lazy="selectin"`, `course_name` property, spelled out in the file list |
| Course in the import bundle | `GameCreate` gains `course_id` *and* the form field takes one, with no precedence stated | **§3.2**: form field only; `import_game` pops `course_id` from `game_data`; bundle stays v1; T6 rationale recorded |
| Export bundle duplication | the shared-logic rule named question CRUD, reorder, roster and import | **§3.3**: the export bundle builder joins that list |
| Non-host users | unspecified — PLAYER-only and GUEST tokens reach the shell and see four empty pages | **new §4.6**, plus a §10 row |
| Dev-mode A2 caveat | documented in §4.3 and a `CLAUDE.md` only | **§4.2**: muted "open the host app" sub-label in the sidebar |
| Review scope | §7's 23 frontend files, §3.3's backend files and §10's tests presented as one undifferentiated unit | **§8**: single MR confirmed, with seven named commit groups and step 3 isolated |

Confirmed against the code and left unchanged: `RoomInfoResponse.session_id` is already present, so
§4.5's GameOverPage plan needs no backend work; `GET /game/sessions/{id}/export` already gates on
session-host-or-ADMIN, so H2 needs no new gate; `GameUpdate` and `GameCreate` are both
`extra="forbid"`, as §3 and §6 say; `my_games` really does join `user_game_access` alone, which is
what makes §3.3 a behaviour change rather than a new filter; `session_status` really has only
`LOBBY`/`IN_PROGRESS`/`COMPLETED`/`ABANDONED`, which is what §4.5's three-option filter rests on;
and there is **no** `DELETE /admin/courses/{id}` route, so `games.course_id` needs no `ondelete`
policy — a course is never deleted out from under a game.

## 13. Goldfish-test revisions (2026-10-02, second Goldfish pass)

The §3 header asked for the Goldfish to be re-run over §3–§4 after §12's changes. A fresh session
read §1–§12 with only the context hierarchy for company and found ten points it would have had to
guess at. Four would have changed code; the other six were single unstated decisions. Each claim
below was checked against the named file before being written up.

| Finding | Was | Now |
|---|---|---|
| `GET /game/my-courses` semantics | Load-bearing for five screens (§4.1, §4.5, §4.6) but stated only in a §10 *test expectation*. If it were not HOST-filtered, §3.3's "a legitimate client never sends a course the user cannot host" would be false and every course pick would 403 | **new §3.4**: HOST-filtered for non-admins, all courses for ADMIN, verified in `routers/game.py::my_courses`; no client-side filter anywhere |
| §4.6's ADMIN carve-out | "An ADMIN always has courses through `assert_host_can_use_course`'s admin bypass" — a non-sequitur: `my-courses` is a list endpoint, not a gate. The conclusion was right, the reason was wrong, and an implementer trusting the reason could have left an ungranted admin locked out of Games/Rosters | **§3.4 + §4.6**: the real reason is `my_courses`' own ADMIN branch; the empty state is explicitly role-gated, with a second message for the zero-courses case |
| `course_id` on `PUT /host/games/{id}` | §3.2 said "not editable"; §10 accepted "field ignored **or** 422". `GameUpdate` has no `course_id` today and `update_game` applies fields with independent `if` blocks, so a host route reusing the grown schema would silently apply it — handing hosts the reassignment power the admin 409 guards | **new §3.5**: a separate `HostGameUpdate` without the field, so `extra="forbid"` returns 422. §10 asserts that one outcome |
| `role` JWT claim | §4.4 asserted it without a citation, unlike every other concrete claim in §3–§4. If absent or renamed, `getRole()` returns `null` and the Admin console link and Delete button never render for anyone | **§4.4**: cited to `auth_service.py::create_access_token`, which sets `"role": role` |
| Who fetches `/game/my-courses` | Shell, Home, Games, Courses and Roster each needed it; ownership unstated → five fetches and five loading states | **§4.6 + §7**: the shell is the sole caller and passes the list down via `<Outlet context>` |
| `create_room`'s mismatch check | "rejects a game whose `course_id` … does not match" — role-blind, so it also binds ADMIN, which reads as a conflict with A2 | **§3.1**: stated as deliberate, with the roster-scoping reason and why A2 still holds |
| ADMIN on host `/sessions` | §3.2 gave ADMIN every host's sessions, duplicating the admin app's page, with no note | **§4.5**: confirmed intended; the admin page keeps the Canvas export, this one is the generic view |
| Revoked HOST access | §4.6's empty state replaced `/sessions` too, hiding a user's own completed-session downloads — their grade data | **§4.6**: `/sessions` is exempt (it filters on `host_user_id`, not course access), plus a §10 row |
| `seed_demo.py` after the change | §3.1 correctly said the script keeps working at the API level, but not that its demo game becomes admin-only hostable — a README-path behaviour change | **§6**: recorded, with the verification that the script signs in as ADMIN, so the documented flow is unaffected; attaching a course noted as an optional follow-up in §9 |
| 401 handling | Pre-existing and noted only in `host/src/lib/CLAUDE.md`; this change takes it from one host screen to five | **§9**: explicitly out of scope, so nobody detours into it mid-implementation |

Confirmed sound and left alone: the host and admin `ui/` primitives are byte-identical
(`admin/src/components/CLAUDE.md`, verified by diff), so the §8-3 page move needs no restyling;
`api.download`'s `filename="([^"]+)"` regex is exactly why §10 asserts a **quoted**
`Content-Disposition`; and `lazy="selectin"` on `Game.course` is the right call given
`models/CLAUDE.md`'s `MissingGreenlet` warning about ORM relationships inside async handlers, at the
accepted cost of one extra SELECT on every `Game` load — including the websocket gateway's.

**Status: ready to implement.** §3.4 and §3.5 are the two new contracts to read before starting;
everything else above is a clarification to a section that already existed.

## 14. Design-review revisions (2026-10-02, third pass)

A third review re-read §1–§13 looking specifically for places where a §8 step or a §10/§8-12
assertion instructs something §3–§4 does not specify — the failure mode that produced three of §13's
ten findings. Ten points needed changing. Two were outright internal contradictions: an implementer
following §4.5 would have built the opposite of §3.2/§6/§8-5, and one following §8-8 would have hunted
for a field that exists on no socket payload. Three were specified-but-dead work. Every claim was
checked against the named file first.

| Finding | Was | Now |
|---|---|---|
| "Attach to course" | §4.5 said "the course is shown but is read-only"; §3.2's `PUT /admin/games/{id}` row, §6 and §8-5 all required an ADMIN-only attach control. §4.5 is the section a page gets built from, and `admin/src/pages/GamesPage.tsx` mentions `course` nowhere today, so the contradiction decides real work | **§4.5**: the ADMIN-only attach `<select>` on `course_id === null` rows, with the inline 409; "read-only" scoped to non-admins and to already-attached games |
| GameOverPage session id | §8-8 said "from `sync_state` or `game_over`, falling back to `GET /game/rooms/{code}`", reopening what §4.5/§11 closed. Verified: `types/game.ts` carries no session id on **any** payload, and `GameLayout.tsx` already calls `/game/rooms/{code}` typed as `{game_title}` | **§8-8**: widen that existing call's type, full stop, with an explicit "do not look on a socket payload". §7's `types/game.ts` row **deleted** — `GameContextValue` is declared in `GameLayout.tsx`, so the row described work that exists nowhere |
| HostShell loading / failure | §4.6 specified `courses === []` precisely and said nothing about in-flight or rejected. Because the shell replaces routed content, one 500 or expired token blanks all five management screens, and a slow fetch flashes "You don't have HOST access" at a user who has it | **§4.6**: three named states — nav + routed content while loading (never the empty state), error + **Retry** on rejection, the existing behaviour on resolve. Cross-referenced to §9's 401 exclusion, which is what makes the error branch the visible one |
| `GET /host/sessions` and co-hosts | §3.2 filtered non-admins on `host_user_id == me`; §4.6 justified the revoked-access case but took the co-host exclusion silently, against T4's looser H1/H2 wording | **§4.6**: rule kept, with both reasons stated (a session row leads to a per-player score CSV; the alternative is the per-endpoint auth check `routers/CLAUDE.md` flags). Widening it is now a named **§9** follow-up |
| GamesPage course filter | "grouped or filtered by a course `<select>`" left the choice *and* the default open, while §3.3 makes `?course_id=` a gate — so the default decided whether the page's first request can 403 | **§4.5**: a filter, defaulting to "All courses" → unfiltered `GET /host/games` (also the only shape that shows ADMIN unattached games); a course adds the gated param. Create/import prefill from the filter but stay independent required fields |
| `reload()` in outlet context | §4.6 and §7 passed it down; no page in §4.5 creates or changes a course, so it was dead | **Dropped** from both. `<Outlet context={{courses}}>`; the refetch stays private to the shell, where the new Retry button is its only caller |
| Multipart roster route | §3.2 listed both `POST …/roster` (multipart) and `…/roster/import`. Verified: admin `RosterPage` calls only `/roster`, `/roster/import` and `/roster/{id}`, and `grep -rn roster tests scripts` is empty — the multipart path has no consumer at all | **§3.2**: row reduced to `…/roster/import`, with a note not to build the multipart route for parity |
| `POST /admin/games` after §4.2 | §3.3's auto-grant paragraph read as a live admin flow, but §4.2 deletes the admin `/games` route and an admin creating through host GamesPage takes the auto-granting path | **§3.3**: stated to have no UI caller — kept for scripts, tests and §10 — so "invisible until granted" describes the script/API path only |
| QuestionEditorPage 403 | §8-12 asserted "a 403 message, not data" while §4.5 said only "behaves the same as today". The message in fact already works (`api.ts` throws `Error(detail)`; the page renders it), but it renders inside the authoring shell — blank title, "No questions yet. Add one above.", live Add Question and Export | **§4.5**: suppress the title block, placeholder and action buttons when the load rejected. **§8-12** amended to assert that shape, since the message alone already passed |
| §8-5 vs §4.6 on who fetches courses | Found while applying the above: step 5 opened "Load `/game/my-courses` alongside `/host/games`", which is the five-fetch duplication §4.6 and §13 exist to prevent | **§8-5**: take the list from outlet context; the shell is the sole caller. §8-2 also now names all three shell states |

Checked and left alone: §3.4, §3.5, §3.3's visibility pseudocode, the `lazy="selectin"` decision and
every §10 row other than the ones above. Two of the nine reported findings turned out milder or worse
than first described, and are recorded that way in the table rather than as written up — the 403
message already renders, and the `types/game.ts` row was not merely redundant but described
non-existent work.

**The pattern worth naming for T11.** Three of these ten (attach, session id, the editor 403) and
three of §13's are the same defect: §8 or the §8-12 matrix asserts a behaviour that §3–§4 never
specified, so the implementation section and the verification section disagree with the section a
page is actually built from. A useful check before the next spec is declared ready: walk every §8 step
and every matrix row and name the §3/§4 sentence it rests on.

## 15. Goldfish-test revisions (2026-10-02, third Goldfish pass)

A third fresh session read §1–§14 with only the context hierarchy for company and found seven points
it would have had to guess at. One changes shipped behaviour (the GameOver buttons), one changes
structure (the sixth extraction), and five are contract text that was wrong or incomplete by a
sentence. Every claim was checked against the named file first.

| Finding | Was | Now |
|---|---|---|
| `GET /host/sessions` row builder | §3.2 said it "returns `AdminSessionItem` unchanged", which reads as if there is nothing to build, and §3.3's extract-don't-copy list had five entries without it. Verified: `AdminSessionItem` is `ConfigDict(from_attributes=False)` and `admin.list_sessions` hand-assembles each row in a ~40-line loop (three `db.get`s and a `count` **per session**) returning `list[dict]`. It is the largest of the six copies, and `routers/CLAUDE.md` already records two places this exact pattern drifted | **§3.3**: the list is now numbered and has six entries, with the extracted signature `(db, status, host_user_id)` — admin passes `None`, host passes `me` for non-admins. **§3.2** states the `from_attributes=False` fact where the row is first mentioned |
| GameOverPage with no session id | §8-8 and §4.5 correctly closed *where* the session id comes from, but neither covered its absence. Verified: `GameLayout.tsx:83-85` is `.catch(() => {})`, commented "non-fatal — title stays blank if fetch fails", so `sessionId` can legitimately be null while the rest of the screen renders from `game_over`. §4.5 explicitly drops the `COMPLETED` gate and named no other, so the natural build ships buttons that request `/host/sessions/null/report` at the end of a game the host just ran | **§4.5**: both buttons disabled while `sessionId` is null, with an explicit "do not make that fetch fatal to fix this". **§8-12** gains a matrix row that blocks the request and checks the buttons are disabled |
| `?course_id=` with a nonexistent course | §3.2 read "403 for a non-admin without HOST on it, 404 if the course does not exist" — role-independent. Verified: `assert_host_can_use_course` ([game_service.py:47-67](../backend/app/services/game_service.py)) raises `NotFoundError` **only in its ADMIN branch**; the non-admin branch just looks for a `user_course_access` row, so a missing course is indistinguishable from a missing grant → **403**. A §10 row written from the old sentence asserts the wrong status | **§3.2**: 403 for non-admins (stated as deliberate — course existence is not leaked to non-hosts), 404 for ADMIN. **§10**: both rows added |
| What `AdminSessionItem` carries | §3.2 listed six fields and claimed "everything §4.5 needs". It omitted `status`, which is what gates §4.5's download buttons on `COMPLETED`, and the id — which is spelled **`session_id` and is a `str`**, where §4.5 wrote `{sid}`. Both are on the schema, so the code would have worked; the completeness claim was what was wrong | **§3.2**: both added, flagged as the two easiest to overlook. **§4.5**: paths and the `status === 'COMPLETED'` gate written with the real field names |
| §4.6's `/sessions` exemption | "the shell renders the empty state in place of the routed content" plus "`/sessions` is never replaced" needs the shell to know the active route, and no section said how. The obvious alternative — lifting `/sessions` out of the shell — is wrong: the page would lose the nav, so a revoked-access host could not reach the one screen the exemption exists to preserve | **§4.6**: `useLocation()`, `<Outlet/>` regardless of the course list on `/sessions`, and the nav renders in all three states |
| §8-1's grep gate vs. "copied from admin" | §8-1 said to copy `put`/`patch`/`postForm`/`download` from admin *and* that `grep -rn localStorage frontend/host/src` should then hit only `lib/auth.ts`. Verified: admin's `api.ts` reads the token in **three** places, because `downloadFetch` and `postForm` bypass `apiFetch` deliberately. A verbatim copy fails the step's own check | **§8-1**: "ported, not copied" — keep both bypasses (the host's `apiFetch` sets `Content-Type: application/json` unconditionally, which would break multipart), route all three reads through `getToken()` |
| HomePage inside the shell | §4.5 said "same layout" and §7's row listed four changes, none about framing. `HomePage`'s root is `min-h-screen flex flex-col items-center justify-center` — a centred splash, which under a top nav is taller than the viewport with the card below the fold. It is the first screen every host sees | **§7**: drop the full-screen centring for shell-relative padding; "same layout" clarified to mean the same content |

Confirmed against the code and left alone, including the claim most likely to be wrong: **the
existing integration suite survives §3.1 unchanged.** `tests/integration/conftest.py` creates its game
through `POST /api/admin/games` with no course **and** creates the room with the **admin** token, so
both the unattached-game rule and the role-blind mismatch check pass it. Also re-verified:
`my_courses`' ADMIN branch returns every course with `"role": "HOST"` (§3.4); `assert_host_can_use_game`'s
**only** caller is `create_room`, so §3.3's tightening cannot reach another flow; admin `RosterPage`
touches only the three roster paths, so §14 is right that no host multipart route and no
`GET /host/courses/{cid}` are needed; `nginx.dev.conf:40` already has `try_files … /host/index.html`;
`/api/host/*` does not collide with nginx's `location /host/`; `create_access_token` sets `"role"`;
`GET /admin/games/{id}` exists, so `GET /host/games/{id}` has a real equivalent; and both download
routes already emit a **quoted** `Content-Disposition`.

**The pattern, confirmed.** Five of these seven (the row builder, the 404, the field list, the
`/sessions` mechanism, the grep gate) are the defect §14 named at its close — a §3/§8/§10 assertion
resting on a §3–§4 sentence that is absent or slightly wrong. §14's proposed check (walk every §8 step
and §10 row and name the sentence it rests on) would have caught three of them. It is worth running
once more in the reverse direction — walk every §3/§4 sentence and name the §8 step or §10 row that
consumes it — which is what surfaced the two findings §14's own direction would have missed.

**Status: ready to implement.** §15 changes no decision. The two to read before starting are §3.3's
sixth extraction and §4.5's null-`sessionId` gate.

## 16. Goldfish-test revisions (2026-10-02, fourth Goldfish pass)

A fourth fresh session read §1–§15 with only the context hierarchy for company. Four gaps, two of
which change code on paths §10 would have caught only at runtime, and two of which are contract text
that is wrong about this codebase and would have shipped as written. Every claim was checked against
the named file first.

| Finding | Was | Now |
|---|---|---|
| `course_name` on a game the request created | §3.3 said `lazy="selectin"` means "no change at any return site". The strategy fires as part of a SELECT, so it does not cover a `Game` that was constructed and flushed — which is the shape `admin.create_game` establishes and `POST /host/games` copies. Pydantic's access to the unloaded relationship then lazy-loads on an async session → `MissingGreenlet`. It hides itself, too: a many-to-one lazy load with a `NULL` FK short-circuits without SQL, so every existing unattached `POST /admin/games` keeps passing and only the new attached-create path 500s | **§3.3** closing paragraph: `await db.refresh(game, ["course"])` after the flush, with "read site" replacing "return site". **§3.2** rows for both create endpoints. **§10** asserts the response body, not just the 201 |
| `course_name` on a game the request re-pointed | Same paragraph, second uncovered path, and this one is the §14-added attach control. `update_game` loads the game with `db.get` (so `course` resolved to `None` — unattached is the only state the control renders on), assigning `course_id` does not update the loaded relationship, `AsyncSessionLocal` is `expire_on_commit=False` and `get_db` commits **after** FastAPI serialises. Nothing refreshes it. §4.5's "the row re-renders as attached" would render attached with a blank course name | **§3.3** + **§3.2**'s `PUT /admin/games/{id}` row: `db.expire(game, ["course"])` after the assignment. **§4.5** states the row re-renders from the response body. **§10** asserts that body |
| §4.6's GUEST case | §4.6 opened by naming the two users it exists for — a PLAYER-only `USER` and "a `GUEST` who just finished a game" — and routed both to the `[]` empty state. The guest half never happens: `require_user` raises `ForbiddenError("Authenticated account required")` for `role == "GUEST"`, so `/game/my-courses` answers **403**. The guest landed in the rejected branch instead, reading a raw server string under a **Retry button that can never succeed**, and §10 tested only the USER | **§4.6**: the two users arrive through different branches, stated where the premise is. The rejected state splits into **403 → a guest message with no Retry** (the GUEST check is `require_user`'s only `ForbiddenError`, so the status alone is enough to branch on) and **anything else → the existing message + Retry**. Four shell states, not three. **§10** + **§8-12** rows |
| `/home` vs the `/sessions` exemption | §4.6 exempted `/sessions` from the empty state because it filters on `host_user_id`, not course access, so a revoked host keeps their own grade data. `GET /game/my-active-sessions` has the identical property — `host_user_id`, no course predicate — and `/home` is where the active-session list and **Rejoin** live. As written, a revoked host lost Rejoin for a session live on the projector while keeping a CSV from last month: the weaker case was exempt and the stronger one was not, with no reason given | **§4.6**: `/home` is exempt on the same `useLocation()` check, and both exemptions are stated to rest on the same property. It needs no new empty state — §4.5's existing no-course rendering is already correct for zero HOST courses. The comparison is spelled out as `pathname` **equality**, so the deep routes `/games/:gameId/questions` and `/courses/:courseId/roster` stay unexempt. **§10** + **§8-12** rows |

Four one-line gaps, fixed in place: `POST /admin/games` with a nonexistent `course_id` had no stated
status and would raise an FK `IntegrityError` → 500, where every other §3.2 error path names a code
(**404** now, matching `assert_host_can_use_course`'s ADMIN branch); §4.6 said the shell calls
`useLocation()` but not whether the test was equality or a prefix; §4.2's `ExternalRedirect` never
said what it renders during the effect (**`null`**); and §7 did not mention that the admin app has no
`types/` directory, so `course_id`/`course_name` have to be added to the inline `Game` interface in
each of `GamesPage`, `QuestionEditorPage` and `UserDetailPage` for §7's existing rows to compile.

Confirmed against the code and left alone — every other concrete claim in §3–§4 this pass could
check, including the ones §11–§15 flagged as load-bearing: `my_courses` is HOST-filtered with an
ADMIN branch returning every course as `"role": "HOST"` (§3.4); `my_games` joins `user_game_access`
alone, so §3.3 really is a behaviour change (§3.3); `assert_host_can_use_course` raises
`NotFoundError` **only** in its ADMIN branch, so a nonexistent course is a 403 for a non-admin
(§3.2, §15); `assert_host_can_use_game`'s only caller is `create_room`, verified by grep across
`backend/`, `scripts/` and `tests/` (§15); `AdminSessionItem` rows are hand-assembled with three
`db.get`s and a `count` per session, returning `list[dict]` (§3.3-6); `RoomInfoResponse.session_id`
exists and `GameLayout` discards it in a `.catch(() => {})` (§4.5, §8-8); `import_game` returns a
plain `{"game_id": …}` dict, so the import path carries no `GameResponse` risk and §4.5's
post-import navigate works; both export routes emit a **quoted** `Content-Disposition` (§10);
`nginx.dev.conf`'s `try_files` covers the deep host routes and `location /api/` wins the
longest-prefix match over `location /host/`, so `/api/host/*` does not collide (§15); the link
scheme survives both builds, since `base` is `/host/`÷`/admin/` in production and `/` in dev while
the host router uses `basename={import.meta.env.BASE_URL}` (§4.3); `lucide-react` is already a
host-app dependency and the Tailwind `content` glob is `./src/**/*.{ts,tsx}`, so §8-3's move into a
new `pages/manage/` subdirectory needs no package or config change; and `tests/integration/conftest.py`
creates its game through `POST /api/admin/games` with no course **and** its room with the **admin**
token, so §3.1's unattached rule and the role-blind mismatch check both leave the existing suite
passing (§15's riskiest claim — it holds).

**The pattern, third direction.** §14 and §15 both closed by naming one defect — a §8 step or §10
row resting on a §3–§4 sentence that is absent or slightly wrong — and proposed walking that
dependency in each direction. All four findings here are a direction neither walk covers: a §3–§4
sentence that is internally consistent, and consistent with §8 and §10, but **wrong about the code
it describes** (ORM loader timing, `require_user`'s GUEST branch) or **inconsistent with a sibling
§3–§4 sentence** (`/sessions` exempt, `/home` not). The check that catches these is the one the
"confirmed and left alone" lists have been doing all along: for every claim about existing
behaviour, name the file and line. That is why those lists are the only part of §11–§16 that has
never needed revising, and it is the version of this worth describing at the T11 review.

**Status: ready to implement.** §16 changes two decisions — §4.6's rejected branch now splits on 403,
and `/home` joins the exemption — and corrects two claims about the code. The two to read before
starting are §3.3's closing paragraph (both refresh calls) and §4.6's four states.

## 17. Design-review revisions (2026-10-02, fourth pass)

A fourth review re-read §1–§16 running §16's own closing check — for every claim about existing
behaviour, name the file — but applied to a target the previous passes had not: not the API contract,
which §11–§16 verified line by line, but the **end-to-end flows a reader actually performs**. Two
findings, one of which changes shipped behaviour on the project's documented first-run path.

| Finding | Was | Now |
|---|---|---|
| `seed_demo.py` after §3.1 + §4.5 | §6 said the README's getting-started flow "still works unchanged, because the script signs in as `ADMIN_USERNAME`", and §9 declined the one-line fix to keep the T5 surface unchanged. The reasoning is sound at the API level and does not reach the UI. Verified: [`HomePage.tsx:29-41`](../frontend/host/src/pages/HomePage.tsx) fetches `/game/my-games` **unfiltered** today and [`game.py:82-84`](../backend/app/routers/game.py)'s ADMIN branch returns every game, which is the only reason an admin can pick the demo game now. §4.5 replaces that with a per-course request, and §3.3's filter binds the ADMIN branch too, so the unattached demo game is excluded from every request HomePage can make. A clean clone then reaches "No quizzes for this course yet" on the only screen that creates rooms — and clean-clone verification is a submission checklist item. `seed_demo.py` is not under `tests/`, so the §9 rationale did not apply either | **§6**: the real failure spelled out, with the one-line fix and the rejected contract-level alternative. **new §8-13** (ordered with step 1; numbered last to keep the `§8-12` matrix references stable). **§8-12**: a matrix row for the README path, flagged as the one row that fails *silently*. **§9**: the bullet retracted, with a pointer rather than a deletion |
| §4.6's exemption scope | §4.6 exempted `/home` and `/sessions` from replacement "regardless of the course list" — phrasing that addresses only the resolved-`[]` state, while both rejected branches say "replace the routed content" unconditionally. Whether a GUEST on `/host/home` sees the guest message or the Play screen was inferable *only* from §8-12's guest row | **§4.6**: the exemption is stated as scoped to resolved-`[]`, with the reason the scoping is not arbitrary (`[]` means the user owns host data the shell can still show; a rejection means the shell does not know what they own) and an explicit note that the in-flight state needs no exemption |

Also recorded: **Alt 9** in §5 — replacing §4.6's `pathname` exemptions with a guard element wrapping
only the four gated routes. It is cleaner on the axis §15 and §16 both had to correct, and is rejected
on cost rather than merit, with the condition that would flip it (a fifth gated route). The §0 header
was cut from a fifteen-line hazard list to a four-line map; everything removed from it was restating
§14–§16's own status lines.

Checked and left alone: every §3 contract, §4.5's page behaviours, §10's rows and §8's commit
grouping. Nothing in this pass contradicts an earlier one.

**The pattern, fourth direction.** §16 closed by saying the check that catches its class of defect is
"for every claim about existing behaviour, name the file and line" — and that check *was* run on §6's
`seed_demo.py` bullet, which cites the script correctly. It still shipped a wrong conclusion, because
the claim it verified ("the script signs in as ADMIN") was true and simply did not entail the claim it
supported ("the flow works unchanged"). Both findings here have that shape: a sentence whose cited
evidence is real and whose scope is narrower than the sentence using it — an API fact standing in for
a UI flow, a course-list rule standing in for all four shell states. The check that catches it is to
**walk the flow, not the claim**: name a user, a starting URL and a sequence of clicks, and follow it
through §3 and §4 end to end. §8-12's matrix is that check in its verification form; the finding above
is what happens when the matrix has no row for a flow the README does have. Worth stating at the T11
review as the limit of the three checks §14–§16 proposed: each walks a dependency *between sections*,
and none of them walks a path *through* them.

**Status: ready to implement.** §17 changes one decision — attaching the demo game's course moves from
§9 to §8-13 — and scopes one existing rule. Read §3.3's closing paragraph and §4.6's four states
before starting; they are still the two easiest things here to get wrong.

## 18. Goldfish-test revisions (2026-10-02, fifth Goldfish pass)

A fifth fresh session read §1–§17 with only the context hierarchy for company, and ran §17's own
closing check — *walk the flow, not the claim* — against the two flows the previous eight passes
never walked, because neither has a user in it: **a pytest run** and **a `npm run dev` session**.
Both findings that change code came from there. Five findings; none changes a decision. Every claim
was checked against the named file first.

| Finding | Was | Now |
|---|---|---|
| §10's fixtures | "Fixtures needed: an ADMIN, a `host_a` …, a `host_b` …" plus "using the existing fixtures", with no scope and no teardown. Verified: `conftest.py::game_setup` is **function-scoped**, creates a course *and* a game per test, deletes only the game, and comments that courses have no DELETE endpoint and are left inert (§12 confirmed no `DELETE /admin/courses/{id}`). Copying the suite's only worked example leaks 2 courses + 2 users + 3 games **per test** across ~25 rows, plus LOBBY sessions that `create_room` counts against `MAX_ROOMS` — the failure [instructions.md](../instructions.md) T5 warns about by name, arriving as unrelated-looking resource limits | **§10**: one **session-scoped** `t4_env` built once; function-scoped resources only for the rows that mutate shared state (question CRUD/reorder, roster, attach); teardown in order — sessions via `DELETE /game/sessions/{id}` (the Redis half), then games, then users; the two courses knowingly inert, **which is why they are session-scoped**, and distinctly named so a leak is identifiable |
| §4.3's dev-mode links | "Those links will land on the host login page. This is acceptable for development." Verified: `frontend/admin/vite.config.ts` sets `base: '/'` in dev and proxies only `/api`, so there is no `/host` route on :5175. `window.location.replace('/host/games')` gets the admin dev server's SPA fallback and lands in the admin router with `basename` `/`, where `/host/games` matches nothing and hits the catch-all §4.2 repoints at **`/users`**. The link silently returns the user to the admin app's own Users page — a worse failure than the token loss §4.3 documents, and one that reads as a broken link | **§4.3**: the links require `VITE_HOST_APP_URL` / `VITE_PLAYER_APP_URL` to work at all in dev; with them set the old sentence is true (host app, no token, login page); without them the bounce-to-`/users` path is spelled out. Both sentences go in the admin `lib/CLAUDE.md` |
| §3.3's "never selected" | The closing paragraph's Created bullet, and §16's first row, both reason from "the object is constructed and flushed, **never selected**, so `course` is unloaded". Verified: `admin.py::create_game` is `db.add` → `flush` → **`await db.refresh(game)`** → `commit`. It *does* re-SELECT, so the premise is false, and a reader cannot tell whether the prescribed `db.refresh(game, ["course"])` replaces that call or duplicates it — the answer turns on whether a bare `Session.refresh()` re-applies the mapper's `selectin` strategy, which the spec never states. `POST /host/games` is specified as copying this shape, so the ambiguity propagates | **§3.3** + the two §3.2 create rows: the existing bare `db.refresh(game)` is named, and the attribute-scoped form **replaces** it on both paths rather than sitting beside it — correct either way, which is the point. §16's self-hiding argument (a `NULL` many-to-one emits no SQL) survives on its own evidence |
| `POST /admin/games/import` | §3.2's row covered both admin create routes as "accept optional `course_id`", but the "never travels in the file" paragraph defines the mechanism only for the **host** import route, and nothing exercises the admin variant: §3.3 keeps the admin create routes for scripts/tests only, §4.2 deletes the admin `/games` route, `seed_demo.py` uses `POST /admin/games` (§8-13), and no §8 step, §8-12 row or §10 row calls it. Since game import is extraction 4 — one service, two routers — the shared signature depended on the answer | **§3.2**: the row splits. The extracted service takes `course_id: int \| None` and **only the host route passes it**; `POST /admin/games/import` keeps `file` alone and passes `None`, so an admin-imported bundle lands unattached. Stated as a decision, with the reason symmetry is not a reason |
| HomePage's auto-select | §4.5 said "the single-course auto-select already in the page still runs". Verified: it is `if (c.length === 1) setCourseId(c[0].id)` **inside** the mount `Promise.all` ([HomePage.tsx](../frontend/host/src/pages/HomePage.tsx)), while §4.6 moves the course list to outlet context, which resolves *after* mount. Left in place it tests an empty list on every load and auto-selects nothing — silently removing the no-extra-click path §4.5 claims for the common case | **§4.5**: it becomes an effect keyed on the context course list, which also covers the shell's Retry refetch. The single-*game* auto-select stays on the `my-games` result |

Two one-line gaps fixed in place: §4.6's "read the status off the response in the shell" never said
what that costs — a raw `fetch` re-implementing the `/api` prefix, the Bearer header and the
`{detail}` parse, which is `frontend/CLAUDE.md`'s first gotcha — so the duplication is now stated as
accepted, scoped to that one call, and required to use `getToken()` so §8-1's grep gate still passes;
and HomePage's catch still said "Failed to load courses or games" for a page that after §4.5 loads
neither.

Confirmed against the code and left alone, including the claims §11–§17 flagged as load-bearing:
`require_user` raises `ForbiddenError("Authenticated account required")` for `role == "GUEST"` and
that is its only `ForbiddenError` ([common/dependencies.py](../backend/app/common/dependencies.py)),
so §4.6's status-only branch holds; `assert_host_can_use_course` raises `NotFoundError` **only** in
its ADMIN branch (§3.2, §15); `my_courses` is HOST-filtered with an ADMIN branch returning every
course as `"role": "HOST"` (§3.4); `my_games` joins `user_game_access` alone (§3.3 is a behaviour
change); `create_room` calls both asserts, and `RoomCreateRequest` is `extra="forbid"` over
`game_id` + `course_id`; `GameCreate`/`GameUpdate` carry exactly title/description/max_players and
are both `extra="forbid"` (§3.2, §3.5); `GameResponse`/`MyGameItem` are `from_attributes=True` with
no course field; `AdminSessionItem` rows are hand-assembled with three `db.get`s and a distinct count
per session returning `list[dict]`, and carry `session_id` (a `str`) and `status` (§3.2, §3.3-6);
`RoomInfoResponse.session_id` exists and `GameLayout.tsx:83-85` discards it in a `.catch(() => {})`
(§4.5, §8-8); `GET /game/sessions/{id}/export` gates on session-host-or-ADMIN, and it,
`/admin/sessions/{id}/report` and `/admin/games/{id}/export` all emit a **quoted**
`Content-Disposition`, which the ported `api.download` regex needs (§10); admin's `api.ts` reads the
token in **three** places (§8-1); the three moved pages import only `lucide-react` and
`ui/{button,card,input}`, and those three files are byte-identical to the host's by `diff`, so §8-3
needs no restyling (§13); admin `App.tsx` uses `:gameId`/`:courseId` and declares `AdminLayout`
inline, so §7's single-file row is right; `nginx.dev.conf:38-40` has `try_files … /host/index.html`
and `location /api/` wins the longest-prefix match (§15, §16); `scripts/smoke_test_websocket.py`
creates its game **and** its room with the **admin** token, so §3.1's unattached rule and the
role-blind mismatch check leave it passing — the same check §15 ran on `conftest.py`; and
`migrations/env.py` imports every model module, so §3.3's `Game.course` relationship string resolves
despite `models/__init__.py` being empty.

**The pattern, fifth direction.** §17 named the right check — walk a flow end to end, not a claim —
and this pass found that all four earlier walks share an unstated assumption: the flow has a *person*
in it. §8-12's matrix is nine user journeys. The two defects above live in flows with no user at all:
a pytest session, where the "actor" is a fixture and the failure surfaces as resource exhaustion in
an unrelated test; and `npm run dev`, where the actor is a developer who is not the audience any
§4 section was written for. Both were verifiable from a file this document already cites. The check
worth stating at the T11 review: **walk the flows whose actor is a script** — the seed script (which
§17 caught), the smoke test and `simulate_players.py` (clean), the test fixtures (finding 1), and
each dev-server config (finding 2). That is the last class of reader this spec has, and it is the one
nobody writes §4.5 for.

**Status: ready to implement.** §18 changes no decision. One thing to read before the §10 tests that
was not in any earlier status line: **§10's fixture scope and teardown**, because it decides how
every row below it is written and it is expensive to retrofit. §3.3's closing paragraph and §4.6's
four states are still the two easiest things here to get wrong.

## 19. Implementation notes (2026-10-02)

Implementation followed §3/§4 and the §8 commit groups. Four places where the code had to differ
from the letter of the spec, each found while building against the running stack:

| Spec said | Built | Why |
|---|---|---|
| `await db.refresh(game, ["course"])` on both create paths (§3.3) | `await db.refresh(game, ["created_at", "course"])` | The attribute-scoped form refreshes **only** the named attributes. `created_at` is a server default that MySQL's INSERT does not return, so a course-only refresh would leave it unloaded and `GameResponse.created_at` would lazy-load → the same `MissingGreenlet` §3.3 exists to avoid. The bare `refresh(game)` loaded it, which is why it never surfaced before. |
| `db.expire(game, ["course"])` after the attach assignment (§3.2, §3.3) | `expire` **then** `await db.flush(); await db.refresh(game, ["course"])` | An expired attribute is reloaded on next access, and that access happens during Pydantic serialisation, outside the greenlet. Expire alone trades the stale `null` for a `MissingGreenlet` 500. The refresh reloads it inside the await. §10's attach row asserts the `course_name` in the 200's body and passes. |
| HostShell reads the status with its own raw `fetch`; `api.ts` stays status-blind "until a second caller needs it" (§4.6) | `api.ts` throws `ApiError(message, status)`; HostShell and RosterPage both use it | RosterPage's "You don't have HOST access to this course" on a **403** (§4.5) *is* that second caller, so §4.6's own fallback applies. This also deletes the raw-fetch copy of the `/api` prefix, Bearer header and error parse. |
| "`api.ts` throws `Error(detail)`", so pages show "the server's message" (§4.5, §11) | the host `api.ts` reads a string `detail`, else `message`, else `HTTP <status>` | `BuzzerError`s (every 403/404/409 from `assert_host_can_use_*`) serialise as `{"error", "message"}`, not `{"detail"}` (`common/exceptions.py`). With `detail` only, every access error §4.5 promises to show reads "HTTP 403". The admin `api.ts` is unchanged. |

Also, not deviations but choices the spec left open:
- **Shared visibility query.** `game_service.visible_games_query(user, course_id)` builds the
  §3.3 SELECT once for both `/game/my-games` and `/host/games`, next to `assert_host_can_use_game`.
  That turns §3.3's "one rule, three endpoints" into two functions instead of three copies.
- `assert_host_can_use_game` returns the `Game`, so `create_room` can apply the role-blind
  course-identity check (§3.1) without a second lookup. For a non-admin it returns a **403** for a
  nonexistent game, matching `assert_host_can_use_course`'s no-existence-leak behaviour.
- `HostGameCreate` (a `GameCreate` subclass) makes `course_id` **required** on `POST /host/games`.
  `GET /host/sessions?status=` validates the value against the four enum members (an unknown
  value, e.g. `ACTIVE`, is a 422).
- The import service raises its own `BundleError`, and both routers map it to the same 422
  `detail` as before. `services/CLAUDE.md` forbids FastAPI imports in services.
- §10 is `tests/integration/test_host_admin_restructure.py`: 56 cases (the §10 rows plus refactor, auth-boundary and malformed-bundle coverage), all passing along with the
  existing suite. A post-run DB check found no leaked T4 games, users or sessions.
