# frontend/player/src/components/

**Purpose.** Presentational UI primitives for the Player app, tuned for touch on phones
(bigger padding, `rounded-xl`, press feedback). Everything lives in `ui/`. These are
hand-written shadcn-style components (Tailwind + `cn`), and none of them holds game state.

**Contents (`ui/`).**
- `button.tsx` — `Button`: as host's (`default`/`secondary`/`outline`/`ghost`/`destructive`, T9
  `nb-box nb-press` styling, press-in tap feedback) with touch sizes: min height 44/48/56 px.
- `card.tsx` — `Card` (`nb-box`), `CardHeader`, `CardContent`.
- `input.tsx` — `Input`: full-width `<input>`, ink outline, `py-3`, `text-base` (16 px, so iOS
  doesn't zoom on focus); passes through all props.
- `TimerBar.tsx` — `TimerBar({ totalSeconds, paused? })`: countdown bar ticking every 100 ms
  against a wall-clock end time, success → warning → danger (seconds beside the bar), freezing while `paused` and resuming from
  the frozen value. Display only, because the server decides when answering ends.

**`PinCanvas.tsx`** (outside `ui/`, it holds input state) — the Pin the Spot board: image
letterboxed into the *stored* aspect, DPR-sharp, redrawn on resize/orientation; one map pin
(tip on the point, head above, flipped below within 40 px of the top). Pointer events with
capture and `touch-action: none`: a tap that starts in the letterbox is ignored, a drag off the
image clamps to its edge, nothing before the image loads. Keyboard (`tabIndex=0`): the first
arrow places the pin at the centre, arrows nudge 0.01 (Shift 0.05), Enter locks in. Read-only
with `reveal` (target and circles) on the results screen. `role="application"` while it takes
input, `role="img"` read-only. `--pin-*` colours (redrawn on theme change); `data-loaded`. Callers pass
`pinImageSrc(config)` (`../lib/pinTheSpot.ts`), so a library `image_id` canvas (T8) loads from
`/api/images/{id}`.

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
