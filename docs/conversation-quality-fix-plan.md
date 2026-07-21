# Conversation quality fix plan

**Status:** implemented (proven with live Azure traces) — **living behavior docs are now** [README.md](README.md), [architecture.md](architecture.md), [scoring-rules.md](scoring-rules.md), [conversation-policy.md](conversation-policy.md), and [conversation-quality.md](conversation-quality.md).

**Based on:** live 5-turn Azure sim `18b70c75-64c8-4d85-ae7c-cda74b04b2f3` (`sim-conversation-dump.json`)  
**Latest proof:** `sim-final-proof.json` (14-turn Maya + conflict probe, 2026-07-21)  
**Goal (achieved):** Keep the frozen architecture (LLM proposes; reducer owns state; raw messages are source of truth) while making assessment conversations *technically correct* and *qualitatively good* over long sessions.

This file remains the design/acceptance record for workstreams W1–W8. Prefer the living docs above for day-to-day “how it works.”

---

## 1. Problem statement

The sim proved the write path works (messages, evidence, snapshots, 45 decision-trace events, resume). It also proved the conversation product fails:

| Failure | Symptom in sim |
|---|---|
| False contradictions | `curiosity`+`impact`, `neighborhood_data`+`science_projects`, multi-skill capability flagged as conflicts |
| No resolution loop | 6 open contradictions, 0 resolved; stage stuck in `gap_resolution` |
| Premature stage jump | Turn 1: `discovery` → `gap_resolution` because coverage hit `1.0` while contested still counts as “known” |
| Weak questions | Turns 2–3 reused generic “I heard two different preferences…” |
| Audit gap | `audit.llm_runs` empty; all decision events have `llm_run_id = null` |
| Long-context gap | `MemoryCompactor` exists but is never called; writer sees only last 6 messages |

Without fixes, longer conversations will not get better — they will accumulate contested dimensions and keep asking unresolved contradiction questions.

---

## 2. Non-negotiable constraints (architecture)

Do **not** violate these while implementing:

1. **No direct LLM profile mutation** — models propose evidence or phrase a selected question only.
2. **Raw messages are source of truth** — memory snapshots are disposable aids regenerated from bounded raw transcript.
3. **Complete explainability** — every profile transition has snapshot, change record, reducer version, and accepted evidence linked to quotes.
4. **Application owns policy** — stage, target priority, and contradiction resolution rules stay deterministic in code/DB, not in the model.
5. **Decision events remain append-only** — corrections are later events, never edits.

---

## 3. Qualitative bar (what “high quality” means)

A good assessment conversation must:

1. **Discover before it adjudicates** — early turns gather breadth; contradiction questions only when values are genuinely incompatible.
2. **Ask one clear job per turn** — name the conflict or gap; never vague “two preferences.”
3. **Acknowledge and advance** — each student answer either fills an unknown, strengthens a provisional, or *closes* an open contradiction.
4. **Preserve nuance** — “small group for brainstorming, alone for coding” is enrichment, not a fight.
5. **Stay coherent over time** — later questions use profile + memory + recent messages so early context is not forgotten.
6. **Exit stages deliberately** — reach `profile_review` / `project_matching` when coverage is real and conflicts are resolved or dismissed with reason.

**Teacher-facing quality check:** a teacher reading the transcript should always understand *why* the next question was asked from the decision-trace alone.

---

## 4. Workstreams

### W1 — Contradiction semantics (correctness of “conflict”)

**Root cause:** `find_contradictions` treats any two distinct *support* `value_key`s on the same dimension as a conflict. Compatible multi-valued signals become contested immediately.

**Design:**

1. Split dimensions into cardinality modes (seeded in DB or code config):
   - **single_choice** (e.g. primary motivation when forced): competing supports may conflict.
   - **multi_value** (topics, capability, constraints tags): multiple supports coexist; conflict only for explicit oppose-vs-support on the *same* `value_key`, or for declared incompatible pairs.
   - **structured** (collaboration / work_mode): allow compound values or facet keys (e.g. `brainstorming=small_group`, `coding=independent`) instead of flat rivals.

2. Replace naive set-size check with:

```text
conflict if:
  (same value_key AND support+oppose both present)
  OR (dimension is single_choice AND ≥2 incompatible support values)
  OR (pair listed in incompatibility table)
else: coexisting evidence, not contested
```

3. Add `assessment.value_incompatibilities(dimension_key, value_a, value_b)` (or code table in `contradiction_engine.py` v2) for true rivals only (e.g. `work_mode: large_group` vs `solo_only` if those keys exist). Prefer **few** rows; default is compatible.

4. Bump contradiction engine / reducer version (`v2`) and record it on snapshots.

**Acceptance:**

- Replaying Maya turn 1 does **not** open motivation or topics contradictions for curiosity+impact / neighborhood+science.
- Capability python+spreadsheets+oppose(full_web_app) does **not** open a capability contradiction.
- Explicit “I prefer X not Y” *does* open or reinforce a conflict.

**Tests:** unit matrix in `test_determinism.py` / new `test_contradiction_semantics.py`.

---

### W2 — Contradiction resolution (exit `gap_resolution`)

**Root cause:** `resolve_with_newest` exists but is never called from `process_student_turn`. Open rows persist forever; policy always selects `priority_contradiction`.

**Design:**

1. When the previous assistant question had `intent_key=contradiction` and `target_key=D`, treat the new student turn as a **resolution attempt for D** unless extractor finds no usable clarifying evidence.

2. Resolution rules (deterministic, documented in `docs/scoring-rules.md`):
   - Prefer **explicit newest** accepted evidence that picks one side or introduces a compound/compatible value.
   - Mark contradiction `resolved` with `resolution`, `resolved_by_evidence_id`, `resolved_at`.
   - Update coverage for `D` from `contested` → `established` or `provisional` per reducer.
   - Emit decision event: `contradiction_resolved` with reason code `explicit_newest` / `compatible_merge` / `dismissed_not_conflict`.

3. If the student refuses or stays ambiguous, keep open **once**, then allow `dismissed` after N failed clarification attempts (config, default 2) with reason `unresolved_after_clarification` so the session can progress (teacher can revisit).

4. Do **not** average competing strengths (preserve HARD RULE / scoring-rules).

**Acceptance:**

- After a clear answer to a contradiction question, open count decreases.
- Stage can leave `gap_resolution` when `contradictions==0` and coverage policy is satisfied.
- Decision-trace shows resolve events with entity refs to contradiction + evidence IDs.

**Tests:** integration turn A (create conflict) → turn B (resolve) → assert DB status.

---

### W3 — Stage & coverage pacing (discovery before adjudication)

**Root cause:** coverage = fraction of required dims with status `<> unknown`. Contested counts as known → coverage `1.0` on turn 1 → stage jumps to `gap_resolution` as soon as any contradiction exists.

**Design:**

1. Redefine coverage inputs for `derive_stage`:
   - `coverage_established` = required dims with status `established` / total required.
   - Optionally keep `coverage_touched` for UI only.
2. Stage policy (keep priority order; adjust thresholds):

```text
if projects_ready and reviewed → complete
if reviewed → project_matching
if open_contradictions > 0 and coverage_established >= 0.5 → gap_resolution
   else if open_contradictions > 0 and still early → stay measurement/discovery
      but still allow contradiction target in question priority
if coverage_established >= 0.9 and contradictions == 0 → profile_review
if coverage_touched >= 0.4 → measurement
else → discovery
```

Exact thresholds belong in `question_policy.derive_stage` + tests; document in `conversation-policy.md`.

3. Question policy: even in discovery/measurement, contradictions remain highest *target priority*, but **writer tone** and **how many contradiction questions in a row** should be gated (see W5) so early chat is not only adjudication.

**Acceptance:**

- Sparse first message → stay in `discovery` or `measurement` unless a *true* hard conflict is present.
- Session with all required established and 0 open contradictions reaches `profile_review`.

---

### W4 — Evidence extraction quality

**Root cause:** extractor prompt is a stub; model invents fine-grained value keys and over-proposes (6 items from one greeting). Grounding only checks quote substring ownership — not taxonomy membership or over-extraction.

**Design:**

1. Expand `apps/api/prompts/evidence_extractor/v1/system.txt` (or `v2`) with:
   - Allowed dimensions and value vocabularies (from taxonomy context already passed in).
   - Prefer **minimal** evidence: 1–3 high-confidence items unless the student stated multiple distinct facts.
   - Multi-value dims: emit multiple supports *without* implying conflict.
   - Do not invent oppose polarity unless the student negated something.
   - Map free text to closest taxonomy keys; if none fit, omit or use controlled `other_*` only when schema allows.

2. Post-validate in application (deterministic):
   - Reject unknown `dimension_key` / `value_key` with reason `taxonomy_value_not_allowed`.
   - Cap proposed items per turn (e.g. 5) via validator or packet trim with reason `excess_proposals_trimmed` logged in trace.
   - Optional: merge near-duplicate quotes.

3. Keep grounding checks; add strength clamp and require non-empty quote.

**Acceptance:**

- Maya turn 1 yields ≤3 accepted items, no false oppose, taxonomy-valid keys.
- Decision-trace shows rejection reason counts when model drifts.

---

### W5 — Question writing quality

**Root cause:** fallback template leaked into model style (“I heard two different preferences”); writer context lacks the concrete conflicting values; prompts are stubs.

**Design:**

1. Expand `question_writer` prompt v2:
   - Must name the target dimension and the **specific options** from context.
   - One question only; teen-appropriate; no therapy tone; no stacked questions.
   - For `contradiction`: present A vs B (or “both in different situations?”) when nuance is plausible.
   - For discovery/required: open but concrete (“What’s a recent project you enjoyed and why?”).
   - Forbidden: generic “two preferences,” repeating the previous assistant question verbatim.

2. Enrich writer context in `ContextBuilder.question_writer`:
   - Include `target_kind`, `target_key`, open contradiction sides (`value_a`, `value_b`, quote snippets by ID only or short quotes already allowed in writer context policy).
   - Include last assistant question so the model can avoid repeats.
   - Pass memory snapshot + public profile (already planned).

3. Application-side **quality gate** before persist:
   - If question equals fallback template and Azure succeeded, prefer regenerating once or substituting a richer seeded template that includes the two values.
   - Detect near-duplicate of previous assistant message → force alternate seeded template.
   - Record `question_quality_gate` in decision-trace (`passed` / `regenerated` / `seeded_override`).

4. Improve seeded fallbacks in `assessment.question_intents` so fallbacks themselves name the dimension (parameterized templates in code: `"For {dimension}, do you lean toward {a} or {b}?"`).

**Acceptance:**

- No assistant message equals the generic contradiction fallback when conflicting values are known.
- Turns 2–3 style questions fail the gate in regression fixtures.

---

### W6 — Decision audit completeness

**Root cause:** `get_llm()` uses `audit_writer=None` (“bind later”).

**Design:**

1. Bind `AssessmentRepository.record_llm_run` (or a thin wrapper) when constructing Azure client per request/turn.
2. Call `set_turn_context(session_id, turn_id)` at turn start.
3. Pass `llm_run_id` into `DecisionTraceRecorder.record` for `evidence_proposed` and `question_written` (and memory compact when added).
4. Never store student text in `llm_runs`; keep metadata only (deployment, prompt version, response id, usage, error).

**Acceptance:**

- Live turn creates ≥1 `audit.llm_runs` row per successful Azure call.
- Decision-trace events for extract/write reference non-null `llm_run_id`.

---

### W7 — Long conversation persistence & continuity

**Root cause:** transcript persists, but writer context is truncated and compaction is unwired.

**Design:**

1. Wire `MemoryCompactor` into `process_student_turn` after persist (or end of successful turn), when `due(responses_since_snapshot, token_estimate)`.
2. Persist to `conversation.memory_snapshots` with `boundary_sequence`; regenerate from raw messages through boundary only (HARD RULE 2).
3. Compaction failure is non-fatal (existing behavior); keep prior snapshot.
4. Writer context: recent raw window (keep ~6–10 messages) **plus** latest memory snapshot summary fields.
5. Extractor continues to use `allowed_messages` (owned raw only) — never memory as evidence source.
6. Optional later: increase recent window slightly for contradiction turns.

**Acceptance:**

- After ≥8 student responses, a memory snapshot row exists.
- A resumed session at turn 20 still asks coherent questions referencing early established profile values.
- Idempotent retries do not duplicate snapshots for the same boundary.

---

### W8 — Conversation strategy (product quality)

Technical fixes alone are not enough. Encode a lightweight dialogue strategy in policy + writer context:

| Stage | Student experience | System behavior |
|---|---|---|
| discovery | Warm, concrete, one topic at a time | Prefer required unknowns / project-critical; limit contradiction questions to true incompatibilities |
| measurement | Deepen provisional dims with examples | Provisional + discrimination targets |
| gap_resolution | Explicit choices; allow “both, differently” | Resolve or dismiss; max 2 clarifications per contradiction |
| profile_review | Reflect back a short accurate summary | Validation intent; student corrections become new evidence |
| project_matching | Compare 2–3 fits with tradeoffs | Discrimination + constraints gates |

Add `docs/conversation-quality.md` (short) describing tone, forbidden patterns, and examples of good/bad questions. Keep `conversation-policy.md` for machine priority/stage.

**Anti-patterns to ban in prompts + gates:**

- Asking a contradiction when values are compatible facets
- Ignoring the student’s last answer
- Repeating the same question text
- Jumping to projects before required dims are established and conflicts cleared
- Multiple questions in one assistant message

---

## 5. Implementation sequence

Ship in order so each phase is demonstrably better in a live sim.

| Phase | Workstreams | Outcome |
|---|---|---|
| **P0 — Correctness** | W1, W2, W3 | False conflicts gone; contradictions can close; stage pacing sane |
| **P1 — Talk quality** | W4, W5, W8 | Evidence disciplined; questions specific; policy/docs aligned |
| **P2 — Operability** | W6, W7 | Full audit trail; long sessions resumable with memory |
| **P3 — Hardening** | eval harness below | Regression suite + golden live sim checklist |

Do not start P2 polish before P0: longer audited conversations that still cannot resolve conflicts will look worse, not better.

---

## 6. Evaluation & acceptance harness

### 6.1 Automated

1. **Unit:** contradiction semantics matrix; stage derivation table; resolution transitions.
2. **Determinism:** same accepted evidence → same profile snapshot (existing invariant).
3. **Integration (API + Postgres):** scripted Maya-like transcript:
   - Assert no false open contradictions after turn 1.
   - Assert resolution on clarifying turn.
   - Assert `llm_run_id` present when Azure configured (or skip marker when fallback LLM).
4. **Question gate fixtures:** fixed writer inputs must not emit banned generics.

### 6.2 Live qualitative checklist (run after each phase)

Re-run a ≥12-turn live Azure sim (not 5) with diverse student moves: enrichment, true conflict, walk-back, skills nuance, constraint.

Pass only if:

- [ ] Transcript readable and non-repetitive
- [ ] Every contradiction question names real options
- [ ] Open contradictions trend down after clarifications
- [ ] Stage path includes meaningful `discovery`/`measurement` before forced gap loop
- [ ] Profile at turn 12 matches human judgment of the student
- [ ] Resume mid-session and continue 5 more turns without amnesia
- [ ] Decision-trace + `llm_runs` explain every Azure call
- [ ] Memory snapshot created when due
- [ ] Zero seeded fallbacks when endpoint/credentials correct

Dump format can extend `sim-conversation-dump.json` with assertions report.

### 6.3 Teacher UX

On teacher console, surface: open vs resolved contradictions, why-next-question, and last resolve reason — so humans can spot false conflicts quickly during dogfood.

---

## 7. Concrete code touchpoints

| Area | Primary files |
|---|---|
| Contradiction detect/resolve | `apps/api/app/services/contradiction_engine.py`, `repository/assessment.py` (`apply_evidence_reduce_contradictions_snapshot`) |
| Stage/targets | `apps/api/app/services/question_policy.py`, `repository/assessment.py` (`stage_inputs`, `question_candidates`) |
| Turn orchestration | `apps/api/app/services/turn_processor.py` |
| Extract/write prompts | `apps/api/prompts/evidence_extractor/**`, `apps/api/prompts/question_writer/**` |
| Writer context / gate | `apps/api/app/services/context_builder.py`, new small `question_quality.py` |
| LLM audit | `apps/api/app/deps.py`, `azure_openai.py`, `decision_trace.py` |
| Memory | `memory_compactor.py` → wire in `turn_processor.py` + repo insert helper |
| Docs | this plan; update `conversation-policy.md`, `scoring-rules.md`, `student-model.md` |
| Tests | `apps/api/tests/test_*.py` + optional `scripts/sim_assessment_conversation.py` |

Migrations only if adding incompatibility tables, parameterized intent metadata, or new contradiction resolution columns (prefer reusing existing `resolution` / `resolved_by_evidence_id` first).

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Over-fitting incompat list | Default compatible; add pairs only from real false-negative dogfood |
| Dismissing real conflicts too fast | Cap dismissals; keep evidence; allow reopen on new oppose |
| Prompt-only fixes regress | Keep deterministic gates + unit tests as source of truth |
| Memory poisoning profile | Never feed memory into extractor/reducer; raw quotes only |
| Breaking explainability | Version engine/reducer; snapshot every transition |

---

## 9. Definition of done

The system is done for this plan when:

1. Technical: contradictions are rare and resolvable; stages progress; llm runs and memory are wired; traces remain complete.
2. Qualitative: a 12–20 turn live Azure conversation feels like a skilled counselor-assessor — specific, cumulative, non-repetitive — and a teacher can justify every question from the decision-trace.
3. Regression: Maya-style sim no longer stalls in `gap_resolution` with six false opens after five turns.

---

## 10. Suggested first PR slice (P0)

Smallest vertical that proves the product can recover:

1. Contradiction engine v2 (multi_value + support/oppose).
2. Resolve-on-answer path + decision event.
3. Stage coverage based on `established`, not merely non-unknown.
4. Tests + 5-turn and 12-turn sim scripts with assertions.
5. Doc updates to scoring-rules + conversation-policy.

Defer prompt wordsmithing (P1) and memory/audit (P2) to follow-up PRs once P0 green.
