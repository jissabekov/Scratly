'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import type { AdminSessionRow } from '../../lib/types';

const VIEWS: [string, string, string][] = [
  ['Profile', 'V1 student model: interests, work modes, motivation, execution, assets', 'profile'],
  ['Evidence ledger', 'Accepted and rejected claims with exact quotes', 'evidence'],
  ['Conversation', 'Raw student and assistant messages', 'transcript'],
  ['Timeline', 'Versioned profile transitions', 'profile-history'],
  ['Contradictions', 'Open conflicts and explicit resolutions', 'contradictions'],
  ['Question history', 'Targets, rationale, and fallback use', 'question-history'],
  ['Why this question?', 'Deterministic priority trace', 'why-next-question'],
  ['Project ranking', 'Eligibility, weighted fit, execution gates, scaffolding', 'project-fit'],
];

function summarize(item: Record<string, unknown>): { title: string; body: string } {
  if ('interests' in item || 'work_modes' in item) {
    return {
      title: 'V1 profile',
      body: JSON.stringify(item, null, 2),
    };
  }
  if ('label' in item && 'key' in item) {
    return {
      title: `${item.label} (${item.key})`,
      body: `status=${item.status ?? '—'} value=${item.value ?? '—'}`,
    };
  }
  if ('role' in item && 'content' in item) {
    const kind = item.message_kind ? ` · ${item.message_kind}` : '';
    return {
      title: `${item.role}${kind} · seq ${item.sequence ?? ''}`,
      body: String(item.content),
    };
  }
  if ('exact_source_quote' in item) {
    return {
      title: `${item.dimension_key} · ${item.status}`,
      body: String(item.exact_source_quote),
    };
  }
  if ('intent_key' in item) {
    return {
      title: `${item.intent_key} → ${item.target_key}${item.used_fallback ? ' (fallback)' : ''}`,
      body: String(item.assistant_question ?? JSON.stringify(item.rationale ?? {}, null, 2)),
    };
  }
  if ('decision_summary' in item) {
    return {
      title: `${item.event_type ?? item.reason_code}`,
      body: String(item.decision_summary),
    };
  }
  if ('archetype_key' in item || 'opportunity_key' in item || 'title' in item) {
    const failed = Array.isArray(item.failed_constraints)
      ? item.failed_constraints.join(',')
      : '';
    return {
      title: String(item.title ?? item.opportunity_key ?? item.archetype_key ?? item.key),
      body: `eligible=${item.eligible ?? '—'} score=${item.total_score ?? '—'} failed=[${failed}] ${item.source_url ?? ''}`,
    };
  }
  if ('version' in item) {
    return {
      title: `Snapshot v${item.version}`,
      body: JSON.stringify(item.state ?? {}, null, 2),
    };
  }
  return { title: 'Item', body: JSON.stringify(item, null, 2) };
}

export default function TeacherPage() {
  const [sessions, setSessions] = useState<AdminSessionRow[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [stage, setStage] = useState<string>('');
  const [turnText, setTurnText] = useState(
    'I like building small science projects with data from my neighborhood.'
  );
  const [viewData, setViewData] = useState<Record<string, unknown[]>>({});
  const [trace, setTrace] = useState<unknown[]>([]);
  const [status, setStatus] = useState('Loading sessions…');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const refreshSessions = useCallback(async () => {
    const data = await api<{ items: AdminSessionRow[] }>('/v1/admin/sessions');
    setSessions(data.items);
    return data.items;
  }, []);

  const loadSessionViews = useCallback(async (id: string) => {
    if (!id) return;
    setStatus(`Loading session ${id}…`);
    const [session, traceData, ...views] = await Promise.all([
      api<{ stage: string }>(`/v1/sessions/${id}`),
      api<{ events: unknown[] }>(`/v1/admin/sessions/${id}/decision-trace`),
      ...VIEWS.map(([, , slug]) =>
        api<{ items: unknown[] }>(`/v1/admin/sessions/${id}/${slug}`)
      ),
    ]);
    setStage(session.stage);
    setTrace(traceData.events);
    const next: Record<string, unknown[]> = {};
    VIEWS.forEach(([, , slug], index) => {
      next[slug] = views[index].items;
    });
    setViewData(next);
    setStatus(`Session ${id} · stage ${session.stage}`);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const items = await refreshSessions();
        if (items[0] && !sessionId) {
          setSessionId(items[0].session_id);
        }
        setError('');
        setStatus(items.length ? `Loaded ${items.length} session(s)` : 'No sessions yet');
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setStatus('API unreachable');
      }
    })();
    // intentionally run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        setBusy(true);
        await loadSessionViews(sessionId);
        setError('');
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    })();
  }, [sessionId, loadSessionViews]);

  const selectedLabel = useMemo(() => {
    const row = sessions.find((s) => s.session_id === sessionId);
    return row
      ? `${row.session_id.slice(0, 8)}… · ${row.stage} · ${row.turn_count} turns`
      : sessionId;
  }, [sessions, sessionId]);

  async function onCreateSession() {
    try {
      setBusy(true);
      const created = await api<{ session_id: string; stage: string }>('/v1/sessions', {
        method: 'POST',
      });
      await refreshSessions();
      setSessionId(created.session_id);
      setStage(created.stage);
      setError('');
      setStatus(`Created session ${created.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSubmitTurn(event: FormEvent) {
    event.preventDefault();
    if (!sessionId || !turnText.trim()) return;
    try {
      setBusy(true);
      const key = `ui-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const result = await api<{ turn_id: string; assistant_message: string; stage: string }>(
        `/v1/sessions/${sessionId}/turns`,
        {
          method: 'POST',
          body: JSON.stringify({ idempotency_key: key, text: turnText.trim() }),
        }
      );
      setStage(result.stage);
      await refreshSessions();
      await loadSessionViews(sessionId);
      setStatus(`Turn ${result.turn_id} · stage ${result.stage}`);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="teacher-main">
      <header>
        <p className="eyebrow">SCRATLY · TEACHER INSPECTION</p>
        <h1>Student assessment console</h1>
        <p className="lede">
          Every conclusion remains traceable to the student’s own words. Live data from the
          local API.{' '}
          <Link href="/">Back to student chat</Link>
        </p>
      </header>

      <div className="toolbar">
        <label>
          Session
          <select
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            disabled={busy}
          >
            <option value="">Select a session…</option>
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id.slice(0, 8)}… · {s.stage} · {s.turn_count} turns
              </option>
            ))}
          </select>
        </label>
        <div className="actions">
          <button type="button" onClick={onCreateSession} disabled={busy}>
            New session
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              void (async () => {
                await refreshSessions();
                if (sessionId) await loadSessionViews(sessionId);
              })();
            }}
            disabled={busy}
          >
            Refresh
          </button>
        </div>
        <form onSubmit={onSubmitTurn} style={{ display: 'contents' }}>
          <label>
            Student turn
            <textarea
              value={turnText}
              onChange={(e) => setTurnText(e.target.value)}
              disabled={busy || !sessionId}
            />
          </label>
          <button type="submit" disabled={busy || !sessionId}>
            Submit turn
          </button>
        </form>
      </div>

      <p className={`status${error ? ' error' : ''}`}>
        {error ? error : status}
        {sessionId ? ` · ${selectedLabel}` : ''}
        {stage ? ` · stage ${stage}` : ''}
      </p>

      <nav>
        {VIEWS.map(([label]) => (
          <a key={label} href={`#${label.replaceAll(' ', '-')}`}>
            {label}
          </a>
        ))}
        <a href="#Decision-trace">Decision trace</a>
      </nav>

      <section className="grid">
        {VIEWS.map(([label, description, slug], index) => {
          const items = (viewData[slug] || []) as Record<string, unknown>[];
          return (
            <article id={label.replaceAll(' ', '-')} key={slug}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <h2>{label}</h2>
              <p>{description}</p>
              {!sessionId ? (
                <div className="empty">Select or create a student session to inspect</div>
              ) : items.length === 0 ? (
                <div className="empty">No rows yet for this view</div>
              ) : (
                <ul className="item-list">
                  {items.map((item, i) => {
                    const { title, body } = summarize(item);
                    return (
                      <li key={String(item.id ?? i)}>
                        <strong>{title}</strong>
                        <div>{body}</div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </article>
          );
        })}
        <article id="Decision-trace">
          <span>09</span>
          <h2>Decision trace</h2>
          <p>Append-only, privacy-safe turn explanations</p>
          {!sessionId ? (
            <div className="empty">Select a session</div>
          ) : trace.length === 0 ? (
            <div className="empty">No decision events yet</div>
          ) : (
            <ul className="item-list">
              {(trace as Record<string, unknown>[]).map((event, i) => (
                <li key={String(event.id ?? i)}>
                  <strong>
                    {String(event.sequence)}. {String(event.event_type)} ·{' '}
                    {String(event.reason_code)}
                  </strong>
                  <div>{String(event.decision_summary)}</div>
                  <pre>
                    {JSON.stringify(
                      { inputs: event.inputs, outputs: event.outputs },
                      null,
                      2
                    )}
                  </pre>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </main>
  );
}
