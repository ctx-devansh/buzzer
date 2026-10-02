# frontend/

**Purpose.** The three browser apps of Buzzer. Each is a separate React 18 + Vite + Tailwind +
react-router project with its own `package.json` and `node_modules`. In the Docker stack,
nginx serves them from one origin.

**Contents.**
| App | Served at (prod / dev port) | Audience | Context |
|---|---|---|---|
| `host/` | `/host/` · 5173 | Instructor's projector: pick course + quiz, run the live game | `host/src/CLAUDE.md` |
| `player/` | `/player/` · 5174 | Students' phones: join by code, answer | `player/src/CLAUDE.md` |
| `admin/` | `/admin/` · 5175 | Administrators: users, courses, grants, plus (today) games, rosters, exports | `admin/src/CLAUDE.md` |

Each `src/` has the same shape: `pages/` (screens; `game/` subfolder for live play in host and
player), `components/ui/` (shadcn-style primitives), `lib/` (`api.ts` + `cn`), and `App.tsx`
(routes, `BrowserRouter basename={BASE_URL}`).

**How it fits in.** All three call the FastAPI backend at `/api` (proxied to `:8000` by Vite in
dev, by nginx in Docker; see `nginx/nginx.dev.conf`). Host and player also open Socket.IO at
`/socket.io` for live games. Event names and payloads mirror `backend/app/websocket/`. The host
links into the player app through the join QR code (`/player/join?code=…`). The backend's
role checks (`require_admin`, `require_user` plus course/game access in
`backend/app/services/game_service.py`) are the only real authorization. Every frontend route
guard just checks that a token exists.

**Gotchas.**
- **Nothing is shared between apps.** `lib/api.ts`, `lib/utils.ts`, and `components/ui/*` are
  copy-pasted and have drifted: admin's `api.ts` is the fullest, only the player has
  `isTokenExpired`, and admin and host `ui/` files are identical while the player's differ. A
  fix in one app must be applied by hand to the others.
- **One token key, one origin.** All apps use `localStorage.token`. Under nginx they share it,
  so signing in or out in one app affects the others in that browser. Under Vite dev (separate
  ports) they don't.
- **A new question type** touches host (`QuestionPage`, `ResultsPage`, `GameOverPage`,
  `types/game.ts`), player (`QuestionPage`, `ResultsPage`, `GameOverPage`, `types/game.ts`), and
  admin (`QuestionEditorPage`), on top of the four backend places listed in
  `backend/app/CLAUDE.md`.
- `npm run dev` at the repo root runs all three via `concurrently`. `npm run build` builds each
  into its own `dist/`, which docker-compose mounts into nginx.
