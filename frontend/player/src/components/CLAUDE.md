# frontend/player/src/components/

**Purpose.** Presentational UI primitives for the Player app, tuned for touch on phones
(bigger padding, `rounded-xl`, press feedback). Everything lives in `ui/`. These are
hand-written shadcn-style components (Tailwind + `cn`), and none of them holds game state.

**Contents (`ui/`).**
- `button.tsx` — `Button`: native `<button>` with `variant` (`default` indigo, `outline`,
  `ghost`, `destructive`) and `size` (`sm`/`md`/`lg`). Adds `active:scale-95` for tap feedback.
- `card.tsx` — `Card` (`rounded-2xl`, translucent slate), `CardHeader`, `CardContent`.
- `input.tsx` — `Input`: full-width styled `<input>` (`rounded-xl`, `py-3`); passes through all
  props.
- `TimerBar.tsx` — `TimerBar({ totalSeconds, paused? })`: countdown bar ticking every 100 ms
  against a wall-clock end time, green → yellow → red, freezing while `paused` and resuming from
  the frozen value. Display only, because the server decides when answering ends.

**`PinCanvas.tsx`** (outside `ui/`, it is a game widget) — the `pin_the_spot` canvas: sized to
the image's aspect ratio (capped at 60% of the viewport, or `maxHeight`), redraws on resize and
theme changes. With `onChange` it is interactive: tap or drag places the pin (pointer capture;
`touch-action: none`), arrow keys nudge (Shift = 5%), Enter calls `onSubmit`. Without it, it is
the read-only result view (`value` = your pin, `reveal` = target and circles).

**How it fits in.** `../pages/JoinPage.tsx` and `NamePage.tsx` use `Button`/`Card`/`Input`.
`../pages/game/QuestionPage.tsx` uses `TimerBar` (with `paused={questionLocked}`).
`game/GameOverPage.tsx` uses `Button`. Note that `QuestionPage` renders its answer buttons
as raw `<button>`s rather than `Button`, to get the coloured option tiles. Class merging comes
from `../lib/utils.ts`.

**Gotchas.**
- `TimerBar` reads `totalSeconds` only on mount (`[]` deps). The parent **must** remount it per
  question with `key={questionId}`, as every branch of `QuestionPage` does.
- Unlike the host `TimerBar`, there is **no `initialSeconds` prop**. A late-joining player
  instead receives a `new_question` whose `timeLimitSeconds` the server has already reduced to
  the remaining time (minimum 5 s; see `backend/app/websocket/gateway.py` join handler). The bar
  therefore starts full and shows the remaining window, not the original one.
- Near-duplicates of `frontend/host/src/components/ui/` and `frontend/admin/src/components/ui/`
  with different radii/padding. Changes don't propagate between apps.
