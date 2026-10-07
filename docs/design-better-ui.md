# Design: UI look-and-feel and theming (T9), neo-brutalist light and dark

Status: **revision 8, revised after six Goldfish passes and a test-planning review** (see §9, "Revision log"). Assesses T9 in `instructions.md`,
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

**Out of scope:** the backend-generated HTML session summary that hosts download (T4). It's a standalone file with its own inline
styles, opened outside the apps, and T9 changes no backend code. It is not themed.

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
| Copy the base and component CSS (`.nb-*`, focus, placeholder, checkbox rules, ~80 lines) into each app's `index.css` `@layer` blocks | Same drift problem the shared folder exists to solve. Plain CSS is easier to read than JS objects, but a Tailwind plugin inside the preset needs no `tailwindcss` import and gives one source. Chosen: the plugin (§4.3). |
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
| Radius | Square by default. The preset **replaces** Tailwind's radius scale with `none`, `DEFAULT` (4px, for chips, badges and inputs only) and `full` (spinners, pills, round avatars). Every other `rounded-*` stops emitting CSS once replaced, and the scan forbids it (§4.3, §4.6). |
| Shadow scale | The preset **replaces** Tailwind's shadow scale with `none`, `brutal-sm`, `brutal` and `brutal-lg`. Soft shadows (`shadow`, `shadow-md`…`shadow-2xl`) use a literal `rgb(0 0 0 / …)` that would survive the palette swap, so they must go. No `backdrop-blur`, `blur` or `drop-shadow`. |
| Fills | Flat. No gradients. Coloured fills are for buttons, option tiles, badges and bars, never large page areas. |
| Text on fills | Always `text-on-fill` (dark in **both** themes), never white. That keeps every fill at AA or better. The same applies to text inside an `image-bg` or `qr-bg` box (§4.9). Text that sits *beside* a fill (not on it) uses `ink`/`ink-muted`. |
| Type | Display face **Space Grotesk 700** for page and section titles, numbers, scores, timers, room codes and button labels. It is **not** used for running text: question prompts and paragraphs use Inter, because a display face reads poorly over several lines. Sizes and spacing come from the scale in §4.11. **`font-display` always means weight 700.** The `fontFamily.display` entry can't carry a weight, so every `font-display` use pairs with `font-bold`, or comes through a class that sets it. The scan forbids `font-display` alongside `font-normal`, `font-medium` or `font-semibold`. Body face **Inter 400/500/600/700** (700 so `font-bold` is real bold, not faux-bold). Both come from `@fontsource`. Scores and timers use `tabular-nums`. |
| Weight mapping | `font-black` (24 uses today) on headings, scores and room codes → `font-display` (Space Grotesk 700). Any other `font-black` → `font-bold`. After migration, `font-black` and `font-extrabold` appear nowhere (the scan test checks this, since those weights aren't loaded). `font-bold` on headings may become `font-display`; on body text it stays Inter 700. |
| Focus | `:focus-visible` gives a 3px solid `focus` outline with a 2px offset, defined in the preset's plugin `addBase` (§4.3). It is **enforced, not just stated**: all 15 `focus:outline-none` and all 40 `focus:ring*`/`ring-offset*` classes are deleted during migration, and the scan forbids `outline-none`, `focus:ring`, `focus-visible:ring` and `ring-offset` from then on. Why the deletion is required: a utility like `focus:outline-none` (specificity 0,1,1) beats a bare `:focus-visible` rule (0,1,0) no matter where that rule sits, so any surviving `outline-none` silently removes the focus state. |
| Status meaning | Colour never carries meaning alone. Right/wrong pairs colour with an icon or word (✓/✗, "Correct"). Option tiles carry a letter (A, B, …) as well as their colour. This includes the fill-in-the-blank word cloud (§4.8). |
| States | Hover, active, disabled and selected are defined once, in §4.11. Pages don't invent their own. |

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
  vouch for text on it. The scan enforces this.
- **Opacity is allowed only as `bg-scrim/…`, `bg-surface*/…` and in `shadow`.** That means no opacity modifier on any `text-*`
  class (`text-ink/50` would fail AA, and no test could see it). Element-level `opacity-*` is allowed **only through the `disabled:`
  variant**: WCAG 1.4.3 exempts inactive UI components, and that's the only case where dimming is acceptable (§4.11). The scan
  enforces both rules. Today there are no `text-*/NN` uses, but element `opacity-*` dims **content** in two places, and those
  get migrated:
  - the player's option fallback letter (`QuestionPage.tsx:39`, `opacity-60`) → `text-on-fill` (it sits in an `image-bg` box);
  - inactive and skipped roster rows (`RosterPage.tsx:370` `opacity-30 line-through`, `:573` `opacity-50`) → `text-ink-muted`,
    plus `line-through` for skipped rows and an "Inactive" `nb-chip` for inactive entries.
  Conditional `opacity-50` on the player's answer tiles and submit buttons (`QuestionPage.tsx` :131, :161, :183, :191, :269, :288,
  :362) becomes `disabled:` styling on the same buttons. Each must carry the `disabled` attribute when submitted or locked; add it
  where it's missing.
- **Any element with a fill-token background sets `text-on-fill` explicitly.** That includes the admin sidebar's active item,
  chips, badges, tiles and buttons. Inheriting `ink` would give about 1.7:1 on dark `accent`.
- In light mode the fills are pale against the cream canvas (yellow vs cream is 1.3:1). That's fine because every filled
  element carries a `line` outline, and the outline carries the WCAG 1.4.11 non-text contrast. **A fill without an outline is
  not allowed.**
- `line` in dark mode must stay at **3:1 or better against `canvas`, `surface` and `surface-muted`**.
- **Text inside an `image-bg` or `qr-bg` box uses `text-on-fill`.** Both stay light in dark mode, so inherited `ink` (off-white)
  would be about 1.1:1. Known sites:
  - the player option fallback letter (`QuestionPage.tsx:39`);
  - "Image failed to load" (host `QuestionPage.tsx:116`, `ResultsPage.tsx:317`, player `QuestionPage.tsx:407`), where those
    messages render inside the image box;
  - the editor's "Missing image" (`QuestionEditorPage.tsx:242`).

  "Image failed to load" in `PinBoard.tsx:194` and `PinCanvas.tsx:242` sits on the themed canvas letterbox, not on `image-bg`, so it
  uses `ink-muted`.

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
    2.5:1 on white, which fails AA. So the preset plugin's `addBase` (below) sets
    `input::placeholder, textarea::placeholder { color: rgb(var(--ink-muted)); opacity: 1; }`, which covers
    every raw page `<input>`/`<textarea>` (11 raw `<textarea>`/`<select>` exist outside the primitives).
  - `boxShadow` and `borderRadius`: see "staging". The tokens are
    `boxShadow = { none: 'none', 'brutal-sm', brutal, 'brutal-lg' }` (hard offsets in `rgb(var(--shadow))`) and
    `borderRadius = { none: '0', DEFAULT: '4px', full: '9999px' }`.
  - `extend.borderWidth`: `3`.
  - `extend.fontFamily`: `display: ['"Space Grotesk"', 'system-ui', 'sans-serif']`, `sans: ['Inter', 'system-ui', 'sans-serif']`.

**Staging (the apps stay usable during migration):**
- **Steps 2–4:** the preset uses `theme.extend` for colours, the brutal shadows and the radius tokens. Tailwind's own palette,
  radii and soft shadows still exist, so unmigrated pages render as they do today, and migrated pages use tokens. The scan test is
  `xfail(strict=True)`.
- **Final commit of step 4:** switch all three to replacement, `theme.colors = { transparent, current, inherit, ...tokenColors }`,
  `theme.boxShadow = {…}` and `theme.borderRadius = {…}`, and remove the `xfail` in the **same commit**. From then on, a leftover
  palette, radius or soft-shadow class produces no CSS and fails the scan.

`frontend/theme/tokens.css` also defines, outside Tailwind:
- `html { color-scheme: light }` / `html[data-theme=dark] { color-scheme: dark }`, so native scrollbars and form controls follow. This is
  block 5 in §4.3.3; it uses `html`, not `:root`, so no selector repeats block 2.
- `body { background: rgb(var(--canvas)); color: rgb(var(--ink)); }`. This replaces the hardcoded body colours in each `index.css`.
- **Not** the placeholder rule. A bare `::placeholder` (specificity 0,0,1) in `tokens.css` loses to preflight's
  `input::placeholder` (0,0,2), which also comes later. The rule goes in the plugin's `addBase` (below).
- `theme-color` (mobile browser chrome) is not set in CSS. Each `index.html` has **exactly one**
  `<meta name="theme-color" content="#FFF8E7">`, with no `media` attribute. Browsers use the first matching meta, so two
  media-scoped metas would always follow the OS and ignore the toggle. The no-flash script sets its `content` from the resolved theme
  (`#FFF8E7` light, `#1B1C20` dark). These two literals are the only hardcoded copies of `canvas`, because the script runs before
  any CSS has loaded. `applyTheme()` doesn't copy them: it reads `getComputedStyle(documentElement).getPropertyValue('--canvas')`
  after setting the attribute and writes `rgb(<channels>)`. `theme.ts` updates it every time it sets the attribute (`setTheme`, OS change, storage event),
  through one internal `applyTheme(t)` that does both.

**Shared base and component CSS lives in one place: a plugin inside `frontend/theme/preset.ts`** (decided). The preset's
`plugins: [nbPlugin]` entry is a plain function `({ addBase, addComponents }) => { … }`. Its parameter is typed by hand (a small local
interface with the two methods taking `Record<string, Record<string, string>>`), because `preset.ts` may not import from `tailwindcss`.
Tailwind emits `addBase` output with the base layer (after preflight) and `addComponents` output with the components layer, which is
the same ordering `@layer base` / `@layer components` would give, without three copies.
- **`addBase`:**
  - `:focus-visible { outline: 3px solid rgb(var(--focus)); outline-offset: 2px; }`
  - `input::placeholder, textarea::placeholder { color: rgb(var(--ink-muted)); opacity: 1; }`. This uses preflight's exact selector,
    so equal specificity plus later position means it wins.
  - the checkbox and radio rule (§4.11).

  These don't go in `tokens.css`, which is `@import`ed before `@tailwind base`, so preflight would follow it. Utilities still beat base
  rules, which is why the deletions and the scan rule in §4.1 are what really guarantee focus visibility.
- **`addComponents`:** every `.nb-*` class in §4.3.1, reading the density variables.
- Each app's `src/index.css` becomes just four lines: `@import '../../theme/tokens.css';` then the three `@tailwind` directives.

#### 4.3.1 Density variables and the layout/typography classes

`tokens.css` defines these non-colour variables in block 1 (the comfortable defaults) and overrides them in block 4
(`[data-density=compact]`, `[data-density=projector]`). Sizes are the rem values of the Tailwind classes chosen in §4.11
(decided: bold contrast).

| Variable | compact (admin) | comfortable (default: player, host manage) | projector (host `/game/*`) |
|---|---|---|---|
| `--nb-border` | 2px | 3px | 4px |
| `--nb-offset` | 2px | 4px | 6px |
| `--nb-h1` (page title) | 1.5rem | 1.875rem | 3.75rem |
| `--nb-h2` (section title) | 1.125rem | 1.25rem | 2.25rem |
| `--nb-stat` (scores, timers, counts) | 1.25rem | 1.5rem | 3rem |
| `--nb-hero` (hero numbers and glyphs) | 2.5rem | 3rem | 6rem |
| `--nb-h3` (card title) | 1rem | 1.125rem | 1.5rem |
| `--nb-body` | 0.875rem | 1rem | 1.5rem |
| `--nb-prompt` (question prompt) | 1rem | 1.125rem | 2.25rem |
| `--nb-caption` | 0.75rem | 0.875rem | 1.125rem |
| `--nb-page-pad` | 1rem | 1.25rem | 2.5rem |
| `--nb-card-pad` | 0.75rem | 1.25rem | 2rem |
| `--nb-gap` | 0.75rem | 1rem | 2rem |

Classes added by the preset plugin's `addComponents` (one definition, used by all three apps):

- **Box and press:**
  - `.nb-box`: `background: rgb(var(--surface)); border: var(--nb-border) solid rgb(var(--line)); box-shadow: var(--nb-offset) var(--nb-offset) 0 0 rgb(var(--shadow));`
  - `.nb-press`: `transition: transform 80ms, box-shadow 80ms`. Hover lifts and `:active` presses, per §4.11. `:disabled` resets transform and shadow.
    Under `prefers-reduced-motion: reduce`, `transition: none` and no translate.
  - `.nb-selected`: `box-shadow: inset 0 0 0 3px rgb(var(--on-fill)), var(--nb-offset) var(--nb-offset) 0 0 rgb(var(--shadow));`
    The selected state is drawn **inside** a constant border, so tiles never change size (§4.11).
    - The ring is `on-fill`, not `line`. `line` would be 1.3–2.1:1 on the dark fills, while `on-fill` is ≥ 6.1:1 on every fill in both
      themes. So `.nb-selected` is **only used on filled elements**: option tiles, put-in-order picks, and selected list rows, which
      become `bg-accent text-on-fill`.
    - **Selected wins over hover and disabled:** the plugin also emits `.nb-press.nb-selected:hover` (same ring plus the lifted shadow)
      and `.nb-press.nb-selected:disabled` (`box-shadow: inset 0 0 0 3px rgb(var(--on-fill)); transform: none;`). At specificity 0,3,0
      these beat `.nb-press:hover` / `.nb-press:disabled` (0,2,0), so hovering a selected row, or the host locking a question, never hides the ring.
    - It lives in the plugin rather than as an arbitrary `shadow-[inset…]` class in `.tsx`, because that class would trip the scan's `rgb(` rule.
  - `.nb-chip`: `border: 2px solid rgb(var(--line))`, small padding, `rounded` (4px), and `font-semibold text-sm`. It has no shadow, at any density.
- **Typography:**
  - `.nb-h1`, `.nb-h2`: `font-family: theme(fontFamily.display); font-weight: 700; font-size: var(--nb-h1 | --nb-h2); line-height: 1.1;`
  - `.nb-h3`: Inter, `font-weight: 600; font-size: var(--nb-h3); line-height: 1.3;`
  - `.nb-body`: Inter 400, `var(--nb-body)`, `line-height: 1.5`.
  - `.nb-prompt`: Inter 600, `var(--nb-prompt)`, `line-height: 1.3`.
  - `.nb-caption`: Inter 500, `var(--nb-caption)`, `color: rgb(var(--ink-muted))`, `text-transform: uppercase; letter-spacing: 0.05em`.
    **Never on a fill**: `ink-muted` on a dark fill is about 1.1:1. On tiles, chips and active items, a caption is `.nb-caption text-on-fill`.
    The colour utility overrides the class colour, and colour utilities are allowed alongside `.nb-*`.
  - `.nb-stat` (scores, timers, counts): display 700, `var(--nb-stat)`, `font-variant-numeric: tabular-nums`, `line-height: 1.1`.
  - `.nb-hero` (the one big thing on a screen): display 700, `var(--nb-hero)`, tabular-nums, `line-height: 1`, `letter-spacing: 0.08em`.
  - `.nb-code` (small room code in the projector's corner QR panel): display 700, `var(--nb-h3)`, tabular-nums, `letter-spacing: 0.15em`.
- **Spacing:**
  - `.nb-page`: `padding: var(--nb-page-pad)`.
  - `.nb-card`: `.nb-box` plus `padding: var(--nb-card-pad)`.
  - `.nb-stack`: `display: flex; flex-direction: column; gap: var(--nb-gap)`.
- **Rule:** an element using an `.nb-h*`/`.nb-body`/`.nb-prompt`/`.nb-caption`/`.nb-stat`/`.nb-hero`/`.nb-code` class adds no `text-{size}`/`font-{weight}`/`tracking-*`/`leading-*`
  utility, and `.nb-page`/`.nb-card`/`.nb-stack` add no `p-*`/`gap-*`/`space-y-*`. tailwind-merge doesn't know these classes, so
  `cn('nb-h1', 'text-xl')` would keep both and the utility would silently win. The scan enforces the rule per class string (§4.6).
  Colour, margin, alignment and width utilities may still be combined with them. **Known limitation:** a `className` *prop* passed
  from another component, e.g. `<CardHeader className="text-xl">` where `CardHeader` applies `.nb-h3`, crosses files and isn't caught.
  Primitives that apply an `.nb-*` type class therefore document "don't pass size or weight classes" in a one-line comment.
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
`cn('font-sans','font-display') === 'font-display'`. If `border-3` or `font-display` misbehave, register them the same way. The
`.nb-*` component classes are deliberately **not** registered (see the rule above).

#### 4.3.3 `tokens.css` structure (the tests parse this)

`tokens.css` has exactly these blocks, in this order. **Every rule selector in the file is unique**, so the tests can locate blocks by
exact selector text.

| # | Selector (exact) | Holds | Parity test | Contrast test |
|---|---|---|---|---|
| 1 | `:root` | **Theme-invariant and derived** variables: the comfortable defaults of every §4.3.1 density variable; `--qr-bg` (`255 255 255`); the saturated marker colours `--pin-full`, `--pin-full-fill`, `--pin-zero`, `--pin-target`, `--pin-tap`, `--pin-tap-stroke`, `--pin-head`, `--pin-stem`, `--pin-marker-stroke` (`#ffffff`); and the derived canvas colours `--pin-letterbox: rgb(var(--canvas))`, `--pin-placeholder: rgb(var(--surface-muted))`, `--pin-image-bg: rgb(var(--image-bg))` | exempt; must **not** be redefined in blocks 2–3 | merged into both themes (supplies `qr-bg`) |
| 2 | `:root, [data-theme=light]` | Every **themed** RGB-channel colour token in §4.2 except `qr-bg` (this includes `image-bg`), at its light value | must define exactly the same names as block 3 | light theme = block 1 + block 2 |
| 3 | `[data-theme=dark]` | The same names as block 2, at dark values | see block 2 | dark theme = block 1 + block 3 |
| 4 | `[data-density=compact]`, `[data-density=projector]` (two rules) | Only §4.3.1 density variables | ignored | ignored |
| 5 | `html`, `html[data-theme=dark]`, `body` | `color-scheme: light` / `dark`, and the body background and colour. **No custom properties.** (`html`, not `:root`, so no selector repeats block 1 or 2.) | ignored | ignored |

- **Parser rule:** for each rule, match its selector text exactly against the table. Collect `--name: value;` declarations only from
  blocks 1–4. Any custom property found in block 5, or in a rule whose selector isn't listed, fails the test. A variable defined in more
  than one of blocks 1–3 fails the parity test, which stops an "invariant" value being silently overridden by one theme.
- The contrast test skips any value that isn't three space-separated integers (the `--pin-*` and density variables).
- **The derived `--pin-*` colours** were checked during design in Playwright's Chromium: `rgb(var(--canvas))` reads back as
  `rgb(27 28 32)`, and a canvas filled with it gives pixel `[27, 28, 32]`. **Safari still needs a check in step 5:**
  - Custom properties' computed values have `var()` substituted, so `getComputedStyle(el).getPropertyValue('--pin-letterbox')`
    should return a resolved `rgb(27 28 32)`-style string, which canvas `fillStyle` accepts.
  - Confirm both in Chromium and Safari.
  - If either fails, move the three variables into blocks 2–3 as literal hex values (the parity test then covers them), and record
    that here.

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
    projector screens (outside the shell), a small **fixed bottom-left** button rendered once in `pages/game/GameLayout.tsx`. That
    keeps it clear of the fixed bottom-right QR/room-code panel (`GameLayout.tsx:241`) and of top-right projector content (timer,
    counts).
  - **Player:** (layout contract in §4.11) a **normal in-flow header row** rendered once in `App.tsx` above `<Routes>`. It's a 56px-tall bar holding only the
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
  - `--pin-letterbox` and `--pin-placeholder` follow the theme by referencing `--canvas` and `--surface-muted` (§4.3.3).
  - New **`--pin-image-bg`** (`rgb(var(--image-bg))`, §4.9): fill the image's destination rectangle with it *before* `drawImage`, so a
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
   - opacity on fill tokens: `\b(bg|border|text)-(accent|accent-2|info|success|danger|warning|option-\d)/\d+`; opacity on any
     text colour: `\btext-[a-z-]+/\d+`; element opacity without `disabled:`: `(?<!disabled:)\bopacity-\d+` (§4.2);
   - `\bmin-h-screen\b` in `frontend/player/src/pages/**` (§4.11 layout contract);
   - radius and soft shadows: `\brounded-(?:[trblse]{1,2}-)?(sm|md|lg|xl|2xl|3xl)\b`,
     `\bshadow(?:-(sm|md|lg|xl|2xl|inner))?(?![-\w])` (bare `shadow` or a soft size; `shadow-brutal*`/`shadow-none` pass), and
     `\b(backdrop-blur|blur|drop-shadow)(-[a-z0-9]+)?\b`;
   - within one class string: a `className="…"` value, one template literal, or **all the arguments of one `cn(…)` call taken
     together** (so `cn('nb-h1', cond && 'text-xl')` is caught): `nb-(h1|h2|h3|body|prompt|caption|stat|hero|code)` together
     with `\btext-(xs|sm|base|lg|[2-9]?xl)\b`, `\bfont-(normal|medium|semibold|bold)\b`, `\btracking-[\w-]+` or `\bleading-[\w-]+`, and `nb-(page|card|stack)` together with
     `\b(p|px|py|pt|pb|pl|pr)-\d` or `\b(gap|space-y|space-x)-\d` (§4.3.1);
   - `font-black` or `font-extrabold` (weights that aren't loaded), and `font-display` on the same line as
     `font-(normal|medium|semibold)` (§4.1);
   - CSS named colours in string literals or JSX attributes in `.ts`/`.tsx`:
     `(['"])(white|black|red|green|blue|yellow|gray|grey|orange|purple|pink)\1` and
     `\b(fill|stroke|color)=\{?["'](?!currentColor|none)[a-z]+["']`. There is **no** allow-list for named colours; none exist today;
   - any hex colour `#[0-9a-fA-F]{3,8}\b` or `rgb(`/`rgba(`/`hsl(` literal in `.ts`/`.tsx`, **except** inside the
     fallback of a `cssVar(…)` call, and in the allow-listed `host/src/lib/imageFile.ts`. **Exemption rule:** a match is exempt only if it
     lies inside a single string literal (`'…'` or `"…"`, no nested quotes) that is the **third argument** of a call whose callee is
     exactly `cssVar`, e.g. `cssVar(canvas, '--pin-full-fill', 'rgba(74, 222, 128, 0.3)')` (`PinBoard.tsx:111`). Implement it by
     matching `cssVar\(\s*[^,]+,\s*(['"])--[\w-]+\1\s*,\s*(['"])([^'"]*)\2\s*\)` and blanking group 3 before running the colour regexes,
     rather than stopping a regex at the first `)`;
   - any hex colour in `index.css` (they may only use `var(--…)`).
2. *Contrast* (always on). Parse `frontend/theme/tokens.css` into the `light` and `dark` maps (RGB-channel tokens only; `--pin-*`
   are skipped) and assert, for each theme:
   - `ink` and `ink-muted` on `canvas`/`surface`/`surface-muted` ≥ 4.5;
   - `on-fill` on `accent`, `accent-2`, `info`, `success`, `danger`, `warning`, `option-1…8`, `image-bg` and `qr-bg` ≥ 4.5 (only
     opaque fills are tested, which is why opacity on fills is banned);
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
- **Entry point.** The module defines **one** non-parametrized function, `test_capture_ui_screens(…fixtures)`, so pytest collects
  it when the file is passed explicitly. Its only assertion is the axe report at the end (§4.10), plus waits for "the page reached the
  expected state". **Shot order:**
  1. game A in **light** (screens 01–19 light);
  2. game B in **dark** (screens 01–19 dark), each in its own room;
  3. only after both games: screens 20–30 in light, then in dark.

  Because both themes' management and admin shots come after both games, they show **identical data** (two completed sessions).
  Screens 27 and 30 need a completed session, and this ordering guarantees one.
- **Context options.** `page_as` gains a pass-through: `page_as(token, *, color_scheme=None, **context_opts)` forwards
  `viewport` and `device_scale_factor` (and anything else) to `browser.new_context`. The device scale can't change after the context
  exists. Existing call sites are unchanged.
- **Roster data** (screen 26). Before the shots, import a small CSV of 6 students for the `env` course through
  `POST /api/host/courses/{course_id}/roster/import` (`routers/host.py:256`) as the `env` host, with one row deactivated so the
  "Inactive" chip shows. `cleanup` must remove the entries.
- **User detail** (screen 29) is the `env` host user's page, which shows course and game grants.
- **Driving the game.** One host page (1920×1080) and three guest player pages (390×844, device scale 2) through `page_as`.
  One player answers correctly and one incorrectly, so both results states exist.
- **Keeping timers from expiring between shots.** The fixture game's questions use `time_limit_seconds = 600`, so nothing expires
  while screenshots are taken. Screens that need the "locked" state are reached through the host's existing lock control, not by
  waiting for the timer. The shots are taken, then the host advances.
- **Theme.** Each context gets `color_scheme=<theme>` **and** `localStorage['buzzer-theme']=<theme>` through `context.add_init_script`
  before the first navigation.
  Before each shot, wait for `[data-loaded=true]` on canvases and for fonts (`document.fonts.ready`).
- **Output:** `docs/ui/after/<theme>/<after file>` from the key-screen table below.

**Key-screen set** (30 screens × 2 themes = 60 images). The after path is `docs/ui/after/<theme>/<after file>`. The before path is
relative to `docs/ui/before/`. Every key screen has a before shot, all dark, since that was the only theme.

| # | Screen | After file | Before file |
|---|---|---|---|
| 01 | Player: join | `player/01-join.png` | `player/01-join/01-enter-room-code.png` |
| 02 | Player: name, guest (`page_as(None)`, so there's no token and the guest form shows) | `player/02-name-guest.png` | `player/01-join/03-name-guest.png` |
| 03 | Player: lobby | `player/03-lobby.png` | `player/02-lobby/01-waiting-for-host.png` |
| 04 | Player: MC with option images | `player/04-question-mc-images.png` | `player/03-question/01-multiple-choice-with-images.png` |
| 05 | Player: true/false | `player/05-question-true-false.png` | `player/03-question/02-true-false-with-prompt-image.png` |
| 06 | Player: fill in the blank | `player/06-question-fill-blank.png` | `player/03-question/03-fill-in-the-blank.png` |
| 07 | Player: multi-select (one option selected) | `player/07-question-multi-select.png` | `player/03-question/04-multi-select.png` |
| 08 | Player: put in order | `player/08-question-put-in-order.png` | `player/03-question/05-put-in-order.png` |
| 09 | Player: Pin the Spot, pin placed | `player/09-question-pin-placed.png` | `player/03-question/06b-pin-the-spot-pin-placed.png` |
| 10 | Player: feedback (answer locked in) | `player/10-feedback.png` | `player/04-feedback/01-answer-locked-in.png` |
| 11 | Player: results, correct | `player/11-results-correct.png` | `player/05-results/01-multiple-choice-with-images.png` |
| 12 | Player: results, incorrect | `player/12-results-incorrect.png` | `player/05-results/01b-multiple-choice-with-images-incorrect.png` |
| 13 | Player: game over | `player/13-game-over.png` | `player/06-game-over/01-final-rank-and-recap.png` |
| 14 | Host projector: lobby with QR and players | `host/14-lobby.png` | `host/03-live-game/01-lobby/02-lobby-with-players.png` |
| 15 | Host projector: true/false with prompt image | `host/15-question-prompt-image.png` | `host/03-live-game/02-question/02-true-false-with-prompt-image.png` |
| 16 | Host projector: Pin the Spot question | `host/16-question-pin.png` | `host/03-live-game/02-question/06-pin-the-spot.png` |
| 17 | Host projector: MC results bars | `host/17-results-mc.png` | `host/03-live-game/03-results/01-multiple-choice-with-images.png` |
| 18 | Host projector: Pin the Spot results (taps) | `host/18-results-pin.png` | `host/03-live-game/03-results/06-pin-the-spot.png` |
| 19 | Host projector: game over | `host/19-game-over.png` | `host/03-live-game/04-game-over/01-game-over.png` |
| 20 | Host: login | `host/20-login.png` | `host/01-sign-in/01-login--desktop.png` |
| 21 | Host: home (play) | `host/21-home.png` | `host/02-manage/01-play-home--desktop.png` |
| 22 | Host: games | `host/22-games.png` | `host/02-manage/02-games--desktop.png` |
| 23 | Host: question editor, Pin the Spot target picker | `host/23-editor-pin.png` | `host/02-manage/03c-question-editor-edit-pin-the-spot--desktop.png` |
| 24 | Host: image library | `host/24-image-library.png` | `host/02-manage/06-image-library--desktop.png` |
| 25 | Host: image picker modal | `host/25-image-picker.png` | `host/02-manage/03d-image-picker-modal--desktop.png` |
| 26 | Host: roster (after import) | `host/26-roster.png` | `host/02-manage/05c-roster-after-import--desktop.png` |
| 27 | Host: sessions | `host/27-sessions.png` | `host/02-manage/07-sessions--desktop.png` |
| 28 | Admin: users | `admin/28-users.png` | `admin/02-users/01-users--desktop.png` |
| 29 | Admin: user detail | `admin/29-user-detail.png` | `admin/02-users/02-user-detail--desktop.png` |
| 30 | Admin: sessions | `admin/30-sessions.png` | `admin/05-sessions/01-sessions--desktop.png` |

Viewports: player 390×844 at device scale 2; host projector 1920×1080; host manage and admin 1440×900.

**`docs/ui/README.md`**: one row per key screen, with *before* (the matching file from `docs/ui/before/` where one exists, which is
dark-only, since that was the only theme), *after light* and *after dark* side by side, plus a short paragraph on the design language.
The T10 document links it.

**Existing tests:** `tests/e2e` has no selectors on colour classes (checked by grep). They must stay green.

### 4.7 QR codes and the player viewport

- **QR codes** (`QRCodeSVG` in `host/src/pages/game/LobbyPage.tsx:26`, 200px, and `GameLayout.tsx:243`, 96px) stay
  **dark-on-light in both themes**, for scanning reliability. Keep the library defaults (black modules on white), and wrap each SVG
  in a `bg-qr-bg p-3 border-4 border-line shadow-brutal` box. The `qr-bg` token is `#FFFFFF` in both themes, so the box stays white in
  dark mode. The QR codes are never inverted. **Only the QR SVG sits inside the `qr-bg` box.** The "Room Code" label and the code
  itself (`GameLayout.tsx:246–247`, and the lobby's code) sit outside it, on the panel's `surface`, in `ink-muted` / `ink`. The contrast
  test checks `on-fill` on `qr-bg` anyway, in case text is ever put inside the box.
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

The themed version uses **one encoding on both pages** (decided: wrong is muted, not red). The fixed `border-4`/`border-2` widths below
are deliberate rather than `--nb-border`: these bars only ever render at projector density, and the correct bar must stay thicker than
the others to work as a non-colour cue.

| Bar state | Fill | Outline | Extra cue |
|---|---|---|---|
| correct | `bg-success` | `border-4 border-line` (projector density) | "✓ Correct" chip: `nb-chip bg-success text-on-fill` |
| wrong | `bg-surface-muted` | `border-2 border-line` | none (the absence of ✓ is the cue) |
| no key (`correct === null`, polls / put-in-order distribution) | `bg-accent` | `border-2 border-line` | none |
| GameOver score histogram (:337) | `bg-accent` | `border-2 border-line`, no rounding | none |

- To keep both pages in step, factor the class choice into one helper, `barClasses(correct: boolean | null)`, in
  `host/src/lib/answerBars.ts`. It returns `{ bar, label }`: `bar` holds the fill and border classes from the table, and `label`
  holds the text class for anything drawn **on** the bar (`text-on-fill` for correct/no-key, `text-ink` for wrong). Labels and counts
  that sit *beside* the bar use `text-ink`/`text-ink-muted` and don't need `label`. Put-in-order bars need nothing extra:
  `lib/putInOrder.ts::buildPioBars` already returns only `correct: true | null` (no colours), so they go through the same renderer and
  `barClasses()`. Both pages call it instead of choosing colours inline (`colorClass={…}` at GameOver :180/:210/:226
  and `barColor` in ResultsPage). GameOverPage gets the same ✓ chip as ResultsPage.
- Inline "correct" text (`text-green-400` at ResultsPage :81, :350, and the equivalents in GameOverPage) becomes
  `text-success-text font-semibold`.
- **Fill-in-the-blank word cloud** (`ResultsPage.tsx:96`, `isCorrectWord(word) ? 'text-green-400' : 'text-slate-300'`): today
  colour alone marks correct words (WCAG 1.4.1). Correct words become `text-success-text font-bold underline decoration-2` with a
  leading "✓ " (`aria-hidden`, plus an `sr-only` "correct"). Other words are `text-ink-muted`. The ✓ and underline carry the meaning
  without colour.
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
- `image-bg` is softened in dark mode (`#EDE9E0`) to limit glare. Fallback and error text can sit inside these boxes (§4.2), so the
  contrast test checks `on-fill` on `image-bg` in both themes.

### 4.10 Test plan: what's needed, and what was deliberately left out

**The filter.** A test is added only if:
- it guards a T9/R9 requirement;
- the failure it catches is plausible during or after an ~860-edit migration; and
- nothing cheaper already catches it (the static scan, the screenshots, or the manual checks in §7).

Everything else is checked by hand in §7 and shown in the screenshots.

**Integration tests (`tests/integration/`): none.** T9 changes no backend code, REST endpoint or socket event, and R5 scopes
integration coverage to T4, T7 and T8. All existing integration tests must stay green, unchanged.

**Unit tests: one file, `tests/unit/test_theme_tokens.py`** (pure Python, fast, no Docker):

| Test | Guards | Why it's needed |
|---|---|---|
| `test_no_raw_palette_or_forbidden_classes` (the §4.6 scan; `xfail` until the end of step 4) | R9 "hardcoded palette colours are gone"; focus never removed; no translucent text fills; no unloaded weights | ~860 manual edits. After the palette is replaced, a missed class renders as *nothing* rather than failing, so this test is the only thing that notices. |
| `test_scan_patterns` (parametrized known-bad and known-good strings: `border-t-slate-700`, `focus:outline-none`, `bg-accent/40`, `'white'`, `cn('nb-hero', big && 'tracking-tight')` → flagged, `cssVar(c,'--x','#fff')` → allowed, the real `cssVar(canvas, '--pin-full-fill', 'rgba(74, 222, 128, 0.3)')` → allowed, `bg-surface/80` → allowed, …) | The scan itself | The scan is the safety net, and a regex bug makes it pass silently. The second Goldfish pass already found regex gaps. Cheap. |
| `test_token_contrast[light/dark]` | R9 "both themes meet the accessibility bar" (token pairs) | The values are hand-picked and will be tuned after screenshots (§8). Every tweak must re-prove AA. |
| `test_token_parity` | Complete dark theme | A token missing from `[data-theme=dark]` silently inherits the light value from `:root`. That's plausible every time a token is added. It shares the parser with the contrast test, so it costs almost nothing. |

**E2E tests: one new file, `tests/e2e/test_theme_ui.py`** (Playwright against nginx :8080, built `dist/`). The first test and the
login and join part of the second open only a login or join page and need no game. The editor case of the second creates one game
through the API, via the `env`/`cleanup` fixtures, and signs in as `env`'s host.

| Test | Guards | Why it's needed |
|---|---|---|
| `test_theme_defaults_to_os_and_persists[app × scheme]` (apps: host `/host/login`, player `/player/join`, admin `/admin/login`; schemes: light, dark) | R9 "toggle that defaults to the OS preference and persists" (graded explicitly) | The defaulting logic is an inline script copied into three `index.html` files, and `tokens.css` reaches each app through a relative `@import`, so each app can break on its own. Steps: (1) new context with `color_scheme=<scheme>` → `html[data-theme=<scheme>]`, and `body` computed background equals that theme's `canvas`, which proves the tokens actually load; (2) click the toggle → attribute flips, `aria-pressed` flips, the accessible name stays "Dark theme"; (3) reload → still flipped; (4) `page.emulate_media(color_scheme=<opposite of scheme>)` and then back to `<scheme>`, which fires real
`change` events → still flipped (stored beats OS). Emulating the same scheme again would fire no event and prove nothing. |
| `test_focus_outline_and_placeholder[case]` (cases: host `/host/login`, player `/player/join`, admin `/admin/login`, and host `QuestionEditorPage` for a game created through the API, which holds the raw `<textarea>`/`<select>`) | R9 "visible focus states"; placeholder contrast | Both depend on cascade order (§4.3), which is exactly what went wrong twice in review, and the static scan can't see cascade order. Steps: Tab through every focusable element and assert the computed `outline-style` isn't `none` and `outline-width` is ≥ 2px; read `getComputedStyle(input, '::placeholder').color` and assert it equals `ink-muted`. That API was **verified during design** in
Playwright's Chromium: it returns the placeholder colour, not the input's own. The e2e suite runs only Chromium. One theme is enough, since the colours are already proven by the contrast unit test. |

**Rendered-contrast check: an axe-core assertion inside the capture module, not a separate test.** Token contrast doesn't
prove that pages *use* the right pairs. For example, `bg-accent` with inherited `ink` text is 1.7:1 in dark mode, and neither the
scan nor the unit test sees it. R9 graders check the running app. So at every screenshot point in `tests/e2e/capture_ui_screens.py`
(30 screens × 2 themes, §4.6), run axe-core's `color-contrast` and `link-in-text-block` rules. **Collect, don't abort.** Each
shot's violations are appended to a list, the run finishes all 60 shots, and the test fails at the end with one report grouped by
screen (rule, selector, ratio). The report is also written to `docs/ui/after/axe-report.txt`. Aborting on the first violation
would leave a half-captured, half-played game. The module already drives every key
screen in both themes, so this adds no game setup. It adds one dependency, `axe-playwright-python`, in
`tests/e2e/requirements.txt`. Because the capture module isn't part of the normal `pytest` run, this check runs whenever screenshots
are produced, which is the moment the evidence for R9 gets created.

**Fixture changes, `tests/e2e/conftest.py`** (needed for the above, and they fix an existing gap):
- `page_as(token, *, color_scheme=None, **context_opts)`: pass `color_scheme` and any other context options (`viewport`,
  `device_scale_factor`) to `browser.new_context`. Existing call sites are unchanged.
- `_built_apps_are_current` today checks only `host` and `admin` `src/`. Extend it to `player`, and for every app, include
  `index.html`, `tailwind.config.ts`, and the shared `frontend/theme/` folder in the "newest source" time. Otherwise, editing a token
  leaves a stale `dist/` that the e2e tests silently run against.

**Existing e2e tests.** Checked: no selector relies on colour classes. The selectors that count buttons are scoped to a table row
(`test_host_admin_ui.py:159`, `:184`). The option-image test matches `name=re.compile("Blue")`, which still matches with an "A"/"B"
letter badge in front. So the new toggle and badges don't break them. They must stay green.

**Left out on purpose (covered by §7 manual checks or the screenshots):**
- live OS-change following and cross-tab sync (not required by T9);
- the no-flash init (polish, not graded);
- Pin the Spot repaint on toggle (rare in practice; manual check);
- QR and image-well backings, tap-target sizes, `theme-color` (visible in the screenshots, and set once with little room to regress);
- answer-bar encoding (one shared helper, `barClasses()`, makes the two pages unable to diverge);
- **non-text contrast (WCAG 1.4.11)**: outlines, spinners, the timer bar, checkboxes and canvas markers. axe's `color-contrast` rule
  checks text only. Graphics are covered by the token rule "`line` ≥ 3:1" in the unit test, and by eye on the screenshots in §7;
- a JS unit-test runner for `theme.ts` (the repo has none, and the e2e test exercises the real logic in a real browser).

### 4.11 States, type scale, spacing and layout contract

**Interactive states** (decided: lift and press). Defined once in `.nb-press` and the primitives:

| State | Rule |
|---|---|
| Hover (pointer devices only: `@media (hover: hover)`) | `.nb-press:hover` → `translate(-1px, -1px)` and the shadow grows to `calc(var(--nb-offset) + 1px)`. Ghost and outline buttons also fill `surface-muted`. No colour change on filled buttons, so there are no hover colour tokens to contrast-test. |
| Active | Press in: `translate(var(--nb-offset), var(--nb-offset))`, no shadow (§4.3.1). Replaces today's `active:scale-95` (13 uses). |
| Disabled | `disabled:` variants only: `bg-surface-muted text-ink-muted shadow-none`, no hover lift or press (`.nb-press:disabled` resets transform), `cursor-not-allowed`. `disabled:opacity-60` is also allowed, since WCAG 1.4.3 exempts inactive components. Replaces today's `disabled:opacity-20/40/50`. |
| Selected (answer tiles, put-in-order picks, admin list rows) | `.nb-selected` (a 3px `on-fill` **inset** ring inside the unchanged border, §4.3.1) plus a ✓ badge (`nb-chip bg-surface text-ink`) in the tile's top-right corner. Only on filled elements: selected list rows become `bg-accent text-on-fill`. The border width never changes, so tiles don't shift and grid rows stay put (the player's "nothing moves under a finger" rule). Colour is never the only cue. |
| Selected + hover | Ring kept, lift applied (the plugin's `.nb-press.nb-selected:hover`). |
| Locked or submitted (player) | **Unselected** tiles take the disabled state (grey `surface-muted`, `ink-muted`, no shadow). **Selected** tiles keep their fill, their `on-fill` ring and their ✓ badge, and lose only the offset shadow (`.nb-press.nb-selected:disabled`), so the player still sees what they chose after the host locks. Tiles therefore apply the disabled grey conditionally (`!selected && 'disabled:bg-surface-muted disabled:text-ink-muted'`). The existing "locked" copy stays. |

Under `prefers-reduced-motion: reduce`, hover and press change only the shadow, with no translate and no transition.

**Type and spacing scale** (decided: bold contrast, applied through component classes). The values live in the §4.3.1 density
variables. Pages use the `.nb-h1/.nb-h2/.nb-h3/.nb-body/.nb-prompt/.nb-caption/.nb-stat/.nb-page/.nb-card/.nb-stack` classes and
never pick their own sizes. The table shows the equivalent Tailwind sizes, for reference:

| Role | compact (admin) | comfortable (player, host manage) | projector (host `/game/*`) | Face |
|---|---|---|---|---|
| Page title (`h1`) | `text-2xl` | `text-3xl` | `text-6xl` | `font-display font-bold` |
| Section title (`h2`) | `text-lg` | `text-xl` | `text-4xl` | `font-display font-bold` |
| Card title (`h3`) | `text-base` | `text-lg` | `text-2xl` | Inter `font-semibold` |
| Body, prompts | `text-sm` | `text-base` | `text-2xl` (question prompt: `text-4xl`, Inter `font-semibold`) | Inter `font-normal` |
| Caption, labels | `text-xs` | `text-sm` | `text-lg` | Inter `font-medium`, `text-ink-muted`, `uppercase tracking-wide` |
| Page padding | `p-4` | `p-5` | `p-10` | |
| Card padding | `p-3` | `p-5` | `p-8` | |
| Stack gap | `gap-3` / `space-y-3` | `gap-4` / `space-y-4` | `gap-8` / `space-y-8` | |

- Each page has exactly one `h1`. Section and card titles use the real heading elements (`h2`, `h3`), so the hierarchy is visible to
  assistive tech too.
- **Numbers and glyphs use exactly one mechanism each.** Every site that's `text-5xl` or larger today is listed here:

  | Element | Class | Projector / comfortable size (today) |
  |---|---|---|
  | Lobby room code (host `LobbyPage.tsx:32`, `text-8xl`) | `.nb-hero` | 6rem (6rem) |
  | Player final rank (`player GameOverPage.tsx:171`, `text-5xl`) | `.nb-hero` | 3rem (3rem) |
  | Player option fallback letter (`QuestionPage.tsx:39`) | `.nb-hero` + `text-on-fill` | 3rem (3rem) |
  | Player lock glyphs 🔒 (`QuestionPage.tsx:210`, `FeedbackPage.tsx:4`) | `.nb-hero` | 3rem (3rem / 3.75rem) |
  | "Game Over!" (host `GameOverPage.tsx:320`) | `.nb-h1` (it's the page title) | 3.75rem (3rem) |
  | Scores, timers, answer counts, leaderboard points | `.nb-stat` | 3rem / 1.5rem |
  | Room code in the projector's corner QR panel (`GameLayout.tsx:247`, `text-lg`) | `.nb-code` | 1.5rem (1.125rem) |

  Nothing shrinks on the projector.
- **The one exception to "no size utilities":** the fill-in-the-blank word cloud (`ResultsPage.tsx` `sizeClass`, `text-base`…`text-5xl`)
  keeps its size ramp, because there size *encodes frequency*. Its `font-black` becomes `font-bold` (Inter). The word cloud never
  carries an `.nb-*` type class, so the scan rule doesn't conflict.

**Player layout contract** (needed because of the in-flow header row, §4.4). There are 11 `min-h-screen` uses in the player app
today, and with a 56px header above them, every centred screen would scroll by 56px.
- `App.tsx`: the root is `flex flex-col h-[100dvh]`. The header is `shrink-0` and padded by `env(safe-area-inset-top)`. The routes
  wrapper is `<main class="flex-1 min-h-0 overflow-y-auto">`.
- Pages replace `min-h-screen` with `min-h-full`, which centres within `main`, not the viewport.
- The `22vh` option-image sizing (`QuestionPage.tsx:21`, `:29`) and the Pin the Spot canvas must still fit at 390×844 without
  scrolling `main`. Recheck them, and switch `22vh` to `22dvh` if needed.

**Remaining unmapped elements, now mapped:**
- **Spinners** (player `LobbyPage.tsx:19`, `FeedbackPage.tsx:7`): `border-4 border-shadow border-t-accent rounded-full
  animate-spin`. The information is the moving `accent` arc. It must clear 3:1 (WCAG 1.4.11) against both neighbours, the track and
  the canvas:
  - **light:** arc/track 13.3:1, arc/canvas 1.3:1. The arc is still bounded by the near-black track on its own ring, so it reads.
  - **dark:** arc/track 10.1:1, arc/canvas 8.9:1.

  A `line` track fails in dark mode (arc/track 1.9:1), and a `surface-muted` track fails in light mode (about 1.2:1). They keep spinning under reduced
  motion, because a spinner is an essential loading indicator.
- **Tables:** the admin table rules (ruled `border-line` rows, a `surface-muted` header, zebra stripes, no per-row shadows) apply to
  **every** table, including host `RosterPage` (the only host `<table>`) and list-style rows in host `SessionsPage` and `GamesPage`.
- **Native checkboxes and radios** (admin `SessionsPage`, `UserDetailPage`; host `RosterPage`): in the preset plugin's `addBase`,
  `input[type=checkbox], input[type=radio] { accent-color: rgb(var(--ink)); width: 1.125rem; height: 1.125rem; }`. Yellow `accent`
  would fail 3:1 non-text contrast on cream; `ink` is about 17:1 in light and 13:1 in dark. They take the global focus outline.

## 5. Implementation steps (in order)

Each step is one or more atomic commits on `feature/better-ui`. **This doc and `docs/ui/before/` are committed before step 1**
(T3/R4: design before implementation).

**Step 1: Shared folder and build-config fixes (one app first, then the other two).**
- **Stop `tsc -b` from emitting config JavaScript.** Today `tsc -b` writes untracked (gitignored) `tailwind.config.js`,
  `vite.config.js` and `.d.ts` files next to the `.ts` configs, and **both Tailwind 3 and Vite load the `.js` before the `.ts`**.
  Edits to `tailwind.config.ts` or `vite.config.ts` are silently ignored under `npm run dev` until the next build. Adding
  `../theme/preset.ts` to the composite project would also emit `frontend/theme/preset.js` and `preset.d.ts`.
  - Fix: in each `tsconfig.node.json`, add `"noEmit": true` (allowed with `composite` in TS ≥ 5.6; every lockfile pins 5.9.3, while
    `package.json` says `^5.5.3`; raise the range to `"typescript": "^5.6.0"` in all three apps so the floor is stated, not just locked) and
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
- In every primitive, **delete** `rounded-lg`/`rounded-xl` (host and admin `button`/`card`/`input` are `rounded-lg`; player's are
  `rounded-xl`, and its card is `rounded-2xl`), any `shadow-*`, and `active:scale-95`. They're replaced by `.nb-box`/`.nb-press`.
- In every primitive, **delete** `focus:outline-none`, `focus:ring-*` and `focus:ring-offset-*`. The base-layer `:focus-visible`
  outline (§4.3) is the only focus style.
- `card.tsx`: `nb-box`. `input.tsx`: surface, line border, and the global placeholder colour (§4.3). The player input is `text-base` or larger.
- `lib/utils.ts`: `extendTailwindMerge` with the shadow keys, plus the three `cn()` checks (§4.3.2).
- `TimerBar.tsx` (host and player): the track becomes `bg-surface-muted border-2 border-line` (square, no `rounded-full`). The fill goes
  `success` → `warning` → `danger` as time runs out. The fill segment carries a `border-r-2 border-line` edge whenever its width is
  above 0, so it obeys the rule that every fill has an outline (§4.2) and stays distinct from the track in light mode. **The seconds text is the existing separate `<span>` beside the bar, not on the
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
| `text-indigo-*` (18 sites: links, emphasis) | `text-ink underline decoration-line decoration-2 underline-offset-2`, with `hover:decoration-accent`. The underline must be `line`: a yellow underline on cream is about 1.3:1 and the link would read as body text. Yellow is for hover only. |
| `bg-green-*` / `text-green-*` | `bg-success text-on-fill` / `text-success-text` |
| `bg-red-*` / `text-red-*` | `bg-danger text-on-fill` / `text-danger-text` |
| `bg-yellow|amber-*` / `text-…` | `bg-warning text-on-fill` / `text-warning-text` |
| `bg-black/50` etc. (modal scrims) | `bg-scrim/60` |
| `font-black` | `font-display font-bold` (headings, scores, codes) or `font-bold` (§4.1) |
| `focus:outline-none`, `focus:ring-*`, `focus:ring-offset-*`, `ring-offset-*` (on raw `<textarea>`/`<select>`/`<input>` in pages too) | delete (§4.1) |
| bar colours on ResultsPage / GameOverPage | `barClasses()` (§4.8) |
| headings and ad-hoc `text-xl`/`text-3xl`/`p-4`/`gap-*` on titles, cards and page wrappers | `.nb-h1`/`.nb-h2`/`.nb-h3`/`.nb-caption`/`.nb-stat` and `.nb-page`/`.nb-card`/`.nb-stack` (§4.3.1); drop the size and padding utilities |
| `hover:bg-*`, `hover:text-*`, `hover:border-*` | `.nb-press` lift (filled buttons) or `hover:bg-surface-muted` (ghost/outline), per §4.11 |
| `active:scale-95` | `.nb-press` |
| `rounded-sm/md/lg/xl/2xl/3xl`, `rounded-t-lg` (117 `rounded*` uses today) | remove (square); bare `rounded` only on chips, badges and inputs; `rounded-full` only on spinners, pills and avatars |
| `shadow`, `shadow-xl` (5), `backdrop-blur-sm` (1, the corner QR panel) | `.nb-box` / `shadow-brutal*`; drop the blur (the panel is an opaque `surface`) |
| `disabled:opacity-*`, conditional `opacity-50 cursor-not-allowed` | `disabled:` state per §4.11, plus the `disabled` attribute |
| `opacity-*` on content (fallback letter, roster rows) | `text-on-fill` / `text-ink-muted` + `line-through` / "Inactive" chip (§4.2) |
| player `min-h-screen` | `min-h-full` (§4.11 layout contract) |
| spinners (`animate-spin` with palette borders) | §4.11 spinner classes |
| `<img>` of an uploaded image | add `bg-image-bg` to it or its box (§4.9) |
| Player `OPTION_COLORS` (`pages/game/QuestionPage.tsx:9`) | Keep a `const OPTION_FILLS = ['bg-option-1', …, 'bg-option-8']` array of **literal strings**, so Tailwind's content scan sees all eight; never build `bg-option-${n}`. Each tile uses `OPTION_FILLS[i % 8]` with `text-on-fill border-line`, and drops the per-option `hover:`/`border-` colours. Past 8 options the colours repeat, as they do today (the backend has no option limit); the letter badge (A, B, C, …, which keeps counting) tells repeated colours apart. |
| Admin `STATUS_COLORS` (`pages/SessionsPage.tsx:34`) | `nb-chip` with `bg-success` (active) / `bg-warning` (lobby) / `bg-surface-muted` (completed) |

Then the per-context passes:
- **Player:** answer tiles at least 56px tall and full-width, a 3px outline, `brutal` shadow and press, `touch-action: manipulation`.
  The selected state is `.nb-selected` (a constant border, an inset `on-fill` ring and a ✓ badge, §4.11). Not a thicker outline, which would shift the layout. Put-in-order chips and the Pin the Spot "lock in"
  button follow the same rules. Bottom action areas pad by `env(safe-area-inset-bottom)`.
- **Host projector** (`pages/game/*`, `data-density="projector"`): prompt `.nb-prompt` (Inter, not the display face, §4.1), room code
  `.nb-hero` (lobby) or `.nb-code` (corner panel), scores and counts `.nb-stat`, as in §4.11,
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
  `tests/unit/test_theme_tokens.py`, `tests/e2e/test_theme_ui.py`, `tests/e2e/capture_ui_screens.py`,
  edits to `tests/e2e/conftest.py` and `tests/e2e/requirements.txt` (`axe-playwright-python`), `docs/ui/README.md`, `docs/ui/after/**`.
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
   `pytest tests/e2e/test_theme_ui.py` passes, and `pytest tests/e2e/capture_ui_screens.py` passes (axe finds no contrast
   violations on any key screen in either theme).
2. CI parity: `ruff check backend/ scripts/ tests/`, `ruff format --check backend/ scripts/`, and `npx tsc --noEmit` in all three apps.
3. `npm run build` succeeds and leaves no emitted `.js`/`.d.ts` next to the configs or in `frontend/theme/`. `pytest tests/integration`
   and `pytest tests/e2e` pass against the Docker stack.
4. Manual, at nginx :8080, in each app:
   - Clear storage and set the OS to dark: the app opens dark, with no light flash. Set the OS to light: it opens light.
     Change the OS setting while the app is open (no stored choice): the app follows live.
   - Toggle the theme and reload: the choice persists. Toggle in admin: an open host tab updates without a reload.
   - Tab through every page: the focus outline is visible on every interactive element in both themes, and **not clipped** by an
     `overflow-hidden` ancestor (8 exist today) or by the player's scrolling `main`. The e2e test only reads the computed style, so
     clipping is checked here. Where it clips, use `outline-offset: -3px` on that element or remove the overflow.
   - Play a full game covering every question type (the fixture from §4.6, or `scripts/seed_demo.py` plus the T6 games with
     `scripts/simulate_players.py`). Every screen looks intentional in both themes, Pin the Spot repaints on toggle, and QR codes
     scan from a phone in both themes.
   - Player at 390×844: no horizontal scroll, **no vertical scroll on join, name, lobby, feedback and results**, tap targets ≥ 44px, the toggle never covers an input, pinch-zoom works, and focusing an
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

**Revision 4** came from planning which tests T9 actually needs (§4.10). Applying the "is this test needed?" filter exposed one
real defect in revision 3:

| # | Finding | Verified? | Change |
|---|---|---|---|
| 1 | Revision 3's `::placeholder` rule in `tokens.css` can never win. Preflight's `input::placeholder, textarea::placeholder` has higher specificity (0,0,2 vs 0,0,1) and comes later. | Yes (`preflight.css` ~333) | Rule moved to each app's `@layer base` with preflight's exact selector (§4.3) |
| 2 | No test plan. The e2e build guard ignores the player app and would ignore `frontend/theme/` | Yes (`conftest.py::_built_apps_are_current` checks host and admin only) | §4.10: four unit tests, two e2e tests, an axe contrast check in the capture module, fixture fixes, and an explicit list of what is *not* tested and why |

**Revision 5** was revised after a third Goldfish pass. Every finding was verified against the code. Three claims turned out wrong,
and the log records them, rather than dropping them, so the reasoning is visible.

| # | Goldfish finding | Verified? | Change |
|---|---|---|---|
| C1 | Text inside `image-bg`/`qr-bg` inherits off-white `ink` (~1.1:1) | Yes: fallback letter (`player QuestionPage:39`), "Image failed to load" ×3, "Missing image". The room code is **outside** the QR box (`GameLayout:242–247`). | `text-on-fill` inside those boxes; `on-fill` on `image-bg`/`qr-bg` added to the contrast test; room-code placement stated (§4.2, §4.7, §4.9) |
| C2 | No spacing, type scale or hierarchy, which R9 grades | Yes | Bold-contrast scale per density (decided), heading elements, mapping row (§4.11) |
| C3.1 | Word cloud marks correct words by colour only | Yes (`ResultsPage:96`) | ✓, bold and underline, plus `sr-only` text (§4.8) |
| C3.2 | `buildPioBars` is a third bar-colour site | **No**: it returns `correct: true\|null`, and colours are picked by the shared renderer | Stated in §4.8. No new site. |
| C4 | Media-scoped `theme-color` metas ignore the toggle | Yes (first matching meta wins) | A single meta, set by the no-flash script and `applyTheme()` (§4.3) |
| C5 | Opacity on `ink*` unchecked; translucent text unmapped | Partly: no `text-*/NN` today, but `opacity-*` dims content (fallback letter, roster rows) | Text opacity banned; element opacity only via `disabled:`; content sites mapped; scan rules (§4.2, §4.6) |
| C6 | Hover, active, disabled and selected unmapped | Yes (e.g. 13 `active:scale-95`, 10 `hover:bg-indigo-500`, `disabled:opacity-20/40/50`) | Lift-and-press states (decided), `border-5` selected, mapping rows (§4.11) |
| C7 | The header row causes vertical scroll | Yes: 11 `min-h-screen` in the player app | Flex-column layout contract, `min-h-full`, a scan rule and a §7 check (§4.11) |
| C8 | `tokens.css` structure unpinned, but the tests depend on it | Yes | Exact blocks, selectors, invariant set, `--pin-marker-stroke` value, test exemptions (§4.3.3) |
| C9 | Test-plan inconsistencies | Two of three. "Needs no game" was wrong for the editor case, and "emulate the same scheme" fired no event. Screen 02 **was** reachable (`page_as(None)` shows the guest form). | Editor case uses API fixtures; step 4 emulates the opposite scheme, then back; screen 02 note (§4.10, §4.6) |
| C10 | `barClasses()` doesn't give label text a colour | Yes | Returns `{ bar, label }` (§4.8) |
| C11 | Spinners, host tables, checkboxes, projector toggle position | Yes: 2 spinners, checkboxes in 3 files, `RosterPage` table, QR panel bottom-right | Mapped in §4.11; projector toggle fixed bottom-left (§4.4) |
| C12 | Sanitised prompt HTML may need themed rules | **No**: no `dangerouslySetInnerHTML`/`innerHTML` in any frontend, so prompts are plain text. The display-face point was valid. | Prompts use Inter, not the display face (§4.1, §4.11) |

**Revision 6** was revised after a fourth Goldfish pass. Every finding was verified.

| # | Goldfish finding | Verified? | Change |
|---|---|---|---|
| C1 | Spinner `surface-muted`/`accent` on cream is about 1.1:1 / 1.3:1 (fails 1.4.11); the TimerBar fill has no outline; axe checks text only | Yes (computed) | Spinner track is `line`; TimerBar fill gets a `border-r-2 border-line` edge; non-text contrast listed as checked by hand (§4.11, step 3, §4.10) |
| C2 | Yellow link underline on cream is about 1.3:1, so links look like body text | Yes: 18 `text-indigo-*` | Underline is `line`; yellow only on hover; axe `link-in-text-block` enabled |
| C3 | The type scale has no mechanism | Yes | `.nb-h*`/`.nb-body`/`.nb-prompt`/`.nb-caption`/`.nb-stat`/`.nb-page`/`.nb-card`/`.nb-stack` on density variables (decided), plus a scan rule against mixing them with size utilities (§4.3.1, §4.6) |
| C4 | Nothing in CI protects the scan after T9 | Yes (CI runs only ruff, tsc and secret detection) | **Decided: no guard added.** The scan runs in `pytest tests/unit` only. |
| C5 | `border-5` selection shifts layout | Yes | Constant border plus a `.nb-selected` inset ring; `border-5` removed (§4.11, §4.3.1) |
| C6 | "three variables" listed two; §4.3.3 before §4.3.2; blocks 2 and 5 shared a selector | Yes | Sections reordered and rewritten; block 5 uses `html`/`html[data-theme=dark]`/`body` so every selector is unique; parser rule stated (§4.3.3) |
| C7 | Before/after pairing undefined | Yes: the before set uses a different naming scheme | A 30-row table with exact after and before paths; all 30 have a before shot (§4.6) |
| C8 | axe aborting mid-run; focus test misses clipped outlines | Yes: 8 `overflow-hidden` | Collect-then-fail with a written report; manual clipping check (§4.10, §7) |
| C9 | `--pin-*` theme colours and `applyTheme` duplicate hex values | Yes | `--pin-*` derive from tokens via `rgb(var(--…))` (browser check in step 5, with a hex fallback); `applyTheme` reads computed `--canvas` (§4.3.3, §4.3) |

**Revision 7** was revised after a fifth Goldfish pass. Two items (C4, and the step-5 `--pin-*` check) were **verified empirically**
during design with a Playwright Chromium probe, rather than deferred.

| # | Goldfish finding | Verified? | Change |
|---|---|---|---|
| C1 | `.nb-stat` (2.25rem) would shrink the 6rem lobby room code; two mechanisms for the same element | Yes (`LobbyPage:32` `text-8xl`). **Corrections:** `ResultsPage:64` is the word-cloud frequency ramp, and `GameOverPage:320` is the page title. Neither is a stat. | `--nb-stat` and `--nb-hero` variables, `.nb-hero`/`.nb-code` classes, a site-by-site table (nothing shrinks), and a word-cloud exception (§4.3.1, §4.11) |
| C2 | Radius and soft shadows unmapped and unscanned | Yes: 117 `rounded*`, 5 soft `shadow`, 1 `backdrop-blur` | The preset replaces the radius and shadow scales (staged with colours), plus scan rules, a mapping row and step-3 primitive stripping (§4.1, §4.3, §4.6) |
| C3 | Capture module unbuildable: viewport/DPR, roster data, shot order, differing data between themes | Yes (`page_as` builds the context at `conftest.py:105`) | `**context_opts` pass-through; roster import via `routers/host.py:256`; one test with a fixed order (two games, then all manage/admin shots); screen 29 defined (§4.6, §4.10) |
| C4 | `getComputedStyle(el, '::placeholder')` support unknown | **Verified OK** in Chromium (returns the placeholder colour) | Stated in §4.10 |
| C5 | Mixing rule only sees one string | Yes | The class string includes all args of one `cn(…)` call; cross-file `className` props are a documented limitation (§4.3.1, §4.6) |
| C6 | Housekeeping | Yes | This row; §4.8 explains the fixed bar border widths |

**Revision 8** was revised after a sixth Goldfish pass. Contrast values were recomputed with the WCAG formula.

| # | Goldfish finding | Verified? | Change |
|---|---|---|---|
| 1 | The dark spinner fails 1.4.11 (arc/track 1.92:1); the doc quoted the light value | Yes (computed) | Track is `shadow`: arc/track 13.3 (light) / 10.1 (dark) (§4.11) |
| 2 | Selected ring weak in dark (`line` on fills 1.26–2.13:1); hidden by hover (0,2,0 > 0,1,0); lost when disabled | Yes (computed) | `on-fill` ring (≥ 6.1:1), only on filled elements; `.nb-press.nb-selected:hover/:disabled` at 0,3,0; locked-and-selected tiles keep fill, ring and ✓ (§4.3.1, §4.11) |
| 3 | §4.3 used block 2's selector for `color-scheme` | Yes | `html` / `html[data-theme=dark]` (§4.3) |
| 4 | Step 4 still said "thicker outline" | Yes | Points to `.nb-selected` |
| 5 | `cssVar` exemption had no parse rule (nested parens at `PinBoard.tsx:111`) | Yes | Exact third-argument rule and regex; the real string added to `test_scan_patterns` (§4.6, §4.10) |
| 6 | Named-colour "allow-list below" didn't exist | Yes | No allow-list (§4.6) |
| 7 | Mixing regex missed `nb-hero`/`nb-code`, `tracking-*`, `leading-*` | Yes | Added (§4.3.1, §4.6) |
| 8 | ~80 lines of `@layer` CSS copied into three apps | Yes | **Decided:** a Tailwind plugin in the shared preset; `index.css` is four lines; copying recorded in §3 (§4.3) |
| 9 | TS floor not pinned (`^5.5.3` vs `noEmit`+`composite` needing ≥ 5.6) | Yes (lockfiles pin 5.9.3) | Raise to `^5.6.0` (step 1) |
| 10 | `.nb-caption` on a fill is ~1.1:1 | Yes | Never on a fill; `text-on-fill` override (§4.3.1) |
| 11 | Options past 8; dynamic `bg-option-${n}` dropped by the content scan | Yes (backend has no limit; player cycles `i % 8`) | Literal-string array, cycling, letter badge disambiguates (step 4 mapping) |
| 12 | HTML session summary scope unstated | n/a | Explicitly out of scope (§1) |
