# frontend/host/src/components/

**Purpose.** Presentational UI primitives for the Host app, styled for its dark slate theme.
Everything lives in `ui/`. These are hand-written components in the shadcn style (Tailwind +
`cn`), not a generated shadcn install, and none of them holds game state.

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

**How it fits in.** Imported by `../pages/` (Login and Home use Button/Card/Input; the in-game
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
