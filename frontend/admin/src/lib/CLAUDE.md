# frontend/admin/src/lib/

**Purpose.** Shared helpers for the Admin app: the most complete of the three apps' REST
clients (it includes file upload and download) and the Tailwind class-merging helper.

**Contents.**
- `api.ts` — `api.get/post/put/patch/delete<T>(path, body?)` over `fetch`, prefixing `/api`,
  sending JSON, and attaching `Authorization: Bearer <localStorage.token>`. On non-2xx it throws
  `Error(detail)` from FastAPI's `{detail}` (or `HTTP <status>`). An empty body resolves to
  `{}`. Two extras:
  - `api.postForm<T>(path, FormData)` — multipart POST **without** a `Content-Type` header (the
    browser sets the boundary). Used for game JSON import.
  - `api.download(path)` — authenticated GET that reads the filename from
    `Content-Disposition: attachment; filename="…"` (fallback `download`), then saves the blob
    via a temporary `<a download>` and object URL. Used for CSV/HTML/JSON exports.
- `links.ts` — `HOST_APP_URL` (`VITE_HOST_APP_URL ?? '/host'`) and `PLAYER_APP_URL`
  (`VITE_PLAYER_APP_URL ?? '/player'`) for the sidebar's Host tools links, the Courses Roster
  link and `ExternalRedirect`.
- `utils.ts` — `cn(...classes)`: `clsx` + `tailwind-merge`.

**How it fits in.** Every page in `../pages/` calls `api`, almost entirely against
`/api/admin/*` (all `require_admin` on the backend). The exceptions are `LoginPage`
(`/auth/login`) and `SessionsPage`'s delete (`/game/sessions/{id}`). `download` serves
`SessionsPage` (CSV export, HTML report). `postForm` currently has no caller (game import moved
to the host app). `../components/ui/` imports `cn`.

**Gotchas.**
- **Cross-app links in Vite dev.** Under nginx/Docker all apps share one origin, so "Games ↗"
  lands in the host app already signed in. In dev each app has its own port: set
  `VITE_HOST_APP_URL=http://localhost:5173` / `VITE_PLAYER_APP_URL=http://localhost:5174` to make
  the links work at all (they then land on the host login page — the token isn't shared across
  ports). **Without them the links fail silently**: `/host/games` hits the admin dev server
  (`base: '/'`, only `/api` proxied), gets the SPA fallback, matches no admin route, and the
  catch-all sends the user to `/users` with no error.
- `download` needs `Content-Disposition` with a **quoted** filename. The regex is
  `filename="([^"]+)"`, so an unquoted or RFC 5987 `filename*=` header falls back to
  `download` with no extension.
- `download` revokes the object URL right after `a.click()`. That works in current browsers,
  but it is the usual suspect if a download silently fails.
- No 401 handling. An expired token (2 h access-token lifetime) shows up as a thrown error on
  whatever page is open, not as a redirect to `/login`.
- The token key `localStorage.token` is shared with `../App.tsx` (`RequireAdmin`) and
  `../pages/LoginPage.tsx`. In the Docker/nginx setup it is also shared with the host and player
  apps (same origin), so logging in or out in one app affects the others in that browser.
- Copy-pasted across `host`/`player`/`admin` with diverging features. The host copy now also
  has `put`/`patch`/`postForm`/`download`, plus `ApiError` (status) and `message` fallback that
  this copy lacks.
