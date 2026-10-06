/**
 * Helpers for the pin_the_spot question type (docs/design-pin-the-spot.md).
 *
 * Coordinates are fractions of the image ([0, 1], origin top-left); radii are fractions of
 * the image width; vertical differences are scaled by aspect (height / width). Every canvas
 * draws the image stretched into a rectangle of the *stored* aspect (D6), so a tap's
 * fraction means the same thing here and on the server.
 */

export interface PinPoint {
  x: number;
  y: number;
}

export interface PinRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PinKey {
  target?: PinPoint;
  rFull?: number;
  rZero?: number;
}

/** Same ε as the server: a tap drawn exactly on a circle counts as on it. */
export const EDGE_EPSILON = 1e-9;

/** height / width from config, or null if the stored size is unusable. */
export function aspectOf(config: { image_width?: number; image_height?: number } | undefined): number | null {
  const w = config?.image_width;
  const h = config?.image_height;
  if (typeof w !== 'number' || typeof h !== 'number' || w <= 0 || h <= 0) return null;
  return h / w;
}

/** A real {x, y} tap in [0, 1]. */
export function isTap(value: unknown): value is PinPoint {
  if (!value || typeof value !== 'object') return false;
  const { x, y } = value as Record<string, unknown>;
  return (
    typeof x === 'number' && typeof y === 'number' &&
    Number.isFinite(x) && Number.isFinite(y) &&
    x >= 0 && x <= 1 && y >= 0 && y <= 1
  );
}

/** The largest rectangle of the given aspect that fits in the box, centred (letterboxed). */
export function fitRect(boxW: number, boxH: number, aspect: number): PinRect {
  let w = boxW;
  let h = w * aspect;
  if (h > boxH) {
    h = boxH;
    w = h / aspect;
  }
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h };
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const round4 = (v: number) => Math.round(v * 10000) / 10000;

/**
 * CSS px (relative to the canvas) → image fraction. Outside the drawn rect: null, unless
 * `clamp` (a drag that leaves the image sticks to the nearest edge).
 */
export function toFraction(px: number, py: number, rect: PinRect, clamp: boolean): PinPoint | null {
  const fx = (px - rect.x) / rect.w;
  const fy = (py - rect.y) / rect.h;
  const inside = fx >= 0 && fx <= 1 && fy >= 0 && fy <= 1;
  if (!inside && !clamp) return null;
  return { x: round4(clamp01(fx)), y: round4(clamp01(fy)) };
}

/** Arrow-key nudge, clamped to the image. */
export function nudge(p: PinPoint, dx: number, dy: number): PinPoint {
  return { x: round4(clamp01(p.x + dx)), y: round4(clamp01(p.y + dy)) };
}

/** Distance in image-width units, as the server computes it. */
export function tapDistance(tap: PinPoint, target: PinPoint, aspect: number): number {
  return Math.hypot(tap.x - target.x, (tap.y - target.y) * aspect);
}

export type PinVerdict = 'correct' | 'partial' | 'incorrect';

/**
 * D9: ✓ from the server's isCorrect; otherwise ◐ when the tap is strictly inside the
 * zero-credit circle (same ε as the server); no target revealed → incorrect. Never from points.
 */
export function pinVerdict(
  isCorrect: boolean,
  tap: unknown,
  key: PinKey,
  aspect: number | null,
): PinVerdict {
  if (isCorrect) return 'correct';
  if (!isTap(tap) || !key.target || typeof key.rZero !== 'number' || aspect === null) return 'incorrect';
  return tapDistance(tap, key.target, aspect) < key.rZero - EDGE_EPSILON ? 'partial' : 'incorrect';
}
