import { useEffect } from 'react';
import { useGame } from './GameLayout';
import { Button } from '../../components/ui/button';
import { TimerBar } from '../../components/ui/TimerBar';
import { PinBoard } from '../../components/PinBoard';
import { aspectOf, pinImageSrc } from '../../lib/pinTheSpot';
import { imageUrl, plainText } from '../../lib/images';

export default function QuestionPage() {
  const { currentQuestion, answeredCount, playerCount, allAnswered, answerPhaseEnded, questionLocked, lockedTimerSeconds, autoAdvance, emitAdvance, emitLockQuestion } = useGame();

  useEffect(() => {
    if (!autoAdvance || !answerPhaseEnded) return;
    const id = setTimeout(emitAdvance, 1500);
    return () => clearTimeout(id);
  }, [autoAdvance, answerPhaseEnded, emitAdvance]);

  if (!currentQuestion) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-ink-muted">Loading question…</p>
      </div>
    );
  }

  const typeLabel: Record<string, string> = {
    multiple_choice: 'Multiple Choice',
    true_false: 'True / False',
    fill_in_the_blank: 'Fill in the Blank',
    multi_select: 'Multi-Select',
    put_in_order: 'Put in Order',
    pin_the_spot: 'Pin the Spot',
  };

  function editDistanceLabel(d: number): string {
    if (d === 0) return 'Exact spelling required';
    if (d === 1) return 'Up to 1 typo allowed';
    return `Up to ${d} typos allowed`;
  }

  const remainingSeconds = questionLocked && lockedTimerSeconds !== null
    ? lockedTimerSeconds
    : currentQuestion.startedAt
      ? Math.max(0, currentQuestion.timeLimitSeconds - (Date.now() - new Date(currentQuestion.startedAt).getTime()) / 1000)
      : currentQuestion.timeLimitSeconds;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 gap-8">
      <div className="nb-caption flex flex-wrap items-center justify-center gap-3">
        <span className="text-ink-muted">
          Question {currentQuestion.questionNumber} of {currentQuestion.totalQuestions}
        </span>
        <span className="text-ink-muted">·</span>
        <span className="text-ink-muted">{typeLabel[currentQuestion.type] ?? currentQuestion.type}</span>
        <span className="text-ink-muted">·</span>
        <span className={`nb-chip ${currentQuestion.gradingType === 'COMPLETENESS' ? 'bg-warning' : 'bg-info'} text-on-fill`}>
          {currentQuestion.gradingType === 'COMPLETENESS' ? 'Participation' : 'Accuracy'}
        </span>
        {currentQuestion.type === 'fill_in_the_blank' && currentQuestion.gradingType === 'ACCURACY' && (
          <>
            <span className="text-ink-muted">·</span>
            <span className="text-ink-muted normal-case">
              {editDistanceLabel(currentQuestion.editDistance ?? 0)}
            </span>
          </>
        )}
      </div>

      <div className="w-full max-w-3xl">
        <TimerBar
          key={currentQuestion.questionId}
          totalSeconds={currentQuestion.timeLimitSeconds}
          initialSeconds={remainingSeconds}
          paused={questionLocked}
        />
      </div>

      {!questionLocked && (
        <>
          {/* Inter, not the display face: prompts are running text (§4.1). */}
          <h2 className="nb-prompt text-ink text-center max-w-4xl">
            {currentQuestion.prompt}
          </h2>
          {/* The prompt image: on this screen only, never on phones; hidden while locked. */}
          {currentQuestion.promptImageId && (
            <img
              src={imageUrl(currentQuestion.promptImageId)}
              alt={plainText(currentQuestion.prompt)}
              className="max-h-[45vh] max-w-full border-4 border-line bg-image-bg object-contain"
              data-testid="prompt-image"
              // A deleted image (the accepted delete race) hides rather than showing a
              // broken-image icon on the projector; the prompt text stands alone.
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          )}
          {/* Scrambled display order, lettered (not numbered) so it doesn't read as positions */}
          {currentQuestion.type === 'put_in_order' && (
            <ul className="w-full max-w-2xl flex flex-col gap-3">
              {(currentQuestion.config.items ?? []).map((item, i) => (
                <li
                  key={i}
                  className="nb-box nb-body flex items-center gap-4 px-5 py-3 text-ink"
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-line bg-accent font-display font-bold text-on-fill">
                    {String.fromCharCode(65 + i)}
                  </span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {/* The image stays while locked (only the prompt hides); no taps until the reveal. */}
      {currentQuestion.type === 'pin_the_spot' && (
        <div className="w-full max-w-4xl">
          {aspectOf(currentQuestion.config) === null ? (
            <p className="text-center text-ink-muted">Image failed to load</p>
          ) : (
            <PinBoard
              imageUrl={pinImageSrc(currentQuestion.config)}
              aspect={aspectOf(currentQuestion.config)!}
              ariaLabel={currentQuestion.prompt}
              maxHeight={window.innerHeight * 0.55}
              testId="pin-board-question"
            />
          )}
        </div>
      )}

      <div className="nb-body text-ink-muted">
        <span className="nb-stat text-ink">{answeredCount} / {playerCount}</span> answered
        {allAnswered && <span className="ml-3 text-success-text font-semibold">All answered!</span>}
        {questionLocked && <span className="ml-3 text-warning-text font-semibold">· Answers locked</span>}
      </div>

      <div className="flex gap-4">
        <Button
          size="lg"
          variant="outline"
          onClick={emitLockQuestion}
          className={`px-10 ${questionLocked ? 'bg-warning text-on-fill hover:bg-warning' : ''}`}
        >
          {questionLocked ? 'Unlock Question' : 'Lock Question'}
        </Button>
        <Button size="lg" onClick={emitAdvance} className="px-10">
          Show Results
        </Button>
      </div>
    </div>
  );
}
