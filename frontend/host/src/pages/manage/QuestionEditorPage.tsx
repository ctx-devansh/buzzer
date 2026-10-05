import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, ChevronUp, ChevronDown, Download } from 'lucide-react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader } from '../../components/ui/card';
import { PinBoard } from '../../components/PinBoard';
import type { PinConfig, Point } from '../../lib/pinTheSpot';

type QuestionType =
  | 'multiple_choice' | 'true_false' | 'fill_in_the_blank' | 'multi_select' | 'put_in_order' | 'pin_the_spot';
type GradingType = 'ACCURACY' | 'COMPLETENESS';

interface Question {
  id: number;
  type: QuestionType;
  grading_type: GradingType;
  prompt: string;
  config: Record<string, unknown>;
  answer_data: Record<string, unknown>;
  time_limit_seconds: number;
  points_value: number;
  order_index: number;
}

interface Game { id: number; title: string; course_id: number | null; course_name: string | null }

// ---- helpers for building config/answer_data per type ----

interface McOption { text: string; points: number }

function buildMcPayload(options: McOption[], _grading: GradingType) {
  return {
    config: { options: options.map((o) => o.text) },
    answer_data: { answer_points: options.map((o) => o.points) },
  };
}

function buildTfPayload(truePoints: number, falsePoints: number) {
  return {
    config: {},
    answer_data: { answer_points: { true: truePoints, false: falsePoints } },
  };
}

function buildMsPayload(options: McOption[]) {
  return {
    config: { options: options.map((o) => o.text) },
    answer_data: { answer_points: options.map((o) => o.points) },
  };
}

interface FibAnswer { text: string; points: number }

function buildFibPayload(answers: FibAnswer[], editDistance: number) {
  return {
    config: {},
    answer_data: {
      acceptedAnswers: answers.map((a) => a.text),
      answerPoints: answers.map((a) => a.points),
      editDistance,
    },
  };
}

// ---- put_in_order ----

const PIO_MIN_ITEMS = 3;
const PIO_MAX_ITEMS = 6;

/** The stored scramble as loaded, so an unchanged item list is resent verbatim. */
interface PioStored { items: string[]; correct_order?: number[] }

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

/** Pairs (i < j) of the display order that already sit in the correct relative order. */
function concordantPairs(correctOrder: number[]): number {
  // correctOrder[p] = display index of the item that belongs at position p, so display
  // order i < j is concordant when the item at i belongs earlier than the item at j.
  const rank: number[] = [];
  correctOrder.forEach((displayIdx, p) => { rank[displayIdx] = p; });
  let c = 0;
  for (let i = 0; i < rank.length; i++) {
    for (let j = i + 1; j < rank.length; j++) if (rank[i] < rank[j]) c++;
  }
  return c;
}

/**
 * Scramble items typed in the correct order. Reshuffles (Fisher–Yates) until at most
 * floor(t/2) pairs are concordant, so locking in without moving anything earns at most
 * about half. Returns the display order and correct_order (display indices in correct order).
 */
function scramblePio(correctItems: string[]): { items: string[]; correct_order: number[] } {
  const n = correctItems.length;
  const maxConcordant = Math.floor((n * (n - 1)) / 2 / 2);
  for (;;) {
    const perm = correctItems.map((_, i) => i); // perm[displayIdx] = correct position
    for (let i = n - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [perm[i], perm[j]] = [perm[j], perm[i]];
    }
    const correct_order: number[] = [];
    perm.forEach((pos, displayIdx) => { correct_order[pos] = displayIdx; });
    if (concordantPairs(correct_order) <= maxConcordant) {
      return { items: perm.map((pos) => correctItems[pos]), correct_order };
    }
  }
}

/**
 * The scramble is fixed for a question's lifetime (past answers index into config.items),
 * so only an edited item list is reshuffled:
 *   1. stored correct_order and the same (trimmed) items → resend both verbatim, unless
 *      switching to ACCURACY with an identity order (the server would reject it) → case 3;
 *   2. stored without correct_order (imported COMPLETENESS) and the same items → resend
 *      the items, still without correct_order;
 *   3. otherwise → fresh scramble of the trimmed items.
 */
function buildPioPayload(pioItems: string[], pioStored: PioStored | null, gradingType: GradingType) {
  const trimmed = pioItems.map((s) => s.trim());
  if (pioStored?.correct_order) {
    const { items, correct_order } = pioStored;
    const storedCorrect = correct_order.map((i) => (items[i] ?? '').trim());
    const isIdentity = correct_order.every((v, i) => v === i);
    if (sameList(trimmed, storedCorrect) && !(gradingType === 'ACCURACY' && isIdentity)) {
      return { config: { items }, answer_data: { correct_order } };
    }
  } else if (pioStored && sameList(trimmed, pioStored.items.map((s) => s.trim()))) {
    return { config: { items: pioStored.items }, answer_data: {} };
  }
  const { items, correct_order } = scramblePio(trimmed);
  return { config: { items }, answer_data: { correct_order } };
}

/** Client-side mirror of the server's commonest put_in_order 422s (same texts). */
function pioItemsError(pioItems: string[]): string | null {
  const trimmed = pioItems.map((s) => s.trim());
  if (trimmed.some((s) => !s)) return 'Every item needs text';
  if (new Set(trimmed.map((s) => s.toLowerCase())).size !== trimmed.length) return 'Items must be different';
  return null;
}

// ---- pin_the_spot ----

/** Longest side of an uploaded image after downscaling (docs/design-pin-the-spot.md §2). */
const PIN_MAX_SIDE = 1280;
/** Aim well under the server's 1,500,000-character image_url cap. */
const PIN_TARGET_URL_LEN = 700_000;
const PIN_MAX_URL_LEN = 1_500_000;
const PIN_DEFAULT_R_FULL = 0.05;
const PIN_DEFAULT_R_ZERO = 0.2;

function loadImg(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not load that image'));
    img.src = src;
  });
}

/** Downscale a local file and re-encode it as a JPEG data: URL (white behind transparency). */
async function fileToPinImage(file: File): Promise<PinConfig> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const img = await loadImg(objectUrl);
    const scale = Math.min(1, PIN_MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    const width = Math.max(1, Math.round(img.naturalWidth * scale));
    const height = Math.max(1, Math.round(img.naturalHeight * scale));
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas is not available in this browser');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(img, 0, 0, width, height);
    let quality = 0.85;
    let url = canvas.toDataURL('image/jpeg', quality);
    while (url.length > PIN_TARGET_URL_LEN && quality > 0.4) {
      quality -= 0.15;
      url = canvas.toDataURL('image/jpeg', quality);
    }
    if (url.length > PIN_MAX_URL_LEN) throw new Error('That image is too large, even after compression');
    return { image_url: url, image_width: width, image_height: height };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/** An http(s) image URL is kept as-is; only its size is measured. */
async function urlToPinImage(url: string): Promise<PinConfig> {
  if (!/^https?:\/\//i.test(url)) throw new Error('Image URL must start with http:// or https://');
  const img = await loadImg(url);
  return { image_url: url, image_width: img.naturalWidth, image_height: img.naturalHeight };
}

function pinDiagonal(width: number, height: number): number {
  return width > 0 ? Math.hypot(1, height / width) : Math.SQRT2;
}

function buildPinPayload(form: FormState) {
  return {
    config: { image_url: form.pinImageUrl, image_width: form.pinImageWidth, image_height: form.pinImageHeight },
    // COMPLETENESS may have no target (an opinion question); ACCURACY always has one.
    answer_data: form.pinTarget
      ? { target: form.pinTarget, r_full: form.pinRFull, r_zero: form.pinRZero }
      : {},
  };
}

/** Client-side mirror of the server's commonest pin_the_spot 422s. */
function pinError(form: FormState): string | null {
  if (!form.pinImageUrl) return 'Choose an image';
  if (form.grading === 'ACCURACY' && !form.pinTarget) return 'Click the image to place the target';
  if (form.pinTarget && !(0 < form.pinRFull && form.pinRFull < form.pinRZero)) {
    return 'The full-credit circle must be smaller than the zero-credit circle';
  }
  return null;
}

// ---- QuestionForm subcomponent ----

interface FormState {
  type: QuestionType;
  grading: GradingType;
  prompt: string;
  timeLimitSeconds: number;
  pointsValue: number;
  // multiple_choice
  mcOptions: McOption[];
  // true_false
  tfTruePoints: number;
  tfFalsePoints: number;
  // fill_in_the_blank
  fibAnswers: FibAnswer[];
  fibEditDistance: number;
  // multi_select
  msOptions: McOption[];
  // put_in_order: items in the CORRECT order; pioStored is the loaded scramble (null if new)
  pioItems: string[];
  pioStored: PioStored | null;
  // pin_the_spot: the image (config) and, when set, the target and radii (answer_data)
  pinImageUrl: string;
  pinImageWidth: number;
  pinImageHeight: number;
  pinTarget: Point | null;
  pinRFull: number;
  pinRZero: number;
}

const defaultForm = (): FormState => ({
  type: 'multiple_choice',
  grading: 'ACCURACY',
  prompt: '',
  timeLimitSeconds: 30,
  pointsValue: 1,
  mcOptions: [{ text: '', points: 1 }, { text: '', points: 0 }],
  tfTruePoints: 1,
  tfFalsePoints: 0,
  fibAnswers: [{ text: '', points: 1 }],
  fibEditDistance: 0,
  msOptions: [{ text: '', points: 1 }, { text: '', points: 1 }],
  pioItems: ['', '', ''],
  pioStored: null,
  pinImageUrl: '',
  pinImageWidth: 0,
  pinImageHeight: 0,
  pinTarget: null,
  pinRFull: PIN_DEFAULT_R_FULL,
  pinRZero: PIN_DEFAULT_R_ZERO,
});

function questionToForm(q: Question): FormState {
  const base: FormState = {
    ...defaultForm(),
    type: q.type,
    grading: q.grading_type,
    prompt: q.prompt,
    timeLimitSeconds: q.time_limit_seconds,
    pointsValue: q.points_value,
  };
  if (q.type === 'multiple_choice') {
    const opts = (q.config['options'] as string[]) ?? [];
    const pts = (q.answer_data['answer_points'] as number[]) ?? [];
    base.mcOptions = opts.map((text, i) => ({ text, points: pts[i] ?? 0 }));
  } else if (q.type === 'true_false') {
    const ap = q.answer_data['answer_points'] as { true: number; false: number } | undefined;
    base.tfTruePoints = ap?.true ?? 1;
    base.tfFalsePoints = ap?.false ?? 0;
  } else if (q.type === 'fill_in_the_blank') {
    const accepted = (q.answer_data['acceptedAnswers'] as string[]) ?? [];
    const pts = (q.answer_data['answerPoints'] as number[]) ?? [];
    base.fibAnswers = accepted.length
      ? accepted.map((text, i) => ({ text, points: pts[i] ?? 1 }))
      : [{ text: '', points: 1 }];
    base.fibEditDistance = (q.answer_data['editDistance'] as number) ?? 0;
  } else if (q.type === 'multi_select') {
    const opts = (q.config['options'] as string[]) ?? [];
    const pts = (q.answer_data['answer_points'] as number[]) ?? [];
    base.msOptions = opts.length
      ? opts.map((text, i) => ({ text, points: pts[i] ?? 1 }))
      : [{ text: '', points: 1 }, { text: '', points: 1 }];
  } else if (q.type === 'put_in_order') {
    const items = (q.config['items'] as string[]) ?? [];
    const co = q.answer_data['correct_order'];
    const correctOrder = Array.isArray(co) ? (co as number[]) : undefined;
    // Without a correct_order (imported COMPLETENESS only) the display order is all we have.
    base.pioItems = correctOrder ? correctOrder.map((i) => items[i] ?? '') : [...items];
    base.pioStored = correctOrder ? { items, correct_order: correctOrder } : { items };
  } else if (q.type === 'pin_the_spot') {
    base.pinImageUrl = (q.config['image_url'] as string) ?? '';
    base.pinImageWidth = (q.config['image_width'] as number) ?? 0;
    base.pinImageHeight = (q.config['image_height'] as number) ?? 0;
    const target = q.answer_data['target'] as Point | undefined;
    base.pinTarget = target ?? null;
    base.pinRFull = (q.answer_data['r_full'] as number) ?? PIN_DEFAULT_R_FULL;
    base.pinRZero = (q.answer_data['r_zero'] as number) ?? PIN_DEFAULT_R_ZERO;
  }
  return base;
}

function formToPayload(form: FormState) {
  let config: Record<string, unknown> = {};
  let answer_data: Record<string, unknown> = {};
  if (form.type === 'multiple_choice') {
    const p = buildMcPayload(form.mcOptions, form.grading);
    config = p.config;
    answer_data = p.answer_data;
  } else if (form.type === 'true_false') {
    const p = buildTfPayload(form.tfTruePoints, form.tfFalsePoints);
    config = p.config;
    answer_data = p.answer_data;
  } else if (form.type === 'multi_select') {
    const p = buildMsPayload(form.msOptions.filter((o) => o.text.trim()));
    config = p.config;
    answer_data = p.answer_data;
  } else if (form.type === 'put_in_order') {
    const p = buildPioPayload(form.pioItems, form.pioStored, form.grading);
    config = p.config;
    answer_data = p.answer_data;
  } else if (form.type === 'pin_the_spot') {
    const p = buildPinPayload(form);
    config = p.config;
    answer_data = p.answer_data;
  } else {
    const p = buildFibPayload(form.fibAnswers.filter((a) => a.text.trim()), form.fibEditDistance);
    config = p.config;
    answer_data = p.answer_data;
  }
  // put_in_order's and pin_the_spot's points_value is authored directly under both grading types.
  const points_value =
    form.grading === 'COMPLETENESS' || form.type === 'put_in_order' || form.type === 'pin_the_spot'
      ? form.pointsValue
      : form.type === 'multiple_choice'
      ? Math.max(0, ...form.mcOptions.map((o) => o.points))
      : form.type === 'true_false'
      ? Math.max(form.tfTruePoints, form.tfFalsePoints)
      : form.type === 'multi_select'
      ? form.msOptions.reduce((sum, o) => sum + (o.points > 0 ? o.points : 0), 0)
      : Math.max(0, ...form.fibAnswers.map((a) => a.points));
  return {
    type: form.type,
    grading_type: form.grading,
    prompt: form.prompt,
    config,
    answer_data,
    time_limit_seconds: form.timeLimitSeconds,
    points_value,
  };
}

function QuestionForm({
  initial,
  onSave,
  onCancel,
  saving,
}: {
  initial: FormState;
  onSave: (payload: ReturnType<typeof formToPayload>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<FormState>(initial);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const pioError = form.type === 'put_in_order' ? pioItemsError(form.pioItems) : null;
  const pinFormError = form.type === 'pin_the_spot' ? pinError(form) : null;
  const [pinUrlInput, setPinUrlInput] = useState('');
  const [pinLoading, setPinLoading] = useState(false);
  const [pinLoadError, setPinLoadError] = useState<string | null>(null);

  async function choosePinImage(load: () => Promise<PinConfig>) {
    setPinLoading(true);
    setPinLoadError(null);
    try {
      const image = await load();
      setForm((prev) => ({
        ...prev,
        pinImageUrl: image.image_url,
        pinImageWidth: image.image_width,
        pinImageHeight: image.image_height,
        // Keep the radii valid for the new image's diagonal.
        pinRZero: Math.min(prev.pinRZero, pinDiagonal(image.image_width, image.image_height)),
      }));
    } catch (err) {
      setPinLoadError(err instanceof Error ? err.message : 'Could not load that image');
    } finally {
      setPinLoading(false);
    }
  }

  function setPinRadius(which: 'full' | 'zero', value: number) {
    setForm((prev) => {
      // Keep 0 < full < zero by nudging the other slider.
      if (which === 'full') {
        return { ...prev, pinRFull: value, pinRZero: Math.max(prev.pinRZero, value + 0.01) };
      }
      return { ...prev, pinRZero: value, pinRFull: Math.min(prev.pinRFull, Math.max(0.005, value - 0.01)) };
    });
  }

  function movePioItem(i: number, direction: -1 | 1) {
    const target = i + direction;
    if (target < 0 || target >= form.pioItems.length) return;
    const items = [...form.pioItems];
    [items[i], items[target]] = [items[target], items[i]];
    set('pioItems', items);
  }

  return (
    <div className="space-y-4">
      {/* Type + grading */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="block text-xs text-slate-400 mb-1">Question type</label>
          <select
            className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100 text-sm"
            value={form.type}
            onChange={(e) => set('type', e.target.value as QuestionType)}
          >
            <option value="multiple_choice">Multiple Choice</option>
            <option value="true_false">True / False</option>
            <option value="fill_in_the_blank">Fill in the Blank</option>
            <option value="multi_select">Multi-Select (Select All That Apply)</option>
            <option value="put_in_order">Put in Order</option>
            <option value="pin_the_spot">Pin the Spot</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs text-slate-400 mb-1">Grading</label>
          <select
            className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100 text-sm"
            value={form.grading}
            onChange={(e) => set('grading', e.target.value as GradingType)}
          >
            <option value="ACCURACY">Accuracy</option>
            <option value="COMPLETENESS">Completeness</option>
          </select>
        </div>
      </div>

      {/* Prompt */}
      <div>
        <label className="block text-xs text-slate-400 mb-1">Prompt</label>
        <textarea
          className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none text-sm"
          rows={3}
          placeholder="Question text…"
          value={form.prompt}
          onChange={(e) => set('prompt', e.target.value)}
          required
        />
      </div>

      {/* Type-specific */}
      {form.type === 'multiple_choice' && (
        <div>
          <label className="block text-xs text-slate-400 mb-2">Options</label>
          {form.grading === 'ACCURACY' && (
            <div className="flex gap-2 mb-1 px-0.5">
              <span className="flex-1 text-xs text-slate-500">Answer text</span>
              <span className="w-24 text-xs text-slate-500">Points</span>
              {form.mcOptions.length > 2 && <span className="w-7" />}
            </div>
          )}
          <div className="space-y-2">
            {form.mcOptions.map((opt, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input
                  placeholder={`Option ${i + 1}`}
                  value={opt.text}
                  onChange={(e) => {
                    const opts = [...form.mcOptions];
                    opts[i] = { ...opts[i], text: e.target.value };
                    set('mcOptions', opts);
                  }}
                  className="flex-1 text-sm"
                />
                {form.grading === 'ACCURACY' && (
                  <Input
                    type="number"
                    placeholder="pts"
                    value={opt.points}
                    onChange={(e) => {
                      const opts = [...form.mcOptions];
                      opts[i] = { ...opts[i], points: Number(e.target.value) };
                      set('mcOptions', opts);
                    }}
                    className="w-24 text-sm"
                    min="0"
                    step="any"
                  />
                )}
                {form.mcOptions.length > 2 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => set('mcOptions', form.mcOptions.filter((_, j) => j !== i))}
                  >
                    <Trash2 size={12} />
                  </Button>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => set('mcOptions', [...form.mcOptions, { text: '', points: 0 }])}
            >
              <Plus size={12} className="mr-1" /> Add option
            </Button>
          </div>
        </div>
      )}

      {form.type === 'multi_select' && (
        <div>
          <label className="block text-xs text-slate-400 mb-2">Options</label>
          {form.grading === 'ACCURACY' && (
            <div className="flex gap-2 mb-1 px-0.5">
              <span className="flex-1 text-xs text-slate-500">Answer text</span>
              <span className="w-24 text-xs text-slate-500">Points (neg = penalty)</span>
              {form.msOptions.length > 2 && <span className="w-7" />}
            </div>
          )}
          <div className="space-y-2">
            {form.msOptions.map((opt, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input
                  placeholder={`Option ${i + 1}`}
                  value={opt.text}
                  onChange={(e) => {
                    const opts = [...form.msOptions];
                    opts[i] = { ...opts[i], text: e.target.value };
                    set('msOptions', opts);
                  }}
                  className="flex-1 text-sm"
                />
                {form.grading === 'ACCURACY' && (
                  <Input
                    type="number"
                    placeholder="pts"
                    value={opt.points}
                    onChange={(e) => {
                      const opts = [...form.msOptions];
                      opts[i] = { ...opts[i], points: Number(e.target.value) };
                      set('msOptions', opts);
                    }}
                    className="w-24 text-sm"
                    step="any"
                  />
                )}
                {form.msOptions.length > 2 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => set('msOptions', form.msOptions.filter((_, j) => j !== i))}
                  >
                    <Trash2 size={12} />
                  </Button>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => set('msOptions', [...form.msOptions, { text: '', points: 1 }])}
            >
              <Plus size={12} className="mr-1" /> Add option
            </Button>
          </div>
          {form.grading === 'ACCURACY' && (
            <p className="text-slate-500 text-xs mt-1">
              Correct options: positive pts. Distractors: negative pts (penalty). Score = sum of selected, capped at 0.
            </p>
          )}
        </div>
      )}

      {form.type === 'put_in_order' && (
        <div>
          <label className="block text-xs text-slate-400 mb-2">
            Items, in the correct order (players see them scrambled)
          </label>
          <div className="space-y-2">
            {form.pioItems.map((item, i) => (
              <div key={i} className="flex gap-2 items-center">
                <span className="w-5 text-right text-xs text-slate-500 font-mono">{i + 1}.</span>
                <Input
                  data-testid={`pio-item-${i}`}
                  placeholder={`Item ${i + 1}`}
                  value={item}
                  maxLength={200}
                  onChange={(e) => {
                    const items = [...form.pioItems];
                    items[i] = e.target.value;
                    set('pioItems', items);
                  }}
                  className="flex-1 text-sm"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid={`pio-up-${i}`}
                  disabled={i === 0}
                  onClick={() => movePioItem(i, -1)}
                >
                  <ChevronUp size={12} />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid={`pio-down-${i}`}
                  disabled={i === form.pioItems.length - 1}
                  onClick={() => movePioItem(i, 1)}
                >
                  <ChevronDown size={12} />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid={`pio-remove-row-${i}`}
                  disabled={form.pioItems.length <= PIO_MIN_ITEMS}
                  onClick={() => set('pioItems', form.pioItems.filter((_, j) => j !== i))}
                >
                  <Trash2 size={12} />
                </Button>
              </div>
            ))}
            {form.pioItems.length < PIO_MAX_ITEMS && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                data-testid="pio-add-row"
                onClick={() => set('pioItems', [...form.pioItems, ''])}
              >
                <Plus size={12} className="mr-1" /> Add item
              </Button>
            )}
          </div>
          {pioError && <p className="text-red-400 text-xs mt-2">{pioError}</p>}
        </div>
      )}

      {form.type === 'pin_the_spot' && (() => {
        const hasImage = !!form.pinImageUrl && form.pinImageWidth > 0;
        const diagonal = pinDiagonal(form.pinImageWidth, form.pinImageHeight);
        return (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-slate-400 mb-2">Image</label>
              <div className="flex flex-wrap gap-2 items-center">
                <label className="inline-flex items-center rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 cursor-pointer">
                  {hasImage ? 'Replace with a file…' : 'Choose a file…'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    data-testid="pin-file"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = '';
                      if (file) void choosePinImage(() => fileToPinImage(file));
                    }}
                  />
                </label>
                <span className="text-slate-500 text-xs">or</span>
                <Input
                  placeholder="https://… image URL"
                  value={pinUrlInput}
                  onChange={(e) => setPinUrlInput(e.target.value)}
                  className="flex-1 min-w-48 text-sm"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!pinUrlInput.trim() || pinLoading}
                  onClick={() => void choosePinImage(() => urlToPinImage(pinUrlInput.trim()))}
                >
                  Use URL
                </Button>
              </div>
              {pinLoading && <p className="text-slate-400 text-xs mt-1">Loading image…</p>}
              {pinLoadError && <p className="text-red-400 text-xs mt-1">{pinLoadError}</p>}
              {hasImage && (
                <p className="text-slate-500 text-xs mt-1">
                  {form.pinImageWidth} × {form.pinImageHeight} px
                  {form.pinImageUrl.startsWith('data:') && ` · ${Math.round(form.pinImageUrl.length / 1024)} KB stored with the question`}
                </p>
              )}
            </div>

            {hasImage && (
              <>
                <div>
                  <label className="block text-xs text-slate-400 mb-2">
                    {form.pinTarget ? 'Target (click or drag to move it)' : 'Click the image to place the target'}
                  </label>
                  <PinBoard
                    config={{ image_url: form.pinImageUrl, image_width: form.pinImageWidth, image_height: form.pinImageHeight }}
                    reveal={form.pinTarget ? { target: form.pinTarget, rFull: form.pinRFull, rZero: form.pinRZero } : null}
                    onPick={(p) => set('pinTarget', p)}
                    maxHeight={420}
                    ariaLabel="Question image; click to place the target"
                    testId="pin-editor-board"
                  />
                </div>
                {form.pinTarget && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block text-xs text-slate-400">
                      Full-credit radius: {Math.round(form.pinRFull * 100)}% of the image width
                      <input
                        type="range"
                        min={0.005}
                        max={0.5}
                        step={0.005}
                        value={form.pinRFull}
                        onChange={(e) => setPinRadius('full', Number(e.target.value))}
                        className="w-full accent-green-500"
                        data-testid="pin-r-full"
                      />
                    </label>
                    <label className="block text-xs text-slate-400">
                      Zero-credit radius: {Math.round(form.pinRZero * 100)}% of the image width
                      <input
                        type="range"
                        min={0.02}
                        max={Math.floor(diagonal * 100) / 100}
                        step={0.01}
                        value={form.pinRZero}
                        onChange={(e) => setPinRadius('zero', Number(e.target.value))}
                        className="w-full accent-amber-500"
                        data-testid="pin-r-zero"
                      />
                    </label>
                    <p className="text-slate-500 text-xs sm:col-span-2">
                      Full points inside the green circle, nothing outside the dashed one, and a
                      straight-line share in between.
                    </p>
                    {form.grading === 'COMPLETENESS' && (
                      <div className="sm:col-span-2">
                        <Button type="button" variant="ghost" size="sm" onClick={() => set('pinTarget', null)}>
                          Remove target (an opinion question with no right spot)
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
            {pinFormError && hasImage && <p className="text-red-400 text-xs">{pinFormError}</p>}
          </div>
        );
      })()}

      {form.type === 'true_false' && form.grading === 'ACCURACY' && (
        <div>
          <label className="block text-xs text-slate-400 mb-2">Points per answer</label>
          <div className="flex gap-4">
            <div>
              <span className="text-slate-300 text-sm">True:</span>
              <Input
                type="number"
                value={form.tfTruePoints}
                onChange={(e) => set('tfTruePoints', Number(e.target.value))}
                className="w-28 mt-1 text-sm"
                min="0"
                step="any"
              />
            </div>
            <div>
              <span className="text-slate-300 text-sm">False:</span>
              <Input
                type="number"
                value={form.tfFalsePoints}
                onChange={(e) => set('tfFalsePoints', Number(e.target.value))}
                className="w-28 mt-1 text-sm"
                min="0"
                step="any"
              />
            </div>
          </div>
        </div>
      )}

      {form.type === 'fill_in_the_blank' && form.grading === 'ACCURACY' && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-2">Accepted answers</label>
            <div className="flex gap-2 mb-1 px-0.5">
              <span className="flex-1 text-xs text-slate-500">Answer text</span>
              <span className="w-24 text-xs text-slate-500">Points</span>
              {form.fibAnswers.length > 1 && <span className="w-7" />}
            </div>
            <div className="space-y-2">
              {form.fibAnswers.map((ans, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <Input
                    placeholder={`Answer ${i + 1}`}
                    value={ans.text}
                    onChange={(e) => {
                      const answers = [...form.fibAnswers];
                      answers[i] = { ...answers[i], text: e.target.value };
                      set('fibAnswers', answers);
                    }}
                    className="flex-1 text-sm"
                  />
                  <Input
                    type="number"
                    placeholder="pts"
                    value={ans.points}
                    onChange={(e) => {
                      const answers = [...form.fibAnswers];
                      answers[i] = { ...answers[i], points: Number(e.target.value) };
                      set('fibAnswers', answers);
                    }}
                    className="w-24 text-sm"
                    min="0"
                    step="any"
                  />
                  {form.fibAnswers.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => set('fibAnswers', form.fibAnswers.filter((_, j) => j !== i))}
                    >
                      <Trash2 size={12} />
                    </Button>
                  )}
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => set('fibAnswers', [...form.fibAnswers, { text: '', points: 1 }])}
              >
                <Plus size={12} className="mr-1" /> Add answer
              </Button>
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Edit distance tolerance (fuzzy match)</label>
            <Input
              type="number"
              value={form.fibEditDistance}
              onChange={(e) => set('fibEditDistance', Number(e.target.value))}
              className="w-28 text-sm"
              min="0"
            />
          </div>
        </div>
      )}

      {/* Time + points */}
      <div className="flex gap-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Time limit (seconds)</label>
          <Input
            type="number"
            value={form.timeLimitSeconds}
            onChange={(e) => set('timeLimitSeconds', Number(e.target.value))}
            className="w-28 text-sm"
            min="2"
            max="300"
          />
        </div>
        {(form.grading === 'COMPLETENESS' || form.type === 'put_in_order' || form.type === 'pin_the_spot') && (
          <div>
            <label className="block text-xs text-slate-400 mb-1">Points value</label>
            <Input
              type="number"
              value={form.pointsValue}
              onChange={(e) => set('pointsValue', Number(e.target.value))}
              className="w-28 text-sm"
              min="0"
              max="100000"
              step="any"
            />
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <Button type="button" onClick={() => onSave(formToPayload(form))} disabled={saving || pioError !== null || pinFormError !== null}>
          {saving ? 'Saving\u2026' : 'Save Question'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

// ---- Main page ----

export default function QuestionEditorPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const [game, setGame] = useState<Game | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  // Separate from `loading`: a failed initial load (e.g. 403) must not render the editor.
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function load() {
    try {
      const [g, qs] = await Promise.all([
        api.get<Game>(`/host/games/${gameId}`),
        api.get<Question[]>(`/host/games/${gameId}/questions`),
      ]);
      setGame(g);
      setQuestions(qs);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [gameId]);

  async function addQuestion(payload: ReturnType<typeof formToPayload>) {
    setSaving(true);
    setError('');
    try {
      await api.post(`/host/games/${gameId}/questions`, payload);
      setShowAddForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save question');
    } finally {
      setSaving(false);
    }
  }

  async function updateQuestion(id: number, payload: ReturnType<typeof formToPayload>) {
    setSaving(true);
    setError('');
    try {
      await api.put(`/host/games/${gameId}/questions/${id}`, payload);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update question');
    } finally {
      setSaving(false);
    }
  }

  async function deleteQuestion(id: number) {
    if (!confirm('Delete this question?')) return;
    try {
      await api.delete(`/host/games/${gameId}/questions/${id}`);
      setQuestions((prev) => prev.filter((q) => q.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete question');
    }
  }

  async function moveQuestion(index: number, direction: -1 | 1) {
    const newOrder = [...questions];
    const target = index + direction;
    if (target < 0 || target >= newOrder.length) return;
    [newOrder[index], newOrder[target]] = [newOrder[target], newOrder[index]];
    try {
      await api.post(`/host/games/${gameId}/questions/reorder`, {
        order: newOrder.map((q) => q.id),
      });
      setQuestions(newOrder);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reorder');
    }
  }

  async function handleExport() {
    setDownloading(true);
    setError('');
    try {
      await api.download(`/host/games/${gameId}/export`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setDownloading(false);
    }
  }

  const typeLabel: Record<QuestionType, string> = {
    multiple_choice: 'MC',
    true_false: 'T/F',
    fill_in_the_blank: 'Fill',
    multi_select: 'Multi',
    put_in_order: 'Order',
    pin_the_spot: 'Pin',
  };

  if (loading) return <div className="p-8 text-slate-400">Loading…</div>;

  const backLink = (
    <button
      onClick={() => navigate('/games')}
      className="flex items-center gap-2 text-slate-400 hover:text-slate-100 text-sm mb-2"
    >
      <ArrowLeft size={14} /> Back to Games
    </button>
  );

  if (!loaded) {
    return (
      <div className="p-8 max-w-4xl mx-auto space-y-4">
        {backLink}
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          {backLink}
          <h2 className="text-2xl font-bold text-slate-100">{game?.title}</h2>
          <p className="text-indigo-300 text-sm mt-0.5">
            {game?.course_name ?? 'Unattached (admin only)'}
          </p>
          <p className="text-slate-400 text-sm mt-0.5">{questions.length} question{questions.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleExport()}
            disabled={downloading}
          >
            <Download size={14} className="mr-1" />
            {downloading ? 'Exporting\u2026' : 'Export JSON'}
          </Button>
          <Button size="sm" onClick={() => { setShowAddForm(true); setEditingId(null); }}>
            <Plus size={14} className="mr-1" /> Add Question
          </Button>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Add question form */}
      {showAddForm && (
        <Card>
          <CardHeader><h3 className="font-semibold text-slate-100">New Question</h3></CardHeader>
          <CardContent>
            <QuestionForm
              initial={defaultForm()}
              onSave={(payload) => void addQuestion(payload)}
              onCancel={() => setShowAddForm(false)}
              saving={saving}
            />
          </CardContent>
        </Card>
      )}

      {/* Question list */}
      {questions.length === 0 && !showAddForm && (
        <p className="text-slate-400">No questions yet. Add one above.</p>
      )}

      <div className="space-y-4">
        {questions.map((q, i) => (
          <Card key={q.id}>
            {editingId === q.id ? (
              <>
                <CardHeader>
                  <h3 className="font-semibold text-slate-100">Edit Question {i + 1}</h3>
                </CardHeader>
                <CardContent>
                  <QuestionForm
                    initial={questionToForm(q)}
                    onSave={(payload) => void updateQuestion(q.id, payload)}
                    onCancel={() => setEditingId(null)}
                    saving={saving}
                  />
                </CardContent>
              </>
            ) : (
              <div className="flex items-start gap-4 px-6 py-4">
                {/* Reorder buttons */}
                <div className="flex flex-col gap-1 mt-1">
                  <button
                    onClick={() => void moveQuestion(i, -1)}
                    disabled={i === 0}
                    className="text-slate-500 hover:text-slate-200 disabled:opacity-20"
                  >
                    <ChevronUp size={16} />
                  </button>
                  <button
                    onClick={() => void moveQuestion(i, 1)}
                    disabled={i === questions.length - 1}
                    className="text-slate-500 hover:text-slate-200 disabled:opacity-20"
                  >
                    <ChevronDown size={16} />
                  </button>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-slate-500 text-xs font-mono">Q{i + 1}</span>
                    <span className="px-1.5 py-0.5 rounded text-xs bg-slate-700 text-slate-300">
                      {typeLabel[q.type]}
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-xs bg-slate-700 text-slate-300">
                      {q.grading_type}
                    </span>
                    <span className="text-slate-500 text-xs">{q.time_limit_seconds}s · {q.points_value}pts</span>
                  </div>
                  <p className="text-slate-100 text-sm leading-relaxed">{q.prompt}</p>

                  {q.type === 'multiple_choice' && (
                    <div className="mt-2 space-y-1">
                      {((q.config['options'] as string[]) ?? []).map((opt, oi) => {
                        const pts = ((q.answer_data['answer_points'] as number[]) ?? [])[oi] ?? 0;
                        return (
                          <div key={oi} className="flex items-center gap-2 text-xs">
                            <span className={pts > 0 ? 'text-green-400' : 'text-slate-500'}>
                              {pts > 0 ? '\u2713' : '\u25cb'}
                            </span>
                            <span className={pts > 0 ? 'text-slate-200' : 'text-slate-400'}>{opt}</span>
                            {pts > 0 && <span className="text-slate-500">({pts}pts)</span>}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {q.type === 'true_false' && (
                    <div className="mt-2 flex gap-4 text-xs">
                      {(['true', 'false'] as const).map((k) => {
                        const pts = (q.answer_data['answer_points'] as Record<string, number>)?.[k] ?? 0;
                        return (
                          <span key={k} className={pts > 0 ? 'text-green-400' : 'text-slate-500'}>
                            {k.charAt(0).toUpperCase() + k.slice(1)}: {pts}pts
                          </span>
                        );
                      })}
                    </div>
                  )}

                  {q.type === 'fill_in_the_blank' && (
                    <div className="mt-2 text-xs text-slate-400">
                      Accepted: {((q.answer_data['acceptedAnswers'] as string[]) ?? []).join(', ')}
                      {(q.answer_data['editDistance'] as number) > 0 && (
                        <span className="ml-2 text-slate-500">(±{q.answer_data['editDistance'] as number} edit distance)</span>
                      )}
                    </div>
                  )}

                  {q.type === 'put_in_order' && (() => {
                    const items = (q.config['items'] as string[]) ?? [];
                    const co = q.answer_data['correct_order'];
                    const ordered = Array.isArray(co) ? (co as number[]).map((i) => items[i]) : null;
                    return (
                      <div className="mt-2 text-xs text-slate-400">
                        {ordered ? 'Correct order: ' : 'Items: '}
                        <span className="text-slate-200">{(ordered ?? items).join(' \u2192 ')}</span>
                      </div>
                    );
                  })()}

                  {q.type === 'pin_the_spot' && typeof q.config['image_url'] === 'string' && (() => {
                    const target = q.answer_data['target'] as Point | undefined;
                    const rFull = q.answer_data['r_full'] as number | undefined;
                    const rZero = q.answer_data['r_zero'] as number | undefined;
                    return (
                      <div className="mt-2 flex items-start gap-3 text-xs text-slate-400">
                        <div className="w-40 shrink-0">
                          <PinBoard
                            config={q.config as unknown as PinConfig}
                            reveal={target && rFull !== undefined && rZero !== undefined ? { target, rFull, rZero } : null}
                            maxHeight={110}
                            ariaLabel="Question image and target"
                          />
                        </div>
                        <span>
                          {target
                            ? `Target (${Math.round(target.x * 100)}%, ${Math.round(target.y * 100)}%) · full credit within ${Math.round((rFull ?? 0) * 100)}%, none beyond ${Math.round((rZero ?? 0) * 100)}% of the width`
                            : 'No target: any tap earns the points'}
                        </span>
                      </div>
                    );
                  })()}

                  {q.type === 'multi_select' && (
                    <div className="mt-2 space-y-1">
                      {((q.config['options'] as string[]) ?? []).map((opt, oi) => {
                        const pts = ((q.answer_data['answer_points'] as number[]) ?? [])[oi] ?? 0;
                        const isCorrect = pts > 0;
                        return (
                          <div key={oi} className="flex items-center gap-2 text-xs">
                            <span className={isCorrect ? 'text-green-400' : pts < 0 ? 'text-red-400' : 'text-slate-500'}>
                              {isCorrect ? '\u2713' : pts < 0 ? '\u2212' : '\u25cb'}
                            </span>
                            <span className={isCorrect ? 'text-slate-200' : 'text-slate-400'}>{opt}</span>
                            {pts !== 0 && <span className="text-slate-500">({pts > 0 ? '+' : ''}{pts}pts)</span>}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="flex gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setEditingId(q.id); setShowAddForm(false); }}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void deleteQuestion(q.id)}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
