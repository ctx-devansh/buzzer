// Cross-app URLs. Under nginx/Docker all apps share one origin (and the token), so the
// paths work. In Vite dev each app has its own port and a bare '/host' would hit this
// app's own dev server and fall through to /users — so dev defaults to the app ports.
// Override with VITE_HOST_APP_URL / VITE_PLAYER_APP_URL. The token is per-origin, so in
// dev the link lands on the other app's login page.
export const HOST_APP_URL: string =
  import.meta.env.VITE_HOST_APP_URL ?? (import.meta.env.DEV ? 'http://localhost:5173' : '/host');
export const PLAYER_APP_URL: string =
  import.meta.env.VITE_PLAYER_APP_URL ?? (import.meta.env.DEV ? 'http://localhost:5174' : '/player');
