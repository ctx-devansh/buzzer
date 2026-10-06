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
        <p className="text-slate-400">Loading question…</p>
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
      <div className="flex items-center gap-3 text-sm uppercase tracking-wider">
        <span className="text-slate-400">
          Question {currentQuestion.questionNumber} of {currentQuestion.totalQuestions}
        </span>
        <span className="text-slate-600">·</span>
        <span className="text-slate-400">{typeLabel[currentQuestion.type] ?? currentQuestion.type}</span>
        <span className="text-slate-600">·</span>
        <span className={currentQuestion.gradingType === 'COMPLETENESS' ? 'text-amber-400' : 'text-indigo-400'}>
          {currentQuestion.gradingType === 'COMPLETENESS' ? 'Participation' : 'Accuracy'}
        </span>
        {currentQuestion.type === 'fill_in_the_blank' && currentQuestion.gradingType === 'ACCURACY' && (
          <>
            <span className="text-slate-600">·</span>
            <span className="text-slate-400 normal-case">
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
          <h2 className="text-4xl font-bold text-slate-100 text-center max-w-3xl leading-tight">
            {currentQuestion.prompt}
          </h2>
          {/* The prompt image: on this screen only, never on phones; hidden while locked. */}
          {currentQuestion.promptImageId && (
            <img
              src={imageUrl(currentQuestion.promptImageId)}
              alt={plainText(currentQuestion.prompt)}
              className="max-h-[45vh] max-w-full rounded-xl object-contain"
              data-testid="prompt-image"
            />
          )}
          {/* Scrambled display order, lettered (not numbered) so it doesn't read as positions */}
          {currentQuestion.type === 'put_in_order' && (
            <ul className="w-full max-w-2xl flex flex-col gap-3">
              {(currentQuestion.config.items ?? []).map((item, i) => (
                <li
                  key={i}
                  className="flex items-center gap-4 rounded-2xl bg-slate-800 border border-slate-700 px-5 py-3 text-2xl text-slate-100"
                >
                  <span className="font-black text-indigo-400 w-8 shrink-0">{String.fromCharCode(65 + i)}</span>
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
            <p className="text-center text-slate-400">Image failed to load</p>
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

      <div className="text-slate-300 text-xl">
        {answeredCount} / {playerCount} answered
        {allAnswered && <span className="ml-3 text-green-400 font-semibold">All answered!</span>}
        {questionLocked && <span className="ml-3 text-amber-400 font-semibold">· Answers locked</span>}
      </div>

      <div className="flex gap-4">
        <Button
          size="lg"
          variant="outline"
          onClick={emitLockQuestion}
          className={`px-10 ${questionLocked ? 'border-amber-500 text-amber-400 hover:bg-amber-500/10' : ''}`}
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
