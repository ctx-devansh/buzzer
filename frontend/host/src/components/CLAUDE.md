# frontend/host/src/components/

**Purpose.** The Host app's management shell plus presentational UI primitives, styled for its
dark slate theme. Primitives live in `ui/`. These are hand-written components in the shadcn style (Tailwind +
`cn`), not a generated shadcn install, and none of them holds game state.

**`HostShell.tsx`.** Layout route for the management pages (`/home`, `/games…`, `/courses…`,
`/sessions`; never the `/game/:code/*` projector screens). Top nav: Play, Games, Rosters,
Sessions, an **Admin console** link (only when `getRole() === 'ADMIN'`), Sign out. It is the
**sole caller of `GET /game/my-courses`** and hands the list to pages via
`<Outlet context={{courses}}>`; pages read it with `useShellCourses()`. Four states:
- *loading* — renders the routed page with `[]` (never the empty state, to avoid flashing "no
  HOST access" at users who have it);
- *403* — the guest-account message, no Retry (a GUEST token can't succeed);
- *other error* — the message plus Retry (this is also how an expired token shows up);
- *resolved* — `[]` for a non-admin shows "ask an administrator" (ADMIN: "No courses exist yet");
  otherwise the page. The `[]` replacement is skipped when `pathname` is **exactly** `/home` or
  `/sessions` (own sessions/live rooms stay reachable); the error states replace every path.

**Contents (`ui/`).**
- `button.tsx` — `Button`: native `<button>` with `variant` (`default` indigo, `outline`,
  `ghost`, `destructive`) and `size` (`sm`/`md`/`lg`); passes through all button props.
- `card.tsx` — `Card`, `CardHeader`, `CardContent`: rounded bordered container plus padded
  sections.
- `input.tsx` — `Input`: full-width styled `<input>`; passes through all input props.
- `TimerBar.tsx` — `TimerBar({ totalSeconds, initialSeconds?, paused? })`: countdown bar that
  ticks every 100 ms against a wall-clock end time, changes colour green → yellow → red as time
  runs out, and freezes while `paused` (resuming continues from the frozen value). Display only:
  the server, not this bar, decides when the answer phase ends.

**`PinBoard.tsx`** — the host's `pin_the_spot` canvas: the image sized to its aspect ratio, plus
optional `taps` and `reveal` (target, filled full-credit circle, dashed zero-credit circle).
Used read-only by `game/QuestionPage` (image only, never taps while open), `ResultsPage` and
the `GameOverPage` card; with `onPick` it is the editor's click/drag target picker. Redraws on
resize and theme changes.

**How it fits in.** `HostShell` wraps the management routes in `../App.tsx`. `ui/` is imported by `../pages/` (Login and Home use Button/Card/Input; the in-game
pages use Button, and `game/QuestionPage.tsx` uses `TimerBar`). Class merging comes from
`../lib/utils.ts`.

**Gotchas.**
- `TimerBar` reads `totalSeconds` and its start value only on mount (its interval effect has
  `[]` deps). The parent **must** remount it per question with `key={questionId}`, as
  `QuestionPage` does, or the bar won't reset.
- `initialSeconds` is how a reconnecting host resumes mid-question. The caller computes it from
  `startedAt` in `sync_state` or from the remaining seconds sent with `question_locked`.
- These files are near-duplicates of `frontend/player/src/components/ui/` (the player's
  `TimerBar` and `button` differ slightly). Admin has no `TimerBar`.
