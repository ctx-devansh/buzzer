/*
 * Shared Tailwind preset for host, player and admin (T9). Spec: docs/design-better-ui.md §4.3.
 *
 * This file must not import anything (not even types from 'tailwindcss'): frontend/theme/ has no
 * node_modules, so a bare import would not resolve. Each app's tailwind.config.ts applies
 * `satisfies Config` instead.
 */

/**
 * Staging switch (§4.3). While pages are being migrated, the tokens are *added* next to Tailwind's
 * own palette, radii and soft shadows, so unmigrated pages still render. The last migration commit
 * flips this to true, which *replaces* those scales: any leftover `bg-slate-800`, `rounded-xl` or
 * `shadow-xl` then produces no CSS, and tests/unit/test_theme_tokens.py fails on it.
 */
const REPLACE_DEFAULT_SCALES = true;

const TOKENS = [
  'canvas', 'surface', 'surface-muted', 'ink', 'ink-muted', 'line', 'shadow', 'scrim', 'qr-bg', 'image-bg',
  'on-fill', 'accent', 'accent-2', 'info', 'success', 'danger', 'warning',
  'success-text', 'danger-text', 'warning-text', 'focus',
  'option-1', 'option-2', 'option-3', 'option-4', 'option-5', 'option-6', 'option-7', 'option-8',
] as const;

const color = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export const tokenColors: Record<string, string> = Object.fromEntries(TOKENS.map((t) => [t, color(t)]));

export const DISPLAY_STACK = ['"Space Grotesk"', 'system-ui', 'sans-serif'];
export const SANS_STACK = ['Inter', 'system-ui', 'sans-serif'];

const display = DISPLAY_STACK.join(', ');
const sans = SANS_STACK.join(', ');
const hardShadow = (offset: string) => `${offset} ${offset} 0 0 rgb(var(--shadow))`;

const brutalShadows = {
  'brutal-sm': hardShadow('2px'),
  brutal: hardShadow('4px'),
  'brutal-lg': hardShadow('6px'),
};

// ---------------------------------------------------------------------------
// The .nb-* plugin (§4.3, §4.3.1, §4.11): base rules and component classes, defined once.
// ---------------------------------------------------------------------------

export type CSSRule = { [key: string]: string | CSSRule };
export interface NbPluginApi {
  addBase(rules: CSSRule): void;
  addComponents(rules: CSSRule): void;
}

const offsetShadow = 'var(--nb-offset) var(--nb-offset) 0 0 rgb(var(--shadow))';
const liftedShadow = 'calc(var(--nb-offset) + 1px) calc(var(--nb-offset) + 1px) 0 0 rgb(var(--shadow))';
const selectedRing = 'inset 0 0 0 3px rgb(var(--on-fill))';

function nbPlugin({ addBase, addComponents }: NbPluginApi): void {
  addBase({
    // The only focus style. Utilities that remove it (outline-none, focus:ring*) are banned by the scan,
    // because any utility beats a base rule (§4.1).
    ':focus-visible': { outline: '3px solid rgb(var(--focus))', 'outline-offset': '2px' },
    // Same selector as preflight's, so equal specificity plus later position wins (§4.3).
    'input::placeholder, textarea::placeholder': { color: 'rgb(var(--ink-muted))', opacity: '1' },
    // ink, not accent: yellow would fail 3:1 non-text contrast on cream (§4.11).
    'input[type=checkbox], input[type=radio]': {
      'accent-color': 'rgb(var(--ink))',
      width: '1.125rem',
      height: '1.125rem',
    },
  });

  addComponents({
    // Box and states
    '.nb-box': {
      'background-color': 'rgb(var(--surface))',
      border: 'var(--nb-border) solid rgb(var(--line))',
      'box-shadow': offsetShadow,
    },
    '.nb-press': { transition: 'transform 80ms ease-out, box-shadow 80ms ease-out' },
    '@media (hover: hover)': {
      '.nb-press:hover:not(:disabled)': { transform: 'translate(-1px, -1px)', 'box-shadow': liftedShadow },
      // 0,4,0 beats the plain hover (0,3,0), so hovering a selected item keeps its ring.
      '.nb-press.nb-selected:hover:not(:disabled)': { 'box-shadow': `${selectedRing}, ${liftedShadow}` },
    },
    '.nb-press:active:not(:disabled)': {
      transform: 'translate(var(--nb-offset), var(--nb-offset))',
      'box-shadow': 'none',
    },
    '.nb-press:disabled': { transform: 'none', 'box-shadow': 'none', cursor: 'not-allowed' },
    // Selected is drawn inside a constant border, so nothing moves under a finger. It's only used on
    // filled elements: the on-fill ring is >= 6.1:1 on every fill in both themes (§4.3.1). Its hover
    // and disabled variants are more specific than .nb-press's, so selection always shows.
    '.nb-selected': { 'box-shadow': `${selectedRing}, ${offsetShadow}` },
    '.nb-press.nb-selected:disabled': { 'box-shadow': selectedRing, transform: 'none' },
    '@media (prefers-reduced-motion: reduce)': {
      '.nb-press': { transition: 'none' },
      '.nb-press:hover:not(:disabled), .nb-press:active:not(:disabled)': { transform: 'none' },
    },
    '.nb-chip': {
      display: 'inline-flex',
      'align-items': 'center',
      gap: '0.25rem',
      padding: '0.125rem 0.5rem',
      border: '2px solid rgb(var(--line))',
      'border-radius': '4px',
      'font-size': '0.875rem',
      'line-height': '1.25rem',
      'font-weight': '600',
    },

    // Typography (sizes come from the density variables in tokens.css)
    '.nb-h1': { 'font-family': display, 'font-weight': '700', 'font-size': 'var(--nb-h1)', 'line-height': '1.1' },
    '.nb-h2': { 'font-family': display, 'font-weight': '700', 'font-size': 'var(--nb-h2)', 'line-height': '1.1' },
    '.nb-h3': { 'font-family': sans, 'font-weight': '600', 'font-size': 'var(--nb-h3)', 'line-height': '1.3' },
    '.nb-body': { 'font-family': sans, 'font-weight': '400', 'font-size': 'var(--nb-body)', 'line-height': '1.5' },
    '.nb-prompt': { 'font-family': sans, 'font-weight': '600', 'font-size': 'var(--nb-prompt)', 'line-height': '1.3' },
    // Never on a fill: ink-muted on a dark fill is ~1.1:1. On fills, add text-on-fill (§4.3.1).
    '.nb-caption': {
      'font-family': sans,
      'font-weight': '500',
      'font-size': 'var(--nb-caption)',
      'line-height': '1.4',
      color: 'rgb(var(--ink-muted))',
      'text-transform': 'uppercase',
      'letter-spacing': '0.05em',
    },
    '.nb-stat': {
      'font-family': display,
      'font-weight': '700',
      'font-size': 'var(--nb-stat)',
      'line-height': '1.1',
      'font-variant-numeric': 'tabular-nums',
    },
    '.nb-hero': {
      'font-family': display,
      'font-weight': '700',
      'font-size': 'var(--nb-hero)',
      'line-height': '1',
      'letter-spacing': '0.08em',
      'font-variant-numeric': 'tabular-nums',
    },
    '.nb-code': {
      'font-family': display,
      'font-weight': '700',
      'font-size': 'var(--nb-h3)',
      'line-height': '1.1',
      'letter-spacing': '0.15em',
      'font-variant-numeric': 'tabular-nums',
    },

    // Spacing
    '.nb-page': { padding: 'var(--nb-page-pad)' },
    '.nb-card': {
      'background-color': 'rgb(var(--surface))',
      border: 'var(--nb-border) solid rgb(var(--line))',
      'box-shadow': offsetShadow,
      padding: 'var(--nb-card-pad)',
    },
    '.nb-stack': { display: 'flex', 'flex-direction': 'column', gap: 'var(--nb-gap)' },
  });
}

// ---------------------------------------------------------------------------
// The preset
// ---------------------------------------------------------------------------

const replaced = {
  colors: { transparent: 'transparent', current: 'currentColor', inherit: 'inherit', ...tokenColors },
  boxShadow: { none: 'none', ...brutalShadows },
  borderRadius: { none: '0', DEFAULT: '4px', full: '9999px' },
};

export const preset = {
  theme: {
    ...(REPLACE_DEFAULT_SCALES ? replaced : {}),
    extend: {
      ...(REPLACE_DEFAULT_SCALES ? {} : { colors: tokenColors, boxShadow: brutalShadows }),
      // Always under extend, never theme (§4.3): Tailwind's own versions of these spread
      // theme('colors'), which is what generates border-line, ring-focus and the rest.
      borderColor: { DEFAULT: color('line') },
      ringColor: { DEFAULT: color('focus') },
      outlineColor: { DEFAULT: color('focus') },
      // No <alpha-value> here: preflight copies this DEFAULT verbatim into --tw-ring-offset-color.
      ringOffsetColor: { DEFAULT: 'rgb(var(--canvas))' },
      borderWidth: { 3: '3px' },
      fontFamily: { display: DISPLAY_STACK, sans: SANS_STACK },
    },
  },
  plugins: [nbPlugin],
};

export default preset;
