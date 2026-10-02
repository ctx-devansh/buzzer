# frontend/admin/src/pages/

**Purpose.** Every screen of the Admin app, a desktop dashboard for administrators. It
currently mixes **admin-level** work (users, courses, access grants, guests) with work a
**host** should own (game/question editing, rosters, session exports). That mix is the
subject of T4 (see `docs/design-host-admin-restructure.md`).

**Contents.**
- `LoginPage.tsx` — username/password only (`POST /auth/login`). Stores the token in
  `localStorage.token` and goes to `/courses`. There is no NetID SSO path, unlike host/player.
- `UsersPage.tsx` — lists all users (`GET /admin/users`) with role badges, and has a
  create-local-account form (`POST /admin/users`). Rows link to `/users/:id`.
- `UserDetailPage.tsx` — one user's profile:
  - edit username/display name/email/password/role (`PUT /admin/users/{id}`), and delete;
  - **course access**: list, revoke, and a multi-select grant panel with a HOST/PLAYER toggle
    per course (`POST/DELETE /admin/users/{id}/course-access…`);
  - **game access**: the same pattern for games (`…/game-access…`).

  Loads all courses and games to label grants.
- `CoursesPage.tsx` — list, create, and edit courses (`/admin/courses`), with a Roster button
  per course leading to `/courses/:id/roster`.
- `RosterPage.tsx` — course roster. Shows active/inactive entries with inline edit
  (`PATCH /admin/courses/{cid}/roster/{rid}`, including toggling `is_active`). The CSV import
  wizard has three steps:
  - **idle → mapping**: client-side `parseCSV`, auto-detecting Canvas gradebook exports (the
    `SIS Login ID` column, a "Points Possible" second row, "Last, First" names);
  - **column mapping** with a preview of 3 rows;
  - **result**: posts mapped rows as JSON to `POST /admin/courses/{cid}/roster/import`.

  Netids missing from the upload are deactivated by the backend.
- `GamesPage.tsx` — list, create, and edit games (title, description, max players), delete
  (also deletes sessions), and import a `buzzer/game` JSON bundle (`postForm`
  `/admin/games/import`, then open its editor). Rows link to `/games/:id/questions`.
- `QuestionEditorPage.tsx` — the 788-line question editor for one game. `QuestionForm` handles
  the four types (MC, T/F, fill-in-the-blank with edit distance, multi-select) × grading
  (`ACCURACY`/`COMPLETENESS`), with per-option/per-answer points. `formToPayload` builds
  `config`/`answer_data`/`points_value`. The page lists questions with add/edit/delete, up/down
  reorder (`POST …/questions/reorder {order: [ids]}`), and Export JSON (`api.download`).
- `SessionsPage.tsx` — every session across all hosts (`GET /admin/sessions?status=`), with a
  status filter. Each session expands into:
  - CSV export options: Canvas or raw format, assignment title/ID, SIS domain, roster-only,
    per-question (`/admin/sessions/{id}/export?…`);
  - an HTML report download (`/admin/sessions/{id}/report`);
  - delete via the host route `DELETE /game/sessions/{id}`.
- `GuestsPage.tsx` — lists GUEST users, merges a guest into a real user by netid
  (`POST /admin/users/merge-guest`), and deletes guests.

**How it fits in.** `../App.tsx` wraps everything except `/login` in `RequireAdmin` →
`AdminLayout` (sidebar: Courses, Users, Games, Guests, Sessions, Logout). Unknown routes go to
`/courses`. Pages call `../lib/api.ts` (see `../lib/CLAUDE.md`) and build on
`../components/ui/`. Unlike host/player there is no `types/` directory: each page declares its
own response interfaces inline, so they can drift from `backend/app/schemas/admin.py`.

**Gotchas.**
- **`RequireAdmin` only checks that a token exists, not the role.** A USER/GUEST token from the
  shared-origin host or player app gets into the layout and then sees 403 errors on every page.
  The backend's `require_admin` is the real gate.
- **Adding a question type** means editing `QuestionEditorPage` in several places: the
  `QuestionType` union, `typeLabel`, a `build*Payload` helper, `questionToForm`,
  `formToPayload` (including the `points_value` derivation), and the `QuestionForm` UI. The
  payload shape must pass `backend/app/schemas/admin.py::QuestionCreate.validate_structure`.
- `points_value` for ACCURACY questions is **derived on the client** (max option points for
  MC/T/F/fill-in-the-blank, sum of positive points for multi-select). Only COMPLETENESS uses
  the typed value.
- Reorder sends the body key **`order`** (not `question_ids`). The swap is applied locally only
  after the request succeeds.
- `UserDetailPage` grants run as parallel single POSTs (`Promise.all`). A partial failure leaves
  some grants applied and shows one error.
- `Loading…` is written as **JSX text** in `UsersPage`, `GuestsPage`, `GamesPage`, and
  `QuestionEditorPage`. JSX text doesn't process JS escapes, so it renders literally as
  `Loading…`. Uses inside `{'…'}` string literals are fine.
- Destructive actions use `window.confirm` (games, questions, users, guests). `SessionsPage`
  uses an inline confirm step instead.
- `SessionsPage` raw-format export still sends `per_question`, which the raw CSV builder
  ignores (raw always has one column per question).
