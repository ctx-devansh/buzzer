import { useGame } from './GameLayout';
import { orderText } from '../../lib/putInOrder';
import { PinCanvas } from '../../components/PinCanvas';
import { aspectOf, isTap, pinVerdict } from '../../lib/pinTheSpot';

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
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-400">Loading results…</p>
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
    <div className="min-h-screen flex flex-col items-center justify-center p-6 gap-5 text-center">

      {/* Correct / Wrong / Recorded */}
      {isCompleteness ? (
        <p className="text-indigo-400 text-4xl font-black">Answer recorded!</p>
      ) : isCorrect ? (
        <p className="text-green-400 text-4xl font-black">Correct!</p>
      ) : isPartial ? (
        <p className="text-amber-400 text-4xl font-black">Partially correct</p>
      ) : (
        <p className="text-red-400 text-4xl font-black">Incorrect</p>
      )}

      {/* pin_the_spot: the player's pin (from this phone's submission) against the reveal */}
      {isPin && pinAspect !== null && (
        <div className="w-full max-w-md">
          <PinCanvas
            imageUrl={currentQuestion?.config.image_url}
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
        <p className="text-slate-400 text-base">
          You answered: <span className="text-slate-200 font-semibold">{answeredLabel}</span>
        </p>
      )}

      {/* Correct answer for FITB ACCURACY */}
      {isFitb && fitbAccepted.length > 0 && (
        <p className="text-slate-400 text-base">
          Correct: <span className="text-green-400 font-semibold">{fitbAccepted.join(' / ')}</span>
        </p>
      )}

      {/* Correct order for put_in_order (both grading types, whenever revealed) */}
      {correctOrderLabel && (
        <p className="text-slate-400 text-base">
          Correct order: <span className="text-green-400 font-semibold">{correctOrderLabel}</span>
        </p>
      )}

      {/* Points for this question */}
      <p className="text-slate-100 text-3xl font-bold">
        +{yourPoints.toLocaleString()} pts
      </p>

      {/* Running total and rank */}
      <div className="mt-2 space-y-1">
        <p className="text-slate-300 text-lg">
          Total: <span className="font-bold text-white">{yourScore.toLocaleString()}</span> pts
        </p>
        <p className="text-slate-400 text-base">
          Rank <span className="font-bold text-white">#{yourRank}</span> of {playerCount}
        </p>
      </div>

      <p className="text-slate-500 text-sm mt-4">Waiting for next question…</p>
    </div>
  );
}
