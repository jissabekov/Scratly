# Scratly system guide (current implementation)

This is the end-to-end reference for how Scratly works **today**: product intent, runtime architecture, turn pipeline, policy, persistence, matching, tracing, and the live eval regressor.

For deeper slices see also: [architecture.md](architecture.md) · [student-model.md](student-model.md) · [conversation-policy.md](conversation-policy.md) · [scoring-rules.md](scoring-rules.md) · [eval-suite.md](eval-suite.md) · [eval-findings-and-fix-plan.md](eval-findings-and-fix-plan.md)

---

## 1. Product intent

Scratly runs an **explainable assessment conversation** for teens:

1. A student chats naturally about interests, work style, motivation, execution, constraints, and access.
2. The system builds a **structured preference profile** from **grounded evidence only**.
3. Teachers can audit **every claim**, **every stage transition**, and **every next question** via decision traces and admin views.
4. When sufficient, the system offers **citation-linked project directions** from a curated opportunity catalog (optionally augmented by bounded web research).

The system does **not** assign personality types, complete every dimension for its own sake, or let the LLM mutate profile state directly.

---

## 2. Runtime topology

```text
Student UI (Next.js :3000/)
  POST /v1/sessions
  POST /v1/sessions/{id}/turns
        │
        ▼
FastAPI API (apps/api, :8000)
  turn_processor.process_student_turn  ← sole write path
        │
        ├── Azure OpenAI (Entra auth)
        │     structured: extractor, intent, writer, memory, compose, web_search
        │
        └── PostgreSQL 16
              core · conversation · assessment · matching · audit
```

| Layer | Role |
|---|---|
| `apps/web` | Student chat; teacher inspect at `/teacher` |
| `apps/api` | Policy, grounding, reduction, matching, audit |
| `migrations/` | Ordered SQL; applied on first Postgres volume boot |
| Azure OpenAI | Proposes/phrases; never owns stage or priority |
| `scripts/eval_conversation_suite.py` | Live 18-persona regression harness |

**Truth hierarchy:** raw message → accepted grounded evidence → deterministic profile → snapshot → memory/research aids (never profile truth).

---

## 3. Session lifecycle and stages

```text
discovery → measurement → gap_resolution → profile_review → project_matching → complete
```

| Stage | Enters when |
|---|---|
| `discovery` | Few required dims touched |
| `measurement` | `coverage_touched ≥ 0.4` |
| `gap_resolution` | Open contradictions + `coverage_established ≥ 0.5` |
| `profile_review` | No open contradictions AND (`coverage_established ≥ 0.9` OR **decision-sufficient review**) |
| `project_matching` | Student latched `profile_reviewed` + `location_ready` |
| `complete` | Matching finished |

**Decision-sufficient review** (`evaluate_review_eligibility` in `question_policy.py`):

- No open contradictions
- `location_ready` is not false
- `topics`, `work_mode`, `motivation` are **supported**
- `execution` is **supported or provisional**
- At least one of `capability` / `assets` is **supported or provisional**
- `coverage_established ≥ 0.6`

Emits trace reason `decision_sufficient_review` on `stage_gate_evaluated`.

**Legacy full-inventory path:** `coverage_established ≥ 0.9` still enters `profile_review` without the alternate rule.

---

## 4. Sole write path: one student turn

All assessment mutations go through `process_student_turn` in `turn_processor.py` inside a single DB transaction. Idempotency: `UNIQUE(session_id, idempotency_key)` on `conversation.turns`.

### 4.1 High-level flow

```text
Student text
  → intent classify (+ heuristic safety overrides)
  → [optional] student Q answer / refuse
  → [optional] evidence extract → ground → persist → reduce → contradictions
  → [optional] geo infer from text if extractor missed place
  → location readiness check
  → question candidates → repetition filter → planner → thin/elicitation branch
  → stage gate + stage derive
  → [optional] profile review narrative
  → question writer + quality gate
  → [optional] project matching (research, rank, compose, cite)
  → persist assistant message + commit trace
```

### 4.2 Decision events (current)

| Event | Component | Purpose |
|---|---|---|
| `turn_started` / `turn_completed` | turn_processor | Turn boundaries |
| `turn_intent_classified` | turn_intent_classifier | assessment vs student Q vs mixed |
| `student_answer_written` / `student_answer_refused` | student_answerer | In-scope answers; homework refuse |
| `evidence_extraction_skipped` | turn_processor | Pure student questions |
| `evidence_proposed` | evidence_extractor | LLM proposals (+ pre-filter drop count) |
| `evidence_validated` | grounding_validator | Accept/reject + yield ratio |
| `geo_inferred_from_text` | location_policy | Fallback when place stated but not extracted |
| `profile_reduced` | profile_reducer | Snapshot from accepted evidence only |
| `contradiction_*` | contradiction_engine | v2 true conflicts only |
| `location_readiness_checked` | location_policy | Geo on constraints dim |
| `reply_signal_classified` | question_policy | greeting / correction / thin / substantive |
| `answer_thinness_evaluated` | thin_answer | Thin detection |
| `elicitation_rephrase` | elicitation_policy | First thin on recoverable dim |
| `elicitation_selected` | elicitation_policy | Option chips unlocked |
| `elicitation_exhausted` | elicitation_policy | Cap reached; soft-skip |
| `elicitation_skipped_not_recoverable` | elicitation_policy | e.g. social_intro |
| `question_target_blocked` | question_policy | `repetition_hard_stop` / `follow_up_exhausted` |
| `question_target_selected` | conversation_planner + question_policy | Planner advisory + committed target |
| `stage_gate_evaluated` | stage_policy | Review latch inputs |
| `stage_derived` | stage_policy | Resulting stage |
| `profile_review_completed` | turn_processor | `profile_reviewed` latch |
| `question_written` / `question_fallback_used` | writer | Assistant question text |
| `question_quality_gate` | question_quality | Leak/compound/elicitation checks |
| `research_*`, `opportunities_matched`, `project_*` | matching stack | Citation-grounded offers |

Migration `011_eval_fix_trace_events.sql` adds the new enum values.

### 4.3 LLM audit isolation

`azure_openai.py` stores per-turn context in **contextvars** (`_llm_audit`, `_llm_session_id`, `_llm_turn_id`, `_llm_last_run_id`) so concurrent sessions cannot cross-link `llm_run_id` on decision events.

---

## 5. Evidence pipeline

### 5.1 Extractor

- Prompt: `apps/api/prompts/evidence_extractor/v3/system.txt`
- Output: `EvidencePacket` with 0–5 `ProposedEvidence` items
- Dimensions: `topics`, `work_mode`, `motivation`, `execution`, `capability`, `constraints` (incl. geo), `assets`
- Rules: verbatim quotes only; cite owned message IDs; geography on `constraints`; no personality inference from interest nouns

### 5.2 Pre-filter (turn_processor)

Proposals referencing unknown message IDs are dropped **before** DB insert (reduces FK abort risk and wasted writes).

### 5.3 Grounding validator

Rejects with auditable reasons: `exact_quote_not_found`, `source_message_unavailable_or_not_owned`, taxonomy misses, etc.

**Rejected evidence:** persisted with reason but **no** `evidence_sources` rows for hallucinated IDs.

**NUL bytes:** stripped from quotes before Postgres insert.

### 5.4 Profile reducer (v2)

- Input: **accepted** evidence only
- Output: dimension statuses (`unknown`, `provisional`, `supported`, `contradicted`), interests, work modes, motivation, execution, constraints/geo, capabilities, assets
- UNKNOWN ≠ 0 — omitted facets stay unknown, not zero

---

## 6. Question selection policy

### 6.1 Control split

```text
Planner (plan_next) → action + target + reason
Policy (select_next, question_candidates) → candidate pool + hard blocks
Writer → phrasing only (cannot change target)
```

### 6.2 Candidate priority

1. `contradiction`
2. `required_hard_variable`
3. `project_critical_unknown`
4. `provisional_dimension`
5. `project_discrimination`
6. `profile_validation` (only when `coverage_established ≥ 0.9` or already in review/matching)

### 6.3 Repetition hard-stop (`is_repetition_blocked`)

Blocks a candidate when:

- `asked_count ≥ 2` and status is `supported` / `established`, OR
- `asked_count ≥ 2` and status is `provisional` on high-repeat keys (`constraints`, `capability`, `execution`, …), OR
- `asked_count ≥ 3` on high-repeat keys

Blocked targets emit `question_target_blocked` with `repetition_hard_stop`.

**Decision value penalty:** `asked_count × 0.35` (uncapped).

**Follow-up exhaustion:** after `asked_count ≥ 3` on same key, planner forces `SWITCH` with `follow_up_exhausted`.

**Provisional discrimination:** skips dims already asked twice before adding `project_discrimination` candidate.

### 6.4 Planner saturation

- `DEFAULT_MAX_TOPIC_DEPTH = 2`, `ABSOLUTE_MAX_TOPIC_DEPTH = 3`
- `no` / `idk` → switch unless essential gate
- Topic rejection / frustration → switch + block topic

### 6.5 Interest-depth gate

Other required dims stay gated until topics depth is real (see `interest_depth_ready` in `question_policy.py`).

---

## 7. Thin answers and elicitation

### 7.1 Thin detection (`thin_answer.py`)

Thin when: idk pattern, or ultra-short mid-assessment with zero accepted evidence. **Never thin:** greetings, name intros before first assistant question, student_question path.

### 7.2 Elicitation policy (`elicitation_policy.py`)

| Attempt | Behavior |
|---|---|
| 1 | Rephrase; trace `elicitation_rephrase`; persist counter |
| ≥ 2 | Offer chips if `should_offer_options`: thin OR `insufficient`/`thin_answer` signal |
| 3+ | `elicitation_exhausted`; soft-skip target |

**Counter persistence:** `elicitation_target_key` + `elicitation_attempts_for_target` on `core.sessions` — **not reset** when planner switches topic; pending key keeps counting.

**Recoverable kinds:** `required_hard_variable`, `project_critical_unknown`, `provisional_dimension`, `project_discrimination`, `contradiction`, `elicitation`, and `behavioral_anchor` after first assistant question.

Option banks per dimension family (`execution:persistence` → `execution` bank).

---

## 8. Location and geo

- Geography lives on **`constraints`** dimension value keys (metros, places, freeform snake_case like `nashville`, `chicago`).
- `location_ready` = accepted geo constraint evidence OR profile constraints with geo value.
- `infer_geo_from_text()` + `record_geo_from_text()` when student clearly states place but extractor missed it.
- `project_matching` requires `location_ready` (does not re-ask forever after clear answer).

---

## 9. Student questions and refusals

| Intent | Behavior |
|---|---|
| Process / profile / project Q | Brief answer; may prefix assistant message |
| Out-of-scope / homework | Refuse; skip evidence extraction |
| Framing pushback | Acknowledge; return to interest depth |
| Consecutive Q cap | Refuse after limit |

Student answers **never write profile**; citations limited to accepted evidence IDs and public profile fields.

---

## 10. Project matching

When stage is `project_matching` and location is ready:

1. `extract_geo_from_profile` → research queries
2. `rank_opportunities` — hard geo + execution gates
3. Optional bounded `web_search` → stored findings
4. `ProjectComposer` drafts packets with citations
5. `filter_grounded_projects` rejects unknown opportunity/finding IDs
6. Persist fits + offer message (`message_kind=project_offer`)

---

## 11. Persistence (`assessment.py`)

Key repository responsibilities:

| Method | Role |
|---|---|
| `validate_and_record_evidence` | Ground + insert evidence + owned sources only |
| `apply_evidence_reduce_contradictions_snapshot` | Reducer + snapshot + contradiction sync |
| `question_candidates` | Build `Target` list with coverage_status, asked_count |
| `stage_inputs` | Coverage ratios, review_eligible, dimension_statuses |
| `record_geo_from_text` | Fallback geo evidence |
| `session_counters` | Elicitation, profile_reviewed, consecutive student Qs |
| `record_decision_event` | Append-only audit |

Schemas: `core`, `conversation`, `assessment`, `matching`, `audit` (see [architecture.md](architecture.md)).

---

## 12. Admin and teacher views

`GET /v1/admin/sessions/{id}/{view}`:

- `transcript`, `evidence`, `profile`, `profile-history`, `contradictions`
- `question-history`, `why-next-question`, `project-fit`
- `GET /v1/admin/sessions/{id}/decision-trace?limit=1000`

Use **correlation_id** from a turn to walk the event chain; follow `entity_refs` and `llm_run_id`.

---

## 13. Live eval regressor

See [eval-suite.md](eval-suite.md).

**18 personas**, 15–22 turns each, covering discovery, thin answers, repair, contradictions, geo delay, hostile openers, bilingual code-switch, rush-to-project, etc.

```bash
.venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/post-fix
.venv/Scripts/python eval/analyze_post_fix.py post-fix-v2
.venv/Scripts/python -m pytest apps/api/tests/test_determinism.py apps/api/tests/test_student_ux.py apps/api/tests/test_reliability_regressions.py -q
```

Assertions A1–A12 in `assert_suite()` — see eval-findings doc for definitions.

**Note:** Harness A2 counts only `question_policy` `question_target_selected` events (not planner duplicates).

---

## 14. Local development

See [local-development.md](local-development.md):

```bash
docker compose up -d postgres
# apply new migrations on existing volume:
docker compose exec -T postgres psql -U scratly -d scratly < migrations/011_eval_fix_trace_events.sql
cd apps/api && uvicorn app.main:app --host 127.0.0.1 --port 8000
cd apps/web && npm run dev
```

On Windows, set `PYTHONIOENCODING=utf-8` when running the eval suite (scenario titles contain Unicode arrows).

---

## 15. Key file index

| Concern | Path |
|---|---|
| Turn orchestration | `apps/api/app/services/turn_processor.py` |
| Stage + repetition + planner | `apps/api/app/services/question_policy.py` |
| Elicitation | `apps/api/app/services/elicitation_policy.py` |
| Thin detection | `apps/api/app/services/thin_answer.py` |
| Geo | `apps/api/app/services/location_policy.py` |
| Grounding | `apps/api/app/services/grounding_validator.py` |
| Reducer | `apps/api/app/services/profile_reducer.py` |
| Contradictions | `apps/api/app/services/contradiction_engine.py` |
| Persistence | `apps/api/app/repository/assessment.py` |
| LLM + audit | `apps/api/app/services/azure_openai.py` |
| Eval harness | `scripts/eval_conversation_suite.py` |
| Post-fix analysis | `eval/analyze_post_fix.py` |

---

## 16. Known limitations (post eval-fix v2)

Documented in [eval-findings-and-fix-plan.md](eval-findings-and-fix-plan.md):

- **Repetition (A2):** hard-stop helps but constraints/capability loops can still exceed threshold 4 under live LLM variance.
- **Stage latch:** Maya-class sessions may stay in `measurement` when capability/assets remain `unknown` despite rich scripts.
- **Eval wall clock:** ~65–80 min full suite serial at ~9–26s/turn depending on Azure load.
- **Infra flakes:** occasional client timeout (`Errno 22`, turn timeout) on long runs — re-run affected `--only` scenarios.

These are tracked by the self-proving harness, not by narrative alone.
