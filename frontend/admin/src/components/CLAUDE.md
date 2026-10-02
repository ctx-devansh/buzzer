# frontend/admin/src/components/

**Purpose.** Presentational UI primitives for the Admin app, sized for a desktop dashboard
(tighter padding than the player's touch UI). Everything lives in `ui/`. These are hand-written
shadcn-style components (Tailwind + `cn`) with no state or data fetching.

**Contents (`ui/`).**
- `button.tsx` — `Button`: native `<button>` with `variant` (`default` indigo, `outline`,
  `ghost`, `destructive`) and `size` (`sm`/`md`/`lg`); passes through all button props.
- `card.tsx` — `Card`, `CardHeader`, `CardContent`: rounded bordered container plus padded
  sections.
- `input.tsx` — `Input`: full-width styled `<input>`; passes through all props.

**How it fits in.** Used by every page in `../pages/`. Pages layer their own Tailwind on top
for selects, textareas, checkboxes, and tables, because there are no primitives for those, so
form-control styling is repeated inline across pages. Icons come from `lucide-react` directly
in pages. The sidebar layout (`AdminLayout`) and the auth guard (`RequireAdmin`) live in
`../App.tsx`, not here. Class merging comes from `../lib/utils.ts`.

**Gotchas.**
- There is no `TimerBar`, since the admin app has no live-game screens.
- These files are identical to `frontend/host/src/components/ui/{button,card,input}.tsx`
  (verified by diff), so pages can move between admin and host without restyling. The player
  copies differ (larger radii and padding). Keep admin and host in sync if you edit either.
