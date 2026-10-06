/**
 * Helpers for the pin_the_spot question type (docs/design-pin-the-spot.md). The player app
 * has its own copy (apps share nothing); keep the geometry identical.
 *
 * Coordinates are fractions of the image ([0, 1], origin top-left); radii are fractions of
 * the image width. Every board draws the image stretched into a rectangle of the *stored*
 * aspect (height / width, D6).
 */

import { imageUrl } from './images';

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

/**
 * The canvas image's source: the course library's public URL for image_id (T8),
 * otherwise the stored image_url (https:// or data:).
 */
export function pinImageSrc(config: { image_id?: string; image_url?: string } | undefined): string | undefined {
  return config?.image_id ? imageUrl(config.image_id) : config?.image_url;
}

/** Editor slider limits and defaults (§3 author 3). */
export const R_FULL_MIN = 0.005;
export const R_FULL_MAX = 0.5;
export const R_ZERO_MIN = 0.02;
export const R_STEP = 0.005;
export const R_GAP = 0.01;
export const DEFAULT_R_FULL = 0.05;
export const DEFAULT_R_ZERO = 0.2;

/** height / width from config, or null if the stored size is unusable. */
export function aspectOf(config: { image_width?: number; image_height?: number } | undefined): number | null {
  const w = config?.image_width;
  const h = config?.image_height;
  if (typeof w !== 'number' || typeof h !== 'number' || w <= 0 || h <= 0) return null;
  return h / w;
}

/** The image diagonal in width units: the largest useful zero-credit radius. */
export function diagonal(aspect: number): number {
  return Math.sqrt(1 + aspect * aspect);
}

/** floor to 2 dp (the r_zero slider's maximum). */
export function floor2(v: number): number {
  return Math.floor(v * 100 + 1e-9) / 100;
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

/** CSS px → image fraction; outside the drawn rect → null unless `clamp`. */
export function toFraction(px: number, py: number, rect: PinRect, clamp: boolean): PinPoint | null {
  const fx = (px - rect.x) / rect.w;
  const fy = (py - rect.y) / rect.h;
  const inside = fx >= 0 && fx <= 1 && fy >= 0 && fy <= 1;
  if (!inside && !clamp) return null;
  return { x: round4(clamp01(fx)), y: round4(clamp01(fy)) };
}

/** "0.4000,0.6300" (the server's tap_key) → point, or null if malformed. */
export function parseTapKey(key: string): PinPoint | null {
  const parts = key.split(',');
  if (parts.length !== 2) return null;
  const x = parseFloat(parts[0]);
  const y = parseFloat(parts[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

/** Dot radius: base · √count, capped at 3 · base; base = 1% of the drawn width, min 4 px. */
export function dotRadius(count: number, drawnWidth: number): number {
  const base = Math.max(drawnWidth * 0.01, 4);
  return Math.min(base * Math.sqrt(count), 3 * base);
}

/** Target and radii from a reveal, if it has them. */
export function revealKey(reveal: unknown): PinKey {
  if (!reveal || typeof reveal !== 'object') return {};
  const r = reveal as Record<string, unknown>;
  const t = r.target as PinPoint | undefined;
  if (!t || typeof t.x !== 'number' || typeof t.y !== 'number') return {};
  if (typeof r.rFull !== 'number' || typeof r.rZero !== 'number') return {};
  return { target: { x: t.x, y: t.y }, rFull: r.rFull, rZero: r.rZero };
}
