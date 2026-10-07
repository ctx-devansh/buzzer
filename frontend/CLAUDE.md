# frontend/

**Purpose.** The three browser apps of Buzzer. Each is a separate React 18 + Vite + Tailwind +
react-router project with its own `package.json` and `node_modules`. In the Docker stack,
nginx serves them from one origin.

**Contents.**
| App | Served at (prod / dev port) | Audience | Context |
|---|---|---|---|
| `host/` | `/host/` · 5173 | Instructors: manage games/questions/rosters for HOST courses, download results, run the live game on the projector | `host/src/CLAUDE.md` |
| `player/` | `/player/` · 5174 | Students' phones: join by code, answer | `player/src/CLAUDE.md` |
| `admin/` | `/admin/` · 5175 | Administrators: users, courses, grants, guests, all-hosts sessions; links out to host tools | `admin/src/CLAUDE.md` |

Each `src/` has the same shape: `pages/` (screens; `game/` subfolder for live play in host and
player), `components/ui/` (shadcn-style primitives), `lib/` (`api.ts` + `cn`), and `App.tsx`
(routes, `BrowserRouter basename={BASE_URL}`).

**`theme/` — the one shared folder (T9, `docs/design-better-ui.md`).** Not an app; source only,
imported by all three:
- `tokens.css` — every colour as a semantic CSS variable (RGB channels) for light
  (`:root, [data-theme=light]`) and dark (`[data-theme=dark]`), the density variables
  (`--nb-*`, overridden under `[data-density=compact|projector]`) and the Pin the Spot canvas
  colours. Each app's `src/index.css` `@import`s it first. Its block order and selectors are
  parsed by `tests/unit/test_theme_tokens.py` — keep them.
- `preset.ts` — the Tailwind preset: token colours **replace** Tailwind's palette, radii and
  shadows (so `bg-slate-800`, `rounded-xl`, `shadow-xl` emit nothing), plus a plugin that adds the
  focus/placeholder/checkbox base rules and every `.nb-*` component class (`nb-box`, `nb-press`,
  `nb-selected`, `nb-chip`, `nb-h1/h2/h3`, `nb-body`, `nb-prompt`, `nb-caption`, `nb-stat`,
  `nb-hero`, `nb-code`, `nb-page`, `nb-card`, `nb-stack`). It must import nothing.
- `theme.ts` — the light/dark runtime (`getTheme`, `setTheme`, `subscribe`; OS and cross-tab
  listeners), React-free because `frontend/theme/` has no `node_modules`. Each app's
  `src/lib/theme.ts` adds `useTheme()`; each `index.html` has the first-paint script (same rule,
  keep in sync) and the `theme-color` meta.

**Adding a colour:** define it in both theme blocks of `tokens.css`, add it to `TOKENS` in
`preset.ts`, use it as `bg-<name>`/`text-<name>`, and run `pytest -c pytest.ini tests/unit`.
Never use a raw Tailwind palette class, hex colour, `outline-none` or `focus:ring*` in `src/`:
the scan test fails on them.

**How it fits in.** All three call the FastAPI backend at `/api` (proxied to `:8000` by Vite in
dev, by nginx in Docker; see `nginx/nginx.dev.conf`). Host and player also open Socket.IO at
`/socket.io` for live games. Event names and payloads mirror `backend/app/websocket/`. The host
links into the player app through the join QR code (`/player/join?code=…`); the admin sidebar
links into the host app (`/host/games`, `/host/courses`, `/host/home`) and the player app. The backend's
role checks (`require_admin`, `require_user` plus course/game access in
`backend/app/services/game_service.py`) are the only real authorization. Every frontend route
guard just checks that a token exists.

**Gotchas.**
- **Only `theme/` is shared.** `lib/api.ts`, `lib/utils.ts`, and `components/ui/*` are
  copy-pasted and have drifted: host's `api.ts` is now the fullest (`ApiError` with status), only the player has
  `isTokenExpired`, and admin and host `ui/` files are identical while the player's differ. A
  fix in one app must be applied by hand to the others.
- **One token key, one origin.** All apps use `localStorage.token`. Under nginx they share it,
  so signing in or out in one app affects the others in that browser. Under Vite dev (separate
  ports) they don't.
- **A new question type** touches host (`QuestionPage`, `ResultsPage`, `GameOverPage`,
  `types/game.ts`, and the editor `pages/manage/QuestionEditorPage.tsx`) and player
  (`QuestionPage`, `ResultsPage`, `GameOverPage`, `types/game.ts`), on top of the four backend
  places listed in `backend/app/CLAUDE.md`. The admin app no longer has an editor.
  `pin_the_spot` also has a canvas per app (`player/…/PinCanvas.tsx`, `host/…/PinBoard.tsx`)
  and a geometry helper per app (`lib/pinTheSpot.ts`) — copies, not shared.
- **Library images (T8)** load by URL with no token: each app (host, player) has its own
  `lib/images.ts::imageUrl(id)` → `/api/images/{id}`, and `lib/pinTheSpot.ts::pinImageSrc`
  (library `image_id` first, else `image_url`). Phones get option images and Pin the Spot
  canvases, never prompt images.
- **Theme key.** `localStorage['buzzer-theme']` is one key for all apps; under nginx a toggle in
  one app changes the others (live, via the storage event). No stored value = follow the OS.
- **Build config.** `tsc -b` emits into `node_modules/.tmp` and the scripts pass `--config
  vite.config.ts` / PostCSS points at `tailwind.config.ts`: a stray emitted `.js` config would
  otherwise silently shadow the `.ts` one.
- `npm run dev` at the repo root runs all three via `concurrently`. `npm run build` builds each
  into its own `dist/`, which docker-compose mounts into nginx.
