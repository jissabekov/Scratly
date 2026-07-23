'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import {
  clearStoredSessionId,
  loadStoredSessionId,
  newIdempotencyKey,
  storeSessionId,
} from '../../lib/session';
import type {
  SessionCreated,
  SessionMessages,
  SessionProjects,
  StudentProject,
  ThreadMessage,
  TurnResponse,
} from '../../lib/types';
import { Composer } from './Composer';
import { MessageBubble } from './MessageBubble';
import { ProjectCards } from './ProjectCards';
import { StageChip } from './StageChip';

const WELCOME_TEXT =
  "Hey — I'm Scratly. Tell me a bit about yourself and what you've been into lately, and I'll help find a course project that actually fits.";

function welcomeMessage(): ThreadMessage {
  return {
    key: 'welcome',
    role: 'welcome',
    content: WELCOME_TEXT,
  };
}

export function StudentChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stage, setStage] = useState('discovery');
  const [messages, setMessages] = useState<ThreadMessage[]>([welcomeMessage()]);
  const [projects, setProjects] = useState<StudentProject[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState('');
  const threadRef = useRef<HTMLDivElement>(null);
  const idempotencyRef = useRef<string | null>(null);

  const scrollToBottom = useCallback(() => {
    const el = threadRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, projects, busy, scrollToBottom]);

  const loadProjects = useCallback(async (id: string, nextStage: string) => {
    if (nextStage !== 'project_matching' && nextStage !== 'complete') {
      setProjects([]);
      return;
    }
    try {
      const data = await api<SessionProjects>(`/v1/sessions/${id}/projects`);
      setProjects(data.items);
    } catch {
      setProjects([]);
    }
  }, []);

  const hydrateFromMessages = useCallback(
    (data: SessionMessages) => {
      setStage(data.stage);
      const items: ThreadMessage[] = data.items.map((m) => ({
        key: m.id,
        id: m.id,
        role: m.role,
        content: m.content,
        message_kind: m.message_kind,
        status: 'sent',
      }));
      if (items.length === 0) {
        setMessages([welcomeMessage()]);
      } else {
        setMessages(items);
      }
      void loadProjects(data.session_id, data.stage);
    },
    [loadProjects]
  );

  const startNewSession = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      const created = await api<SessionCreated>('/v1/sessions', { method: 'POST' });
      storeSessionId(created.session_id);
      setSessionId(created.session_id);
      setStage(created.stage);
      setMessages([welcomeMessage()]);
      setProjects([]);
      setDraft('');
      idempotencyRef.current = null;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setBooting(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const stored = loadStoredSessionId();
      if (!stored) {
        await startNewSession();
        return;
      }
      try {
        const data = await api<SessionMessages>(`/v1/sessions/${stored}/messages`);
        storeSessionId(stored);
        setSessionId(stored);
        hydrateFromMessages(data);
        setError('');
      } catch {
        clearStoredSessionId();
        await startNewSession();
        return;
      } finally {
        setBooting(false);
      }
    })();
  }, [hydrateFromMessages, startNewSession]);

  const sendText = useCallback(
    async (text: string) => {
      if (!sessionId || busy || stage === 'complete') return;
      const trimmed = text.trim();
      if (!trimmed) return;

      const key = idempotencyRef.current || newIdempotencyKey();
      idempotencyRef.current = key;
      const pendingId = `pending-${key}`;
      setDraft('');
      setBusy(true);
      setError('');
      setMessages((prev) => [
        ...prev.filter(
          (m) =>
            m.role !== 'welcome' &&
            m.status !== 'failed' &&
            m.key !== pendingId
        ),
        {
          key: pendingId,
          role: 'student',
          content: trimmed,
          status: 'pending',
        },
      ]);

      try {
        const result = await api<TurnResponse>(`/v1/sessions/${sessionId}/turns`, {
          method: 'POST',
          body: JSON.stringify({ idempotency_key: key, text: trimmed }),
        });
        setStage(result.stage);
        setMessages((prev) => {
          const withoutPending = prev.filter((m) => m.key !== pendingId);
          return [
            ...withoutPending,
            {
              key: result.student_message_id || pendingId,
              id: result.student_message_id || undefined,
              role: 'student',
              content: trimmed,
              status: 'sent',
            },
            {
              key: result.assistant_message_id || `asst-${result.turn_id}`,
              id: result.assistant_message_id || undefined,
              role: 'assistant',
              content: result.assistant_message,
              message_kind: result.message_kind,
              status: 'sent',
              elicitation: result.elicitation,
            },
          ];
        });
        idempotencyRef.current = null;
        await loadProjects(sessionId, result.stage);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setMessages((prev) =>
          prev.map((m) =>
            m.key === pendingId ? { ...m, status: 'failed' as const } : m
          )
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, loadProjects, sessionId, stage]
  );

  function retryFailed() {
    const failed = messages.find((m) => m.status === 'failed' && m.role === 'student');
    if (!failed) return;
    void sendText(failed.content);
  }

  const completed = stage === 'complete';

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <div className="chat-brand-block">
          <h1 className="chat-brand">Scratly</h1>
          <p className="chat-tagline">Find a project that fits how you work</p>
        </div>
        <div className="chat-header-actions">
          <StageChip stage={stage} />
          <button
            type="button"
            className="secondary chat-new"
            onClick={() => void startNewSession()}
            disabled={busy || booting}
          >
            New chat
          </button>
          <Link className="teacher-link" href="/teacher">
            Teacher
          </Link>
        </div>
      </header>

      <div className="chat-thread" ref={threadRef}>
        {booting ? (
          <p className="chat-booting">Starting…</p>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.key}
                message={message}
                onElicitation={
                  !busy && !completed && message.message_kind === 'elicitation'
                    ? (label) => void sendText(label)
                    : undefined
                }
                onRetry={
                  message.status === 'failed' ? () => retryFailed() : undefined
                }
              />
            ))}
            {busy ? (
              <div className="chat-row assistant enter">
                <div className="chat-bubble assistant working">
                  <span className="working-dot" />
                  Thinking…
                </div>
              </div>
            ) : null}
            <ProjectCards projects={projects} />
            {completed ? (
              <div className="chat-complete enter">
                <p>That’s a wrap — your preferences are matched.</p>
                <button type="button" onClick={() => void startNewSession()}>
                  Start a new chat
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>

      {error ? <p className="chat-error">{error}</p> : null}

      <Composer
        value={draft}
        onChange={setDraft}
        onSend={(text) => void sendText(text)}
        disabled={busy || booting || completed || !sessionId}
        placeholder={
          completed
            ? 'This chat is complete'
            : 'Share an interest, preference, or answer…'
        }
      />
    </div>
  );
}
