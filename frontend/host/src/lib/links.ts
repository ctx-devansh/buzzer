// Cross-app URL. Same origin under nginx/Docker (token is shared); in Vite dev set
// VITE_ADMIN_APP_URL=http://localhost:5175 or the link hits this app's own dev server.
export const ADMIN_APP_URL: string = import.meta.env.VITE_ADMIN_APP_URL ?? '/admin';
