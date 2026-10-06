# frontend/host/src/lib/

**Purpose.** Small shared helpers for the Host app: the auth-token accessor, a REST client for
the backend's `/api` routes, cross-app links, and the Tailwind class-merging helper.

**Contents.**
- `auth.ts` — the **only** place that touches `localStorage.token`: `getToken`, `setToken`,
  `clearToken`, and `getRole()`, which base64-decodes the JWT payload's `role` claim
  (`ADMIN`/`USER`/`GUEST`) **without verifying it**. `getRole()` is display-only (Admin console
  link, Delete-game button, Attach-to-course control); the server authorises every action.
- `api.ts` — `api.get/post/put/patch/delete<T>(path, body?)` over `fetch`, prefixing `/api`,
  sending JSON and a Bearer token from `getToken()`. Non-2xx throws `ApiError(message, status)`:
  the message is FastAPI's string `detail`, else a `BuzzerError`'s `message`, else a 422's
  field-error list flattened by `validationMessage` (`max_players: Input should be …`), else
  `HTTP <status>`. Two extras ported from admin: `postForm` (multipart, deliberately no
  `Content-Type`) and `download(path)` (reads the quoted `filename="…"` from
  `Content-Disposition`, saves the blob). Both bypass `apiFetch` on purpose.
- `links.ts` — `ADMIN_APP_URL` (`VITE_ADMIN_APP_URL`, else `http://localhost:5175` in dev and
  `/admin` in a build).
- `utils.ts` — `cn(...classes)`: `clsx` + `tailwind-merge`.
- `putInOrder.ts` — `buildPioBars(reveal, distribution, items)` (one bar per correct position,
  counting `"{item}@{position}"` keys; green for ACCURACY, neutral for COMPLETENESS, `[]`
  without `correctOrder`), `pioCaption(reveal)` and `correctOrderText(reveal, items)`. Used by
  `ResultsPage` and `GameOverPage` so the live and game-over charts can't drift.

- `pinTheSpot.ts` — Pin the Spot geometry (`fitRect`, `toFraction`, `aspectOf`, `diagonal`,
  `floor2`, `parseTapKey`, `dotRadius`, `revealKey`) and the editor's slider limits/defaults.
  The player app has its own copy (`frontend/player/src/lib/pinTheSpot.ts`); keep the geometry
  identical.

**How it fits in.** `../pages/` and `../components/HostShell.tsx` call `api` for everything
outside a live game. In-game traffic uses Socket.IO directly in `../pages/game/GameLayout.tsx`
(which takes its socket token from `getToken()`). `../components/ui/` imports `cn`.

**Gotchas.**
- Keep `grep -rn localStorage src` returning hits only in `auth.ts`.
- Never use `getRole()` for a real access decision — that would be a security bug.
- No 401 handling: an expired token surfaces as a thrown error on the calling page (the shell
  shows it with Retry), not a redirect to `/login`.
- In Vite dev the apps run on separate ports, so `ADMIN_APP_URL` defaults to
  `http://localhost:5175` there (a bare `/admin` would hit the host dev server, match no route and
  land on `/login`). The token is per-origin, so the admin app asks you to sign in again.
- `api.ts`/`utils.ts` are still copy-pasted per app; admin's `api.ts` has the same message
  parse (incl. `validationMessage`) but throws plain `Error`s.
