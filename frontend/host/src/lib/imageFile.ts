/**
 * Browser-side image preparation (docs/design-image-support.md §5.1), shared by the
 * library page, the ImagePicker and the question editor. The server re-checks
 * everything; this keeps uploads small.
 */

export const MAX_SIDE = 1280;
export const MAX_UPLOAD_BYTES = 5_000_000;

/** Loads an image; one that loads as 0 × 0 (e.g. an SVG without dimensions) is refused. */
export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    // An SVG without dimensions loads as 0 × 0: no aspect, so no target or radii to set.
    img.onload = () =>
      img.naturalWidth > 0 && img.naturalHeight > 0
        ? resolve(img)
        : reject(new Error('Image has no size; use a PNG, JPEG, GIF or WebP'));
    img.onerror = () => reject(new Error('Image failed to load'));
    img.src = src;
  });
}

/** Draw `img` with its longest side at most `maxSide` (never upscaled); `background` fills transparency. */
function drawScaled(img: HTMLImageElement, maxSide: number, background: string | null): HTMLCanvasElement {
  const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Image failed to load');
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Could not encode the image'))), type, quality);
  });
}

/**
 * Prepare a file for the course library:
 *   - JPEG → downscaled to ≤ 1280 px when larger, and re-encoded as JPEG (quality 0.9) either way;
 *   - PNG → as-is when ≤ 1280 px, otherwise downscaled and re-encoded as PNG (keeps transparency);
 *   - GIF and WebP → as-is at any size (the browser can't cheaply tell whether they're
 *     animated, and a canvas would keep only the first frame);
 *   - anything else (HEIC, SVG, …) → as-is; the server answers 422.
 * A result over the server's 5 MB limit is refused here, with the server's wording.
 */
export async function prepareUpload(file: File): Promise<File> {
  let out: Blob = file;
  if (file.type === 'image/jpeg' || file.type === 'image/png') {
    const objectUrl = URL.createObjectURL(file);
    try {
      const img = await loadImage(objectUrl);
      const longest = Math.max(img.naturalWidth, img.naturalHeight);
      if (file.type === 'image/jpeg') {
        out = await canvasToBlob(drawScaled(img, MAX_SIDE, '#ffffff'), 'image/jpeg', 0.9);
      } else if (longest > MAX_SIDE) {
        out = await canvasToBlob(drawScaled(img, MAX_SIDE, null), 'image/png');
      }
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  }
  if (out.size > MAX_UPLOAD_BYTES) throw new Error('Image is too large; the limit is 5 MB');
  return out === file ? file : new File([out], file.name, { type: out.type });
}

/** A Pin the Spot canvas kept in config.image_url (unattached games, pasted URLs). */
export interface PinUrlImage { image_url: string; image_width: number; image_height: number }

const PIN_MAX_URL_CHARS = 1_500_000;
const PIN_QUALITIES = [0.85, 0.7, 0.5];

/**
 * Pin the Spot in an unattached game (no course library), unchanged from T7: a local file
 * → JPEG data: URL, longest side ≤ 1280 px (never upscaled), drawn on white so PNG
 * transparency doesn't turn black (an animated GIF keeps its first frame). Retries at
 * lower quality while over the server's 1,500,000-character limit.
 */
export async function toPinDataUrl(file: File): Promise<PinUrlImage> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const canvas = drawScaled(await loadImage(objectUrl), MAX_SIDE, '#ffffff');
    for (const q of PIN_QUALITIES) {
      const url = canvas.toDataURL('image/jpeg', q);
      if (url.length <= PIN_MAX_URL_CHARS) {
        return { image_url: url, image_width: canvas.width, image_height: canvas.height };
      }
    }
    throw new Error('Image too large');
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
