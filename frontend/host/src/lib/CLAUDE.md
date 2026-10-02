# frontend/host/src/lib/

**Purpose.** Tiny shared helpers for the Host app (the big-screen display): a JSON REST client
for the backend's `/api` routes and the Tailwind class-merging helper used by every UI component.

**Contents.**
- `api.ts` — `api.get/post/delete<T>(path, body?)`, a thin wrapper over `fetch` that prefixes
  `/api`, sends JSON, and attaches `Authorization: Bearer <localStorage.token>` when a token
  exists. On a non-2xx response it throws `Error(detail)` using FastAPI's `{detail}` body (falls
  back to `HTTP <status>`). An empty response body resolves to `{}`.
- `utils.ts` — `cn(...classes)`: `clsx` + `tailwind-merge`, so later Tailwind classes override
  earlier conflicting ones (lets callers pass `className` to override component defaults).

**How it fits in.** `../pages/` calls `api` for everything that happens *outside* a live game
(login, listing the host's courses/games/active sessions, creating/deleting rooms, fetching a
room's title). In-game traffic does not go through here — it uses Socket.IO directly in
`../pages/game/GameLayout.tsx`. `../components/ui/` imports `cn`.

**Gotchas.**
- The auth token lives in `localStorage` under the key `token`. That key is shared knowledge
  between `api.ts`, `../App.tsx`'s `RequireAuth`, `../pages/LoginPage.tsx` and
  `../pages/game/GameLayout.tsx` (socket auth) — there's no single accessor.
- There is no `put`/`patch` method and no 401 handling: an expired token surfaces as a thrown
  error on the calling page, not a redirect to `/login`.
- `api.ts` and `utils.ts` are copy-pasted (not shared) across `host`, `player` and `admin`;
  fixes here don't propagate to the other apps.
