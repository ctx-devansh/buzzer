import { useNavigate } from 'react-router-dom';
import { useGame } from './GameLayout';
import { Button } from '../../components/ui/button';
import type { PlayerAnswerReveal, QuestionSummaryItem } from '../../types/game';
import { orderText } from '../../lib/putInOrder';
import { aspectOf, isTap, pinVerdict } from '../../lib/pinTheSpot';

function describePlayerAnswer(
  playerAnswer: QuestionSummaryItem['playerAnswer'],
  type: string,
  options: string[] | undefined,
  items: string[] | undefined,
): string {
  if (!playerAnswer) return 'No answer';
  if (type === 'multiple_choice') {
    const idx = playerAnswer.selectedIndex;
    if (typeof idx === 'number' && options && options[idx] !== undefined) {
      return `${String.fromCharCode(65 + idx)} — ${options[idx]}`;
    }
    return '?';
  }
  if (type === 'true_false') {
    return playerAnswer.selectedValue ? 'True' : 'False';
  }
  if (type === 'fill_in_the_blank') {
    return typeof playerAnswer.text === 'string' ? playerAnswer.text : '—';
  }
  if (type === 'multi_select') {
    const indices = playerAnswer.selectedIndices;
    if (!indices || indices.length === 0) return 'No selection';
    if (options) return indices.map(i => `${String.fromCharCode(65 + i)} — ${options[i]}`).join(', ');
    return indices.map(i => String.fromCharCode(65 + i)).join(', ');
  }
  if (type === 'put_in_order') {
    return orderText(playerAnswer.orderedIndices, items) ?? '—';
  }
  if (type === 'pin_the_spot') {
    return isTap(playerAnswer) ? 'Pin placed' : '—';
  }
  return '—';
}

function describeCorrectAnswer(
  answerReveal: PlayerAnswerReveal,
  options: string[] | undefined,
  items: string[] | undefined,
): string {
  if (answerReveal.type === 'multiple_choice') {
    const indices = answerReveal.correctIndices;
    if (options) {
      return indices.map(i => `${String.fromCharCode(65 + i)} — ${options[i]}`).join(', ');
    }
    return indices.map(i => String.fromCharCode(65 + i)).join(', ');
  }
  if (answerReveal.type === 'true_false') {
    return answerReveal.correctValue ? 'True' : 'False';
  }
  if (answerReveal.type === 'fill_in_the_blank') {
    const label = answerReveal.acceptedAnswers.join(' / ');
    return answerReveal.editDistance > 0 ? `${label} (±${answerReveal.editDistance})` : label;
  }
  if (answerReveal.type === 'multi_select') {
    const correct = answerReveal.answerPoints
      .map((p, i) => ({ p, i }))
      .filter(({ p }) => p > 0)
      .map(({ i }) => options ? `${String.fromCharCode(65 + i)} — ${options[i]}` : String.fromCharCode(65 + i));
    return correct.join(', ');
  }
  if (answerReveal.type === 'put_in_order') {
    return orderText(answerReveal.correctOrder, items) ?? '';
  }
  return '';
}

function QuestionRow({ item, index }: { item: QuestionSummaryItem; index: number }) {
  const options = item.config.options;
  const items = item.config.items;
  const isCompleteness = item.answerReveal.type === 'completeness';
  const noAnswer = !item.playerAnswer;
  // put_in_order ACCURACY: correctness is the stored is_correct (perfect order only).
  const isPioAccuracy = item.type === 'put_in_order' && item.answerReveal.type === 'put_in_order';
  // pin_the_spot ACCURACY: ✓ from the stored isCorrect, ◐ by the stored tap's distance (D9).
  const pinVerdictValue =
    item.type === 'pin_the_spot' && item.answerReveal.type === 'pin_the_spot' && !noAnswer
      ? pinVerdict(item.isCorrect, item.playerAnswer, item.answerReveal, aspectOf(item.config))
      : null;
  const isCorrect = pinVerdictValue
    ? pinVerdictValue === 'correct'
    : isPioAccuracy
      ? !noAnswer && item.isCorrect
      : !isCompleteness && !noAnswer && item.pointsAwarded > 0;
  const isPartial = pinVerdictValue
    ? pinVerdictValue === 'partial'
    : isPioAccuracy && !noAnswer && !item.isCorrect && item.pointsAwarded > 0;
  const showCorrectAnswer = !isCompleteness && !isCorrect;

  const playerAnswerLabel = describePlayerAnswer(item.playerAnswer, item.type, options, items);
  const correctAnswerLabel = !isCompleteness
    ? describeCorrectAnswer(item.answerReveal, options, items)
    : '';

  return (
    <div className="nb-card">
      <p className="nb-caption mb-1">Q{index + 1}</p>
      <p className="text-ink text-sm font-medium leading-snug mb-3">{item.prompt}</p>

      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-ink-muted text-xs mb-0.5">Your answer</p>
          <div className="flex items-center gap-2">
            {noAnswer ? (
              <span className="text-ink-muted text-base">—</span>
            ) : isCompleteness ? (
              <span className="text-ink text-base">●</span>
            ) : isCorrect ? (
              <span className="text-success-text text-base">✓</span>
            ) : isPartial ? (
              <span className="text-warning-text text-base">◐</span>
            ) : (
              <span className="text-danger-text text-base">✗</span>
            )}
            <span className={`text-sm font-semibold truncate ${
              noAnswer ? 'text-ink-muted' :
              isCompleteness ? 'text-ink' :
              isCorrect ? 'text-success-text' :
              isPartial ? 'text-warning-text' : 'text-danger-text'
            }`}>
              {playerAnswerLabel}
            </span>
          </div>

          {showCorrectAnswer && correctAnswerLabel && (
            <p className="text-ink-muted text-xs mt-1">
              Correct: <span className="text-success-text font-medium">{correctAnswerLabel}</span>
            </p>
          )}
        </div>

        <div className="text-right shrink-0">
          <p className={`text-sm font-bold ${
            item.pointsAwarded > 0 ? 'text-success-text' : 'text-ink-muted'
          }`}>
            +{item.pointsAwarded.toLocaleString()}
          </p>
          <p className="text-ink-muted text-xs">pts</p>
        </div>
      </div>
    </div>
  );
}

export default function GameOverPage() {
  const { gameOver } = useGame();
  const navigate = useNavigate();

  if (!gameOver) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <p className="text-ink-muted">Loading final results…</p>
      </div>
    );
  }

  const { yourFinalScore, yourFinalRank, playerCount, questionSummary } = gameOver;

  return (
    <div className="flex flex-1 flex-col p-4 gap-5">
      <div className="text-center pt-4 pb-2">
        <h1 className="nb-h1 text-ink">Game Over!</h1>
        <div className="mt-3 flex items-baseline justify-center gap-3">
          <span className="nb-hero text-ink">#{yourFinalRank}</span>
          <span className="text-ink-muted text-lg">of {playerCount}</span>
        </div>
        <p className="nb-stat text-ink mt-1">
          {yourFinalScore.toLocaleString()} pts
        </p>
      </div>

      <div className="flex flex-col gap-3 pb-4">
        <h2 className="nb-caption text-center">Question Recap</h2>
        {questionSummary.map((item, i) => (
          <QuestionRow key={item.questionId} item={item} index={i} />
        ))}
      </div>

      <div className="pb-6 flex justify-center">
        <Button
          variant="outline"
          onClick={() => {
            localStorage.removeItem('token');
            navigate('/join');
          }}
        >
          Play Again
        </Button>
      </div>
    </div>
  );
}
