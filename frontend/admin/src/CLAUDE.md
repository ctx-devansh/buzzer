# frontend/admin/src/

**Purpose.** Source of the Admin app, a desktop dashboard served at `/admin/` for
administrators. Today it mixes admin work (users, courses, access grants, guests) with host
work (games/questions, rosters, session exports). T4 separates the two
(`docs/design-host-admin-restructure.md`).

**Contents.**
- `pages/` — `LoginPage` (password only), `UsersPage`/`UserDetailPage` (accounts plus
  course/game access grants), `CoursesPage`, `RosterPage` (Canvas-aware CSV import wizard),
  `GamesPage` (CRUD and JSON import), `QuestionEditorPage` (all question types and scoring,
  reorder, JSON export), `SessionsPage` (all hosts; Canvas/raw CSV and HTML report), and
  `GuestsPage` (merge/delete). See `pages/CLAUDE.md`.
- `components/` — `ui/` primitives (`Button`, `Card`, `Input`), identical to the host's copies.
  See `components/CLAUDE.md`.
- `lib/` — the fullest `api.ts` (`get/post/put/patch/delete`, `postForm`, `download`) and
  `cn`. See `lib/CLAUDE.md`.
- `App.tsx` — `RequireAdmin` (token-presence only) → `AdminLayout` (sidebar: Courses, Users,
  Games, Guests, Sessions, Logout). Unknown routes → `/courses`.
- `main.tsx`, `index.css` — React root and Tailwind entry.

**How it fits in.** Sibling of the host and player apps under `frontend/`. It talks almost
exclusively to `/api/admin/*`, which the backend gates with `require_admin`. That gate, not the
client, is what keeps non-admins out.

**Gotchas.**
- No `types/` directory: response shapes are declared inline per page and can drift from
  `backend/app/schemas/admin.py`.
- A non-admin token (shared origin) passes `RequireAdmin` and then hits 403s everywhere.
- `Loading…` renders literally in four pages (JS escape inside JSX text).
