// Cross-app URL. Under nginx/Docker all apps share one origin (and the token), so the
// path works. In Vite dev each app has its own port and a bare '/admin' would hit this
// app's own dev server and fall through to /login — so dev defaults to the admin port.
// Override with VITE_ADMIN_APP_URL. The token is per-origin, so in dev you sign in again.
export const ADMIN_APP_URL: string =
  import.meta.env.VITE_ADMIN_APP_URL ?? (import.meta.env.DEV ? 'http://localhost:5175' : '/admin');
