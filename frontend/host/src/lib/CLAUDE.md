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
  the message is FastAPI's string `detail`, else a `BuzzerError`'s `message`, else
  `HTTP <status>`. Two extras ported from admin: `postForm` (multipart, deliberately no
  `Content-Type`) and `download(path)` (reads the quoted `filename="…"` from
  `Content-Disposition`, saves the blob). Both bypass `apiFetch` on purpose.
- `links.ts` — `ADMIN_APP_URL` (`VITE_ADMIN_APP_URL ?? '/admin'`).
- `utils.ts` — `cn(...classes)`: `clsx` + `tailwind-merge`.

**How it fits in.** `../pages/` and `../components/HostShell.tsx` call `api` for everything
outside a live game. In-game traffic uses Socket.IO directly in `../pages/game/GameLayout.tsx`
(which takes its socket token from `getToken()`). `../components/ui/` imports `cn`.

**Gotchas.**
- Keep `grep -rn localStorage src` returning hits only in `auth.ts`.
- Never use `getRole()` for a real access decision — that would be a security bug.
- No 401 handling: an expired token surfaces as a thrown error on the calling page (the shell
  shows it with Retry), not a redirect to `/login`.
- In Vite dev the apps run on separate ports, so `ADMIN_APP_URL` needs
  `VITE_ADMIN_APP_URL=http://localhost:5175`, and even then the token is not shared.
- `api.ts`/`utils.ts` are still copy-pasted per app; admin's `api.ts` reads only `detail` and
  throws plain `Error`s.
