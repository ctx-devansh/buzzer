export interface PlayerInfo {
  userId: string;
  displayName: string;
}

export interface SyncStatePayload {
  status: 'LOBBY' | 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
  players: PlayerInfo[];
  playerCount: number;
  questionPhase?: 'QUESTION' | 'RESULTS' | null;
  currentQuestion?: QuestionPayload | null;
  questionLocked?: boolean;
  timerRemainingSeconds?: number | null;
}

export interface PlayerJoinedPayload {
  userId: string;
  displayName: string;
  playerCount: number;
}

export interface PlayerLeftPayload {
  userId: string;
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
  gradingType: 'ACCURACY' | 'COMPLETENESS';
  prompt: string;
  config: QuestionConfig;
  timeLimitSeconds: number;
  pointsValue: number;
  editDistance?: number;
  startedAt?: string;  // ISO timestamp — only present in sync_state reconnect payloads
}

export interface AnswerStatusPayload {
  userId: string;
  displayName: string;
  answered: boolean;
  answeredCount: number;
  totalPlayers: number;
}

export interface AnswerPhaseEndedPayload {
  questionId: number;
  answeredCount: number;
  totalPlayers: number;
  allAnswered?: boolean; // true only when every player answered (not just timer expiry)
}

export interface LeaderboardEntry {
  userId: string;
  displayName: string;
  score: number;
  rank: number;
}

export type AnswerReveal =
  | { type: 'multiple_choice'; correctIndices: number[] }
  | { type: 'true_false'; correctValue: boolean }
  | { type: 'fill_in_the_blank'; acceptedAnswers: string[]; editDistance: number }
  | ({ type: 'completeness'; correctOrder?: number[] } & Partial<PinReveal>)
  | { type: 'multi_select'; answerPoints: number[] }
  | { type: 'put_in_order'; correctOrder: number[] }
  | ({ type: 'pin_the_spot' } & PinReveal)
  | Record<string, never>;

export interface HostResultsPayload {
  questionId: number;
  answerReveal: AnswerReveal;
  answerDistribution: Record<string, number>;
  totalAnswered: number;
  totalPlayers: number;
}

export interface HostQuestionSummaryItem {
  questionId: number;
  questionNumber: number;
  prompt: string;
  type: 'multiple_choice' | 'true_false' | 'fill_in_the_blank' | 'multi_select' | 'put_in_order' | 'pin_the_spot';
  gradingType: 'ACCURACY' | 'COMPLETENESS';
  config: QuestionConfig;
  pointsValue: number;
  answerReveal: AnswerReveal;
  answerDistribution: Record<string, number>;
  totalAnswered: number;
  totalPlayers: number;
  correctCount: number;
  avgAnswerTimeMs: number | null;
}

export interface HostGameOverPayload {
  scores: number[];
  playerCount: number;
  maxPossibleScore: number;
  questionSummary: HostQuestionSummaryItem[];
}

export type HostPhase = 'lobby' | 'question' | 'results' | 'gameover';
