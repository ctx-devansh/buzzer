import type { AnswerReveal } from '../types/game';

/**
 * Shared put_in_order helpers for the live results chart (ResultsPage) and the game-over
 * card (GameOverPage), so the two can't drift apart. All indices point into config.items.
 */

export const PIO_CAPTION_ACCURACY = 'Players who placed each item correctly';
export const PIO_CAPTION_COMPLETENESS = 'Players who placed each item at this position';

export interface PioBar {
  label: string;
  count: number;
  correct: boolean | null;
  testId: string;
}

function isPermutation(value: unknown, n: number): value is number[] {
  if (!Array.isArray(value) || value.length !== n) return false;
  const seen = new Set<number>();
  for (const x of value) {
    if (typeof x !== 'number' || !Number.isInteger(x) || x < 0 || x >= n || seen.has(x)) return false;
    seen.add(x);
  }
  return true;
}

function revealCorrectOrder(reveal: AnswerReveal, items: string[] | undefined): number[] | null {
  if (!items || !('correctOrder' in reveal)) return null;
  return isPermutation(reveal.correctOrder, items.length) ? reveal.correctOrder : null;
}

/**
 * One bar per position p (in correct order): how many players put the item that belongs
 * at p exactly there (distribution key `${item}@${p}`). ACCURACY reveals (type
 * 'put_in_order') colour the bars as correct; a completeness reveal is neutral. No
 * correctOrder → no bars.
 */
export function buildPioBars(
  reveal: AnswerReveal,
  distribution: Record<string, number>,
  items: string[] | undefined,
): PioBar[] {
  const order = revealCorrectOrder(reveal, items);
  if (!order || !items) return [];
  const correct = reveal.type === 'put_in_order' ? true : null;
  return order.map((item, p) => ({
    label: `${p + 1}. ${items[item]}`,
    count: distribution[`${item}@${p}`] ?? 0,
    correct,
    testId: `pio-bar-${p}`,
  }));
}

/** Caption shown above the put_in_order bars. */
export function pioCaption(reveal: AnswerReveal): string {
  return reveal.type === 'put_in_order' ? PIO_CAPTION_ACCURACY : PIO_CAPTION_COMPLETENESS;
}

/** "A → B → C" from the reveal's correctOrder, or null when there is none. */
export function correctOrderText(reveal: AnswerReveal, items: string[] | undefined): string | null {
  const order = revealCorrectOrder(reveal, items);
  if (!order || !items) return null;
  return order.map(i => items[i]).join(' → ');
}
