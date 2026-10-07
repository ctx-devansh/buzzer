import { useEffect, useMemo, useState } from 'react';
import { useGame } from './GameLayout';
import { Button } from '../../components/ui/button';
import type { AnswerReveal } from '../../types/game';
import { buildPioBars, correctOrderText, pioCaption } from '../../lib/putInOrder';
import { PinBoard } from '../../components/PinBoard';
import { aspectOf, pinImageSrc, revealKey } from '../../lib/pinTheSpot';
import { imageUrl } from '../../lib/images';
import { barClasses, CORRECT_CHIP } from '../../lib/answerBars';

const RESULTS_DISPLAY_SECONDS = 10;

function optionLabel(i: number): string {
  return String.fromCharCode(65 + i);
}

// ---------------------------------------------------------------------------
// Levenshtein distance — used to colour word-cloud entries for FITB questions
// ---------------------------------------------------------------------------

function levenshtein(a: string, b: string): number {
  const m = a.length, n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, (_, i) =>
    Array.from({ length: n + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1]
          : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }
  return dp[m][n];
}

// ---------------------------------------------------------------------------
// Word Cloud — for fill_in_the_blank questions
// ---------------------------------------------------------------------------

interface WordCloudProps {
  distribution: Record<string, number>;
  answerReveal: AnswerReveal;
  totalAnswered: number;
  totalPlayers: number;
}

function WordCloud({ distribution, answerReveal, totalAnswered, totalPlayers }: WordCloudProps) {
  const entries = Object.entries(distribution).sort(([, a], [, b]) => b - a);
  const maxCount = Math.max(...entries.map(([, c]) => c), 1);

  const isAccuracy =
    'type' in answerReveal && answerReveal.type === 'fill_in_the_blank';
  const acceptedAnswers: string[] =
    isAccuracy && 'acceptedAnswers' in answerReveal
      ? (answerReveal as { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }).acceptedAnswers.map(a => a.toLowerCase())
      : [];
  const editDistance: number =
    isAccuracy && 'editDistance' in answerReveal
      ? (answerReveal as { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }).editDistance
      : 0;

  function sizeClass(count: number): string {
    const f = count / maxCount;
    if (f > 0.75) return 'text-5xl font-bold';
    if (f > 0.5)  return 'text-4xl font-bold';
    if (f > 0.25) return 'text-3xl font-semibold';
    if (f > 0.1)  return 'text-2xl font-medium';
    return 'text-xl';
  }

  function isCorrectWord(word: string): boolean {
    if (!isAccuracy || acceptedAnswers.length === 0) return false;
    return acceptedAnswers.some(a => levenshtein(word.toLowerCase(), a) <= editDistance);
  }

  return (
    <div className="w-full max-w-3xl flex flex-col gap-4">
      {isAccuracy && acceptedAnswers.length > 0 && (
        <p className="nb-body text-center text-ink-muted">
          Correct answer:{' '}
          <span className="text-success-text font-semibold">
            {(answerReveal as { acceptedAnswers: string[] }).acceptedAnswers.join(' / ')}
            {editDistance > 0 && (
              <span className="text-ink-muted font-normal text-sm ml-1">(±{editDistance})</span>
            )}
          </span>
        </p>
      )}

      <div className="nb-box flex flex-wrap gap-x-5 gap-y-3 justify-center items-center min-h-32 p-4">
        {entries.map(([word, count]) => (
          <span
            key={word}
            title={`${count} player${count !== 1 ? 's' : ''}`}
            className={`${sizeClass(count)} ${
              isCorrectWord(word) ? 'text-success-text font-bold underline decoration-2 underline-offset-4' : 'text-ink-muted'
            }`}
          >
            {/* Colour is never the only cue (WCAG 1.4.1): correct words also get a check and an underline. */}
            {isCorrectWord(word) && (
              <>
                <span aria-hidden="true">✓ </span>
                <span className="sr-only">correct: </span>
              </>
            )}
            {word}
          </span>
        ))}
        {entries.length === 0 && (
          <p className="text-ink-muted text-sm">No answers submitted</p>
        )}
      </div>

      <p className="nb-caption text-right">
        {totalAnswered} / {totalPlayers} answered
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bar Chart — for multiple_choice and true_false
// ---------------------------------------------------------------------------

interface BarChartProps {
  bars: { label: string; count: number; correct: boolean | null; testId?: string; imageId?: string | null }[];
  totalAnswered: number;
  totalPlayers: number;
}

function AnswerBarChart({ bars, totalAnswered, totalPlayers }: BarChartProps) {
  const maxCount = Math.max(...bars.map(b => b.count), 1);

  return (
    <div className="w-full max-w-2xl space-y-3">
      {bars.map((bar, i) => {
        const pct = Math.round((bar.count / maxCount) * 100);
        const { bar: barClass, label: barLabel } = barClasses(bar.correct);

        return (
          <div key={i} className="flex items-center gap-3" data-testid={bar.testId}>
            {bar.imageId && (
              <img
                src={imageUrl(bar.imageId)}
                alt=""
                className="h-12 w-16 shrink-0 border-2 border-line bg-image-bg object-contain"
                data-testid="bar-thumb"
              />
            )}
            <span className="font-display font-bold text-2xl text-ink w-10 text-right shrink-0">
              {bar.label}
            </span>
            <div className="flex-1 h-12">
              <div
                className={`h-full flex items-center justify-end pr-3 transition-all duration-500 ${barClass}`}
                style={{ width: `${Math.max(pct, bar.count > 0 ? 4 : 0)}%` }}
              >
                {bar.count > 0 && (
                  <span
                    className={`font-display font-bold text-lg tabular-nums ${barLabel}`}
                    data-testid={bar.testId ? `${bar.testId}-count` : undefined}
                  >
                    {bar.count}
                  </span>
                )}
              </div>
            </div>
            {bar.correct === true && (
              <span className={`${CORRECT_CHIP} shrink-0`}>✓ Correct</span>
            )}
            {bar.count === 0 && (bar.correct !== true || bar.testId) && (
              <span
                className="text-ink-muted font-display font-bold text-lg shrink-0"
                data-testid={bar.testId ? `${bar.testId}-count` : undefined}
              >
                0
              </span>
            )}
          </div>
        );
      })}

      <p className="nb-caption text-right pt-1">
        {totalAnswered} / {totalPlayers} answered
      </p>
    </div>
  );
}

function buildBars(
  reveal: AnswerReveal,
  distribution: Record<string, number>,
  options: string[] | undefined,
  imageIds: (string | null)[] | undefined,
): BarChartProps['bars'] {
  if (reveal.type === 'multiple_choice') {
    const opts = options ?? [];
    return opts.map((opt, i) => ({
      label: `${optionLabel(i)}  ${opt}`,
      count: distribution[String(i)] ?? 0,
      correct: reveal.correctIndices.includes(i),
      imageId: imageIds?.[i] ?? null,
    }));
  }

  if (reveal.type === 'multi_select') {
    const opts = options ?? [];
    return opts.map((opt, i) => ({
      label: `${optionLabel(i)}  ${opt}`,
      count: distribution[String(i)] ?? 0,
      correct: (reveal.answerPoints[i] ?? 0) > 0,
      imageId: imageIds?.[i] ?? null,
    }));
  }

  if (reveal.type === 'true_false') {
    return [
      { label: 'True', count: distribution['true'] ?? 0, correct: reveal.correctValue === true },
      { label: 'False', count: distribution['false'] ?? 0, correct: reveal.correctValue === false },
    ];
  }

  // completeness (non-FITB) — no right/wrong
  if (options && options.length > 0) {
    return options.map((opt, i) => ({
      label: `${optionLabel(i)}  ${opt}`,
      count: distribution[String(i)] ?? 0,
      correct: null,
      imageId: imageIds?.[i] ?? null,
    }));
  }

  if ('true' in distribution || 'false' in distribution) {
    return [
      { label: 'True', count: distribution['true'] ?? 0, correct: null },
      { label: 'False', count: distribution['false'] ?? 0, correct: null },
    ];
  }

  return [];
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ResultsPage() {
  const { questionResults, currentQuestion, autoAdvance, emitAdvance } = useGame();
  const [countdown, setCountdown] = useState(RESULTS_DISPLAY_SECONDS);

  const isLast = currentQuestion
    ? currentQuestion.questionNumber >= currentQuestion.totalQuestions
    : false;

  useEffect(() => {
    if (!autoAdvance) return;
    setCountdown(RESULTS_DISPLAY_SECONDS);
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { clearInterval(interval); emitAdvance(); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [autoAdvance, questionResults, emitAdvance]);

  const isFitb = currentQuestion?.type === 'fill_in_the_blank';
  // Branch on the question type, not reveal.type: a COMPLETENESS put_in_order reveal is
  // type 'completeness', and buildBars' completeness fallback reads config.options.
  const isPio = currentQuestion?.type === 'put_in_order';
  // pin_the_spot: every tap on the image, plus target and circles when revealed.
  const isPin = currentQuestion?.type === 'pin_the_spot';
  const pinAspect = isPin ? aspectOf(currentQuestion?.config) : null;
  const pinKey = useMemo(
    () => revealKey(questionResults?.answerReveal),
    [questionResults?.answerReveal],
  );

  const bars = !questionResults || isPin
    ? []
    : isPio
      ? buildPioBars(
          questionResults.answerReveal,
          questionResults.answerDistribution,
          currentQuestion?.config?.items,
        )
      : !isFitb
        ? buildBars(
            questionResults.answerReveal,
            questionResults.answerDistribution,
            currentQuestion?.config?.options,
            currentQuestion?.config?.option_image_ids,
          )
        : [];
  const pioOrderText =
    isPio && questionResults
      ? correctOrderText(questionResults.answerReveal, currentQuestion?.config?.items)
      : null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 gap-8">
      <h1 className="nb-h1 text-ink">
        Question {currentQuestion?.questionNumber} Results
      </h1>

      {currentQuestion && (
        <p className="nb-body text-ink-muted text-center max-w-3xl">
          {currentQuestion.prompt}
        </p>
      )}

      {questionResults && isPio && bars.length > 0 && (
        <p className="nb-caption -mb-4">{pioCaption(questionResults.answerReveal)}</p>
      )}

      {questionResults && isPin ? (
        <div className="w-full max-w-4xl flex flex-col gap-2">
          {pinAspect === null ? (
            <p className="text-center text-ink-muted">Image failed to load</p>
          ) : (
            <PinBoard
              imageUrl={pinImageSrc(currentQuestion?.config)}
              aspect={pinAspect}
              taps={questionResults.answerDistribution}
              pinKey={pinKey}
              ariaLabel={`${currentQuestion?.prompt ?? 'Pin the Spot'}: every answer`}
              maxHeight={window.innerHeight * 0.6}
              testId="pin-board-results"
            />
          )}
          <p className="nb-caption text-right">
            {questionResults.totalAnswered} / {questionResults.totalPlayers} answered
          </p>
        </div>
      ) : questionResults && isFitb ? (
        <WordCloud
          distribution={questionResults.answerDistribution}
          answerReveal={questionResults.answerReveal}
          totalAnswered={questionResults.totalAnswered}
          totalPlayers={questionResults.totalPlayers}
        />
      ) : questionResults ? (
        <AnswerBarChart
          bars={bars}
          totalAnswered={questionResults.totalAnswered}
          totalPlayers={questionResults.totalPlayers}
        />
      ) : null}

      {pioOrderText && (
        <p className="nb-body text-ink-muted">
          Correct order: <span className="text-success-text font-semibold">{pioOrderText}</span>
        </p>
      )}

      <div className="flex flex-col items-center gap-2">
        <Button size="lg" onClick={emitAdvance} className="px-10">
          {isLast ? 'Show Final Results' : 'Next Question'}
        </Button>
        {autoAdvance && (
          <p className="text-ink-muted text-sm tabular-nums">
            Auto-advancing in {countdown}s
          </p>
        )}
      </div>
    </div>
  );
}
