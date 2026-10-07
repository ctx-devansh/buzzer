import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, FileText } from 'lucide-react';
import { useGame } from './GameLayout';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import type { AnswerReveal, HostQuestionSummaryItem } from '../../types/game';
import { buildPioBars, correctOrderText, pioCaption } from '../../lib/putInOrder';
import { PinBoard } from '../../components/PinBoard';
import { aspectOf, pinImageSrc, revealKey } from '../../lib/pinTheSpot';
import { imageUrl } from '../../lib/images';
import { barClasses, CORRECT_CHIP, HISTOGRAM_BAR } from '../../lib/answerBars';

const TARGET_BUCKETS = 8;

interface Bucket {
  label: string;
  count: number;
  rangeStart: number;
  rangeEnd: number;
}

function chooseWidth(ceiling: number): number {
  const N = ceiling + 1;
  let bestW = 1;
  let bestDiff = Infinity;
  for (let w = 1; w * w <= N; w++) {
    if (N % w !== 0) continue;
    for (const cand of [w, N / w]) {
      const numBins = N / cand;
      if (numBins < 2) continue;
      const diff = Math.abs(numBins - TARGET_BUCKETS);
      if (diff < bestDiff) { bestDiff = diff; bestW = cand; }
    }
  }
  if (bestDiff > TARGET_BUCKETS) bestW = Math.max(1, Math.ceil(N / TARGET_BUCKETS));
  return bestW;
}

function buildBuckets(scores: number[], maxPossibleScore: number): Bucket[] {
  const ceiling = Math.max(maxPossibleScore, 1);
  const width = chooseWidth(ceiling);
  const numBuckets = Math.ceil((ceiling + 1) / width);
  const buckets: Bucket[] = Array.from({ length: numBuckets }, (_, i) => {
    const start = i * width;
    const end = Math.min(start + width - 1, ceiling);
    const label = start === end ? `${start}` : `${start}–${end}`;
    return { label, count: 0, rangeStart: start, rangeEnd: end };
  });
  for (const score of scores) {
    const idx = Math.min(Math.floor(score / width), numBuckets - 1);
    buckets[idx].count++;
  }
  return buckets;
}

// ---------------------------------------------------------------------------
// Per-question summary card
// ---------------------------------------------------------------------------

function optionLabel(i: number) { return String.fromCharCode(65 + i); }

/** One answer bar, in the same encoding as ResultsPage (lib/answerBars.ts, docs/design-better-ui.md §4.8). */
function AnswerBar({ label, count, total, correct, testId }: {
  label: string; count: number; total: number; correct: boolean | null; testId?: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3" data-testid={testId}>
      <span className="w-8 text-center font-display font-bold text-lg text-ink shrink-0">
        {label}
      </span>
      <div className="flex-1 h-8">
        <div
          className={`h-full transition-all duration-500 ${count > 0 ? barClasses(correct).bar : ''}`}
          style={{ width: `${Math.max(pct, count > 0 ? 2 : 0)}%` }}
        />
      </div>
      <span
        className="w-10 text-right font-display font-bold text-lg tabular-nums text-ink shrink-0"
        data-testid={testId ? `${testId}-count` : undefined}
      >
        {count}
      </span>
      {correct === true ? <span className={`${CORRECT_CHIP} shrink-0`}>✓ Correct</span> : <span className="w-28 shrink-0" />}
    </div>
  );
}

function QuestionCard({ item, index }: { item: HostQuestionSummaryItem; index: number }) {
  const { type, gradingType, prompt, config, answerReveal, answerDistribution, totalAnswered, totalPlayers, correctCount, avgAnswerTimeMs, pointsValue } = item;

  const typeLabel: Record<string, string> = {
    multiple_choice: 'Multiple Choice',
    true_false: 'True / False',
    fill_in_the_blank: 'Fill in the Blank',
    multi_select: 'Multi-Select',
    put_in_order: 'Put in Order',
    pin_the_spot: 'Pin the Spot',
  };

  const answeredPct = totalPlayers > 0 ? Math.round((totalAnswered / totalPlayers) * 100) : 0;
  const correctPct = totalAnswered > 0 ? Math.round((correctCount / totalAnswered) * 100) : 0;

  const reveal = answerReveal as AnswerReveal;
  // put_in_order is decided by question type before any reveal.type check: a COMPLETENESS
  // put_in_order reveal is type 'completeness'.
  const isPio = type === 'put_in_order';
  const pioBars = isPio ? buildPioBars(reveal, answerDistribution, config.items) : [];
  const pioOrderText = isPio ? correctOrderText(reveal, config.items) : null;

  function isCorrectIndex(i: number): boolean {
    if (reveal.type === 'multiple_choice') {
      return (reveal as { type: 'multiple_choice'; correctIndices: number[] }).correctIndices.includes(i);
    }
    if (reveal.type === 'multi_select') {
      return ((reveal as { type: 'multi_select'; answerPoints: number[] }).answerPoints[i] ?? 0) > 0;
    }
    return false;
  }
  function isCorrectTF(val: 'true' | 'false'): boolean {
    if (reveal.type !== 'true_false') return false;
    const rv = reveal as { type: 'true_false'; correctValue: boolean };
    return val === 'true' ? rv.correctValue : !rv.correctValue;
  }

  return (
    <div className="nb-card w-full">
      <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-ink-muted text-xs uppercase tracking-widest font-semibold">
            Q{index + 1}
          </span>
          <span className="text-ink-muted">·</span>
          <span className="text-ink-muted text-xs uppercase tracking-widest">
            {typeLabel[type] ?? type}
          </span>
          <span className="text-ink-muted">·</span>
          <span className={`nb-chip ${gradingType === 'COMPLETENESS' ? 'bg-warning' : 'bg-info'} text-on-fill`}>
            {gradingType === 'COMPLETENESS' ? 'Participation' : 'Accuracy'}
          </span>
          <span className="text-ink-muted">·</span>
          <span className="text-ink-muted text-xs">{pointsValue.toLocaleString()} {pointsValue === 1 ? 'pt' : 'pts'}</span>
        </div>
        <div className="text-right text-xs text-ink-muted shrink-0">
          <span className="text-ink-muted font-semibold">{totalAnswered}</span>/{totalPlayers} answered
          {avgAnswerTimeMs !== null && (
            <span className="ml-2 text-ink-muted">· avg {(avgAnswerTimeMs / 1000).toFixed(1)}s</span>
          )}
        </div>
      </div>

      {/* Prompt */}
      <h3 className="nb-h3 text-ink">{prompt}</h3>

      {/* Distribution */}
      <div className="space-y-2">
        {type === 'pin_the_spot' && aspectOf(config) !== null && (
          <PinBoard
            imageUrl={pinImageSrc(config)}
            aspect={aspectOf(config)!}
            taps={answerDistribution}
            pinKey={revealKey(reveal)}
            ariaLabel={`${prompt}: every answer`}
            maxHeight={420}
            testId="pin-board-gameover"
          />
        )}
        {isPio && pioBars.length > 0 && (
          <p className="text-ink-muted text-sm">{pioCaption(reveal)}</p>
        )}
        {isPio && pioBars.map((bar, p) => (
          <div key={p} className="space-y-0.5">
            <div className="text-sm text-ink-muted">{bar.label}</div>
            <AnswerBar
              label={String(p + 1)}
              count={bar.count}
              total={totalPlayers}
              correct={bar.correct}
              testId={bar.testId}
            />
          </div>
        ))}
        {pioOrderText && (
          <p className="text-ink-muted text-sm">
            Correct order: <span className="text-success-text font-medium">{pioOrderText}</span>
          </p>
        )}

        {(type === 'multiple_choice' || type === 'multi_select') && (config.options ?? []).map((opt, i) => {
          const count = answerDistribution[String(i)] ?? 0;
          const correct = isCorrectIndex(i);
          // From the summary's config: no separate field (design §4.5).
          const imageId = config.option_image_ids?.[i];
          return (
            <div key={i} className="space-y-0.5">
              <div className="flex items-center gap-2 text-xs text-ink-muted">
                {imageId && (
                  <img src={imageUrl(imageId)} alt="" className="h-12 w-16 border-2 border-line bg-image-bg object-contain" />
                )}
                <span className={`font-bold ${correct ? 'text-success-text' : 'text-ink'}`}>{optionLabel(i)}.</span>
                <span className={correct ? 'text-success-text font-semibold' : 'text-ink'}>{opt}</span>
              </div>
              <AnswerBar
                label={optionLabel(i)}
                count={count}
                total={totalPlayers}
                correct={correct}
              />
            </div>
          );
        })}

        {type === 'true_false' && (['true', 'false'] as const).map((val) => {
          const count = answerDistribution[val] ?? 0;
          const correct = isCorrectTF(val);
          return (
            <AnswerBar
              key={val}
              label={val === 'true' ? 'T' : 'F'}
              count={count}
              total={totalPlayers}
              correct={correct}
            />
          );
        })}

        {type === 'fill_in_the_blank' && (
          <div className="space-y-2">
            {reveal.type === 'fill_in_the_blank' && (
              <p className="text-ink-muted text-sm">
                Accepted:{' '}
                {(reveal as { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }).acceptedAnswers.map((a, i, arr) => (
                  <span key={i}>
                    <span className="text-success-text font-mono">"{a}"</span>
                    {i < arr.length - 1 && <span className="text-ink-muted">, </span>}
                  </span>
                ))}
                {(reveal as { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }).editDistance > 0 && (
                  <span className="text-ink-muted ml-1">
                    (±{(reveal as { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }).editDistance} typo)
                  </span>
                )}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Footer stats */}
      <div className="flex items-center gap-4 pt-3 border-t-2 border-line text-sm">
        {gradingType === 'ACCURACY' ? (
          <>
            <span className="text-success-text font-semibold">{correctCount} correct</span>
            <span className="text-ink-muted">·</span>
            <span className="text-ink-muted">{correctPct}% accuracy</span>
            <span className="text-ink-muted">·</span>
            <span className="text-ink-muted">{answeredPct}% responded</span>
          </>
        ) : (
          <>
            <span className="text-warning-text font-semibold">{totalAnswered} completed</span>
            <span className="text-ink-muted">·</span>
            <span className="text-ink-muted">{answeredPct}% response rate</span>
          </>
        )}
      </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function GameOverPage() {
  const { gameOver, sessionId } = useGame();
  const navigate = useNavigate();
  const [downloadError, setDownloadError] = useState('');
  const [downloading, setDownloading] = useState(false);

  // No COMPLETED gate: reaching this screen means the server emitted game_over. But
  // sessionId is null if GET /game/rooms/{code} failed or is still in flight, so the
  // buttons stay disabled rather than requesting /host/sessions/null/report.
  async function download(path: string) {
    setDownloading(true);
    setDownloadError('');
    try {
      await api.download(path);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  }

  if (!gameOver) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="nb-body text-ink-muted">Loading final results…</p>
      </div>
    );
  }

  const { scores, playerCount, maxPossibleScore, questionSummary = [] } = gameOver;
  const buckets = buildBuckets(scores, maxPossibleScore);
  const maxCount = Math.max(...buckets.map(b => b.count), 1);

  const avg = scores.length > 0
    ? scores.reduce((a, b) => a + b, 0) / scores.length
    : 0;
  const high = scores.length > 0 ? Math.max(...scores) : 0;

  return (
    <div className="min-h-screen flex flex-col items-center p-8 gap-8">
      <div className="text-center">
        <h1 className="nb-h1 text-ink">Game Over!</h1>
        <p className="nb-body text-ink-muted mt-2">{playerCount} players · Max possible: {maxPossibleScore.toLocaleString()} pts</p>
      </div>

      {/* Histogram */}
      <div className="w-full max-w-3xl">
        <h2 className="nb-caption text-center mb-4">Score Distribution</h2>
        <div className="flex items-end gap-2 h-48">
          {buckets.map((bucket, i) => {
            const heightPct = (bucket.count / maxCount) * 100;
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-ink font-display font-bold text-lg tabular-nums">
                  {bucket.count > 0 ? bucket.count : ''}
                </span>
                <div className="w-full border-b-2 border-line relative" style={{ height: '160px' }}>
                  <div
                    className={`absolute bottom-0 left-0 right-0 transition-all duration-700 ${HISTOGRAM_BAR}`}
                    style={{ height: `${Math.max(heightPct, bucket.count > 0 ? 4 : 0)}%` }}
                  />
                </div>
                <span className="text-ink-muted text-sm">{bucket.label}</span>
              </div>
            );
          })}
        </div>
        <p className="nb-caption text-center mt-2">Score (points) →</p>
      </div>

      {/* Summary stats */}
      <div className="flex gap-12 text-center">
        <div>
          <p className="nb-caption">Average</p>
          <p className="nb-stat text-ink">{avg.toLocaleString()}</p>
        </div>
        <div>
          <p className="nb-caption">High Score</p>
          <p className="nb-stat text-ink">{high.toLocaleString()}</p>
        </div>
        <div>
          <p className="nb-caption">Players</p>
          <p className="nb-stat text-ink">{playerCount}</p>
        </div>
      </div>

      <div className="flex flex-col items-center gap-2">
        <div className="flex gap-3 flex-wrap justify-center">
          <Button onClick={() => navigate('/home')}>New Game</Button>
          <Button
            variant="outline"
            disabled={!sessionId || downloading}
            onClick={() => void download(`/host/sessions/${sessionId}/report`)}
          >
            <FileText size={16} className="mr-1" /> Download summary (HTML)
          </Button>
          <Button
            variant="outline"
            disabled={!sessionId || downloading}
            onClick={() => void download(`/game/sessions/${sessionId}/export`)}
          >
            <Download size={16} className="mr-1" /> Download scores (CSV)
          </Button>
        </div>
        {downloadError && <p className="text-danger-text text-sm">{downloadError}</p>}
      </div>

      {/* Per-question breakdown */}
      {questionSummary.length > 0 && (
        <div className="w-full max-w-3xl space-y-4 pb-8">
          <h2 className="nb-caption text-center">
            Question Breakdown
          </h2>
          {questionSummary.map((item, i) => (
            <QuestionCard key={item.questionId} item={item} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
