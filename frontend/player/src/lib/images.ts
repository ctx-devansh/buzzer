/**
 * Course-library images (T8, docs/design-image-support.md). Public by unguessable id, so
 * an <img> needs no token; /api is proxied by Vite in dev and by nginx in Docker. The host
 * app has its own copy (apps share nothing).
 */
export function imageUrl(id: string): string {
  return `/api/images/${id}`;
}
