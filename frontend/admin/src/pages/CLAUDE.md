# frontend/admin/src/pages/

**Purpose.** Every screen of the Admin app, a desktop dashboard for administrators: users,
courses, access grants, guests, and the all-hosts session view. The game, question-editor and
roster screens moved to the host app in T4 (`docs/design-host-admin-restructure.md`,
`frontend/host/src/pages/manage/`).

**Contents.**
- `LoginPage.tsx` — username/password only (`POST /auth/login`). Stores the token in
  `localStorage.token` and goes to `/users`. There is no NetID SSO path, unlike host/player.
- `UsersPage.tsx` — lists all users (`GET /admin/users`) with role badges, and has a
  create-local-account form (`POST /admin/users`). Rows link to `/users/:id`.
- `UserDetailPage.tsx` — one user's profile:
  - edit username/display name/email/password/role (`PUT /admin/users/{id}`), and delete;
  - **course access**: list, revoke, and a multi-select grant panel with a HOST/PLAYER toggle
    per course (`POST/DELETE /admin/users/{id}/course-access…`);
  - **game access**: the same pattern for games (`…/game-access…`), each game labelled
    "Title — Course" (or "Unattached"). A grant row shows a yellow note when the user has no
    HOST access to the game's course (or the game is unattached) — the grant is stored but has
    no effect, because effective access is HOST on the course **and** the grant.

  Loads all courses and games (`GET /admin/games`, which carries `course_name`) to label grants.
- `CoursesPage.tsx` — list, create, and edit courses (`/admin/courses`). Each course's Roster
  button is an **external** link to `{HOST_APP_URL}/courses/{id}/roster`.
- `SessionsPage.tsx` — every session across all hosts (`GET /admin/sessions?status=`), with a
  status filter. Each session expands into:
  - CSV export options: Canvas or raw format, assignment title/ID, SIS domain, roster-only,
    per-question (`/admin/sessions/{id}/export?…`);
  - an HTML report download (`/admin/sessions/{id}/report`);
  - delete via the host route `DELETE /game/sessions/{id}`.
- `GuestsPage.tsx` — lists GUEST users, merges a guest into a real user by netid
  (`POST /admin/users/merge-guest`), and deletes guests.

**How it fits in.** `../App.tsx` wraps everything except `/login` in `RequireAdmin` →
`AdminLayout` (Administration: Users, Courses, Guests; Host tools: Sessions plus host/player-app
links). Unknown routes go to `/users`. Pages call `../lib/api.ts` (see `../lib/CLAUDE.md`) and build on
`../components/ui/`. Unlike host/player there is no `types/` directory: each page declares its
own response interfaces inline, so they can drift from `backend/app/schemas/admin.py`.

**Gotchas.**
- **`RequireAdmin` only checks that a token exists, not the role.** A USER/GUEST token from the
  shared-origin host or player app gets into the layout and then sees 403 errors on every page.
  The backend's `require_admin` is the real gate.
- **Adding a question type** no longer touches this app: the editor is
  `frontend/host/src/pages/manage/QuestionEditorPage.tsx` (its notes: `QuestionType` union,
  `typeLabel`, `build*Payload`, `questionToForm`, `formToPayload` incl. the client-derived
  ACCURACY `points_value`, and reorder's body key `order`).
- `UserDetailPage` grants run as parallel single POSTs (`Promise.all`). A partial failure leaves
  some grants applied and shows one error.
- `Loading…` is written as **JSX text** in `UsersPage` and `GuestsPage`. JSX text doesn't process JS escapes, so it renders literally as
  `Loading…`. Uses inside `{'…'}` string literals are fine.
- Destructive actions use `window.confirm` (users, guests). `SessionsPage`
  uses an inline confirm step instead.
- `SessionsPage` raw-format export still sends `per_question`, which the raw CSV builder
  ignores (raw always has one column per question).
