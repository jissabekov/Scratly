export type Stage =
  | 'discovery'
  | 'measurement'
  | 'gap_resolution'
  | 'profile_review'
  | 'project_matching'
  | 'complete';

export type MessageKind =
  | 'assessment_question'
  | 'student_answer'
  | 'refusal'
  | 'elicitation'
  | 'profile_review'
  | 'project_offer'
  | 'matching_unavailable'
  | 'post_match_feedback'
  | null;

export type ChatRole = 'student' | 'assistant' | 'system';

export type ElicitationOption = {
  key: string;
  label: string;
};

export type ElicitationSpec = {
  options: ElicitationOption[];
  allow_both: boolean;
  allow_skip: boolean;
  dimension_key: string;
  fallback_template: string;
};

export type SessionCreated = {
  session_id: string;
  student_id: string;
  stage: Stage;
};

export type SessionResume = {
  session_id: string;
  student_id: string;
  stage: Stage;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type MessageItem = {
  id: string;
  turn_id: string | null;
  sequence: number;
  role: ChatRole;
  content: string;
  message_kind: MessageKind;
  created_at: string;
};

export type SessionMessages = {
  session_id: string;
  stage: Stage;
  completed_at: string | null;
  items: MessageItem[];
};

export type TurnResponse = {
  turn_id: string;
  assistant_message: string;
  stage: Stage;
  message_kind: MessageKind;
  elicitation: ElicitationSpec | null;
  student_message_id: string | null;
  assistant_message_id: string | null;
};

export type StudentProject = {
  id: string;
  title: string;
  summary: string;
  topic_keys: string[];
  work_mode_keys: string[];
  motivation_keys: string[];
  citation_count: number;
};

export type SessionProjects = {
  session_id: string;
  items: StudentProject[];
};

export type AdminSessionRow = {
  session_id: string;
  student_id: string;
  stage: string;
  turn_count: number;
  created_at?: string;
  updated_at?: string;
};

/* --- Learning track (Plan 03) -------------------------------------------- */

export type LearningModuleState = 'locked' | 'available' | 'in_progress' | 'passed';

export type LearningModuleSummary = {
  id: string;
  slug: string;
  seq: number;
  title: string;
  description: string;
  est_minutes: number;
  state: LearningModuleState;
  slides_total: number;
  slides_completed: number;
  progress_pct: number;
  quiz_gate_locked: boolean;
};

export type LearningHub = {
  session_id: string;
  archetype_key: string;
  modules: LearningModuleSummary[];
  mastery_pct: number;
  streak_days: number;
};

/** Typed slide blocks — rendered by one component, never free-form HTML. */
export type SlideBlock =
  | { type: 'text'; text: string }
  | { type: 'callout'; tone: 'info' | 'success' | 'warning'; title: string; text: string }
  | { type: 'diagram'; asset: string; alt: string; caption: string; steps: string[] }
  | {
      type: 'check';
      question: string;
      options: { key: string; label: string }[];
      answer_key: string;
      explanation: string;
      objective?: string | null;
    }
  | { type: 'worked_example'; title: string; steps: string[] };

export type SlideItem = {
  id: string;
  index: number;
  lesson_seq: number;
  lesson_title: string;
  seq: number;
  kind: string;
  title: string;
  content: SlideBlock[];
  objective_code: string | null;
  completed: boolean;
};

export type ModuleProgress = {
  slides_total: number;
  slides_completed: number;
  current_slide_index: number;
};

export type QuizGate = {
  state: 'locked' | 'available' | 'passed';
  available: boolean;
  planned_phase: number;
};

export type ModuleDetail = {
  session_id: string;
  module: LearningModuleSummary;
  slides: SlideItem[];
  progress: ModuleProgress;
  quiz: QuizGate;
};

export type SlideCompleteResult = {
  slide_id: string;
  completed: boolean;
  already_completed: boolean;
  module_progress: ModuleProgress;
  next_slide_index: number | null;
};

/** Client-only thread row (includes optimistic / welcome). */
export type ThreadMessage = {
  key: string;
  id?: string;
  role: ChatRole | 'welcome';
  content: string;
  message_kind?: MessageKind;
  status?: 'pending' | 'failed' | 'sent';
  elicitation?: ElicitationSpec | null;
};
