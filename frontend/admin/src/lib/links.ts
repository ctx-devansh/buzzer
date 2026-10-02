// Cross-app URLs. Under nginx/Docker all apps share one origin (and the token), so
// the defaults just work. In Vite dev each app has its own port: set
// VITE_HOST_APP_URL=http://localhost:5173 and VITE_PLAYER_APP_URL=http://localhost:5174,
// otherwise these links hit the admin dev server and silently land back on /users.
export const HOST_APP_URL: string = import.meta.env.VITE_HOST_APP_URL ?? '/host';
export const PLAYER_APP_URL: string = import.meta.env.VITE_PLAYER_APP_URL ?? '/player';
