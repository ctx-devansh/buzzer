# Design: UI look-and-feel and theming (T9), neo-brutalist light and dark

Status: **revision 3, revised after two Goldfish passes** (see §9, "Revision log"). Assesses T9 in `instructions.md`,
graded by R9 in `rubric.md`. Owner: one member does all of T9 (no team split for this task).

## 1. Problem

All three frontends (`frontend/host`, `frontend/player`, `frontend/admin`) hardcode one dark slate
palette. Each `src/index.css` sets `body { background:#0f172a; color:#f8fafc }`, and roughly
**860 raw Tailwind palette utilities** (`bg-slate-800`, `text-red-400`, `border-indigo-500`, …) are
spread across **44 files** (host 469 hits / 20 files, player 216 / 14, admin 178 / 10). There is
no theme system, no light theme, no toggle, and no deliberate visual identity.

T9 requires:

1. A semantic color-token layer (CSS variables mapped into each app's Tailwind theme), with **no raw palette
   utilities left outside the token definitions**.
2. Complete **light and dark** themes in all three apps, including the T7/T8 surfaces (question editor,
   Pin the Spot canvases, put-in-order, image picker and library).
3. A visible toggle in every app. The first visit follows `prefers-color-scheme`, and the choice persists across reloads.
4. WCAG 2.1 AA: body text at 4.5:1 or better in both themes, and visible focus states.
5. Context fit: player stays thumb-friendly, the host projector is readable from the back of a room, and admin
   stays information-dense and scannable.
6. Before/after screenshots of key screens in both themes under `docs/ui/`.

The chosen visual direction is **neo-brutalism**.

## 2. Technical plan (summary)

- **Visual language.** Neo-brutalism expressed through *structure*: solid outlines, hard offset shadows with no blur, flat
  saturated fills, almost no rounding, and heavy grotesk display type. The palette is yellow, hot pink and cyan on cream (light).
- **Dark theme.** Built to be *easy on the eyes for long sessions*: soft charcoal instead of black, warm off-white instead
  of white, muted outlines, shadows darker than the canvas, and "dusty" fills. It keeps the structure and lowers the glare.
- **One shared, framework-free theme folder** at `frontend/theme/`: `tokens.css` (CSS variables for both themes),
  `preset.ts` (a Tailwind preset mapping tokens to utilities), and `theme.ts` (read, write and subscribe to the theme
  preference; **no React import**). Each app wraps `theme.ts` in its own `src/lib/theme.ts` with a `useTheme()` hook.
- **Theme switching** uses `data-theme="light|dark"` on `<html>`. An inline script in each `index.html` sets it before first
  paint. `localStorage['buzzer-theme']` is written only when the user toggles. Without a stored value the apps follow the OS, live.
- **Migration is staged so the apps never break.** The preset *adds* the tokens alongside Tailwind's palette while
  pages are migrated. The last migration commit *replaces* the palette and turns on the raw-palette scan test.
- **Enforcement and evidence** come from unit tests in `tests/unit/` (raw-palette scan, WCAG contrast, token parity) and a
  Playwright capture module that writes a defined key-screen set in both themes.

## 3. Alternatives considered

| Alternative | Why it lost |
|---|---|
| Keep Tailwind's default palette and add `dark:` variants everywhere | Fails T9's token requirement outright, and doubles the class count. |
| Copy `tokens.css` and the preset into each app, following the repo's "nothing is shared" convention | The three copies would drift, as `lib/api.ts` and `ui/*` already have. `frontend/theme/` holds only CSS and dependency-free TS, which resolve from any importer. |
| Put `useTheme` (React) in the shared `theme.ts` | Bare imports resolve from the *importing file's* directory. Nothing in `frontend/theme/` or above has `react` (the root `node_modules` has only `concurrently`), so `import 'react'` there fails in both tsc and Vite. The hook lives in each app's `lib/theme.ts`. |
| Share the `ui/` primitives too | The player's primitives are deliberately different (bigger touch targets). Primitives stay per app and only *consume* the shared tokens. |
| Replace Tailwind's palette from the first token commit | Every app would render unstyled until all ~860 edits land, so every intermediate commit is unusable. Replaced with staged extend-then-replace (§5). |
| Dark mode with off-white outlines and shadows on near-black | Most "brutalist", but bright lines on black cause halation and eye strain over long sessions, and it reads as a plain inversion. |
| Dark mode with coloured (accent) shadows | Distinctive, but saturated glow around every element is tiring. Rejected for the same long-session reason. |
| Per-app theme keys (`buzzer-theme-host`, …) | Under nginx all apps share one origin. A single key matches how the auth token is already shared. |
| `@import` Google Fonts | The app may run on a classroom LAN without internet. Fonts are self-hosted through `@fontsource`. |
| Host result bars in option colours | Today the bars encode *correctness* (correct green, wrong slate, no-key indigo), not option identity, and `option-4` is close to `success`. Keeping the correctness encoding, plus a non-colour ✓ cue, is clearer (§4.8). |
| Recapture all ~95 before-screens in both themes | No capture tooling exists for the before set. A defined key-screen set (§4.6) is enough evidence for R9 and is scripted end to end. |

## 4. Design detail

### 4.1 Visual language

| Element | Rule |
|---|---|
| Outline | Solid `border-line` on every card, input, button, table and tile. Width by density: **admin 2px, player and host-manage 3px, host projector 4px**. |
| Shadow | Hard offset, no blur, colour `shadow` token: `brutal-sm` 2px 2px, `brutal` 4px 4px, `brutal-lg` 6px 6px. Admin uses shadows only on interactive elements and cards, **not** table rows. |
| Press | Interactive elements with a shadow translate by the shadow offset and drop the shadow on `:active`, so they feel "pushed in". Under `prefers-reduced-motion: reduce`, nothing transitions; the shadow simply disappears. Offsets come from density variables (§4.3.1), so one `.nb-press` class works at every size. |
| Density | One set of component classes, three densities set by CSS variables on a root element: **compact** (admin), **comfortable** (player, host manage; the default) and **projector** (host `/game/:code/*`). See §4.3.1. |
| Radius | `rounded-none` by default. Up to 4px is allowed only on small chips and badges. |
| Fills | Flat. No gradients. Coloured fills are for buttons, option tiles, badges and bars, never large page areas. |
| Text on fills | Always `text-on-fill` (dark in **both** themes), never white. That keeps every fill at AA or better. Text that sits *beside* a fill (not on it) uses `ink`/`ink-muted`. |
| Type | Display face **Space Grotesk 700** for headings, numbers, scores, room codes and button labels. **`font-display` always means weight 700.** The `fontFamily.display` entry can't carry a weight, so every `font-display` use pairs with `font-bold`, or comes through a class that sets it. The scan forbids `font-display` alongside `font-normal`, `font-medium` or `font-semibold`. Body face **Inter 400/500/600/700** (700 so `font-bold` is real bold, not faux-bold). Both come from `@fontsource`. Scores and timers use `tabular-nums`. |
| Weight mapping | `font-black` (24 uses today) on headings, scores and room codes → `font-display` (Space Grotesk 700). Any other `font-black` → `font-bold`. After migration, `font-black` and `font-extrabold` appear nowhere (the scan test checks this, since those weights aren't loaded). `font-bold` on headings may become `font-display`; on body text it stays Inter 700. |
| Focus | `:focus-visible` gives a 3px solid `focus` outline with a 2px offset, defined in each app's `@layer base` (§4.3). It is **enforced, not just stated**: all 15 `focus:outline-none` and all 40 `focus:ring*`/`ring-offset*` classes are deleted during migration, and the scan forbids `outline-none`, `focus:ring`, `focus-visible:ring` and `ring-offset` from then on. Why the deletion is required: a utility like `focus:outline-none` (specificity 0,1,1) beats a bare `:focus-visible` rule (0,1,0) no matter where that rule sits, so any surviving `outline-none` silently removes the focus state. |
| Status meaning | Colour never carries meaning alone. Right/wrong pairs colour with an icon or word (✓/✗, "Correct"). Option tiles carry a letter (A, B, …) as well as their colour. |

### 4.2 Tokens

Tokens are CSS variables holding **space-separated RGB channels** (`--accent: 255 214 10;`), so Tailwind can use
`rgb(var(--accent) / <alpha-value>)` and opacity modifiers (`bg-accent/40`) keep working. The values below are the
**starting values**. The contrast test (§4.6) is the authority, and any value it rejects gets adjusted, with the change
recorded in this doc.

| Token | Role | Light | Dark |
|---|---|---|---|
| `canvas` | page background | `#FFF8E7` cream | `#1B1C20` charcoal |
| `surface` | cards, panels, inputs | `#FFFFFF` | `#24262B` |
| `surface-muted` | stripes, disabled, wells, timer track | `#F3EBD6` | `#2E3036` |
| `ink` | primary text | `#121212` | `#E8E4DA` warm off-white |
| `ink-muted` | secondary text | `#4A4640` | `#B5B0A5` |
| `line` | outlines and dividers (also the default border colour) | `#121212` | `#8A857B` muted warm grey |
| `shadow` | hard shadows | `#121212` | `#0D0D0F` (darker than canvas) |
| `scrim` | modal backdrop, used at `/60` | `#121212` | `#0D0D0F` |
| `on-fill` | text and icons on any coloured fill | `#121212` | `#16171A` |
| `accent` | primary action (yellow) | `#FFD60A` | `#D9B93F` |
| `accent-2` | secondary highlight (pink) | `#FF6FB5` | `#D98AAE` |
| `info` | info fill (cyan) | `#3DD6F5` | `#6EC1D1` |
| `success` | correct, positive fill | `#7BE07B` | `#86C48A` |
| `danger` | wrong, destructive fill | `#FF5A5F` | `#E07A7A` |
| `warning` | caution fill | `#FFA94D` | `#D9A066` |
| `success-text` | success text on canvas/surface | `#1E6B2A` | `#A8DDAB` |
| `danger-text` | error text on canvas/surface | `#B3261E` | `#F2A7A7` |
| `warning-text` | warning text on canvas/surface | `#8A4B00` | `#F0C48F` |
| `focus` | focus outline | `#2B59FF` | `#8FB0FF` |
| `option-1…8` | answer-tile fills (with `on-fill` text) | `#FFD60A #FF6FB5 #3DD6F5 #7BE07B #FFA94D #B79CFF #C8F169 #FF8A65` | `#D9B93F #D98AAE #6EC1D1 #86C48A #D9A066 #A99BD9 #B5CF7A #D98C73` |
| `qr-bg` | QR code backing box (§4.7) | `#FFFFFF` | `#FFFFFF` (intentionally not themed) |
| `image-bg` | backing behind every uploaded image (§4.9) | `#FFFFFF` | `#EDE9E0` (light on purpose, slightly softened) |
| `pin-*` | canvas colours (§4.5) | in `tokens.css` | in `tokens.css` |

Rules for using tokens:
- **Fill tokens (`accent`, `success`, `danger`, …) are never used as text colours.** Status text uses `*-text` tokens.
  Example: `text-red-400` error messages become `text-danger-text`.
- **Never use `ink` as a backdrop or overlay.** It's off-white in dark mode. Scrims use `bg-scrim/60`.
- **No opacity modifiers on fill tokens** (`accent`, `accent-2`, `info`, `success`, `danger`, `warning`, `option-1…8`). For
  example, `bg-accent/40` is not allowed. A translucent fill blends with whatever sits underneath it, so the contrast test can't
  vouch for text on it. The scan enforces this. Opacity is allowed only on `scrim`, `surface*`, `ink*` and `shadow`.
- **Any element with a fill-token background sets `text-on-fill` explicitly.** That includes the admin sidebar's active item,
  chips, badges, tiles and buttons. Inheriting `ink` would give about 1.7:1 on dark `accent`.
- In light mode the fills are pale against the cream canvas (yellow vs cream is 1.3:1). That's fine because every filled
  element carries a `line` outline, and the outline carries the WCAG 1.4.11 non-text contrast. **A fill without an outline is
  not allowed.**
- `line` in dark mode must stay at **3:1 or better against `canvas`, `surface` and `surface-muted`**.

Contrast at the starting values (computed with the WCAG 2.1 formula):

| Pair | Light | Dark |
|---|---|---|
| `ink` on canvas / surface / surface-muted | 17.7 / 18.7 / 15.8 | 13.4 / 11.9 / 10.4 |
| `ink-muted` on canvas / surface / surface-muted | 8.9 / 9.4 / 7.9 | 7.9 / 7.0 / **6.1** |
| `on-fill` on fills (lowest) | 6.1 (danger) | 6.2 (danger) |
| `*-text` on canvas/surface/surface-muted (lowest) | 5.5 | 6.8 |
| `line` on canvas / surface | n/a (ink) | 4.6 / 4.1 |
| `focus` on canvas / surface | 5.0 / 5.3 | 8.0 / 7.1 |

Every pair clears AA. The lowest text pair is dark `ink-muted` on `surface-muted`, at 6.1.

### 4.3 Tailwind mapping (`frontend/theme/preset.ts`)

`preset.ts` exports two plain objects. It **must not import anything**, including `import type` from `tailwindcss`,
because `frontend/theme/` has no `node_modules`. Each app's `tailwind.config.ts` applies `satisfies Config`.

- `tokenColors`: every token above under its kebab-case name (`canvas`, `surface`, `surface-muted`, `ink`, `ink-muted`,
  `line`, `shadow`, `scrim`, `qr-bg`, `image-bg`, `on-fill`, `accent`, `accent-2`, `info`, `success`, `danger`, `warning`, `success-text`,
  `danger-text`, `warning-text`, `focus`, `option-1`…`option-8`), each as `rgb(var(--<name>) / <alpha-value>)`.
- `preset`: the Tailwind preset:
  - `theme.colors` / `theme.extend.colors`: see "staging" below.
  - **Defaults that Tailwind derives from the palette, set explicitly** (otherwise replacing the palette makes a bare
    `border` fall back to `currentColor`, which is off-white in dark mode and causes the halation this design rejects):
    `borderColor.DEFAULT = line`, `divideColor.DEFAULT = line`, `ringColor.DEFAULT = focus`,
    `outlineColor.DEFAULT = focus`, `ringOffsetColor.DEFAULT = canvas`. (51 bare `border`/`border-x` uses exist today.)
    `ringOffsetColor` matters because Tailwind's own default is `#fff`, which would show as a white halo in dark mode.
  - **Placeholders are not covered by the preset.** Tailwind 3's preflight hardcodes
    `input::placeholder, textarea::placeholder { color: theme('colors.gray.400', #9ca3af) }` (`tailwindcss/src/css/preflight.css`
    around line 333), and `placeholderColor.DEFAULT` doesn't feed it. Once the palette is replaced, that becomes `#9ca3af`, about
    2.5:1 on white, which fails AA. So `tokens.css` sets `::placeholder { color: rgb(var(--ink-muted)); opacity: 1; }`, which covers
    every raw page `<input>`/`<textarea>` (11 raw `<textarea>`/`<select>` exist outside the primitives).
  - `extend.boxShadow`: `brutal-sm`, `brutal`, `brutal-lg` (hard offsets in `rgb(var(--shadow))`).
  - `extend.borderWidth`: `3`.
  - `extend.fontFamily`: `display: ['"Space Grotesk"', 'system-ui', 'sans-serif']`, `sans: ['Inter', 'system-ui', 'sans-serif']`.

**Staging (the apps stay usable during migration):**
- **Steps 2–4:** the preset uses `theme.extend.colors = tokenColors`. Tailwind's palette still exists, so unmigrated pages render as
  they do today, and migrated pages use tokens. The scan test is `xfail(strict=True)`.
- **Final commit of step 4:** switch to `theme.colors = { transparent, current, inherit, ...tokenColors }` (replace), and remove
  the `xfail` in the **same commit**. From then on, a leftover palette class produces no CSS and fails the scan.

`frontend/theme/tokens.css` also defines, outside Tailwind:
- `:root, [data-theme=light] { color-scheme: light }` / `[data-theme=dark] { color-scheme: dark }`, so native scrollbars and form controls follow.
- `body { background: rgb(var(--canvas)); color: rgb(var(--ink)); }`. This replaces the hardcoded body colours in each `index.css`.
- `::placeholder { color: rgb(var(--ink-muted)); opacity: 1; }`. See above.
- `<meta name="theme-color">` is not set in CSS. Each `index.html` carries two of them,
  `<meta name="theme-color" media="(prefers-color-scheme: light)" content="#FFF8E7">` and the dark one with `#1B1C20`, and
  `theme.ts` updates a single un-media'd `theme-color` meta on every `setTheme` and attribute change, so mobile browser chrome
  matches the chosen theme rather than only the OS setting.

Each app's `src/index.css` (same block in all three, under 40 lines, every value a token or density variable):
- **`@layer base`** (after `@tailwind base`): `:focus-visible { outline: 3px solid rgb(var(--focus)); outline-offset: 2px; }`.
  It lives here, not in `tokens.css`. `tokens.css` is `@import`ed before `@tailwind base`, so preflight would follow it. Putting it
  in `@layer base` places it after preflight and before every utility. Utilities still beat it, which is why the deletions and the
  scan rule in §4.1 are what really guarantee focus visibility.
- **`@layer components`** (after `@tailwind components`): `.nb-box`, `.nb-press` and `.nb-chip`, all reading the density variables
  below. `@layer` needs the Tailwind directives in the same file, which is why these aren't in `tokens.css`.

#### 4.3.1 Density variables

`tokens.css` defines three non-colour variables on `:root` (the comfortable defaults) and overrides them under `[data-density]`:

| Variable | compact (`[data-density=compact]`) | comfortable (default) | projector (`[data-density=projector]`) |
|---|---|---|---|
| `--nb-border` | 2px | 3px | 4px |
| `--nb-offset` | 2px | 4px | 6px |

- `.nb-box`: `background: rgb(var(--surface)); border: var(--nb-border) solid rgb(var(--line)); box-shadow: var(--nb-offset) var(--nb-offset) 0 0 rgb(var(--shadow));`
- `.nb-press`: `transition: transform 80ms, box-shadow 80ms;` and on `:active`, `transform: translate(var(--nb-offset), var(--nb-offset)); box-shadow: none;`.
  Under `prefers-reduced-motion: reduce`, `transition: none`.
- `.nb-chip`: `border: 2px solid rgb(var(--line))`, small padding, `rounded` (4px), and `font-semibold text-sm`. It has no shadow, at any density.
- Where `data-density` is set:
  - **admin:** `<div data-density="compact">` at the root of `AdminLayout` and `LoginPage`;
  - **host projector:** the root element of `pages/game/GameLayout.tsx`;
  - **player and host manage:** nothing (comfortable).
- The `shadow-brutal-sm/-/lg` utilities stay available for one-off elements that sit outside `.nb-box`, but primitives use
  `.nb-box`/`.nb-press` so density follows automatically.

#### 4.3.2 `cn()` / tailwind-merge

Each app's `lib/utils.ts` `cn()` uses `twMerge` (tailwind-merge ^2.5). It doesn't know the custom shadow keys. It classifies
`shadow-brutal*` as a shadow-**colour** class, so `cn('shadow-brutal', 'shadow-none')` keeps both, and a colour-like class would
knock out `shadow-brutal`. Replace `twMerge` with `extendTailwindMerge({ extend: { classGroups: { shadow: [{ shadow: ['brutal-sm', 'brutal', 'brutal-lg'] }] } } })`
in all three `lib/utils.ts`. Check during step 3, with a quick assertion in the browser console or a scratch call, that these
resolve as expected: `cn('shadow-brutal','shadow-none') === 'shadow-none'`, `cn('border-2','border-3') === 'border-3'`, and
`cn('font-sans','font-display') === 'font-display'`. If `border-3` or `font-display` misbehave, register them the same way.

### 4.4 Theme mechanics

- **Attribute:** `<html data-theme="light">` or `"dark"`. `tokens.css` defines light values on `:root, [data-theme=light]`
  and dark values on `[data-theme=dark]`.
- **No-flash init:** an inline `<script>` in the `<head>` of each `frontend/*/index.html`, before the module script:
  read `localStorage['buzzer-theme']` (wrapped in try/catch); if it's `'light'` or `'dark'`, use it; otherwise use
  `matchMedia('(prefers-color-scheme: dark)').matches`. Then set `document.documentElement.dataset.theme`. This is
  the only logic duplicated outside `theme.ts`, and both places carry a comment pointing at each other. No CSP exists, so
  an inline script is allowed.
- **`frontend/theme/theme.ts`** is dependency-free. **It owns all listeners and the attribute.**
  - `getTheme(): 'light' | 'dark'` reads `document.documentElement.dataset.theme`.
  - `getStoredTheme(): 'light' | 'dark' | null` (try/catch).
  - `setTheme(t)` sets the attribute, writes `localStorage['buzzer-theme']`, and notifies subscribers.
  - `subscribe(cb): () => void` adds a listener and returns an unsubscribe function.
  - **Module-level listeners, installed once when the module is first imported:**
    - a `matchMedia('(prefers-color-scheme: dark)')` `change` listener. **If `getStoredTheme()` is null**, it *sets the
      attribute* to the OS value and then notifies. Otherwise it does nothing.
    - a `window` `storage` listener for key `buzzer-theme`. It *sets the attribute* to the new value (or, if the value was
      removed, to the OS value) and then notifies. This keeps other tabs and apps on the same origin in sync.
  - **No "follow system" option after toggling (intended).** Once a user toggles, the stored choice wins until storage is
    cleared. The toggle is a two-state light/dark button. This is deliberate, for simplicity. T9 only requires that the
    OS is the default on first visit.
- **Per-app `src/lib/theme.ts`:** re-exports `getTheme`/`setTheme` from `'../../../theme/theme'` and defines
  `useTheme(): ['light'|'dark', (t) => void]` with React's `useSyncExternalStore(subscribe, getTheme)`.
  Components import only from `lib/theme`.
- **Shared key:** `buzzer-theme` is one key for all three apps. Under nginx (:8080), toggling in one app changes all of them in that
  browser (live, through the storage listener). Under `npm run dev` each port has its own storage.
- **Host's localStorage rule:** `frontend/host/src/lib/CLAUDE.md` says to keep `localStorage` hits only in `auth.ts`. Update the rule
  to name `buzzer-theme` in `frontend/theme/theme.ts` as the single exception.
- **Toggle component:** each app gets `src/components/ThemeToggle.tsx`. It's a `<button type="button">` with a **fixed**
  accessible name, `aria-label="Dark theme"`, and `aria-pressed={theme === 'dark'}`. This is the conventional toggle-button
  pattern: the name doesn't change and the state is carried by `aria-pressed`. It has a sun/moon glyph (`aria-hidden`) and
  `nb-box nb-press` styling. The visible text label "Dark theme", where width allows, matches the accessible name. Placement:
  - **Host:** right side of the `HostShell` top nav, before Sign out. On `LoginPage`, top-right of the page. On the `/game/:code/*`
    projector screens (outside the shell), a small fixed top-right button rendered once in `pages/game/GameLayout.tsx`. It must not
    overlap the corner QR code that `GameLayout` renders (§4.7); place it on the opposite side from the QR code, or stack them.
  - **Player:** a **normal in-flow header row** rendered once in `App.tsx` above `<Routes>`. It's a 56px-tall bar holding only the
    toggle (44×44 or larger, right-aligned). It isn't a fixed overlay, so no page needs to reserve padding. The
    "Host disconnected" banner in `pages/game/GameLayout.tsx` (currently `fixed top-0 … z-50`) becomes an **in-flow** block, so it
    appears directly below the header without covering the toggle.
  - **Admin:** sidebar footer above Logout, and top-right on `LoginPage`.

### 4.5 Canvases (Pin the Spot, T7)

`host/src/components/PinBoard.tsx` and `player/src/components/PinCanvas.tsx` already read `--pin-*` variables through
`getComputedStyle` (helper `cssVar`), but only while drawing. Changes:
- Move **all** the `--pin-*` definitions out of each app's `index.css` into `tokens.css`, with light and dark values. The full set is
  `--pin-letterbox`, `--pin-placeholder`, `--pin-full`, `--pin-full-fill`, `--pin-zero`, `--pin-target`, `--pin-tap`, and
  `--pin-tap-stroke` (host), plus `--pin-head` and `--pin-stem` (player). Add a new `--pin-marker-stroke`.
  - `--pin-letterbox` and `--pin-placeholder` follow the theme (canvas and surface-muted values).
  - New **`--pin-image-bg`** (equal to `image-bg`, §4.9): fill the image's destination rectangle with it *before* `drawImage`, so a
    transparent Pin the Spot image sits on a light backing inside the themed letterbox.
  - The marker colours must stay visible on arbitrary *photos*, so they stay saturated in both themes and rely on a contrasting
    stroke, not on the page theme.
- These stay as **full colour strings** (`#4ade80`, `rgba(…)`), not RGB channels, because canvas `fillStyle` needs a
  complete colour. Document this exception in `tokens.css`.
- Replace both literal `'#ffffff'` strokes with `cssVar(canvas, '--pin-marker-stroke', '#ffffff')`: **`PinBoard.tsx:143`** (target
  marker) and **`PinCanvas.tsx:169`**. The `cssVar` fallback literals stay; they're defaults for a missing variable, not styling.
- **Redraw on theme change:** in both components, read `const [theme] = useTheme()` and add `theme` to the dependency list of
  the draw `useEffect`, so toggling repaints the canvas.
- `host/src/lib/imageFile.ts`'s `'#ffffff'` is the JPEG flatten background for uploads, not UI. It's exempt, and the scan test
  allow-lists that file.

### 4.6 Tests and evidence

**`tests/unit/test_theme_tokens.py`** (pure Python, no Docker, runs in the existing `tests/unit` collection):
1. *Raw-palette and class-rule scan* (`xfail(strict=True)` until the final step-4 commit). Walk
   `frontend/{host,player,admin}/src/**/*.{ts,tsx,css}` and fail with file:line for:
   - any Tailwind utility with a default palette name, including side-specific borders and any variant prefix:
     `\b(bg|text|border(-[trblxyse])?|ring|ring-offset|outline|from|via|to|fill|stroke|divide|placeholder|accent|caret|decoration|shadow)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)\b`
     (this catches `bg-white`, `text-black` and `border-t-slate-700`);
   - focus removal and rings: `\boutline-none\b`, `\b(focus|focus-visible|focus-within):ring\b`, `\bring-offset\b` (§4.1);
   - opacity on fill tokens: `\b(bg|border|text)-(accent|accent-2|info|success|danger|warning|option-\d)/\d+` (§4.2);
   - `font-black` or `font-extrabold` (weights that aren't loaded), and `font-display` on the same line as
     `font-(normal|medium|semibold)` (§4.1);
   - CSS named colours in string literals or JSX attributes in `.ts`/`.tsx`:
     `(['"])(white|black|red|green|blue|yellow|gray|grey|orange|purple|pink)\1` and
     `\b(fill|stroke|color)=\{?["'](?!currentColor|none)[a-z]+["']`, apart from the allow-list below;
   - any hex colour `#[0-9a-fA-F]{3,8}\b` or `rgb(`/`rgba(`/`hsl(` literal in `.ts`/`.tsx`, **except** as the fallback
     argument of a `cssVar(…)` call, and in the allow-listed `host/src/lib/imageFile.ts`;
   - any hex colour in `index.css` (they may only use `var(--…)`).
2. *Contrast* (always on). Parse `frontend/theme/tokens.css` into the `light` and `dark` maps (RGB-channel tokens only; `--pin-*`
   are skipped) and assert, for each theme:
   - `ink` and `ink-muted` on `canvas`/`surface`/`surface-muted` ≥ 4.5;
   - `on-fill` on `accent`, `accent-2`, `info`, `success`, `danger`, `warning` and `option-1…8` ≥ 4.5 (only opaque fills are
     tested, which is why opacity on fills is banned);
   - `*-text` on `canvas`/`surface`/`surface-muted` ≥ 4.5;
   - `line` on `canvas`/`surface`/`surface-muted` ≥ 3.0;
   - `focus` on `canvas`/`surface` ≥ 3.0.

   Use the WCAG 2.1 relative-luminance formula. On failure, report the pair and the ratio.
3. *Token parity* (always on). Every variable defined for light is defined for dark, and the reverse.

**Screenshot capture: `tests/e2e/capture_ui_screens.py`.** It's deliberately *not* named `test_*`, so the normal `pytest` run
doesn't collect it. Run it explicitly: `npm run build && pytest tests/e2e/capture_ui_screens.py`, against the Docker stack (nginx
:8080). It reuses the existing e2e fixtures in `tests/e2e/conftest.py`: `api`, `admin_token`, `env` (a course plus host user),
`page_as`, and `cleanup` (which deletes everything it created).

- **Fixture game.** Created through the REST API in the module: one game in the `env` course with one question of every type:
  multiple choice with option images, true/false with a prompt image, fill in the blank, multi-select, put in order, Pin the
  Spot (library image), and a COMPLETENESS multiple choice. Images are uploaded to the course library from
  `sample_games/` assets or generated in memory with Pillow (already used by `scripts/make_pin_images.py`).
- **Entry point.** The module defines one function, `test_capture_ui_screens(theme, …fixtures)`, parametrized over
  `theme in ('light', 'dark')`, so pytest collects it when the file is passed explicitly. It holds no assertions beyond "the page
  reached the expected state". Each parametrized run is a **full, separate game in its own room**: two rooms in total.
- **Driving the game.** One host page (1920×1080) and three guest player pages (390×844, device scale 2) through `page_as`.
  One player answers correctly and one incorrectly, so both results states exist.
- **Keeping timers from expiring between shots.** The fixture game's questions use `time_limit_seconds = 600`, so nothing expires
  while screenshots are taken. Screens that need the "locked" state are reached through the host's existing lock control, not by
  waiting for the timer. The shots are taken, then the host advances.
- **Theme.** Set `localStorage['buzzer-theme']` with `context.add_init_script` before the first navigation, in every page of that run.
  Before each shot, wait for `[data-loaded=true]` on canvases and for fonts (`document.fonts.ready`).
- **Output:** `docs/ui/after/<theme>/<app>/<NN-screen>.png`.

**Key-screen set** (30 screens × 2 themes = 60 images):

| App | Screens |
|---|---|
| Player (390×844) | 01 join, 02 name (guest), 03 lobby, 04 question MC with images, 05 true/false, 06 fill in the blank, 07 multi-select, 08 put in order, 09 Pin the Spot with pin placed, 10 feedback (answer locked in), 11 results correct, 12 results incorrect, 13 game over |
| Host projector (1920×1080) | 14 lobby with QR code, 15 question MC with prompt image, 16 question Pin the Spot, 17 results MC bars, 18 results Pin the Spot taps, 19 game over |
| Host manage (1440×900) | 20 login, 21 home (play), 22 games, 23 question editor (Pin the Spot target picker), 24 image library, 25 image picker modal, 26 roster, 27 sessions |
| Admin (1440×900) | 28 users, 29 user detail, 30 sessions |

**`docs/ui/README.md`**: one row per key screen, with *before* (the matching file from `docs/ui/before/` where one exists, which is
dark-only, since that was the only theme), *after light* and *after dark* side by side, plus a short paragraph on the design language.
The T10 document links it.

**Existing tests:** `tests/e2e` has no selectors on colour classes (checked by grep). They must stay green.

### 4.7 QR codes and the player viewport

- **QR codes** (`QRCodeSVG` in `host/src/pages/game/LobbyPage.tsx:26`, 200px, and `GameLayout.tsx:243`, 96px) stay
  **dark-on-light in both themes**, for scanning reliability. Keep the library defaults (black modules on white), and wrap each SVG
  in a `bg-qr-bg p-3 border-4 border-line shadow-brutal` box. The `qr-bg` token is `#FFFFFF` in both themes, so the box stays white in
  dark mode. The QR codes are never inverted. The contrast test skips `qr-bg`, since no text sits on it.
- **Player viewport** (`frontend/player/index.html:5`), currently
  `width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no`, changes to
  `width=device-width, initial-scale=1.0, viewport-fit=cover`:
  - `viewport-fit=cover` is required for `env(safe-area-inset-*)` to be non-zero. The header row and bottom action areas pad by it.
  - Removing `maximum-scale`/`user-scalable=no` restores pinch-zoom (WCAG 1.4.4 Resize Text, AA).
  - **Side effects to handle:** iOS zooms on focus for inputs below 16px, so every player `<input>` uses `text-base` or larger.
    Double-tap zoom on answer tiles and the Pin the Spot canvas is prevented with `touch-action: manipulation`, which doesn't
    disable pinch-zoom.

### 4.8 Host answer bars: one encoding on ResultsPage *and* GameOverPage

Today the two pages disagree:
- `ResultsPage.tsx` around line 131 uses green (correct), slate (wrong) and indigo (no key).
- `GameOverPage.tsx` uses green/indigo at :180, green/slate at :210, green/**red-700** at :226 (so wrong is red here), plus an
  indigo score histogram at :337.

The themed version uses **one encoding on both pages** (decided: wrong is muted, not red):

| Bar state | Fill | Outline | Extra cue |
|---|---|---|---|
| correct | `bg-success` | `border-4 border-line` (projector density) | "✓ Correct" chip: `nb-chip bg-success text-on-fill` |
| wrong | `bg-surface-muted` | `border-2 border-line` | none (the absence of ✓ is the cue) |
| no key (`correct === null`, polls / put-in-order distribution) | `bg-accent` | `border-2 border-line` | none |
| GameOver score histogram (:337) | `bg-accent` | `border-2 border-line`, no rounding | none |

- To keep both pages in step, factor the class choice into one helper, `barClasses(correct: boolean | null)`, in
  `host/src/lib/answerBars.ts`. Both pages call it instead of choosing colours inline (`colorClass={…}` at GameOver :180/:210/:226
  and `barColor` in ResultsPage). GameOverPage gets the same ✓ chip as ResultsPage.
- Inline "correct" text (`text-green-400` at ResultsPage :81, :96, :350, and the equivalents in GameOverPage) becomes
  `text-success-text font-semibold`.
- Option colours are **not** used on host bars.

### 4.9 Uploaded images (T8) on dark surfaces

`prepareUpload` (`host/src/lib/imageFile.ts`) keeps PNG, GIF and WebP alpha channels. So a black line drawing on a transparent
background vanishes on the charcoal surface. **Decision: every image well has a fixed light backing in both themes.**
- Every `<img>` that shows an uploaded or library image sits on `bg-image-bg`, set either on the `<img>` itself or on its fixed-size box. That
  covers option tiles (host and player `QuestionPage`), the prompt image (host `QuestionPage`, `ResultsPage`, `GameOverPage`), the library
  grid (`ImagesPage`), `ImagePicker` thumbnails, and the editor previews in `QuestionEditorPage`. That's the 13 `<img>` sites today.
  `object-contain` letterboxing then shows `image-bg`, not the page surface.
- The well keeps its `border-line` outline, so the light box reads as a deliberate frame in dark mode.
- Pin the Spot canvases fill the image rectangle with `--pin-image-bg` before drawing (§4.5).
- `image-bg` is softened in dark mode (`#EDE9E0`) to limit glare. It's skipped by the contrast test, since no text sits on it.

## 5. Implementation steps (in order)

Each step is one or more atomic commits on `feature/better-ui`. **This doc and `docs/ui/before/` are committed before step 1**
(T3/R4: design before implementation).

**Step 1: Shared folder and build-config fixes (one app first, then the other two).**
- **Stop `tsc -b` from emitting config JavaScript.** Today `tsc -b` writes untracked (gitignored) `tailwind.config.js`,
  `vite.config.js` and `.d.ts` files next to the `.ts` configs, and **both Tailwind 3 and Vite load the `.js` before the `.ts`**.
  Edits to `tailwind.config.ts` or `vite.config.ts` are silently ignored under `npm run dev` until the next build. Adding
  `../theme/preset.ts` to the composite project would also emit `frontend/theme/preset.js` and `preset.d.ts`.
  - Fix: in each `tsconfig.node.json`, add `"noEmit": true` (allowed with `composite` in TS ≥ 5.6; the repo has 5.9.3) and
    `"tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo"`. Then delete the stale `tailwind.config.{js,d.ts}` and
    `vite.config.{js,d.ts}` in all three apps, once.
  - Belt and braces: `postcss.config.js` → `tailwindcss: { config: './tailwind.config.ts' }`; `package.json` scripts →
    `"dev": "vite --config vite.config.ts"`, `"build": "tsc -b && vite build --config vite.config.ts"`.
  - Add `frontend/theme/*.js` and `frontend/theme/*.d.ts` to `.gitignore`, in case anything ever emits there.
  - Fallback, if `noEmit` with `composite` is rejected: `"outDir": "./node_modules/.tmp/tsconfig.node"` instead. It's
    equivalent for our purposes, because the explicit `--config` paths still guarantee the `.ts` is loaded.
- **Shared folder.** Create `frontend/theme/{tokens.css,preset.ts,theme.ts}` with a token or two. In each app:
  - `tailwind.config.ts`: `presets: [preset]` from `'../theme/preset'`; keep `content`.
  - `tsconfig.node.json` `include`: add `"../theme/preset.ts"` (composite projects must list every file, or `tsc -b` fails with TS6307).
  - `tsconfig.json` `include`: add `"../theme/theme.ts"`. CI runs `npx tsc --noEmit` with this config.
  - `vite.config.ts`: `server: { …existing, fs: { allow: ['..'] } }`, because Vite's dev server refuses files outside the app's package root.
  - `src/index.css`: `@import '../../theme/tokens.css';` as the **first line** (CSS requires `@import` before other rules).
- **Verify before continuing:**
  - `npm run build` from the root;
  - `(cd frontend/<app> && npx tsc --noEmit)` for all three;
  - no `*.js`/`*.d.ts` appear next to the configs or in `frontend/theme/`;
  - `npm run dev` with `bg-canvas` rendering in each app;
  - an edit to `tailwind.config.ts` takes effect in dev without a build.

**Step 2: Tokens, fonts, theme runtime, toggle (palette still extended).**
- Fill in `tokens.css` and `preset.ts` as in §4.2–4.3, with **`extend.colors`** (staging).
- Add `@fontsource/space-grotesk` (700) and `@fontsource/inter` (400, 500, 600, 700) to each app's `package.json` and lockfile,
  imported per weight in each `src/main.tsx` (for example `@fontsource/inter/700.css`). The imports go in the app, not in
  `tokens.css`, because `frontend/theme/` has no `node_modules`.
- Add the no-flash script to each `index.html`, plus `frontend/theme/theme.ts`, per-app `src/lib/theme.ts` with `useTheme`, and
  per-app `ThemeToggle`, placed as in §4.4. This includes the player header row in `App.tsx` and the in-flow disconnected banner.
- Change the player viewport meta (§4.7).
- Add `tests/unit/test_theme_tokens.py`. Contrast and parity pass now. The scan is `xfail(strict=True)`.

**Step 3: Restyle the primitives (per app).**
- `components/ui/button.tsx` variants: `default` (accent fill, on-fill text), `secondary` (new, accent-2), `outline`
  (surface + line), `ghost` (no box until hover, then `surface-muted`), and `destructive` (danger fill, on-fill text). All get
  `border-line`, the shadow and press, and `focus-visible`. Keep the existing variant and size **names** so call sites don't break.
  Player sizes stay larger (min height 48px for `md`, 56px for `lg`).
- In every primitive, **delete** `focus:outline-none`, `focus:ring-*` and `focus:ring-offset-*`. The base-layer `:focus-visible`
  outline (§4.3) is the only focus style.
- `card.tsx`: `nb-box`. `input.tsx`: surface, line border, and the global placeholder colour (§4.3). The player input is `text-base` or larger.
- `lib/utils.ts`: `extendTailwindMerge` with the shadow keys, plus the three `cn()` checks (§4.3.2).
- `TimerBar.tsx` (host and player): the track becomes `bg-surface-muted border-2 border-line` (square, no `rounded-full`). The fill goes
  `success` → `warning` → `danger` as time runs out. **The seconds text is the existing separate `<span>` beside the bar, not on the
  fill.** It becomes `text-ink-muted font-display tabular-nums`, replacing `text-slate-300` and `font-mono`. On-fill text is
  not used here.

**Step 4: Migrate pages, app by app (admin, then player, then host).**
Mechanical mapping (applies to every file the scan lists):

| Old (typical) | New |
|---|---|
| `bg-slate-900`/`950` (page) | nothing (body has `canvas`) or `bg-canvas` |
| `bg-slate-800`, `bg-slate-800/50` (cards, panels) | `bg-surface` or `nb-box` |
| `bg-slate-700`/`600` (inner wells, hover, tracks) | `bg-surface-muted` |
| `text-white`, `text-slate-100/200` | `text-ink` |
| `text-slate-300/400/500` | `text-ink-muted` |
| `border-slate-*`, `divide-slate-*` | `border-line`, `divide-line` (or bare `border`, which now defaults to `line`) |
| `bg-indigo-*` (primary) | `bg-accent text-on-fill` |
| `text-indigo-*` (links, emphasis) | `text-ink underline decoration-accent decoration-2` (yellow text fails AA on cream) |
| `bg-green-*` / `text-green-*` | `bg-success text-on-fill` / `text-success-text` |
| `bg-red-*` / `text-red-*` | `bg-danger text-on-fill` / `text-danger-text` |
| `bg-yellow|amber-*` / `text-…` | `bg-warning text-on-fill` / `text-warning-text` |
| `bg-black/50` etc. (modal scrims) | `bg-scrim/60` |
| `font-black` | `font-display font-bold` (headings, scores, codes) or `font-bold` (§4.1) |
| `focus:outline-none`, `focus:ring-*`, `focus:ring-offset-*`, `ring-offset-*` (on raw `<textarea>`/`<select>`/`<input>` in pages too) | delete (§4.1) |
| bar colours on ResultsPage / GameOverPage | `barClasses()` (§4.8) |
| `<img>` of an uploaded image | add `bg-image-bg` to it or its box (§4.9) |
| Player `OPTION_COLORS` (`pages/game/QuestionPage.tsx:9`) | `bg-option-1 … bg-option-8` with `text-on-fill border-line`, plus a letter badge (A, B, C, …) |
| Admin `STATUS_COLORS` (`pages/SessionsPage.tsx:34`) | `nb-chip` with `bg-success` (active) / `bg-warning` (lobby) / `bg-surface-muted` (completed) |

Then the per-context passes:
- **Player:** answer tiles at least 56px tall and full-width, a 3px outline, `brutal` shadow and press, `touch-action: manipulation`.
  The selected state uses a thicker outline plus a ✓ badge (not colour alone). Put-in-order chips and the Pin the Spot "lock in"
  button follow the same rules. Bottom action areas pad by `env(safe-area-inset-bottom)`.
- **Host projector** (`pages/game/*`): prompt `text-4xl` or larger in `font-display`, room code and scores in `font-display tabular-nums`,
  4px outlines and `brutal-lg`. Results bars as in §4.8. QR codes as in §4.7. Check readability at 1920×1080 viewed at 25% zoom, as a
  back-of-room proxy, in both themes.
- **Host manage** (`pages/manage/*`, `HostShell`, `ImagePicker`): 3px outlines. The question editor groups fields in `nb-box` sections.
  Image library tiles are outlined thumbnails with a visible focus. The `ImagePicker` modal is `nb-box` + `brutal-lg` over a
  `bg-scrim/60` backdrop.
- **Admin:** compact density (`data-density="compact"`), with 2px outlines and 2px shadows on cards and buttons only. Tables use
  `border-line` ruled rows, a `surface-muted` header row and zebra stripes, with no per-row shadows. The sidebar is a `surface` column
  with a line border. The active item is `bg-accent text-on-fill` (text set explicitly, §4.2), and the "Host tools" group uses
  `ink-muted` labels.
- Delete each app's hardcoded `body { background; color }` and `--pin-*` block from `index.css`.
- **Final commit of step 4:** switch the preset from `extend.colors` to replacing `colors` (§4.3) and remove the scan's `xfail`,
  in the same commit. The scan must pass.

**Step 5: Canvases.** Make the changes in §4.5 to `PinBoard.tsx` and `PinCanvas.tsx`. Check in both themes that a toggle
mid-question repaints the canvas without a reload.

**Step 6: Evidence and docs.**
- Write `tests/e2e/capture_ui_screens.py` (§4.6), generate `docs/ui/after/{light,dark}/…`, and write `docs/ui/README.md`.
- Update the context hierarchy (context-sync rule):
  - `frontend/CLAUDE.md`: the shared `frontend/theme/` now breaks the "nothing is shared" rule; explain what is and isn't
    shared, and why there's no React in it.
  - each `*/src/CLAUDE.md`: `index.css` no longer owns `--pin-*` or the body colours; `lib/theme.ts`; `ThemeToggle`.
  - each `components/CLAUDE.md`: primitive variants, and the TimerBar label.
  - host `lib/CLAUDE.md`: the localStorage exception.
  - player `CLAUDE.md`: header row, viewport.
  - Add a short "adding a colour" note: add a token to `tokens.css` (both themes), map it in `preset.ts`, and run `pytest tests/unit`.

## 6. Files touched

- **New:** `frontend/theme/tokens.css`, `frontend/theme/preset.ts`, `frontend/theme/theme.ts`,
  `frontend/{host,player,admin}/src/lib/theme.ts`, `frontend/{host,player,admin}/src/components/ThemeToggle.tsx`,
  `frontend/host/src/lib/answerBars.ts`,
  `tests/unit/test_theme_tokens.py`, `tests/e2e/capture_ui_screens.py`, `docs/ui/README.md`, `docs/ui/after/**`.
- **Config per app:** `index.html`, `tailwind.config.ts`, `postcss.config.js`, `vite.config.ts`, `tsconfig.json`,
  `tsconfig.node.json`, `package.json` (+ lockfile), `src/index.css`, `src/main.tsx`, `src/lib/utils.ts` (tailwind-merge). **Root:** `.gitignore`.
- **Host (20):** `components/{HostShell,PinBoard,ImagePicker}.tsx`, `components/ui/{button,card,input,TimerBar}.tsx`,
  `pages/{HomePage,LoginPage}.tsx`, `pages/game/{GameLayout,LobbyPage,QuestionPage,ResultsPage,GameOverPage}.tsx`,
  `pages/manage/{GamesPage,QuestionEditorPage,CoursesPage,RosterPage,ImagesPage,SessionsPage}.tsx`.
- **Player (14):** `components/PinCanvas.tsx`, `components/ui/{button,card,input,TimerBar}.tsx`, `App.tsx` (header + toggle),
  `pages/{JoinPage,NamePage,LoginPage}.tsx`, `pages/game/{GameLayout,LobbyPage,QuestionPage,FeedbackPage,ResultsPage,GameOverPage}.tsx`.
- **Admin (10):** `App.tsx` (sidebar + toggle), `components/ui/{button,card,input}.tsx`,
  `pages/{LoginPage,UsersPage,UserDetailPage,CoursesPage,GuestsPage,SessionsPage}.tsx`.
- **Context docs:** listed in step 6.

The authoritative list of files to migrate is whatever the scan test reports. The list above is the snapshot at time of writing.

## 7. Verification (definition of done)

1. `pytest tests/unit` passes, including `test_theme_tokens.py` with no `xfail`.
2. CI parity: `ruff check backend/ scripts/ tests/`, `ruff format --check backend/ scripts/`, and `npx tsc --noEmit` in all three apps.
3. `npm run build` succeeds and leaves no emitted `.js`/`.d.ts` next to the configs or in `frontend/theme/`. `pytest tests/integration`
   and `pytest tests/e2e` pass against the Docker stack.
4. Manual, at nginx :8080, in each app:
   - Clear storage and set the OS to dark: the app opens dark, with no light flash. Set the OS to light: it opens light.
     Change the OS setting while the app is open (no stored choice): the app follows live.
   - Toggle the theme and reload: the choice persists. Toggle in admin: an open host tab updates without a reload.
   - Tab through every page: the focus outline is visible on every interactive element in both themes.
   - Play a full game covering every question type (the fixture from §4.6, or `scripts/seed_demo.py` plus the T6 games with
     `scripts/simulate_players.py`). Every screen looks intentional in both themes, Pin the Spot repaints on toggle, and QR codes
     scan from a phone in both themes.
   - Player at 390×844: no horizontal scroll, tap targets ≥ 44px, the toggle never covers an input, pinch-zoom works, and focusing an
     input doesn't auto-zoom on iOS Safari.
5. `docs/ui/after/{light,dark}` holds all 30 key screens, and `docs/ui/README.md` shows before/after side by side.

## 8. Risks and open questions

- **Expected staging artefact (don't "fix" it mid-migration).** From step 2, `borderColor.DEFAULT` is `line`. On pages not yet
  migrated, a bare `border` therefore draws near-black (`#121212`) outlines on the old slate surfaces whenever the theme is light, and
  some unmigrated pages look odd in light mode until step 4 reaches them. That's harmless on the feature branch and resolves itself
  as each page is migrated.
- **Scale.** About 860 class edits is where regressions hide. Staging (extend, then replace) keeps the apps usable, but the
  final replace commit will expose any missed class as *no CSS* (for example, a transparent button). The scan test runs in that
  same commit, which is the safety net.
- **The soft dark theme may lose the brutalist punch.** Muted outlines on charcoal can drift toward "generic dark UI". The shadows,
  type weight and flat fills must carry the identity. Judge this from the step 6 screenshots, and adjust `line` and the fills if
  needed (staying at 3:1 or better).
- **Projector gamma.** Contrast ratios computed from hex values don't model a washed-out projector. If the step 4 projector check
  fails, add a `[data-surface=projector]` override of the fill tokens on `GameLayout`'s root. That's a new token dimension, so update
  this doc first.
- **`noEmit` with `composite`** is believed supported on TS 5.9 but is unverified in this repo. Step 1 has a documented fallback.
- **Shared origin.** One `buzzer-theme` key means a host projecting from the same browser as an admin session shares the theme
  (accepted).
- **Fonts.** `@fontsource` adds roughly 150–250 KB per app. Only the listed weights are imported.
- **Open:** whether `TimerBar` should pulse at ≤5s (motion, which `prefers-reduced-motion` would gate). Decide during step 3. It
  doesn't affect the token design.

## 9. Revision log

**Revision 1** was the first spec, written from the Elephant design discussion.

**Revision 2** was revised after the Goldfish test, a fresh session reading only revision 1. Every finding was verified against the
code before changing this doc.

| # | Goldfish finding | Verified? | Change |
|---|---|---|---|
| 1 | `react` import from `frontend/theme/theme.ts` can't resolve | Yes: root `node_modules` has only `concurrently` | `theme.ts` is React-free; `useTheme` is in each app's `lib/theme.ts`; the spike branch is dropped (§4.4, §3) |
| 2 | Stale `vite.config.js` shadows `.ts`, as `tailwind.config.js` does; `preset.ts` would emit `.js`/`.d.ts` | Yes: all three apps have emitted `vite.config.js` | `noEmit` + `tsBuildInfoFile` in `tsconfig.node.json`, delete stale files, explicit `--config`, `.gitignore` (step 1) |
| 3 | TimerBar seconds are a separate span, not on the fill | Yes (`TimerBar.tsx` span with `text-slate-300`) | `text-ink-muted` beside the bar (step 3) |
| 4 | 37 `font-bold` and 24 `font-black` but no Inter 700 | Yes | Load Inter 700; `font-black` → `font-display`/`font-bold`; scan forbids unloaded weights (§4.1) |
| 5a | `PinCanvas.tsx:169` also has `'#ffffff'` | Yes | Both literals → `--pin-marker-stroke` (§4.5) |
| 5b | `--pin-full-fill` missing from the list | Yes | Full `--pin-*` list (§4.5) |
| 5c | "ink-muted ≥ 7.9 everywhere" wrong; dark on surface-muted is 6.1 | Yes | Contrast table corrected (§4.2) |
| 6 | Replacing `colors` makes a bare `border` use `currentColor` | Yes (51 bare `border` uses) | Explicit `borderColor`/`divideColor`/`ringColor`/`outlineColor`/`placeholderColor` defaults (§4.3) |
| 7 | `bg-ink/40` scrim becomes a light wash in dark mode | Yes (ink is off-white in dark) | New `scrim` token, `bg-scrim/60`; rule "never use ink as a backdrop" (§4.2) |
| 8 | Option-colour bars clash with green correct marking | Yes: bars encode correctness, not option | Keep the correctness encoding, plus ✓ badge and thicker outline (§4.8) |
| 9 | QR codes not addressed | Yes (`LobbyPage:26`, `GameLayout:243`) | Black-on-white in a `qr-bg` box in both themes (§4.7) |
| 10 | `env(safe-area-*)` needs `viewport-fit=cover`; `user-scalable=no` blocks zoom | Yes (`player/index.html:5`) | New viewport meta, 16px inputs, `touch-action: manipulation` (§4.7) |
| 11 | Player toggle placement vague; disconnected banner overlap | Yes (banner is `fixed top-0 z-50`) | In-flow header row in `App.tsx`; banner in-flow (§4.4) |
| 12 | Listener ownership; no reset to OS | Yes | Module-level listeners set the attribute; no follow-system after toggle, stated as intended (§4.4) |
| 13 | Screenshot capture under-specified; ~95 × 2 too large | Yes: no capture tooling committed | Defined 30-screen set, a fixture game, and a capture module on existing e2e fixtures (§4.6) |
| 14 | Replacing the palette in step 2 breaks apps until step 4 ends | Yes | Extend during migration, replace in the final step-4 commit together with removing the `xfail` (§4.3, step 4) |
| 15 | No work split for R11 | n/a | Decision: one member owns all of T9 (header) |
| 16 | Design doc not committed | Yes (untracked) | Committed before step 1, with `docs/ui/before/` |

**Revision 3** was revised after a second Goldfish pass (a fresh session reading only revision 2). Every finding was verified against
the code first.

| # | Goldfish finding | Verified? | Change |
|---|---|---|---|
| 1 | `focus:outline-none` utilities beat the global `:focus-visible` rule, so "never removed" was unenforced | Yes: 15 `focus:outline-none`, 40 `focus:ring*` (the Goldfish said 26), 11 raw `<textarea>`/`<select>` | Focus rule moved to `@layer base`; every `outline-none` and `focus:ring*` deleted; scan forbids them (§4.1, §4.3, step 3, step 4) |
| 2 | Preflight hardcodes `::placeholder` as gray-400 (`#9ca3af`, ~2.5:1) | Yes (`preflight.css` ~333) | Global `::placeholder` rule in `tokens.css` (§4.3) |
| 3 | GameOverPage bars use a different encoding (wrong = red at :226) | Yes (:180, :210, :226, :337) | One encoding for both pages (wrong = muted, decided), shared `barClasses()` helper, ✓ chip on both (§4.8) |
| 4 | Transparent PNG/GIF/WebP images vanish on dark surfaces | Yes (`prepareUpload` keeps alpha) | `image-bg` light backing in every image well, plus `--pin-image-bg` (§4.9, §4.5) |
| 5 | `.nb-press`/`.nb-box` can't serve three shadow sizes | Yes | Density variables `--nb-border`/`--nb-offset` with `data-density` roots (§4.3.1) |
| 6 | tailwind-merge treats `shadow-brutal*` as a shadow colour | Yes (twMerge ^2.5, `lib/utils.ts`) | `extendTailwindMerge` plus three `cn()` checks (§4.3.2) |
| 7 | Scan misses side borders, named colours, `ring-offset` (default `#fff` halo) | Yes: none exist today | Regex widened; `ringOffsetColor.DEFAULT = canvas` (§4.6, §4.3) |
| 8 | Contrast test misses opacity fills; sidebar active item text unspecified | Yes | Opacity banned on fill tokens; `text-on-fill` required on every fill (§4.2) |
| 9a | `font-display font-semibold` would be faux-bold | Yes (only Space Grotesk 700 loaded) | `font-display` ⇒ 700, enforced by the scan (§4.1) |
| 9b | `borderColor.DEFAULT` darkens unmigrated pages mid-migration | Yes | Stated as an expected artefact (§8) |
| 9c | Toggle `aria-label` changes with state | Yes | Fixed name plus `aria-pressed` (§4.4) |
| 9d | Capture module needs a `test_*` function; two games; timers | Yes | Parametrized `test_capture_ui_screens`, one room per theme, `time_limit_seconds = 600`, host lock control (§4.6) |
| 9e | No `theme-color` meta | Yes (none in any `index.html`) | Two media-scoped metas plus a runtime update in `theme.ts` (§4.3) |
