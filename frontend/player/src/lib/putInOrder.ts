/** Helpers for the put_in_order question type (indices always point into config.items). */

/** True if `value` is a list of integers forming a permutation of 0..n-1. */
export function isPermutation(value: unknown, n: number): value is number[] {
  if (!Array.isArray(value) || value.length !== n) return false;
  const seen = new Set<number>();
  for (const x of value) {
    if (typeof x !== 'number' || !Number.isInteger(x) || x < 0 || x >= n || seen.has(x)) return false;
    seen.add(x);
  }
  return true;
}

/** "A → B → C" for a list of item indices, or null if it isn't a valid order for `items`. */
export function orderText(indices: unknown, items: string[] | undefined): string | null {
  if (!items || !isPermutation(indices, items.length)) return null;
  return indices.map(i => items[i]).join(' → ');
}
