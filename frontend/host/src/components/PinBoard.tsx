import { useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import {
  clampUnit,
  drawImage,
  drawTaps,
  drawTarget,
  fitRect,
  loadImage,
  pinAspect,
  prepareCanvas,
  readPinColors,
  toImagePoint,
} from '../lib/pinTheSpot';
import type { PinConfig, PinTarget, Point, Tap } from '../lib/pinTheSpot';

interface PinBoardProps {
  config: PinConfig;
  /** Player taps (results / game over). Never passed while a question is open (§2, A4). */
  taps?: Tap[];
  /** Target and circles. */
  reveal?: PinTarget | null;
  /** Cap on the canvas height in CSS px; defaults to 60% of the viewport. */
  maxHeight?: number;
  /** Editor only: click or drag on the image to place the target. */
  onPick?: (p: Point) => void;
  ariaLabel: string;
  testId?: string;
}

/**
 * The host's pin_the_spot canvas (docs/design-pin-the-spot.md §7): the image sized to its
 * aspect ratio, plus, when given, every tap and the target's full-credit (filled) and
 * zero-credit (dashed) circles. With `onPick` it is the editor's target picker.
 */
export function PinBoard({ config, taps = [], reveal = null, maxHeight, onPick, ariaLabel, testId }: PinBoardProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragging = useRef(false);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [failed, setFailed] = useState(false);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [themeTick, setThemeTick] = useState(0);
  const aspect = pinAspect(config);

  useEffect(() => {
    setImg(null);
    setFailed(false);
    return loadImage(config.image_url, (loaded) => {
      setImg(loaded);
      setFailed(!loaded);
    });
  }, [config.image_url]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => {
      const cap = maxHeight ?? window.innerHeight * 0.6;
      let w = el.clientWidth;
      let h = w * aspect;
      if (h > cap) { h = cap; w = h / aspect; }
      setSize({ w, h });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener('resize', measure);
    return () => { ro.disconnect(); window.removeEventListener('resize', measure); };
  }, [aspect, maxHeight]);

  // Theme changes (OS setting or a data-theme/class switch on <html>) → redraw.
  useEffect(() => {
    const bump = () => setThemeTick((t) => t + 1);
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', bump);
    const mo = new MutationObserver(bump);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme', 'style'] });
    return () => { mq.removeEventListener('change', bump); mo.disconnect(); };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.w === 0) return;
    const ctx = prepareCanvas(canvas, size.w, size.h);
    if (!ctx) return;
    const rect = fitRect(size.w, size.h, aspect);
    const colors = readPinColors(canvas);
    ctx.clearRect(0, 0, size.w, size.h);
    drawImage(ctx, img, rect, colors);
    // Dots scale gently with the board so a game-over thumbnail isn't all dots.
    drawTaps(ctx, taps, rect, colors, Math.min(1.4, Math.max(0.6, rect.width / 700)));
    if (reveal) drawTarget(ctx, reveal, rect, colors);
  }, [img, size, aspect, taps, reveal, themeTick]);

  function pick(e: PointerEvent<HTMLCanvasElement>, clamp: boolean) {
    const box = e.currentTarget.getBoundingClientRect();
    const rect = fitRect(size.w, size.h, aspect);
    const px = e.clientX - box.left;
    const py = e.clientY - box.top;
    const p = clamp
      ? { x: clampUnit((px - rect.left) / rect.width), y: clampUnit((py - rect.top) / rect.height) }
      : toImagePoint(px, py, rect);
    if (p) onPick!(p);
    return p;
  }

  return (
    <div ref={wrapRef} className="relative w-full flex justify-center">
      <canvas
        ref={canvasRef}
        data-testid={testId}
        role="img"
        aria-label={ariaLabel}
        onPointerDown={onPick ? (e) => {
          if (pick(e, false)) {
            e.currentTarget.setPointerCapture(e.pointerId);
            dragging.current = true;
          }
        } : undefined}
        onPointerMove={onPick ? (e) => { if (dragging.current) pick(e, true); } : undefined}
        onPointerUp={() => { dragging.current = false; }}
        onPointerCancel={() => { dragging.current = false; }}
        style={{ width: size.w, height: size.h, touchAction: onPick ? 'none' : 'auto' }}
        className={`rounded-xl ${onPick ? 'cursor-crosshair' : ''}`}
      />
      {!img && (
        <p className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
          {failed ? 'Image failed to load' : 'Loading image…'}
        </p>
      )}
    </div>
  );
}
