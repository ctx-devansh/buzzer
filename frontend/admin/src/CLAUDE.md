# frontend/admin/src/

**Purpose.** Source of the Admin app, a desktop dashboard served at `/admin/` for
administrators. Admin-first since T4 (`docs/design-host-admin-restructure.md`): users, courses,
access grants and guests come first; host work (games/questions, rosters) moved to the host app,
which the "Host tools" sidebar group links to.

**Contents.**
- `pages/` — `LoginPage` (password only), `UsersPage`/`UserDetailPage` (accounts plus
  course/game access grants), `CoursesPage`, `SessionsPage` (all hosts; Canvas/raw CSV and HTML
  report), and `GuestsPage` (merge/delete). See `pages/CLAUDE.md`.
- `components/` — `ExternalRedirect` plus `ui/` primitives (`Button`, `Card`, `Input`),
  identical to the host's copies. See `components/CLAUDE.md`.
- `lib/` — `api.ts` (`get/post/put/patch/delete`, `postForm`, `download`), `links.ts`
  (`HOST_APP_URL`, `PLAYER_APP_URL`) and `cn`. See `lib/CLAUDE.md`.
- `App.tsx` — `RequireAdmin` (token-presence only) → `AdminLayout`. Sidebar group
  **Administration** (Users, Courses, Guests) above a muted **Host tools** group (Sessions, then
  outbound links: Games ↗, Rosters & images ↗ (the host Courses page), Host a game ↗, Join as player ↗) and Logout. The old
  `/games`, `/games/:gameId/questions`, `/courses/:courseId/roster` routes are
  `ExternalRedirect`s to the same resource in the host app. Unknown routes → `/users`.
- `main.tsx`, `index.css` — React root (also imports the self-hosted fonts) and Tailwind entry;
  `index.css` `@import`s `../../theme/tokens.css` (T9). `AdminLayout` and `LoginPage` set
  `data-density="compact"` (2 px outlines, smaller type); `ThemeToggle` sits in the sidebar footer
  and on the login page.

**How it fits in.** Sibling of the host and player apps under `frontend/`. It talks almost
exclusively to `/api/admin/*`, which the backend gates with `require_admin`. That gate, not the
client, is what keeps non-admins out.

**Gotchas.**
- No `types/` directory: response shapes are declared inline per page and can drift from
  `backend/app/schemas/admin.py`.
- A non-admin token (shared origin) passes `RequireAdmin` and then hits 403s everywhere.
- `Loading…` renders literally in two remaining pages (JS escape inside JSX text).
- Host-tool links need the shared origin (nginx build) to arrive signed in; see `lib/CLAUDE.md`.
