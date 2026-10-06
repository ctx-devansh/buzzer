import { useRef, useState, useCallback, useEffect } from 'react';
import { useGame } from './GameLayout';
import { TimerBar } from '../../components/ui/TimerBar';
import { PinCanvas } from '../../components/PinCanvas';
import { aspectOf, pinImageSrc } from '../../lib/pinTheSpot';
import { imageUrl } from '../../lib/images';
import type { PinPoint } from '../../lib/pinTheSpot';

const OPTION_COLORS = [
  'bg-red-600 hover:bg-red-500 border-red-500',
  'bg-blue-600 hover:bg-blue-500 border-blue-500',
  'bg-yellow-500 hover:bg-yellow-400 border-yellow-400',
  'bg-green-600 hover:bg-green-500 border-green-500',
  'bg-purple-600 hover:bg-purple-500 border-purple-500',
  'bg-orange-500 hover:bg-orange-400 border-orange-400',
  'bg-pink-600 hover:bg-pink-500 border-pink-500',
  'bg-teal-600 hover:bg-teal-500 border-teal-500',
];

/**
 * The picture area of an image-option tile (T8, design §5.4): a fixed 22vh box, so every
 * tile is the same size and nothing shifts under a finger while images load (an MC tap
 * submits at once). Without an image, or if it fails to load, the box shows the letter.
 */
function OptionPicture({ imageId, letter }: { imageId: string | null | undefined; letter: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [imageId]);
  return (
    <span className="flex h-[22vh] w-full items-center justify-center">
      {imageId && !failed ? (
        <img
          src={imageUrl(imageId)}
          alt=""
          onError={() => setFailed(true)}
          className="max-h-full max-w-full rounded-lg object-contain"
          data-testid="option-image"
        />
      ) : (
        <span className="text-5xl font-black opacity-60">{letter}</span>
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
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-400">Loading question…</p>
      </div>
    );
  }

  function submit(answerData: Record<string, unknown>) {
    if (submitted) return;
    setSubmitted(true);
    emitAnswer(currentQuestion!.questionId, answerData, Date.now() - startTimeRef.current);
  }

  const questionLabel = (
    <p className="text-slate-400 text-sm text-center tracking-wide uppercase mb-1">
      Question {currentQuestion.questionNumber} of {currentQuestion.totalQuestions}
    </p>
  );

  const lockedMsg = (
    <p className="text-center text-amber-400 text-sm mt-4 font-semibold">
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
              className={`flex flex-col items-stretch gap-2 rounded-2xl p-2 text-white font-semibold border-2 transition-all
                ${submitted || questionLocked ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}
                ${OPTION_COLORS[i % OPTION_COLORS.length]}`}
            >
              <OptionPicture imageId={optionImageIds?.[i]} letter={optionLabel(i)} />
              <span className="text-left text-base leading-snug">
                <span className="font-black mr-2">{optionLabel(i)}</span>{opt}
              </span>
            </button>
          ))}
        </div>
        {submitted && <p className="text-center text-slate-400 text-sm mt-4">Answer submitted — waiting for results…</p>}
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
            className={`w-full flex items-center gap-4 rounded-2xl px-5 py-4 text-left text-white font-semibold text-lg border-2 transition-all
              ${submitted || questionLocked ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}
              ${OPTION_COLORS[i % OPTION_COLORS.length]}`}
          >
            <span className="text-2xl font-black w-8 shrink-0">{optionLabel(i)}</span>
            <span>{opt}</span>
          </button>
        ))}
        {submitted && <p className="text-center text-slate-400 text-sm mt-4">Answer submitted — waiting for results…</p>}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'true_false') {
    return (
      <div className="min-h-screen flex flex-col justify-center p-4 gap-4">
        {questionLabel}
        <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />
        <button
          disabled={submitted || questionLocked}
          onClick={() => submit({ selectedValue: true })}
          className={`w-full rounded-2xl py-8 text-white font-black text-3xl border-2 border-green-500 transition-all
            ${submitted || questionLocked ? 'opacity-50 cursor-not-allowed bg-green-700' : 'bg-green-600 hover:bg-green-500 active:scale-95'}`}
        >
          True
        </button>
        <button
          disabled={submitted || questionLocked}
          onClick={() => submit({ selectedValue: false })}
          className={`w-full rounded-2xl py-8 text-white font-black text-3xl border-2 border-red-500 transition-all
            ${submitted || questionLocked ? 'opacity-50 cursor-not-allowed bg-red-700' : 'bg-red-600 hover:bg-red-500 active:scale-95'}`}
        >
          False
        </button>
        {submitted && <p className="text-center text-slate-400 text-sm mt-2">Answer submitted — waiting for results…</p>}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  if (currentQuestion.type === 'fill_in_the_blank') {
    const maxLength = currentQuestion.config.maxLength ?? 100;
    return (
      <div className="min-h-screen flex flex-col justify-center p-4 gap-5">
        {questionLabel}
        <TimerBar key={currentQuestion.questionId} totalSeconds={currentQuestion.timeLimitSeconds} paused={questionLocked} />

        {submitted ? (
          <div className="flex flex-col items-center gap-3">
            <div className="text-5xl">🔒</div>
            <p className="text-slate-100 text-xl font-bold">Answer locked in!</p>
            <p className="text-slate-400 text-base italic">"{inputValue.trim()}"</p>
            <p className="text-slate-500 text-sm mt-2">Waiting for results…</p>
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
              className="w-full rounded-xl px-4 py-4 text-slate-900 text-xl bg-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className="w-full rounded-2xl py-5 text-white font-black text-2xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
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
        <p className="text-center text-slate-400 text-sm">Select all that apply</p>
        <div className={hasOptionImages ? 'grid grid-cols-2 gap-3' : 'flex flex-col gap-3'} data-testid={hasOptionImages ? 'option-grid' : undefined}>
        {options.map((opt, i) => {
          const isSelected = selectedIndices.has(i);
          if (hasOptionImages) {
            return (
              <button
                key={i}
                disabled={submitted || questionLocked}
                onClick={() => toggleIndex(i)}
                className={`flex flex-col items-stretch gap-2 rounded-2xl p-2 font-semibold border-2 transition-all
                  ${submitted || questionLocked ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}
                  ${isSelected
                    ? 'bg-indigo-600 border-indigo-400 text-white'
                    : 'bg-slate-700 border-slate-600 text-slate-200 hover:bg-slate-600'
                  }`}
              >
                <OptionPicture imageId={optionImageIds?.[i]} letter={optionLabel(i)} />
                <span className="text-left text-base leading-snug">
                  <span className="font-black mr-2">{isSelected ? '✓' : optionLabel(i)}</span>{opt}
                </span>
              </button>
            );
          }
          return (
            <button
              key={i}
              disabled={submitted || questionLocked}
              onClick={() => toggleIndex(i)}
              className={`w-full flex items-center gap-4 rounded-2xl px-5 py-4 text-left font-semibold text-lg border-2 transition-all
                ${submitted || questionLocked ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}
                ${isSelected
                  ? 'bg-indigo-600 border-indigo-400 text-white'
                  : 'bg-slate-700 border-slate-600 text-slate-200 hover:bg-slate-600'
                }`}
            >
              <span className={`text-xl font-black w-8 shrink-0 flex items-center justify-center rounded-md border-2 transition-colors
                ${isSelected ? 'border-white bg-white text-indigo-700' : 'border-slate-500 text-slate-400'}`}>
                {isSelected ? '✓' : optionLabel(i)}
              </span>
              <span>{opt}</span>
            </button>
          );
        })}
        </div>
        {!submitted && !questionLocked && (
          <button
            disabled={selectedIndices.size === 0}
            onClick={() => submit({ selectedIndices: Array.from(selectedIndices) })}
            className="w-full rounded-2xl py-5 text-white font-black text-2xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed mt-2"
          >
            Submit ({selectedIndices.size} selected)
          </button>
        )}
        {submitted && <p className="text-center text-slate-400 text-sm mt-4">Answer submitted — waiting for results…</p>}
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
        <p className="text-center text-slate-400 text-sm">
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
              className={`w-full flex items-center gap-4 rounded-2xl px-5 py-4 text-left font-semibold text-lg border-2 transition-all
                ${inactive ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}
                ${isPicked
                  ? 'bg-indigo-600 border-indigo-300 text-white ring-2 ring-indigo-300'
                  : isMoved
                    ? 'bg-emerald-700 border-emerald-400 text-white'
                    : 'bg-slate-700 border-slate-600 text-slate-200 hover:bg-slate-600'
                }`}
            >
              <span className="text-xl font-black w-8 shrink-0 text-center">{pos + 1}</span>
              <span>{items[itemIdx]}</span>
            </button>
          );
        })}
        {!inactive && (
          <button
            data-testid="pio-lock-in"
            disabled={inactive}
            onClick={() => submit({ orderedIndices: order })}
            className="w-full rounded-2xl py-5 text-white font-black text-2xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed mt-2"
          >
            Lock in
          </button>
        )}
        {submitted && <p className="text-center text-slate-400 text-sm mt-4">Answer submitted — waiting for results…</p>}
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
        <p data-testid="pin-prompt" className="text-center text-slate-100 text-lg font-semibold leading-snug">
          {currentQuestion.prompt}
        </p>
        {aspect === null ? (
          <p className="text-center text-slate-400">Image failed to load</p>
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
            <p className="text-center text-slate-400 text-sm">
              {pin ? 'Drag to adjust, then lock in' : 'Tap the image to drop your pin'}
            </p>
            <button
              data-testid="pin-lock-in"
              disabled={!canLock}
              onClick={() => canLock && submit({ x: pin!.x, y: pin!.y })}
              className="w-full rounded-2xl py-5 text-white font-black text-2xl bg-indigo-600 hover:bg-indigo-500 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed mt-1"
            >
              Lock in
            </button>
          </>
        )}
        {submitted && <p className="text-center text-slate-400 text-sm mt-4">Answer submitted — waiting for results…</p>}
        {!submitted && questionLocked && lockedMsg}
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <p className="text-slate-400">Unsupported question type.</p>
    </div>
  );
}
