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
- `utils.ts` — `cn(...classes)`: `clsx` + `tailwind-merge`.

**How it fits in.** Every page in `../pages/` calls `api`, almost entirely against
`/api/admin/*` (all `require_admin` on the backend). The exceptions are `LoginPage`
(`/auth/login`) and `SessionsPage`'s delete (`/game/sessions/{id}`). `download` serves
`QuestionEditorPage` (game export) and `SessionsPage` (CSV export, HTML report). `postForm`
serves `GamesPage` (import). `../components/ui/` imports `cn`.

**Gotchas.**
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
- Copy-pasted across `host`/`player`/`admin` with diverging features (only this copy has
  `put`/`patch`/`postForm`/`download`). Porting a page to another app means porting these too.
