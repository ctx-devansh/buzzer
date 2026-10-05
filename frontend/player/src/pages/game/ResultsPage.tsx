import { useGame } from './GameLayout';
import { orderText } from '../../lib/putInOrder';
import { PinCanvas } from '../../components/PinCanvas';
import type { PinConfig, PinTarget } from '../../lib/pinTheSpot';

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
  // put_in_order and pin_the_spot ACCURACY read the server's is_correct (perfect order /
  // inside the full-credit circle); other positive scores are "Partially correct".
  const isPioAccuracy =
    currentQuestion?.type === 'put_in_order' && answerReveal.type === 'put_in_order';
  const isPin = currentQuestion?.type === 'pin_the_spot';
  const isPinAccuracy = isPin && answerReveal.type === 'pin_the_spot';
  const usesServerFlag = isPioAccuracy || isPinAccuracy;
  const isCorrect = usesServerFlag ? yourIsCorrect : !isCompleteness && yourPoints > 0;
  const isPartial = usesServerFlag && !yourIsCorrect && yourPoints > 0;
  const pinReveal: PinTarget | null =
    isPin && 'target' in answerReveal && answerReveal.target
      ? { target: answerReveal.target, rFull: answerReveal.rFull!, rZero: answerReveal.rZero! }
      : null;
  const myPin =
    isPin && typeof lastAnswerData?.x === 'number' && typeof lastAnswerData?.y === 'number'
      ? { x: lastAnswerData.x, y: lastAnswerData.y }
      : null;
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

      {/* pin_the_spot: your pin over the target and circles */}
      {isPin && currentQuestion?.config.image_url && (myPin || pinReveal) && (
        <div className="w-full max-w-md">
          <PinCanvas
            config={currentQuestion.config as PinConfig}
            value={myPin}
            reveal={pinReveal}
            maxHeight={Math.round(window.innerHeight * 0.4)}
            ariaLabel={myPin ? 'Your pin and the target' : 'The target'}
          />
        </div>
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
