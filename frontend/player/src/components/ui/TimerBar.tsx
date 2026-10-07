import { useEffect, useRef, useState } from 'react';

interface TimerBarProps {
  totalSeconds: number;
  paused?: boolean;
}

export function TimerBar({ totalSeconds, paused = false }: TimerBarProps) {
  const [timeLeft, setTimeLeft] = useState(totalSeconds);
  const pausedRef = useRef(paused);
  const endTimeRef = useRef(Date.now() + totalSeconds * 1000);
  const frozenRef = useRef(totalSeconds);

  // Keep pausedRef in sync; on resume, reset endTime from the frozen value
  useEffect(() => {
    pausedRef.current = paused;
    if (!paused) {
      endTimeRef.current = Date.now() + frozenRef.current * 1000;
    }
  }, [paused]);

  useEffect(() => {
    if (totalSeconds <= 0) return;

    const id = setInterval(() => {
      if (pausedRef.current) {
        // Slide endTime forward so resume continues from the frozen value
        endTimeRef.current = Date.now() + frozenRef.current * 1000;
        return;
      }
      const remaining = Math.max(0, (endTimeRef.current - Date.now()) / 1000);
      frozenRef.current = remaining;
      setTimeLeft(remaining);
    }, 100);

    return () => clearInterval(id);
  }, []); // runs once on mount; parent uses key={questionId} to remount per question

  const fraction = Math.max(0, Math.min(1, timeLeft / totalSeconds));
  const displaySeconds = Math.ceil(timeLeft);

  const barColor =
    fraction > 0.6 ? 'bg-success' :
    fraction > 0.3 ? 'bg-warning' :
    'bg-danger';

  // Square track with an ink outline; the fill carries its own edge so it is never an outline-less
  // fill (docs/design-better-ui.md §4.2). The seconds sit beside the bar, so they use ink-muted.
  return (
    <div className="w-full flex items-center gap-3">
      <div className="flex-1 h-4 bg-surface-muted border-2 border-line overflow-hidden">
        <div
          className={`h-full transition-[width] duration-100 ease-linear ${barColor} ${fraction > 0 ? 'border-r-2 border-line' : ''}`}
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
      <span className="text-ink-muted font-display font-bold text-sm w-8 text-right tabular-nums shrink-0">
        {displaySeconds}s
      </span>
    </div>
  );
}
