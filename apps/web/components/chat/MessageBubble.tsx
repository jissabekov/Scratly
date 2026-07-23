'use client';

import type { ElicitationSpec, MessageKind, ThreadMessage } from '../../lib/types';

const KIND_LABELS: Partial<Record<NonNullable<MessageKind>, string>> = {
  student_answer: '',
  refusal: 'Out of scope',
  elicitation: '',
  profile_review: 'Profile review',
  project_offer: 'Project ideas',
  assessment_question: '',
};

type Props = {
  message: ThreadMessage;
  onElicitation?: (label: string) => void;
  onRetry?: () => void;
};

export function MessageBubble({ message, onElicitation, onRetry }: Props) {
  if (message.role === 'welcome') {
    return (
      <div className="chat-bubble welcome enter">
        <p className="welcome-brand">Scratly</p>
        <p>{message.content}</p>
      </div>
    );
  }

  const isStudent = message.role === 'student';
  const kindLabel =
    !isStudent && message.message_kind
      ? KIND_LABELS[message.message_kind] || ''
      : '';
  const elicitation: ElicitationSpec | null | undefined = message.elicitation;

  return (
    <div
      className={`chat-row ${isStudent ? 'student' : 'assistant'} enter${
        message.status === 'pending' ? ' pending' : ''
      }${message.status === 'failed' ? ' failed' : ''}`}
    >
      <div
        className={`chat-bubble ${isStudent ? 'student' : 'assistant'}${
          message.message_kind === 'profile_review' ? ' review' : ''
        }${message.message_kind === 'project_offer' ? ' project' : ''}`}
      >
        {kindLabel ? <span className="kind-label">{kindLabel}</span> : null}
        <p>{message.content}</p>
        {message.status === 'failed' ? (
          <button type="button" className="retry" onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
      {elicitation && elicitation.options.length >= 2 && onElicitation ? (
        <div className="elicit-chips">
          {elicitation.options.map((opt) => (
            <button
              key={opt.key}
              type="button"
              className="elicit-chip"
              onClick={() => onElicitation(opt.label)}
            >
              {opt.label}
            </button>
          ))}
          {elicitation.allow_skip ? (
            <button
              type="button"
              className="elicit-chip skip"
              onClick={() => onElicitation('something else')}
            >
              Something else
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
