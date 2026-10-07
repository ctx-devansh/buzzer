/**
 * The one answer-bar encoding shared by ResultsPage and GameOverPage (docs/design-better-ui.md §4.8).
 *
 * - correct (`true`): success fill and a thick outline; call sites add the "✓ Correct" chip, so colour
 *   is never the only cue;
 * - wrong (`false`): muted, not red, so the correct answer is the only thing that stands out;
 * - no key (`null`: polls, put-in-order distributions): accent.
 *
 * The widths are fixed rather than --nb-border on purpose: these bars only render at projector
 * density, and the correct bar must stay thicker than the others to work as a non-colour cue.
 * `label` is the text class for anything drawn *on* the bar; text beside a bar uses ink/ink-muted.
 */
export function barClasses(correct: boolean | null): { bar: string; label: string } {
  if (correct === true) return { bar: 'bg-success border-4 border-line', label: 'text-on-fill' };
  if (correct === false) return { bar: 'bg-surface-muted border-2 border-line', label: 'text-ink' };
  return { bar: 'bg-accent border-2 border-line', label: 'text-on-fill' };
}

/** Bars of the game-over score histogram (§4.8). */
export const HISTOGRAM_BAR = 'bg-accent border-2 border-line';

/** The non-colour cue next to a correct bar. */
export const CORRECT_CHIP = 'nb-chip bg-success text-on-fill';
