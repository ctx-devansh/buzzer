import { useRef, useState, useCallback, useEffect } from 'react';
import { useGame } from './GameLayout';
import { TimerBar } from '../../components/ui/TimerBar';
import { PinCanvas } from '../../components/PinCanvas';
import { aspectOf, pinImageSrc } from '../../lib/pinTheSpot';
import { imageUrl } from '../../lib/images';
import type { PinPoint } from '../../lib/pinTheSpot';

// Literal strings, so Tailwind's content scan sees all eight; never build `bg-option-${n}`.
// Past eight options the colours repeat; the letter badge tells them apart (docs/design-better-ui.md).
const OPTION_FILLS = [
  'bg-option-1', 'bg-option-2', 'bg-option-3', 'bg-option-4',
  'bg-option-5', 'bg-option-6', 'bg-option-7', 'bg-option-8',
];

// Tiles (§4.11): constant outline and hard shadow, lift on hover, press on tap. Text on a fill
// is text-on-fill. Disabled tiles go grey, except selected ones, which keep their fill and ring.
const TILE = 'nb-box nb-press touch-manipulation disabled:cursor-not-allowed';
const TILE_DISABLED = 'disabled:bg-surface-muted disabled:text-ink-muted';
const ROW = `${TILE} w-full flex items-center gap-4 px-5 py-4 text-left font-semibold text-lg`;
const BADGE = 'flex h-9 w-9 shrink-0 items-center justify-center border-2 border-line bg-surface text-ink font-display font-bold text-xl';
const SUBMIT =
  'nb-box nb-press w-full min-h-14 font-display font-bold text-2xl bg-accent text-on-fill disabled:bg-surface-muted disabled:text-ink-muted';
const WAITING = <p className="text-center text-ink-muted text-sm mt-4">Answer submitted — waiting for results…</p>;

/**
 * The picture area of an image-option tile (T8, design §5.4): a fixed 22vh box, so every
 * tile is the same size and nothing shifts under a finger while images load (an MC tap
 * submits at once). Without an image, or if it fails to load, the box shows the letter.
 */
function OptionPicture({ imageId, letter }: { imageId: string | null | undefined; letter: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [imageId]);
  return (
    // image-bg: a light backing, so transparent images stay visible in dark mode (§4.9).
    <span className="flex h-[22vh] w-full items-center justify-center border-2 border-line bg-image-bg">
      {imageId && !failed ? (
        <img
          src={imageUrl(imageId)}
          alt=""
          onError={() => setFailed(true)}
          className="max-h-full max-w-full object-contain"
          data-testid="option-image"
        />
      ) : (
        <span className="nb-hero text-on-fill">{letter}</span>
      )}
    </span>
  );
}

function optionLabel(i: number): string {
  return String.fromCharCode(65 + i); // A, B, C, … Z
}

export default function QuestionPage() {
  const { currentQuestion, questionLocked, emitAnswer } = useGame();
  const startTimeRef = useRef(Date.now());
  const [submitted, setSubmitted] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  // put_in_order: `order` holds indices into config.items in on-screen order; `picked` is
  // the position tapped first. Both reset on remount, like `submitted`.
  const [order, setOrder] = useState<number[]>(() =>
    Array.from({ length: currentQuestion?.config.items?.length ?? 0 }, (_, i) => i),
  );
  const [picked, setPicked] = useState<number | null>(null);
  const [movedPos, setMovedPos] = useState<number | null>(null);
  // pin_the_spot: the placed (not yet locked) pin; resets on remount like `submitted`.
  const [pin, setPin] = useState<PinPoint | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    if (questionLocked) setPicked(null);
  }, [questionLocked]);

  useEffect(() => {
    if (movedPos === null) return;
    const t = setTimeout(() => setMovedPos(null), 600);
    return () => clearTimeout(t);
  }, [movedPos]);

  const toggleIndex = useCallback((i: number) => {
    if (submitted || questionLocked) return;
    setSelectedIndices(prev => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  }, [submitted, questionLocked]);

  if (!currentQuestion) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-ink-muted">Loading question…</p>
      </div>
    );
  }

  function submit(answerData: Record<string, unknown>) {
    if (submitted) return;
    setSubmitted(true);
    emitAnswer(currentQuestion!.questionId, answerData, Date.now() - startTimeRef.current);
  }

  const questionLabel = (
    <p className="nb-caption text-center mb-1">
      Question {currentQuestion.questionNumber} of {currentQuestion.totalQuestions}
    </p>
  );

  const lockedMsg = (
    <p className="text-center text-warning-text text-sm mt-4 font-semibold">
      Answers locked — waiting for results…
    </p>
  );

  // Any option image turns the tiles into a 2-column grid of equal tiles (design §5.4);
  // the option text stays, as the caption. No images: the tiles look as before.
  const optionImageIds = currentQuestion.config.option_image_ids;
  const hasOptionImages = (optionImageIds ?? []).some((id) => id);

  if (currentQuestion.type === 'multiple_choice' && hasOptionImages) {
    const options = currentQuestion.config.options ?? [];
    return (
      <div className="py-6 px-4 flex flex-col gap-3">
        <div className="pb-2">
          {questionLabel}
          <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        </div>
        <div className="grid grid-cols-2 gap-3" data-testid="option-grid">
          {options.map((opt, i) => (
            <button
              key={i}
              disabled={submitted || questionLocked}
              onClick={() => submit({ selectedIndex: i })}
              className={`${TILE} ${TILE_DISABLED} ${OPTION_FILLS[i % OPTION_FILLS.length]} flex flex-col items-stretch gap-2 p-2 text-on-fill font-semibold`}
            >
              <OptionPicture imageId={optionImageIds?.[i]} letter={optionLabel(i)} />
              <span className="text-left text-base leading-snug">
                <span className="font-display font-bold mr-2">{optionLabel(i)}</span>{opt}
              </span>
            </button>
          ))}
        </div>
        {submitted && WAITING}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'multiple_choice') {
    const options = currentQuestion.config.options ?? [];
    return (
      <div className="py-6 px-4 flex flex-col gap-3">
        <div className="pb-2">
          {questionLabel}
          <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        </div>
        {options.map((opt, i) => (
          <button
            key={i}
            disabled={submitted || questionLocked}
            onClick={() => submit({ selectedIndex: i })}
            className={`${ROW} ${TILE_DISABLED} ${OPTION_FILLS[i % OPTION_FILLS.length]} text-on-fill`}
          >
            <span className={BADGE}>{optionLabel(i)}</span>
            <span>{opt}</span>
          </button>
        ))}
        {submitted && WAITING}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'true_false') {
    return (
      <div className="flex flex-1 flex-col justify-center p-4 gap-4">
        {questionLabel}
        <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        <button
          disabled={submitted || questionLocked}
          onClick={() => submit({ selectedValue: true })}
          className={`${TILE} ${TILE_DISABLED} w-full py-8 bg-success text-on-fill font-display font-bold text-3xl`}
        >
          True
        </button>
        <button
          disabled={submitted || questionLocked}
          onClick={() => submit({ selectedValue: false })}
          className={`${TILE} ${TILE_DISABLED} w-full py-8 bg-danger text-on-fill font-display font-bold text-3xl`}
        >
          False
        </button>
        {submitted && <p className="text-center text-ink-muted text-sm mt-2">Answer submitted — waiting for results…</p>}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'fill_in_the_blank') {
    const maxLength = currentQuestion.config.maxLength ?? 100;
    return (
      <div className="flex flex-1 flex-col justify-center p-4 gap-5">
        {questionLabel}
        <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />

        {submitted ? (
          <div className="flex flex-col items-center gap-3">
            <div className="nb-hero" aria-hidden="true">🔒</div>
            <p className="nb-h2 text-ink">Answer locked in!</p>
            <p className="text-ink-muted text-base italic">"{inputValue.trim()}"</p>
            <p className="text-ink-muted text-sm mt-2">Waiting for results…</p>
          </div>
        ) : questionLocked ? (
          <div className="flex flex-col items-center gap-3 mt-4">
            {lockedMsg}
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const trimmed = inputValue.trim();
              if (trimmed) submit({ text: trimmed });
            }}
            className="flex flex-col gap-4"
          >
            <input
              type="text"
              maxLength={maxLength}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Type your answer…"
              autoFocus
              className="w-full border-2 border-line bg-surface px-4 py-4 text-ink text-xl"
            />
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className={SUBMIT}
            >
              Submit
            </button>
          </form>
        )}
      </div>
    );
  }

  if (currentQuestion.type === 'multi_select') {
    const options = currentQuestion.config.options ?? [];
    return (
      <div className="py-6 px-4 flex flex-col gap-3">
        <div className="pb-2">
          {questionLabel}
          <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        </div>
        <p className="text-center text-ink-muted text-sm">Select all that apply</p>
        <div className={hasOptionImages ? 'grid grid-cols-2 gap-3' : 'flex flex-col gap-3'} data-testid={hasOptionImages ? 'option-grid' : undefined}>
        {options.map((opt, i) => {
          const isSelected = selectedIndices.has(i);
          if (hasOptionImages) {
            return (
              <button
                key={i}
                disabled={submitted || questionLocked}
                onClick={() => toggleIndex(i)}
                aria-pressed={isSelected}
                className={`${TILE} flex flex-col items-stretch gap-2 p-2 font-semibold ${
                  isSelected ? 'nb-selected bg-accent text-on-fill' : `bg-surface text-ink ${TILE_DISABLED}`
                }`}
              >
                <OptionPicture imageId={optionImageIds?.[i]} letter={optionLabel(i)} />
                <span className="text-left text-base leading-snug">
                  <span className="font-display font-bold mr-2">{isSelected ? '✓' : optionLabel(i)}</span>{opt}
                </span>
              </button>
            );
          }
          return (
            <button
              key={i}
              disabled={submitted || questionLocked}
              onClick={() => toggleIndex(i)}
              aria-pressed={isSelected}
              className={`${ROW} ${isSelected ? 'nb-selected bg-accent text-on-fill' : `bg-surface text-ink ${TILE_DISABLED}`}`}
            >
              <span className={BADGE}>{isSelected ? '✓' : optionLabel(i)}</span>
              <span>{opt}</span>
            </button>
          );
        })}
        </div>
        {!submitted && !questionLocked && (
          <button
            disabled={selectedIndices.size === 0}
            onClick={() => submit({ selectedIndices: Array.from(selectedIndices) })}
            className={`${SUBMIT} mt-2`}
          >
            Submit ({selectedIndices.size} selected)
          </button>
        )}
        {submitted && WAITING}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'put_in_order') {
    const items = currentQuestion.config.items ?? [];
    const inactive = submitted || questionLocked;

    // Pick-and-place with insert semantics: the picked item is removed and re-inserted at
    // the tapped position, so it always ends up exactly where the player tapped.
    const tapRow = (pos: number) => {
      if (inactive) return;
      if (picked === null) {
        setPicked(pos);
        return;
      }
      if (picked === pos) {
        setPicked(null);
        return;
      }
      const next = [...order];
      const [item] = next.splice(picked, 1);
      next.splice(pos, 0, item);
      setOrder(next);
      setPicked(null);
      setMovedPos(pos);
    };

    return (
      <div className="py-6 px-4 flex flex-col gap-3">
        <div className="pb-2">
          {questionLabel}
          <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        </div>
        <p className="text-center text-ink-muted text-sm">
          {picked === null ? 'Tap an item to move it' : 'Tap where it goes'}
        </p>
        {order.map((itemIdx, pos) => {
          const isPicked = picked === pos;
          const isMoved = movedPos === pos;
          return (
            <button
              key={itemIdx}
              data-testid={`pio-row-${pos}`}
              aria-pressed={isPicked}
              disabled={inactive}
              onClick={() => tapRow(pos)}
              className={`${ROW} ${
                isPicked
                  ? 'nb-selected bg-accent text-on-fill'
                  : isMoved
                    ? `bg-success text-on-fill ${TILE_DISABLED}`
                    : `bg-surface text-ink ${TILE_DISABLED}`
              }`}
            >
              <span className={BADGE}>{isPicked ? '✓' : pos + 1}</span>
              <span>{items[itemIdx]}</span>
            </button>
          );
        })}
        {!inactive && (
          <button
            data-testid="pio-lock-in"
            disabled={inactive}
            onClick={() => submit({ orderedIndices: order })}
            className={`${SUBMIT} mt-2`}
          >
            Lock in
          </button>
        )}
        {submitted && WAITING}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'pin_the_spot') {
    const aspect = aspectOf(currentQuestion.config);
    const inactive = submitted || questionLocked;
    const canLock = !inactive && !!pin && !imageFailed;
    return (
      <div className="py-6 px-4 flex flex-col gap-3">
        <div className="pb-2">
          {questionLabel}
          <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        </div>
        {/* The one type whose prompt the phone shows: the player is looking down at the image.
            Plain React text (escaped), as on the host. */}
        <p data-testid="pin-prompt" className="nb-prompt text-center text-ink">
          {currentQuestion.prompt}
        </p>
        {aspect === null ? (
          <p className="text-center text-ink-muted">Image failed to load</p>
        ) : (
          <PinCanvas
            imageUrl={pinImageSrc(currentQuestion.config)}
            aspect={aspect}
            pin={pin}
            onChange={imageFailed ? undefined : setPin}
            onSubmit={() => canLock && submit({ x: pin!.x, y: pin!.y })}
            disabled={inactive}
            ariaLabel={currentQuestion.prompt}
            onImageError={() => {
              setImageFailed(true);
              setPin(null);
            }}
          />
        )}
        {!inactive && !imageFailed && aspect !== null && (
          <>
            <p className="text-center text-ink-muted text-sm">
              {pin ? 'Drag to adjust, then lock in' : 'Tap the image to drop your pin'}
            </p>
            <button
              data-testid="pin-lock-in"
              disabled={!canLock}
              onClick={() => canLock && submit({ x: pin!.x, y: pin!.y })}
              className={`${SUBMIT} mt-1`}
            >
              Lock in
            </button>
          </>
        )}
        {submitted && WAITING}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6">
      <p className="text-ink-muted">Unsupported question type.</p>
    </div>
  );
}
