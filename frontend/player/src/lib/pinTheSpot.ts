/**
 * Canvas helpers for the pin_the_spot question type (docs/design-pin-the-spot.md §6).
 *
 * Points are fractions of the image (0..1, origin top-left); radii are fractions of the
 * image width. The host app keeps its own copy of the drawing half of this file
 * (frontend/host/src/lib/pinTheSpot.ts) — nothing is shared between apps.
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

const PIN_HEAD_RADIUS = 11;
const PIN_HEIGHT = 30;

/**
 * A map pin whose tip is the chosen point and whose head sits above it, so a thumb doesn't
 * hide it. Near the top edge the pin flips to hang below the point.
 */
export function drawPin(ctx: CanvasRenderingContext2D, p: Point, rect: ImageRect, colors: PinColors) {
  const tx = rect.left + p.x * rect.width;
  const ty = rect.top + p.y * rect.height;
  const dir = ty - PIN_HEIGHT - PIN_HEAD_RADIUS < 0 ? 1 : -1;
  const hy = ty + dir * PIN_HEIGHT;
  ctx.save();
  ctx.fillStyle = colors.marker;
  ctx.strokeStyle = colors.outline;
  ctx.lineWidth = 2;
  // Stem first, then the head drawn over its wide end.
  ctx.beginPath();
  ctx.moveTo(tx, ty);
  ctx.lineTo(tx - PIN_HEAD_RADIUS * 0.75, hy);
  ctx.lineTo(tx + PIN_HEAD_RADIUS * 0.75, hy);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(tx, hy, PIN_HEAD_RADIUS, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(tx, hy, PIN_HEAD_RADIUS * 0.4, 0, Math.PI * 2);
  ctx.fillStyle = colors.outline;
  ctx.fill();
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
