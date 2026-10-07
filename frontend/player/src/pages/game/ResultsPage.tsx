import { useGame } from './GameLayout';
import { orderText } from '../../lib/putInOrder';
import { PinCanvas } from '../../components/PinCanvas';
import { aspectOf, isTap, pinImageSrc, pinVerdict } from '../../lib/pinTheSpot';

function describeAnswer(
  lastAnswerData: Record<string, unknown> | null,
  type: string,
  options: string[] | undefined,
  items: string[] | undefined,
): string | null {
  if (!lastAnswerData) return null;
  if (type === 'multiple_choice') {
    const idx = lastAnswerData.selectedIndex;
    if (typeof idx === 'number' && options && options[idx] !== undefined) {
      return `${String.fromCharCode(65 + idx)} — ${options[idx]}`;
    }
  }
  if (type === 'true_false') {
    return lastAnswerData.selectedValue ? 'True' : 'False';
  }
  if (type === 'fill_in_the_blank') {
    return typeof lastAnswerData.text === 'string' ? lastAnswerData.text : null;
  }
  if (type === 'multi_select') {
    const indices = lastAnswerData.selectedIndices;
    if (Array.isArray(indices) && options) {
      return indices
        .filter((i): i is number => typeof i === 'number' && options[i] !== undefined)
        .map(i => options[i])
        .join(', ');
    }
  }
  if (type === 'put_in_order') {
    return orderText(lastAnswerData.orderedIndices, items);
  }
  return null;
}

export default function ResultsPage() {
  const { questionResults, currentQuestion, lastAnswerData } = useGame();

  if (!questionResults) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-ink-muted">Loading results…</p>
      </div>
    );
  }

  const { answerReveal, yourPoints, yourIsCorrect, yourScore, yourRank, playerCount } = questionResults;
  const items = currentQuestion?.config.items;
  const answeredLabel = describeAnswer(
    lastAnswerData,
    currentQuestion?.type ?? '',
    currentQuestion?.config.options,
    items,
  );
  const isCompleteness = answerReveal.type === 'completeness';
  const isFitb = answerReveal.type === 'fill_in_the_blank';
  // put_in_order ACCURACY reads the server's is_correct (perfect order only); partial
  // scores are "Partially correct". Points can equal pointsValue without a perfect order.
  const isPioAccuracy =
    currentQuestion?.type === 'put_in_order' && answerReveal.type === 'put_in_order';
  // pin_the_spot ACCURACY: ✓ from yourIsCorrect, ◐ by distance (D9), never from points.
  const isPin = currentQuestion?.type === 'pin_the_spot';
  const pinAspect = isPin ? aspectOf(currentQuestion?.config) : null;
  const pinKey = 'rZero' in answerReveal || 'target' in answerReveal ? answerReveal : {};
  const verdict = isPin && answerReveal.type === 'pin_the_spot'
    ? pinVerdict(yourIsCorrect, lastAnswerData, pinKey, pinAspect)
    : null;
  const isCorrect = verdict
    ? verdict === 'correct'
    : isPioAccuracy ? yourIsCorrect : !isCompleteness && yourPoints > 0;
  const isPartial = verdict ? verdict === 'partial' : isPioAccuracy && !yourIsCorrect && yourPoints > 0;
  const correctOrderLabel =
    'correctOrder' in answerReveal ? orderText(answerReveal.correctOrder, items) : null;

  const fitbAccepted: string[] =
    isFitb && 'acceptedAnswers' in answerReveal ? answerReveal.acceptedAnswers : [];

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-6 gap-5 text-center">

      {/* Correct / Wrong / Recorded */}
      {isCompleteness ? (
        <p className="nb-h1 nb-box bg-info text-on-fill px-6 py-3">Answer recorded!</p>
      ) : isCorrect ? (
        <p className="nb-h1 nb-box bg-success text-on-fill px-6 py-3"><span aria-hidden="true">✓ </span><span>Correct!</span></p>
      ) : isPartial ? (
        <p className="nb-h1 nb-box bg-warning text-on-fill px-6 py-3"><span aria-hidden="true">◐ </span><span>Partially correct</span></p>
      ) : (
        <p className="nb-h1 nb-box bg-danger text-on-fill px-6 py-3"><span aria-hidden="true">✗ </span><span>Incorrect</span></p>
      )}

      {/* pin_the_spot: the player's pin (from this phone's submission) against the reveal */}
      {isPin && pinAspect !== null && (
        <div className="w-full max-w-md">
          <PinCanvas
            imageUrl={pinImageSrc(currentQuestion?.config)}
            aspect={pinAspect}
            pin={isTap(lastAnswerData) ? { x: lastAnswerData.x, y: lastAnswerData.y } : null}
            reveal={pinKey}
            ariaLabel={currentQuestion?.prompt ?? 'Pin the Spot results'}
            maxHeight={typeof window !== 'undefined' ? window.innerHeight * 0.45 : undefined}
          />
        </div>
      )}

      {/* What the player answered */}
      {answeredLabel && (
        <p className="text-ink-muted text-base">
          You answered: <span className="text-ink font-semibold">{answeredLabel}</span>
        </p>
      )}

      {/* Correct answer for FITB ACCURACY */}
      {isFitb && fitbAccepted.length > 0 && (
        <p className="text-ink-muted text-base">
          Correct: <span className="text-success-text font-semibold">{fitbAccepted.join(' / ')}</span>
        </p>
      )}

      {/* Correct order for put_in_order (both grading types, whenever revealed) */}
      {correctOrderLabel && (
        <p className="text-ink-muted text-base">
          Correct order: <span className="text-success-text font-semibold">{correctOrderLabel}</span>
        </p>
      )}

      {/* Points for this question */}
      <p className="nb-h1 text-ink tabular-nums">
        +{yourPoints.toLocaleString()} pts
      </p>

      {/* Running total and rank */}
      <div className="mt-2 space-y-1">
        <p className="text-ink-muted text-lg">
          Total: <span className="font-bold text-ink tabular-nums">{yourScore.toLocaleString()}</span> pts
        </p>
        <p className="text-ink-muted text-base">
          Rank <span className="font-bold text-ink">#{yourRank}</span> of {playerCount}
        </p>
      </div>

      <p className="text-ink-muted text-sm mt-4">Waiting for next question…</p>
    </div>
  );
}
