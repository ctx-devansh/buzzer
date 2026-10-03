# frontend/admin/src/lib/

**Purpose.** Shared helpers for the Admin app: the most complete of the three apps' REST
clients (it includes file upload and download) and the Tailwind class-merging helper.

**Contents.**
- `api.ts` — `api.get/post/put/patch/delete<T>(path, body?)` over `fetch`, prefixing `/api`,
  sending JSON, and attaching `Authorization: Bearer <localStorage.token>`. On non-2xx it throws
  `Error` with FastAPI's string `detail`, else a `BuzzerError`'s `message`, else a 422's
  field-error list flattened by `validationMessage`, else `HTTP <status>`.
  A **401 on a request that sent a token** (outside `/auth/*`) clears the token and
  `location.replace`s to the admin `login` — `RequireAdmin` only checks that a token exists, so
  an expired or leftover one would otherwise strand every page on a 401. An empty body resolves to
  `{}`. Two extras:
  - `api.postForm<T>(path, FormData)` — multipart POST **without** a `Content-Type` header (the
    browser sets the boundary). Used for game JSON import.
  - `api.download(path)` — authenticated GET that reads the filename from
    `Content-Disposition: attachment; filename="…"` (fallback `download`), then saves the blob
    via a temporary `<a download>` and object URL. Used for CSV/HTML/JSON exports.
- `links.ts` — `HOST_APP_URL` and `PLAYER_APP_URL` (the `VITE_*` override, else
  `http://localhost:5173`/`5174` in dev and `/host`/`/player` in a build) for the sidebar's Host tools links, the Courses Roster
  link and `ExternalRedirect`.
- `utils.ts` — `cn(...classes)`: `clsx` + `tailwind-merge`.

**How it fits in.** Every page in `../pages/` calls `api`, almost entirely against
`/api/admin/*` (all `require_admin` on the backend). The exceptions are `LoginPage`
(`/auth/login`) and `SessionsPage`'s delete (`/game/sessions/{id}`). `download` serves
`SessionsPage` (CSV export, HTML report). `postForm` currently has no caller (game import moved
to the host app). `../components/ui/` imports `cn`.

**Gotchas.**
- **Cross-app links in Vite dev.** Under nginx/Docker all apps share one origin, so "Games ↗"
  lands in the host app already signed in. In dev each app has its own port, so the links default
  to `http://localhost:5173` / `5174` (override with `VITE_HOST_APP_URL` / `VITE_PLAYER_APP_URL`)
  and land on that app's login page — the token isn't shared across ports. A bare `/host` path in
  dev would fail silently: it hits the admin dev server (`base: '/'`, only `/api` proxied), matches
  no admin route, and the catch-all sends the user to `/users`.
- `download` needs `Content-Disposition` with a **quoted** filename. The regex is
  `filename="([^"]+)"`, so an unquoted or RFC 5987 `filename*=` header falls back to
  `download` with no extension.
- `download` revokes the object URL right after `a.click()`. That works in current browsers,
  but it is the usual suspect if a download silently fails.
- 401 → login applies to `apiFetch`, `download` and `postForm` alike. `/auth/*` is excluded so a
  wrong password still shows its error on the login page. In the nginx setup clearing the token
  also signs the user out of the host app (shared origin) — correct, since that token is dead
  there too.
- The token key `localStorage.token` is shared with `../App.tsx` (`RequireAdmin`) and
  `../pages/LoginPage.tsx`. In the Docker/nginx setup it is also shared with the host and player
  apps (same origin), so logging in or out in one app affects the others in that browser.
- Copy-pasted across `host`/`player`/`admin` with diverging features. The host copy now also
  has `put`/`patch`/`postForm`/`download` and `ApiError` (status); this copy shares the `message`
  fallback but not `ApiError`, and only this copy redirects on 401.
