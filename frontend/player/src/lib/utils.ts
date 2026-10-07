import { type ClassValue, clsx } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

// tailwind-merge only knows Tailwind's built-in shadow sizes; without this it treats shadow-brutal*
// as a shadow *colour*, so cn('shadow-brutal', 'shadow-none') would keep both (docs/design-better-ui.md §4.3.2).
const twMerge = extendTailwindMerge({
  extend: { classGroups: { shadow: [{ shadow: ['brutal-sm', 'brutal', 'brutal-lg'] }] } },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Returns true if the token is missing, malformed, or past its exp claim. */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return Date.now() / 1000 >= (payload.exp ?? 0);
  } catch {
    return true;
  }
}
