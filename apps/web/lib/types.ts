export type Stage =
  | 'discovery'
  | 'measurement'
  | 'gap_resolution'
  | 'profile_review'
  | 'project_matching'
  | 'complete'
  | string;

export type MessageKind =
  | 'assessment_question'
  | 'student_answer'
  | 'refusal'
  | 'elicitation'
  | 'profile_review'
  | 'project_offer'
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
