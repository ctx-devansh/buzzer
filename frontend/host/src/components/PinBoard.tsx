import { useEffect, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { dotRadius, fitRect, parseTapKey, toFraction } from '../lib/pinTheSpot';
import type { PinKey, PinPoint, PinRect } from '../lib/pinTheSpot';
import { useTheme } from '../lib/theme';

interface PinBoardProps {
  imageUrl: string | undefined;
  aspect: number;
  /** Tap distribution ("x,y" → count); drawn as dots, bigger for repeats. */
  taps?: Record<string, number>;
  /** Target and circles (reveal, game over, editor preview). */
  pinKey?: PinKey;
  /** Editor: click/drag places the target. */
  onPick?: (p: PinPoint) => void;
  /** Tallest the board may be, in CSS px (never taller than width × aspect). */
  maxHeight?: number;
  ariaLabel: string;
  testId?: string;
}

function cssVar(el: Element, name: string, fallback: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || fallback;
}

/**
 * The host's Pin the Spot board: the image fitted (letterboxed) into the stored aspect, every
 * tap as a dot, the dashed zero-credit circle, the filled full-credit circle and the target.
 * With `onPick` it is the editor's target picker. Colours come from `--pin-*` custom
 * properties with fallbacks.
 */
export function PinBoard({ imageUrl, aspect, taps, pinKey, onPick, maxHeight, ariaLabel, testId }: PinBoardProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rectRef = useRef<PinRect | null>(null);
  const draggingRef = useRef(false);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setImage(null);
    setFailed(false);
    if (!imageUrl) return;
    const img = new Image();
    img.onload = () => setImage(img);
    img.onerror = () => setFailed(true);
    img.src = imageUrl;
    return () => {
      img.onload = null;
      img.onerror = null;
    };
  }, [imageUrl]);

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
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [aspect, maxHeight]);

  // Colours are read from CSS variables while drawing, so a theme change must trigger a redraw.
  const [theme] = useTheme();

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
      // A light backing first, so a transparent image stays visible in dark mode (§4.9).
      ctx.fillStyle = cssVar(canvas, '--pin-image-bg', '#ffffff');
      ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
      ctx.drawImage(image, rect.x, rect.y, rect.w, rect.h);
    } else {
      ctx.fillStyle = cssVar(canvas, '--pin-placeholder', '#1e293b');
      ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    }

    const px = (p: PinPoint) => ({ x: rect.x + p.x * rect.w, y: rect.y + p.y * rect.h });
    const hasCircles =
      !!pinKey?.target && typeof pinKey.rFull === 'number' && typeof pinKey.rZero === 'number';

    if (hasCircles) {
      const c = px(pinKey!.target!);
      ctx.save();
      ctx.beginPath();
      ctx.arc(c.x, c.y, pinKey!.rZero! * rect.w, 0, Math.PI * 2);
      ctx.setLineDash([10, 7]);
      ctx.lineWidth = 3;
      ctx.strokeStyle = cssVar(canvas, '--pin-zero', '#fbbf24');
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(c.x, c.y, pinKey!.rFull! * rect.w, 0, Math.PI * 2);
      ctx.fillStyle = cssVar(canvas, '--pin-full-fill', 'rgba(74, 222, 128, 0.3)');
      ctx.fill();
      ctx.strokeStyle = cssVar(canvas, '--pin-full', '#4ade80');
      ctx.stroke();
      ctx.restore();
    }

    if (taps) {
      ctx.save();
      ctx.fillStyle = cssVar(canvas, '--pin-tap', 'rgba(129, 140, 248, 0.85)');
      ctx.strokeStyle = cssVar(canvas, '--pin-tap-stroke', '#ffffff');
      ctx.lineWidth = 1.5;
      for (const [key, count] of Object.entries(taps)) {
        const p = parseTapKey(key);
        if (!p || count <= 0) continue;
        const c = px(p);
        ctx.beginPath();
        ctx.arc(c.x, c.y, dotRadius(count, rect.w), 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
      ctx.restore();
    }

    if (pinKey?.target) {
      const c = px(pinKey.target);
      ctx.save();
      ctx.beginPath();
      ctx.arc(c.x, c.y, Math.max(rect.w * 0.008, 5), 0, Math.PI * 2);
      ctx.fillStyle = cssVar(canvas, '--pin-target', '#ef4444');
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = cssVar(canvas, '--pin-marker-stroke', '#ffffff');
      ctx.stroke();
      ctx.restore();
    }
  }, [box, aspect, image, taps, pinKey, theme]);

  function localPoint(e: PointerEvent<HTMLCanvasElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function handlePointerDown(e: PointerEvent<HTMLCanvasElement>) {
    if (!onPick || !image || !rectRef.current) return;
    const { x, y } = localPoint(e);
    const p = toFraction(x, y, rectRef.current, false);
    if (!p) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    draggingRef.current = true;
    onPick(p);
  }

  function handlePointerMove(e: PointerEvent<HTMLCanvasElement>) {
    if (!onPick || !draggingRef.current || !rectRef.current) return;
    const { x, y } = localPoint(e);
    onPick(toFraction(x, y, rectRef.current, true)!);
  }

  function endDrag(e: PointerEvent<HTMLCanvasElement>) {
    draggingRef.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  return (
    // An outline, not a border: the box is measured to size the canvas, and outlines take no space.
    <div ref={boxRef} className="relative w-full outline outline-4 outline-line" style={{ height: box.h || undefined }}>
      <canvas
        ref={canvasRef}
        data-testid={testId}
        data-loaded={image ? 'true' : 'false'}
        role="img"
        aria-label={ariaLabel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        className={`block ${onPick && image ? 'cursor-crosshair' : ''}`}
        style={{ width: box.w, height: box.h, touchAction: onPick ? 'none' : undefined }}
      />
      {failed && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface">
          <p className="text-ink-muted font-semibold">Image failed to load</p>
        </div>
      )}
    </div>
  );
}
