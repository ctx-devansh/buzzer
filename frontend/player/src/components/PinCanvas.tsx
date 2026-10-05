import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { fitRect, nudge, toFraction } from '../lib/pinTheSpot';
import type { PinKey, PinPoint, PinRect } from '../lib/pinTheSpot';

/** Pin height in CSS px: tip at the point, head above it (below near the top edge). */
const PIN_HEIGHT = 40;
const PIN_HEAD_RADIUS = 10;

interface PinCanvasProps {
  imageUrl: string | undefined;
  aspect: number;
  pin: PinPoint | null;
  /** Interactive when given and not `disabled`. */
  onChange?: (p: PinPoint) => void;
  /** Enter, only when a pin exists. */
  onSubmit?: () => void;
  disabled?: boolean;
  /** Target and circles, drawn on the results screen. */
  reveal?: PinKey;
  ariaLabel: string;
  /** Tallest the board may be, in CSS px (it is never taller than width × aspect). */
  maxHeight?: number;
  onImageError?: () => void;
}

function cssVar(el: Element, name: string, fallback: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || fallback;
}

/**
 * The player's Pin the Spot board: the image fitted (letterboxed) into the stored aspect,
 * one map pin, and optionally the revealed target and circles. Colours come from
 * `--pin-*` custom properties with fallbacks.
 */
export function PinCanvas({
  imageUrl, aspect, pin, onChange, onSubmit, disabled, reveal, ariaLabel, maxHeight, onImageError,
}: PinCanvasProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rectRef = useRef<PinRect | null>(null);
  const draggingRef = useRef(false);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [failed, setFailed] = useState(false);
  // No pin until the image is there: a pin on a placeholder means nothing.
  const interactive = !!onChange && !disabled && !!image;

  // Load the image (no crossOrigin: pixels are never read back).
  useEffect(() => {
    setImage(null);
    setFailed(false);
    if (!imageUrl) return;
    const img = new Image();
    img.onload = () => setImage(img);
    img.onerror = () => {
      setFailed(true);
      onImageError?.();
    };
    img.src = imageUrl;
    return () => {
      img.onload = null;
      img.onerror = null;
    };
    // onImageError is a notification only; reloading on its identity would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUrl]);

  // Size the board: full width, height from the aspect, capped by maxHeight.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      const cap = maxHeight ?? window.innerHeight * 0.6;
      setBox({ w, h: Math.min(w * aspect, cap) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener('resize', measure);
    window.addEventListener('orientationchange', measure);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('orientationchange', measure);
    };
  }, [aspect, maxHeight]);

  // Draw.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || box.w <= 0 || box.h <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(box.w * dpr);
    canvas.height = Math.round(box.h * dpr);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, box.w, box.h);

    const rect = fitRect(box.w, box.h, aspect);
    rectRef.current = rect;
    ctx.fillStyle = cssVar(canvas, '--pin-letterbox', '#020617');
    ctx.fillRect(0, 0, box.w, box.h);
    if (image) {
      // Stretched into the stored aspect on purpose (D6).
      ctx.drawImage(image, rect.x, rect.y, rect.w, rect.h);
    } else {
      ctx.fillStyle = cssVar(canvas, '--pin-placeholder', '#1e293b');
      ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    }

    const px = (p: PinPoint) => ({ x: rect.x + p.x * rect.w, y: rect.y + p.y * rect.h });

    if (reveal?.target && typeof reveal.rFull === 'number' && typeof reveal.rZero === 'number') {
      const c = px(reveal.target);
      ctx.save();
      ctx.beginPath();
      ctx.arc(c.x, c.y, reveal.rZero * rect.w, 0, Math.PI * 2);
      ctx.setLineDash([8, 6]);
      ctx.lineWidth = 2;
      ctx.strokeStyle = cssVar(canvas, '--pin-zero', '#fbbf24');
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(c.x, c.y, reveal.rFull * rect.w, 0, Math.PI * 2);
      ctx.fillStyle = cssVar(canvas, '--pin-full-fill', 'rgba(74, 222, 128, 0.3)');
      ctx.fill();
      ctx.strokeStyle = cssVar(canvas, '--pin-full', '#4ade80');
      ctx.stroke();
      ctx.restore();
    }

    if (pin) {
      const tip = px(pin);
      // Head above the tip, flipped below when the point is near the top of the image.
      const dir = tip.y - rect.y < PIN_HEIGHT ? 1 : -1;
      const head = { x: tip.x, y: tip.y + dir * (PIN_HEIGHT - PIN_HEAD_RADIUS) };
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(tip.x, tip.y);
      ctx.lineTo(head.x, head.y);
      ctx.lineWidth = 3;
      ctx.strokeStyle = cssVar(canvas, '--pin-stem', '#f8fafc');
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(head.x, head.y, PIN_HEAD_RADIUS, 0, Math.PI * 2);
      ctx.fillStyle = cssVar(canvas, '--pin-head', '#6366f1');
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = cssVar(canvas, '--pin-stem', '#f8fafc');
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(tip.x, tip.y, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = cssVar(canvas, '--pin-stem', '#f8fafc');
      ctx.fill();
      ctx.restore();
    }

    if (reveal?.target) {
      const c = px(reveal.target);
      ctx.save();
      ctx.beginPath();
      ctx.arc(c.x, c.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = cssVar(canvas, '--pin-target', '#ef4444');
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
      ctx.restore();
    }
  }, [box, aspect, image, pin, reveal]);

  function localPoint(e: PointerEvent<HTMLCanvasElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function handlePointerDown(e: PointerEvent<HTMLCanvasElement>) {
    if (!interactive || !rectRef.current) return;
    const { x, y } = localPoint(e);
    // A tap that starts in the letterbox bars is ignored.
    const p = toFraction(x, y, rectRef.current, false);
    if (!p) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    draggingRef.current = true;
    onChange!(p);
  }

  function handlePointerMove(e: PointerEvent<HTMLCanvasElement>) {
    if (!interactive || !draggingRef.current || !rectRef.current) return;
    const { x, y } = localPoint(e);
    onChange!(toFraction(x, y, rectRef.current, true)!);
  }

  function endDrag(e: PointerEvent<HTMLCanvasElement>) {
    draggingRef.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLCanvasElement>) {
    if (!interactive) return;
    const step = e.shiftKey ? 0.05 : 0.01;
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step],
    };
    if (e.key in moves) {
      e.preventDefault();
      if (!pin) onChange!({ x: 0.5, y: 0.5 });
      else onChange!(nudge(pin, ...moves[e.key]));
    } else if (e.key === 'Enter' && pin) {
      e.preventDefault();
      onSubmit?.();
    }
  }

  return (
    <div ref={boxRef} className="relative w-full" style={{ height: box.h || undefined }}>
      <canvas
        ref={canvasRef}
        data-testid="pin-canvas"
        role="img"
        aria-label={ariaLabel}
        tabIndex={interactive ? 0 : -1}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={handleKeyDown}
        className={`block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
          interactive ? 'cursor-crosshair' : ''
        }`}
        style={{ width: box.w, height: box.h, touchAction: 'none' }}
      />
      {failed && (
        <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-slate-800/90">
          <p className="text-slate-300 font-semibold">Image failed to load</p>
        </div>
      )}
    </div>
  );
}
