import { useSyncExternalStore } from 'react';
import { getTheme, setTheme, subscribe, type Theme } from '../../../theme/theme';

// The shared runtime (frontend/theme/theme.ts) owns the data-theme attribute and its listeners;
// this file only adds the React hook. Components import theme helpers from here.
export { getTheme, setTheme };
export type { Theme };

export function useTheme(): [Theme, (theme: Theme) => void] {
  const theme = useSyncExternalStore(subscribe, getTheme);
  return [theme, setTheme];
}
