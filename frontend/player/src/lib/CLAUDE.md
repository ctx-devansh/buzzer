# frontend/player/src/lib/

**Purpose.** Tiny shared helpers for the Player app (the phone-sized answering UI): a minimal
JSON REST client for the backend's `/api` routes, the Tailwind class-merging helper, and a
client-side JWT expiry check.

**Contents.**
- `api.ts` — `api.get/post<T>(path, body?)` only. A thin wrapper over `fetch` that prefixes
  `/api`, sends JSON, and attaches `Authorization: Bearer <localStorage.token>` when a token
  exists. On a non-2xx response it throws `Error(detail)` from FastAPI's `{detail}` body (or
  `HTTP <status>`). An empty response body resolves to `{}`.
- `utils.ts` — `cn(...classes)` (`clsx` + `tailwind-merge`), plus
  `isTokenExpired(token)`: base64url-decodes the JWT payload **without verifying it** and
  returns true if the token is missing, malformed, or past `exp`.

**How it fits in.** `../pages/JoinPage.tsx` (`GET /game/rooms/{code}/ping`) and
`../pages/NamePage.tsx` (`POST /auth/guest`, `POST /auth/login`) are the only `api` callers.
Gameplay goes over Socket.IO in `../pages/game/GameLayout.tsx`, not through here.
`isTokenExpired` gates `NamePage` (whether to show sign-in options) and `GameLayout` (whether
to connect or bounce back to `/name/:code`). `../components/ui/` imports `cn`.

**Gotchas.**
- `isTokenExpired` is a UX check only. The server still verifies the signature. Don't use it
  for anything security-relevant.
- The token lives in `localStorage.token`, written by `NamePage`/`LoginPage` and read here and
  in `GameLayout`. In the Docker/nginx setup the player, host, and admin apps share one origin,
  so they **share that key**. A host testing as a player on the same browser will overwrite
  their host token (and vice versa).
- `../pages/LoginPage.tsx` calls `fetch('/api/auth/exchange-temp')` directly instead of using
  `api`, because it must send the *temp* token as the bearer, not the stored one.
- `api.ts` and `utils.ts` are copy-pasted across `host`, `player`, and `admin`. Only the
  player's `utils.ts` has `isTokenExpired`, and only admin's `api.ts` has
  `put`/`patch`/`postForm`/`download`.
