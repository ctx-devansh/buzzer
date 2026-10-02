# frontend/host/src/

**Purpose.** Source of the Host app, the instructor-facing big-screen display served at
`/host/`. Hosts sign in, pick a course and quiz, open a room, and drive a live game that is
projected for the class.

**Contents.**
- `pages/` — the screens. `LoginPage` (NetID SSO or password) and `HomePage` (active sessions
  with rejoin/delete, plus the course + quiz picker that creates a room) run over REST.
  `game/` is the live Socket.IO state machine (Lobby → Question → Results → Game Over), with
  `GameLayout` as the sole socket owner. See `pages/CLAUDE.md`.
- `components/` — `ui/` primitives (`Button`, `Card`, `Input`) plus `TimerBar` for the
  question countdown. See `components/CLAUDE.md`.
- `lib/` — `api.ts` (`get/post/delete` only, Bearer token from `localStorage.token`) and `cn`.
  See `lib/CLAUDE.md`.
- `types/game.ts` — socket payload types mirroring `backend/app/websocket/gateway.py`
  (no nested `CLAUDE.md`; outside T3's directory list).
- `App.tsx` — routes: `/login`, `/home` and `/game/:code/{lobby,question,results,gameover}`
  behind `RequireAuth` (token-presence check only), `*` → `/login`.
- `main.tsx`, `index.css` — React root and Tailwind entry.

**How it fits in.** One of three sibling Vite apps under `frontend/` (see `../../CLAUDE.md`).
REST goes to `/api/game/*` and `/api/auth/*`; realtime goes to `/socket.io`. The host shows the
QR code and join URL (`/player/join?code=…`) that bring players into the player app.

**Gotchas.**
- The server drives phase navigation. Pages emit `host_advance` and wait; they never route
  themselves between phases.
- Host capabilities beyond running a game (editing games, rosters, downloading results) don't
  exist here yet; they live in the admin app. T4 moves them here
  (`docs/design-host-admin-restructure.md`).
- Reconnect gaps: no `COMPLETED` branch in `sync_state`, and `answeredCount` is not restored.
  Auto-advance is client-only and lost on refresh.
- `api.ts` lacks `put`/`patch`/upload/download. Port them from `frontend/admin/src/lib/api.ts`
  before porting any admin page.
