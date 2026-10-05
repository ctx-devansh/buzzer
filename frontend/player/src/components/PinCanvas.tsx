import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import {
  clampUnit,
  drawImage,
  drawPin,
  drawTarget,
  fitRect,
  loadImage,
  pinAspect,
  prepareCanvas,
  readPinColors,
  toImagePoint,
} from '../lib/pinTheSpot';
import type { PinConfig, PinTarget, Point } from '../lib/pinTheSpot';

interface PinCanvasProps {
  config: PinConfig;
  /** The player's pin, or null before the first tap. */
  value: Point | null;
  /** Omit for a read-only canvas (results screens). */
  onChange?: (p: Point) => void;
  /** Enter key, when a pin is placed. */
  onSubmit?: () => void;
  disabled?: boolean;
  /** Target and circles to draw (revealed after the question). */
  reveal?: PinTarget | null;
  /** Cap on the canvas height in CSS px; defaults to 60% of the viewport. */
  maxHeight?: number;
  ariaLabel: string;
}

/**
 * The pin_the_spot canvas (docs/design-pin-the-spot.md §6). The canvas is sized to the
 * image's aspect ratio, so the whole image is visible without cropping; tap or drag to
 * place the pin, arrow keys nudge it (Shift for bigger steps), Enter locks in.
 */
export function PinCanvas({
  config, value, onChange, onSubmit, disabled = false, reveal = null, maxHeight, ariaLabel,
}: PinCanvasProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragging = useRef(false);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [failed, setFailed] = useState(false);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [themeTick, setThemeTick] = useState(0);
  const aspect = pinAspect(config);
  const interactive = !!onChange && !disabled;

  useEffect(() => {
    setImg(null);
    setFailed(false);
    return loadImage(config.image_url, (loaded) => {
      setImg(loaded);
      setFailed(!loaded);
    });
  }, [config.image_url]);

  // Resize (including orientation changes) → recompute the CSS size and redraw.
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
    if (reveal) drawTarget(ctx, reveal, rect, colors);
    if (value) drawPin(ctx, value, rect, colors);
  }, [img, size, aspect, value, reveal, themeTick]);

  function pointFromEvent(e: PointerEvent<HTMLCanvasElement>, clamp: boolean): Point | null {
    const box = e.currentTarget.getBoundingClientRect();
    const rect = fitRect(size.w, size.h, aspect);
    const px = e.clientX - box.left;
    const py = e.clientY - box.top;
    if (clamp) {
      return {
        x: clampUnit((px - rect.left) / rect.width),
        y: clampUnit((py - rect.top) / rect.height),
      };
    }
    return toImagePoint(px, py, rect);
  }

  function onPointerDown(e: PointerEvent<HTMLCanvasElement>) {
    if (!interactive) return;
    const p = pointFromEvent(e, false); // a tap in the letterbox bars is ignored
    if (!p) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragging.current = true;
    onChange!(p);
  }

  function onPointerMove(e: PointerEvent<HTMLCanvasElement>) {
    if (!interactive || !dragging.current) return;
    onChange!(pointFromEvent(e, true)!); // a drag that slips off the edge stays on it
  }

  function endDrag() {
    dragging.current = false;
  }

  function onKeyDown(e: KeyboardEvent<HTMLCanvasElement>) {
    if (!interactive) return;
    if (e.key === 'Enter' && value && onSubmit) {
      e.preventDefault();
      onSubmit();
      return;
    }
    const step = e.shiftKey ? 0.05 : 0.01;
    const delta: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step],
    };
    const d = delta[e.key];
    if (!d) return;
    e.preventDefault();
    const base = value ?? { x: 0.5, y: 0.5 };
    onChange!({ x: clampUnit(base.x + d[0]), y: clampUnit(base.y + d[1]) });
  }

  return (
    <div ref={wrapRef} className="relative w-full flex justify-center">
      <canvas
        ref={canvasRef}
        data-testid="pin-canvas"
        role="img"
        aria-label={ariaLabel}
        tabIndex={interactive ? 0 : -1}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        style={{ width: size.w, height: size.h, touchAction: interactive ? 'none' : 'auto' }}
        className={`rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
          interactive ? 'cursor-crosshair' : ''
        } ${disabled ? 'opacity-60' : ''}`}
      />
      {!img && (
        <p className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
          {failed ? 'Image failed to load' : 'Loading image…'}
        </p>
      )}
    </div>
  );
}
