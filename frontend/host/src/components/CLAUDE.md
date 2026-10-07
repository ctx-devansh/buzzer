# frontend/host/src/components/

**Purpose.** The Host app's management shell plus presentational UI primitives, styled for its
T9 token theme (light/dark, `frontend/theme/`). Primitives live in `ui/`. These are hand-written components in the shadcn style (Tailwind +
`cn`), not a generated shadcn install, and none of them holds game state.

**`HostShell.tsx`.** Layout route for the management pages (`/home`, `/games…`, `/courses…`,
`/sessions`; never the `/game/:code/*` projector screens). Top nav: Play, Games, Courses,
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

**`PinBoard.tsx`.** The Pin the Spot canvas: the image letterboxed into the *stored* aspect
(stretched if its natural size differs), DPR-sharp, redrawn on resize. Optional `taps` (the
`"x,y"` distribution; dot radius `base·√count`, capped at `3·base`), `pinKey` (dashed
zero-credit circle, filled full-credit circle, target), and `onPick` (the editor's target
picker: click places, drag moves, a click in the letterbox is ignored, nothing before the image
loads). Shows "Image failed to load" in its box on error. Colours come from `--pin-*` custom
properties (defined in `frontend/theme/tokens.css`; it redraws on theme change via `useTheme`, fills the
image rect with `--pin-image-bg` first so transparent images stay visible, and has an ink `outline`) with fallbacks. `data-loaded` is `'true'` once the image has decoded (e2e waits on it).
Used by `game/QuestionPage` (no taps), `game/ResultsPage`, `game/GameOverPage` and the editor.

**`ImagePicker.tsx`** (T8). A modal over a course's image library (`GET /host/courses/{id}/images`)
with an **Upload new** tab; returns the whole `LibraryImage`, so callers get the id and the size.
Thumbnails are lazy, in fixed boxes. Also exports `uploadToLibrary(courseId, file)`
(`prepareUpload` + `postForm`), which the editor's Pin the Spot "Choose file" uses. Rendered by
`pages/manage/QuestionEditorPage.tsx` only when the game has a course.

**Contents (`ui/`).**
- `button.tsx` — `Button`: native `<button>` with `variant` (`default` accent fill, `secondary`
  pink fill, `outline` surface box, `ghost` no box until hover, `destructive` danger fill) and `size`
  (`sm`/`md`/`lg`); passes through all button props. Boxed variants use `nb-box nb-press` (ink outline,
  hard shadow, lift/press); text on fills is `text-on-fill`; focus is the global outline (T9).
- `card.tsx` — `Card` (`nb-box`: surface, ink outline, hard shadow sized by the page's density),
  `CardHeader`, `CardContent`.
- `input.tsx` — `Input`: full-width styled `<input>`; passes through all input props.
- `TimerBar.tsx` — `TimerBar({ totalSeconds, initialSeconds?, paused? })`: countdown bar that
  ticks every 100 ms against a wall-clock end time, changes colour success → warning → danger as time runs out (the fill has its own ink edge; the
  seconds sit beside the bar in `ink-muted`), and freezes while `paused` (resuming continues from the frozen value). Display only:
  the server, not this bar, decides when the answer phase ends.

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
