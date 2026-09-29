# Plan 03 — Learning modules & slide lesson player (Phase 3)

> **Status: READY (after Phases 1–2)** · Owner: Devin (full-stack) · Depends on: Plan 01 (W1.6 hygiene), Plan 02 (UI foundation)
> **Goal:** after the assessment chat completes and the student selects a project, deliver **learning modules** ("classes" teaching the core concepts needed to start developing that project) as a pleasing slide-based player, with automatic per-slide tracking. Content is provided later — everything here is content-agnostic.

## 3.1 Product flow

```
chat (assessment) → project selected → LEARNING HUB (module path)
  → module N: slides (one idea per slide, low-stakes checks)
  → quiz gate (Plan 04) → next module unlocks → … → project ready to start
```

## 3.2 Data model (new schema `learning`; migration `014_learning_content.sql`)

```sql
learning.modules(id, project_archetype_id, seq, title, description,
                 est_minutes, status)              -- content authored in repo, seeded
learning.objectives(id, module_id, code, label, is_critical, ordinal)
learning.lessons(id, module_id, seq, title)
learning.slides(id, lesson_id, seq, kind,           -- text|callout|diagram|check|worked_example
                content jsonb, objective_id)        -- typed blocks, NOT free-form HTML
learning.slide_completions(id, student_id, slide_id, completed_at,
                           request_id UNIQUE)       -- idempotent automatic tracking
```

- **Content lives in the repo** (`content/modules/<archetype>/<module>/…`) as versioned JSON — reproducible, reviewable, no CMS. Seed script loads it; teacher console can preview.
- `content` jsonb is a **typed block list** rendered by one `SlideBlock` renderer: `text`, `callout`, `diagram` (SVG/asset ref + step captions), `check` (retryable low-stakes question), `worked_example`. One idea per slide; max ~2 blocks + 1 interaction.
- Modules are linked to the matched project archetype (from `matching`), with a fallback generic set.

## 3.3 API surface (FastAPI, new router `routes/learning.py`)

| Endpoint | Purpose |
|---|---|
| `GET /v1/sessions/{id}/learning` | hub: modules with state (locked/available/in_progress/passed), mastery %, streak |
| `GET /v1/sessions/{id}/learning/modules/{mid}` | module detail: slides + progress + quiz status |
| `POST /v1/sessions/{id}/learning/slides/{sid}/complete` | automatic tracking (idempotent `request_id`) |
| `GET /v1/sessions/{id}/learning/modules/{mid}/quiz` | next quiz attempt (5 items, form selection) |
| `POST /v1/sessions/{id}/learning/quiz-attempts` | submit attempt → `{passed, missed[], per_objective}` |
| `GET/POST /v1/sessions/{id}/learning/checkins[/{cid}]` | check-in delivery + response (Plan 05) |

All writes: `request_id` idempotency, append-only `learning.learning_events` (xAPI-shaped: actor/verb/object/result/context/ts), derived rollups replayable. **Quiz answers never write `assessment.evidence`** (hard rules 2/4 — learning evidence is a separate stream).

## 3.4 Slide player UX (from Brilliant/Duolingo/Khan research)

- One-idea-per-slide; top progress bar (slide x of n, `aria-valuenow`); fixed bottom `FlowActionBar` (Back ghost / Check→Continue primary) shared with quizzes.
- In-slide `check` blocks are retryable and award a small XP tick; wrong answers show explanation, never silently advance.
- Slide transitions: Motion `AnimatePresence` direction-aware; `prefers-reduced-motion` respected.
- Keyboard: ←/→ navigate, 1–4 pick options, Enter = primary CTA.
- Celebration at module completion only (milestone rewards, not constant animation).
- Deep-linkable: `/modules/[moduleId]?slide=n` — refresh/back/Playwright all work.

## 3.5 Component inventory (frontend)

```
app/(student)/modules/page.tsx            # server: hub/path
app/(student)/modules/[moduleId]/page.tsx # server → <LessonPlayer/>
components/learn/LessonPlayer.tsx         # client: ?slide= param, AnimatePresence, focus mgmt
components/learn/SlideBlock.tsx           # typed block renderer
components/learn/FlowActionBar.tsx        # shared bottom bar
components/learn/SlideProgress.tsx        # top bar
components/learn/CheckBlock.tsx           # in-slide check (retryable)
components/progress/ModulePath.tsx        # locked/current/done nodes + quiz-gate icons
lib/actions.ts                            # 'use server': completeSlide, submitQuizAttempt, …
```

## 3.4 Automatic tracking

- Slide completion, section completion, time-on-slide → `learning_events` (xAPI-shaped: actor/verb/object/result) — the append-only source of truth; `progress_rollups` are replayable projections (no hidden state).
- Deterministic triggers only; LLM never owns tracking state.

## 3.5 Acceptance

- Hub renders module path with locked/current/done states (Duolingo-path pattern); active node emphasized.
- Player: slide x of n bar, keyboard nav, focus management, live regions; one-idea-per-slide enforced by content schema.
- Slide completion persists idempotently; refresh/back restore position from URL + server.
- Playwright: hub → module → complete slides → quiz gate locked until Plan 04 lands.
