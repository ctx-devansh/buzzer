/*
 * Theme runtime shared by host, player and admin (T9). Spec: docs/design-better-ui.md §4.4.
 *
 * Dependency-free on purpose (no React): bare imports resolve from the importing file's folder, and
 * frontend/theme/ has no node_modules. Each app wraps this in src/lib/theme.ts with a useTheme() hook.
 *
 * The first paint is handled by the inline script in each app's index.html, which duplicates the
 * "stored choice, else OS preference" rule below. Keep the two in sync.
 */

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'buzzer-theme';
const listeners = new Set<() => void>();
const osDark = window.matchMedia('(prefers-color-scheme: dark)');

/** The user's explicit choice, or null if they've never toggled (or storage is unavailable). */
export function getStoredTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

function osTheme(): Theme {
  return osDark.matches ? 'dark' : 'light';
}

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

/** Sets the attribute and the mobile browser-chrome colour, then notifies subscribers. */
function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  const canvas = getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim();
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta && canvas) meta.setAttribute('content', `rgb(${canvas})`);
  listeners.forEach((listener) => listener());
}

/** An explicit choice: it's stored, and from then on beats the OS preference. */
export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage blocked (private mode): the choice still applies for this page.
  }
  applyTheme(theme);
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Installed once, when the module is first imported.
// Follow the OS live, but only while the user hasn't made a choice.
osDark.addEventListener('change', () => {
  if (getStoredTheme() === null) applyTheme(osTheme());
});
// Another tab or app on the same origin toggled (all three apps share the key under nginx).
window.addEventListener('storage', (event) => {
  if (event.key === STORAGE_KEY) applyTheme(getStoredTheme() ?? osTheme());
});
