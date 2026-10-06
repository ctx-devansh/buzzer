/**
 * Course image library (T8, docs/design-image-support.md). Images are public by
 * unguessable id, so an <img> needs no token: `/api/images/{id}` works under nginx and
 * under `npm run dev` (Vite proxies /api). The player app has its own copy of imageUrl.
 */

/**
 * `bust` is only for the library page after a replace: within one document the
 * browser may reuse an image it already loaded from the same URL without revalidating
 * it, so that page appends a local counter (design §5.1).
 */
export function imageUrl(id: string, bust?: number): string {
  return `/api/images/${id}${bust ? `?v=${bust}` : ''}`;
}

/** One question using a library image (ImageUse in backend/app/schemas/image.py). */
export interface ImageUse {
  game_id: number;
  game_title: string;
  question_id: number;
  order_index: number;
  roles: ('prompt' | 'option' | 'canvas')[];
  played: boolean;
}

export interface LibraryImage {
  id: string;
  course_id: number;
  filename: string;
  content_type: string;
  width: number;
  height: number;
  byte_size: number;
  uploaded_by_name: string | null;
  created_at: string;
  updated_at: string;
  url: string;
  used_by: ImageUse[];
}

export interface ImageReplaceResult extends LibraryImage {
  size_changed: boolean;
  resized_question_ids: number[];
  clamped_question_ids: number[];
}

/** "Party Night, question 3": how the library names a question (numbered from 1). */
export function questionLabel(use: ImageUse): string {
  return `${use.game_title}, question ${use.order_index + 1}`;
}

export function formatBytes(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1000))} KB`;
}
