// The single accessor for the auth token. All three apps share one origin in
// production, so `localStorage.token` is shared with the admin and player apps.
const TOKEN_KEY = 'token';

export type Role = 'ADMIN' | 'USER' | 'GUEST';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * The `role` claim from the JWT payload, decoded WITHOUT verifying the signature.
 *
 * DISPLAY ONLY — use it to show or hide UI (the Admin console link, the Delete-game
 * button), never to decide whether an action is allowed. Every action is authorised
 * by the server; a forged claim only reveals a button that returns 403. Using this
 * for a real access decision would be a security bug.
 */
export function getRole(): Role | null {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = token.split('.')[1];
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    const role = (JSON.parse(json) as { role?: unknown }).role;
    return role === 'ADMIN' || role === 'USER' || role === 'GUEST' ? role : null;
  } catch {
    return null;
  }
}
