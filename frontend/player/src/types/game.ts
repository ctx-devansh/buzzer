export interface SyncStatePayload {
  status: 'LOBBY' | 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
  playerCount: number;
  questionLocked?: boolean;
}

export interface PlayerJoinedPayload {
  playerCount: number;
}

export type QuestionType =
  | 'multiple_choice'
  | 'true_false'
  | 'fill_in_the_blank'
  | 'multi_select'
  | 'put_in_order'
  | 'pin_the_spot';

/** Per-type config. pin_the_spot: image_url is absent in the game-over summary. */
export interface QuestionConfig {
  options?: string[];
  maxLength?: number;
  items?: string[];
  image_url?: string;
  /** A course-library canvas (T8): exactly one of image_url and image_id is set. */
  image_id?: string;
  image_width?: number;
  image_height?: number;
  /** MC / multi-select option images (T8), one entry per option. */
  option_image_ids?: (string | null)[];
}

export interface PinPoint {
  x: number;
  y: number;
}

export interface QuestionPayload {
  questionId: number;
  questionNumber: number;
  totalQuestions: number;
  type: QuestionType;
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
  | { type: 'completeness'; correctOrder?: number[]; target?: PinPoint; rFull?: number; rZero?: number }
  | { type: 'multi_select'; answerPoints: number[] }
  | { type: 'put_in_order'; correctOrder: number[] }
  | { type: 'pin_the_spot'; target?: PinPoint; rFull?: number; rZero?: number };

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
  type: QuestionType;
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
