# Design: Host / Admin UI Restructuring (T4) — Frontend

Status: **Draft — awaiting Goldfish test** · Scope: `frontend/host`, `frontend/admin` (plus the
backend API contract they depend on) · Task: T4 in [instructions.md](../instructions.md)

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

### 3.2 Endpoints (new unless marked)

| Method & path | Gate | Used by |
|---|---|---|
| `GET /game/my-courses` *(existing)* | require_user | Host shell, Games, Rosters, Home |
| `GET /game/my-games?course_id=` *(add optional filter; add `course_id`, `course_name` to `MyGameItem`)* | require_user | Home picker |
| `GET /host/games?course_id=` | require_user; returns only games the user can manage (ADMIN: all, including unattached) | Games list |
| `POST /host/games` `{title, description, max_players, course_id}` | HOST on `course_id`; inserts a `user_game_access` row for the creator | Games list |
| `GET /host/games/{id}` · `PUT /host/games/{id}` | host-gated on game. `course_id` is **not** editable through PUT | Question editor, Games list |
| `GET/POST /host/games/{id}/questions` | host-gated on game | Question editor |
| `PUT/DELETE /host/games/{id}/questions/{qid}` | host-gated on game; `qid` must belong to `id` | Question editor |
| `POST /host/games/{id}/questions/reorder` `{order: [ids]}` (same body as admin) | host-gated on game | Question editor |
| `GET /host/games/{id}/export` | host-gated on game | Question editor |
| `POST /host/games/import` multipart `file`, `course_id` | HOST on `course_id`; auto-grants the creator | Games list |
| `GET /host/courses/{cid}/roster` | HOST on `cid` | Roster |
| `POST /host/courses/{cid}/roster` (multipart CSV) · `POST /host/courses/{cid}/roster/import` (mapped rows) | HOST on `cid` | Roster |
| `PATCH /host/courses/{cid}/roster/{rid}` | HOST on `cid`; `rid` must belong to `cid` | Roster |
| `GET /host/sessions?status=` | require_user; non-admin sees only `host_user_id == me` | Sessions |
| `GET /host/sessions/{sid}/report` | session host or ADMIN | Sessions |
| `GET /game/sessions/{sid}/export` *(existing, raw per-player CSV)* | session host or ADMIN | Sessions |
| `POST /admin/games` · `POST /admin/games/import` *(existing; accept optional `course_id`)* | require_admin | unchanged callers |
| `DELETE /admin/games/{id}` *(existing)* | require_admin | Host Games list, shown to ADMIN only |
| `GET /admin/games` *(existing; add `course_id`, `course_name` to `GameResponse`)* | require_admin | Admin UserDetail grants |

Response shapes for the `/host/*` endpoints match their `/admin/*` equivalents, so the moved
pages only need their path prefix changed. `GameResponse` gains `course_id: int | null` and
`course_name: str | null`.

**Backend files implied** (owned by the backend half of T4, listed so this list is complete):
`backend/app/models/game.py`, new `backend/app/migrations/versions/<rev>_game_course_id.py`,
`backend/app/schemas/admin.py`, `backend/app/schemas/game.py`, new
`backend/app/routers/host.py`, `backend/app/main.py` (mount the router),
`backend/app/routers/game.py` (my-games filter), `backend/app/routers/admin.py` (optional
`course_id`), `backend/app/services/game_service.py` (`assert_host_can_use_game`,
`create_room`), and the matching `CLAUDE.md` files.

Shared logic between `/admin/*` and `/host/*` (question create/update with bleach
sanitisation, reorder, roster upsert, import) must be **extracted into a service function and
called from both routers**, not copied. `routers/CLAUDE.md` already records two places where
duplicated logic has drifted (guest merge, auth checks).

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
  Sessions     /sessions                 (all hosts; Canvas export; unchanged page)
  Games ↗      external link → {HOST_APP_URL}/games
  Rosters ↗    external link → {HOST_APP_URL}/courses
  Host a game ↗ external link → {HOST_APP_URL}/home
  Join as player ↗ external link → {PLAYER_APP_URL}/join
```

Removed admin routes: `/games`, `/games/:gameId/questions`, `/courses/:courseId/roster`. Each
one is replaced with `<ExternalRedirect>` to the matching host-app URL so old bookmarks still
work. The catch-all changes from `/courses` to `/users`.

There is no separate "Access" page. Course and game grants already live on `UserDetailPage`,
and keeping them there avoids building a second grant UI. The A1 "access grants" requirement is
covered by Users being first in the nav and UserDetail being where grants happen.

### 4.3 Cross-app URLs and the auth token

- Production (nginx) and the Docker stack serve all three apps from one origin (`/host/`,
  `/admin/`, `/player/`). `localStorage.token` is per-origin, so it is **shared**: an admin who
  follows "Games ↗" arrives already signed in.
- In Vite dev mode each app has its own port (5173/5175), so the token is **not** shared. Those
  links will land on the host login page. This is acceptable for development and is documented
  in the admin `lib/CLAUDE.md`.
- URLs come from `import.meta.env.VITE_HOST_APP_URL ?? '/host'` and
  `import.meta.env.VITE_PLAYER_APP_URL ?? '/player'`, defined once in `admin/src/lib/links.ts`
  and `host/src/lib/links.ts` (`VITE_ADMIN_APP_URL ?? '/admin'`).

### 4.4 Role awareness in the UI (display only)

New `host/src/lib/auth.ts`: `getToken()`, `clearToken()`, and `getRole(): 'ADMIN' | 'USER' |
'GUEST' | null`. `getRole()` base64-decodes the JWT payload's `role` claim without verifying it.
It is used **only** to show or hide UI (the Admin console link, and the Delete-game button
that calls `/admin/games/{id}`). Every action is still authorised by the server. A forged role
claim only reveals a button that returns 403. `api.ts`, `App.tsx`, `LoginPage`, and
`GameLayout` switch to `getToken()`, which fixes the "no single accessor" gotcha in
`host/src/lib/CLAUDE.md`.

### 4.5 Page behaviour

**HomePage (host)**: same layout, with one change. When a course is selected, the Quiz select
lists only games with `course_id === courseId`, fetched with `/game/my-games?course_id=`. If the
course changes and the selected game is not in the new list, clear `gameId`. The "auto-select a
single game" logic applies after filtering. Empty state: "No quizzes for this course yet —
create one in Games."

**GamesPage (host, moved)**:
- List: `GET /host/games`, grouped or filtered by a course `<select>` (populated from
  `/game/my-courses`). Each row shows title, course name, and description.
  ADMIN-only rows with `course_id = null` are labelled "Unattached (admin only)".
- Create form: title, description, max players, and a **required** course `<select>`. The
  submit button stays disabled until a course is chosen.
- Import JSON: a file picker plus the same required course select. Sends `FormData` with `file`
  and `course_id`, then navigates to the new game's question editor.
- Edit title/description/max players inline (`PUT /host/games/{id}`). The course is shown but
  is read-only.
- Delete: rendered only when `getRole() === 'ADMIN'`, behind the existing confirm step, and
  calls `DELETE /admin/games/{id}`. Hosts cannot delete games (see §5, Alt 5).

**QuestionEditorPage (host, moved)**: behaves the same as today. The only change is the API
prefix: `/admin/games/...` becomes `/host/games/...`. The header also shows the game's course
name, and the back button goes to `/games`.

**CoursesPage (host, new, small)**: `GET /game/my-courses`, with one card per course
(name · semester) and a "Manage roster" button that goes to `/courses/:id/roster`. It is
read-only, because course creation stays an admin task.

**RosterPage (host, moved)**: same CSV upload, column-mapping wizard, and inline edit/deactivate
as today. The prefix changes from `/admin/courses/...` to `/host/courses/...`. A 403 response
renders "You don't have HOST access to this course" instead of a generic error.

**SessionsPage (host, new)**:
- `GET /host/sessions` with a status filter whose default is **Completed** (All / Completed /
  Abandoned / Active).
- Each row shows game title, course · semester, room code, date, and player count.
- **Download summary (HTML)** button: `api.download('/host/sessions/{sid}/report')`. Enabled
  only for `COMPLETED`.
- **Download scores (CSV)** button: `api.download('/game/sessions/{sid}/export')`. Enabled only
  for `COMPLETED`.
- Download errors are shown inline on the row.

**GameOverPage (host)**: add the same two download buttons next to "New Game". The session id
comes from `sync_state`/`game_over`. If the payload does not include it, use
`GET /game/rooms/{code}`, which already returns room info, and add `session_id` there if it is
missing. These buttons are where hosts most expect to find the downloads, right after a game
ends.

**Admin UserDetailPage**: the game-grant picker labels each game as "Title — Course", using the
new `course_name` on `GameResponse`. A grant for a game whose course the user has no HOST access
to is allowed, because the server stores it, but the row shows a yellow note: "No HOST access to
this game's course — grant has no effect until course access is granted." This makes the
intersection rule from §2.5 visible to the admin.

**Admin CoursesPage**: the "Roster" button becomes an external link to
`{HOST_APP_URL}/courses/{id}/roster`.

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

## 6. Risks and self-critique

- **Intersection rule versus co-hosts.** With rule §2.5, a TA with HOST on a course cannot run a
  quiz that another instructor created until an admin grants it. This is deliberate, but it will
  confuse users. The UserDetail note (§4.5) makes it visible. If the team finds this too strict,
  dropping the `user_game_access` check (Alt 7) is a single change in `assert_host_can_use_game`
  plus updated tests.
- **`/game/my-games` semantics change.** For non-admins it must apply the same intersection
  rule, or the Home picker will list games that `create_room` then rejects. Integration tests
  must cover "listed ⇒ creatable".
- **Editing a game that already has completed sessions.** Questions can be edited or deleted
  after a session, which changes what the HTML report shows for that older session.
  Admin has this problem today too. It is out of scope, but worth noting.
- **Unattached games (`course_id = NULL`)** never appear for non-admin hosts. Existing
  production games (if any) would disappear from host pickers until an admin attaches them.
  This needs an admin-side way to set `course_id` on an unattached game: `PUT /admin/games/{id}`
  accepts `course_id` **only when the current value is null**, and the host GamesPage shows ADMIN
  an "Attach to course" select on unattached rows.
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
| `components/HostShell.tsx` | **New**: top nav and `<Outlet/>` |
| `pages/HomePage.tsx` | Filter games by course; remove its own Sign Out button (moves to the shell); use `getToken`/`clearToken` |
| `pages/LoginPage.tsx` | `setToken()` instead of raw `localStorage` |
| `pages/manage/GamesPage.tsx` | **New** (moved from admin; course select; import with course; admin-only delete) |
| `pages/manage/QuestionEditorPage.tsx` | **New** (moved from admin; `/host` prefix; course in header) |
| `pages/manage/CoursesPage.tsx` | **New** (my HOST courses → roster) |
| `pages/manage/RosterPage.tsx` | **New** (moved from admin; `/host` prefix; 403 message) |
| `pages/manage/SessionsPage.tsx` | **New** (my sessions; HTML + CSV download) |
| `pages/game/GameLayout.tsx` | Use `getToken()`; keep `sessionId` in `GameContext` |
| `pages/game/GameOverPage.tsx` | Add the two download buttons |
| `types/game.ts` | Add `sessionId` where the payload type needs it |
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

**Player app**: no changes. H5 is enforced server-side in `create_room` plus the existing roster
check.

## 8. Implementation steps

Order: the backend contract (§3) lands first, or in parallel behind the same branch, so each
frontend step can be checked against a running stack. Each step below should end with
`npm run build` passing for the affected app.

1. **Host plumbing.** Add `lib/auth.ts` and `lib/links.ts`. Extend `lib/api.ts` with `put`,
   `patch`, `postForm`, and `download`, copied from admin. Replace every
   `localStorage.getItem/setItem/removeItem('token')` in the host app with the helpers
   (`grep -rn "localStorage" frontend/host/src` should then find hits only in `lib/auth.ts`).
2. **HostShell + routing.** Create `components/HostShell.tsx` (nav: Play, Games, Rosters,
   Sessions, [Admin console], Sign out). In `App.tsx`, wrap the management routes in
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
5. **Course attachment in GamesPage.** Load `/game/my-courses` alongside `/host/games`. Add the
   required course select to the create and import forms and send `course_id`. Add the course
   filter and course column. Make delete ADMIN-only and point it at `/admin/games/{id}`. Add
   "Attach to course" for unattached rows, shown to ADMIN only.
6. **CoursesPage + RosterPage polish.** Build the small CoursesPage. Map a 403 on RosterPage to
   the friendly message.
7. **SessionsPage.** Build the list with a status filter and both download buttons, gated on
   `COMPLETED`.
8. **GameOverPage downloads.** Get `sessionId` into `GameContext` (from `sync_state` or
   `game_over`, falling back to `GET /game/rooms/{code}`) and add the two buttons.
9. **HomePage course filter.** Fetch games per selected course, clear a stale `gameId`, handle
   the empty state, and remove the local Sign Out button.
10. **Admin restructure.** Add `lib/links.ts` and `ExternalRedirect`. Regroup the sidebar. Swap
    the removed routes for redirects. Change the catch-all and post-login route to `/users`.
    Change CoursesPage's Roster button to an external link. Add the course labels and warning
    to UserDetailPage. Delete the three moved pages.
11. **Context sync.** Update or create the `CLAUDE.md` files listed in §7.
12. **Manual verification matrix** (Docker stack, same origin), run before writing the T5
    tests:
    - USER with HOST on course A only: sees only course A in Rosters and Games. Creating a game
      without a course is impossible in the UI. Opening `/games/{courseB-game}/questions`
      directly shows a 403 message, not data. Session downloads work for their own completed
      session, and someone else's session id returns 403.
    - ADMIN: the admin app lands on Users, and the Host tools links open the host app already
      signed in. The host app shows the Admin console link, Delete buttons, and unattached
      games.
    - Room creation with a course-B game in course A fails with the server's 403 message on
      Home.
    - A player on course A's roster cannot join a session for course B (existing behaviour,
      re-checked).

## 9. Out of scope

- Canvas-format export for hosts. Hosts get the raw per-player CSV that H2 asks for. The Canvas
  export stays on the admin Sessions page.
- Merging guest players into real accounts from the host app. `/game/sessions/{id}/guests` and
  `merge-guest` exist, but T4 does not ask for them.
- Unifying `api.ts`/`utils.ts`/`ui/*` across the three apps (see Alt 3).
- Fixing the `multi_select` gap in the HTML report (backend; see §6).
