/**
 * Canvas helpers for the pin_the_spot question type (docs/design-pin-the-spot.md §6–7):
 * the live question image, the reveal board (every tap plus the two circles) and the
 * editor's target preview.
 *
 * Points are fractions of the image (0..1, origin top-left); radii are fractions of the
 * image width. The drawing half is a copy of frontend/player/src/lib/pinTheSpot.ts —
 * nothing is shared between apps, so fix both.
 */

export interface Point { x: number; y: number }

export interface PinConfig { image_url: string; image_width: number; image_height: number }

/** Target and radii as revealed by the server (camelCase, see gateway._answer_reveal). */
export interface PinTarget { target: Point; rFull: number; rZero: number }

/** Where the image sits inside the canvas, in CSS pixels. */
export interface ImageRect { left: number; top: number; width: number; height: number }

export function pinAspect(config: Partial<PinConfig> | undefined): number {
  const w = config?.image_width ?? 0;
  const h = config?.image_height ?? 0;
  return w > 0 && h > 0 ? h / w : 1;
}

/** Fit an image of `aspect` (height / width) inside a box without cropping, centred. */
export function fitRect(boxWidth: number, boxHeight: number, aspect: number): ImageRect {
  let width = boxWidth;
  let height = width * aspect;
  if (height > boxHeight) {
    height = boxHeight;
    width = height / aspect;
  }
  return { left: (boxWidth - width) / 2, top: (boxHeight - height) / 2, width, height };
}

/** CSS-pixel position inside the canvas → image fraction, or null in the letterbox bars. */
export function toImagePoint(px: number, py: number, rect: ImageRect): Point | null {
  const x = (px - rect.left) / rect.width;
  const y = (py - rect.top) / rect.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

export function clampUnit(v: number): number {
  return Math.min(1, Math.max(0, v));
}

/** Canvas can't use CSS classes: read colours from custom properties (T9), with fallbacks. */
export interface PinColors { marker: string; outline: string; target: string; full: string; zero: string; tap: string; backdrop: string }

export function readPinColors(el: Element): PinColors {
  const css = getComputedStyle(el);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    marker: v('--pin-marker', '#ec4899'),
    outline: v('--pin-outline', '#ffffff'),
    target: v('--pin-target', '#22c55e'),
    full: v('--pin-full', '#22c55e'),
    zero: v('--pin-zero', '#f59e0b'),
    tap: v('--pin-tap', '#f472b6'),
    backdrop: v('--pin-backdrop', '#1e293b'),
  };
}

/**
 * Size the canvas backing store for devicePixelRatio and return a context scaled so that
 * drawing uses CSS pixels.
 */
export function prepareCanvas(canvas: HTMLCanvasElement, cssWidth: number, cssHeight: number) {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

export function drawImage(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement | null,
  rect: ImageRect,
  colors: PinColors,
) {
  ctx.fillStyle = colors.backdrop;
  ctx.fillRect(rect.left, rect.top, rect.width, rect.height);
  if (img) ctx.drawImage(img, rect.left, rect.top, rect.width, rect.height);
}

/** Full-credit (filled) and zero-credit (dashed) circles plus a dot on the target. */
export function drawTarget(ctx: CanvasRenderingContext2D, t: PinTarget, rect: ImageRect, colors: PinColors) {
  const cx = rect.left + t.target.x * rect.width;
  const cy = rect.top + t.target.y * rect.height;
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, t.rZero * rect.width, 0, Math.PI * 2);
  ctx.setLineDash([8, 6]);
  ctx.lineWidth = 2;
  ctx.strokeStyle = colors.zero;
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.arc(cx, cy, t.rFull * rect.width, 0, Math.PI * 2);
  ctx.globalAlpha = 0.2;
  ctx.fillStyle = colors.full;
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = colors.full;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, 5, 0, Math.PI * 2);
  ctx.fillStyle = colors.target;
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = colors.outline;
  ctx.stroke();
  ctx.restore();
}

/** The target and radii from a pin_the_spot reveal (either grading type), or null. */
export function revealTarget(reveal: { target?: Point; rFull?: number; rZero?: number } | null | undefined): PinTarget | null {
  if (!reveal?.target || typeof reveal.rFull !== 'number' || typeof reveal.rZero !== 'number') return null;
  return { target: reveal.target, rFull: reveal.rFull, rZero: reveal.rZero };
}

export interface Tap extends Point { count: number }

/**
 * The host's answerDistribution for pin_the_spot: "x,y" keys (4 dp) → count. Keys that
 * don't parse to two numbers in 0..1 are skipped.
 */
export function parseTaps(distribution: Record<string, number>): Tap[] {
  const taps: Tap[] = [];
  for (const [key, count] of Object.entries(distribution)) {
    const parts = key.split(',');
    if (parts.length !== 2) continue;
    const [x, y] = parts.map(Number);
    if ([x, y].every((v) => Number.isFinite(v) && v >= 0 && v <= 1)) taps.push({ x, y, count });
  }
  return taps;
}

export function tapTotal(taps: Tap[]): number {
  return taps.reduce((sum, t) => sum + t.count, 0);
}

/** One dot per distinct tap; repeated taps at the same spot draw a bigger dot. */
export function drawTaps(ctx: CanvasRenderingContext2D, taps: Tap[], rect: ImageRect, colors: PinColors, scale = 1) {
  ctx.save();
  ctx.lineWidth = 1.5 * scale;
  ctx.strokeStyle = colors.outline;
  ctx.fillStyle = colors.tap;
  for (const t of taps) {
    const r = (5 + 2 * Math.min(t.count - 1, 4)) * scale;
    ctx.beginPath();
    ctx.arc(rect.left + t.x * rect.width, rect.top + t.y * rect.height, r, 0, Math.PI * 2);
    ctx.globalAlpha = 0.8;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.stroke();
  }
  ctx.restore();
}

/** Load an image element; null until it has loaded (or if it fails). */
export function loadImage(url: string, onDone: (img: HTMLImageElement | null) => void): () => void {
  let cancelled = false;
  const img = new Image();
  img.decoding = 'async';
  img.onload = () => { if (!cancelled) onDone(img); };
  img.onerror = () => { if (!cancelled) onDone(null); };
  img.src = url;
  return () => { cancelled = true; };
}
