# frontend/host/src/

**Purpose.** Source of the Host app, served at `/host/`. Instructors sign in, manage the games,
questions and rosters of the courses they HOST, download session results, and open a room and
drive a live game that is projected for the class.

**Contents.**
- `pages/` — the screens. `LoginPage` (NetID SSO or password) and `HomePage` ("Play": active
  sessions with rejoin/delete, plus the course-filtered quiz picker that creates a room) run over
  REST, as do `manage/` (Games, QuestionEditor, Courses/Rosters, Roster, Sessions — moved here
  from the admin app and pointed at `/api/host/*`).
  `game/` is the live Socket.IO state machine (Lobby → Question → Results → Game Over), with
  `GameLayout` as the sole socket owner. See `pages/CLAUDE.md`.
- `components/` — `HostShell` (management top nav + the shared course list), `PinBoard` (the
  Pin the Spot canvas), `ui/` primitives (`Button`, `Card`, `Input`) and `TimerBar`. See
  `components/CLAUDE.md`.
- `lib/` — `auth.ts` (single token accessor, display-only `getRole`), `api.ts` (full client:
  put/patch/postForm/download, `ApiError` with status), `links.ts`, `cn`. See `lib/CLAUDE.md`.
- `types/game.ts` — socket payload types mirroring `backend/app/websocket/gateway.py`
  (no nested `CLAUDE.md`; outside T3's directory list).
- `App.tsx` — routes: `/login`; `RequireAuth` (token-presence only) → `HostShell` →
  `/home`, `/games`, `/games/:gameId/questions`, `/courses`, `/courses/:courseId/roster`,
  `/sessions`; `/game/:code/{lobby,question,results,gameover}` outside the shell; `*` → `/login`.
- `main.tsx`, `index.css` — React root and Tailwind entry; `index.css` also defines the
  `--pin-*` colour hooks the Pin the Spot board reads (T9).

**How it fits in.** One of three sibling Vite apps under `frontend/` (see `../../CLAUDE.md`).
REST goes to `/api/game/*`, `/api/host/*` and `/api/auth/*` (plus `/api/admin/games/{id}` for
the ADMIN-only delete and attach controls); realtime goes to `/socket.io`. The host shows the
QR code and join URL (`/player/join?code=…`) that bring players into the player app.

**Gotchas.**
- The server drives phase navigation. Pages emit `host_advance` and wait; they never route
  themselves between phases.
- Game, roster and download screens now live **only** here (T4,
  `docs/design-host-admin-restructure.md`); the admin app links/redirects to them. A new question
  type's editor changes go in `pages/manage/QuestionEditorPage.tsx`.
- Reconnect gaps: no `COMPLETED` branch in `sync_state`, and `answeredCount` is not restored.
  Auto-advance is client-only and lost on refresh.
