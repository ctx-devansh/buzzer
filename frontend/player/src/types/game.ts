export interface SyncStatePayload {
  status: 'LOBBY' | 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
  playerCount: number;
  questionLocked?: boolean;
}

export interface PlayerJoinedPayload {
  playerCount: number;
}

export interface QuestionConfig {
  options?: string[];
  maxLength?: number;
  items?: string[];
  // pin_the_spot
  image_url?: string;
  image_width?: number;
  image_height?: number;
}

/** pin_the_spot reveal content: target and radii in image fractions / widths. */
export interface PinReveal {
  target: { x: number; y: number };
  rFull: number;
  rZero: number;
}

export interface QuestionPayload {
  questionId: number;
  questionNumber: number;
  totalQuestions: number;
  type: 'multiple_choice' | 'true_false' | 'fill_in_the_blank' | 'multi_select' | 'put_in_order' | 'pin_the_spot';
  prompt: string;
  config: QuestionConfig;
  timeLimitSeconds: number;
  pointsValue: number;
}

export interface AnswerResultPayload {
  questionId: number;
  isCorrect: boolean;
  pointsAwarded: number;
  totalScore: number;
  alreadyAnswered?: boolean;
}

export type PlayerAnswerReveal =
  | { type: 'multiple_choice'; correctIndices: number[] }
  | { type: 'true_false'; correctValue: boolean }
  | { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }
  | ({ type: 'completeness'; correctOrder?: number[] } & Partial<PinReveal>)
  | { type: 'multi_select'; answerPoints: number[] }
  | { type: 'put_in_order'; correctOrder: number[] }
  | ({ type: 'pin_the_spot' } & PinReveal);

export interface PlayerResultsPayload {
  questionId: number;
  answerReveal: PlayerAnswerReveal;
  yourPoints: number;
  yourIsCorrect: boolean;
  yourScore: number;
  yourRank: number;
  playerCount: number;
}

export interface QuestionSummaryItem {
  questionId: number;
  prompt: string;
  type: 'multiple_choice' | 'true_false' | 'fill_in_the_blank' | 'multi_select' | 'put_in_order' | 'pin_the_spot';
  gradingType: 'ACCURACY' | 'COMPLETENESS';
  config: QuestionConfig;
  pointsAwarded: number;
  maxPoints: number;
  answerTimeMs: number | null;
  playerAnswer: { selectedIndex?: number; selectedValue?: boolean; text?: string; selectedIndices?: number[]; orderedIndices?: number[]; x?: number; y?: number } | null;
  answerReveal: PlayerAnswerReveal;
  isCorrect: boolean;
}

export interface PlayerGameOverPayload {
  yourFinalScore: number;
  yourFinalRank: number;
  playerCount: number;
  questionSummary: QuestionSummaryItem[];
}

export type PlayerPhase = 'lobby' | 'question' | 'feedback' | 'results' | 'gameover';
