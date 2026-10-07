import { Moon, Sun } from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../lib/theme';

/**
 * Light/dark switch. A toggle button with a fixed accessible name and aria-pressed carrying the
 * state (docs/design-better-ui.md §4.4). `showLabel={false}` hides the visible text where space is tight.
 */
export function ThemeToggle({ className, showLabel = true }: { className?: string; showLabel?: boolean }) {
  const [theme, setTheme] = useTheme();
  const dark = theme === 'dark';
  return (
    <button
      type="button"
      aria-label="Dark theme"
      aria-pressed={dark}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      className={cn(
        'nb-box nb-press inline-flex h-11 min-w-11 items-center justify-center gap-2 px-3 text-sm font-semibold text-ink',
        className
      )}
    >
      {dark ? <Moon aria-hidden="true" size={18} /> : <Sun aria-hidden="true" size={18} />}
      {showLabel && <span aria-hidden="true">Dark theme</span>}
    </button>
  );
}
