# Plan 07 — Conversation quality: planner directive v2 + writer turn-contract

**Status:** in implementation
**Trigger:** live UX feedback — chat abruptly changes topics, asks weird questions, lacks continuity.
**Basis:** full pipeline map (`turn_processor.py`, `question_policy.py`, `context_builder.py`, `question_quality.py`, `elicitation_policy.py`, `thin_answer.py`, `repository/assessment.py`) + external research (MockMate, Parlant, Rasa CALM, Pipecat Flows, STORM, Copilot Studio, CHI 2020 active-listening study, ENLG 2015 topic-transition strategies, Gallup/NORC probing norms).

**Hard invariants (unchanged):** LLMs propose; reducer owns state; raw messages are truth; decision events append-only; no new migrations (all counters/columns exist); `complete` stays terminal; no eval-threshold changes. **No eval-suite runs in this plan** — gates are unit tests + lint/typecheck + build; the user tests by hand.

---

## 1. Diagnosis (evidence → symptom)

| # | Root cause | Evidence | Symptom |
|---|---|---|---|
| R1 | Breadth-scan forces SWITCH at `depth>=2` (`topic_budget_reached`), `>=3` (`follow_up_exhausted`), on any `INSUFFICIENT` reply (`branch_yield_collapsed`); family `consecutive>=2` exposure cap; follow-ups nearly unwinnable in scoring (~0.27 vs ~0.77 fresh dim) | `question_policy.py:169-265, 306, 347-374, 393-411` | Abrupt topic changes mid-thought |
| R2 | `plan_next` is text-blind — only counters + regex on current message; continuity = one 0.10 field | `turn_processor.py:706-712`, `assessment.py:1083` | Can't see a rich thread worth one more probe |
| R3 | Ordinary reply = bare question; prompt r3 "acknowledgment optional", r16 "never add a follow-up… merely to preserve continuity"; SWITCH gets no transition | `turn_processor.py:1049-1150`, `question_writer/v3` rules 3/16, `assessment.py:1819-1821` | No acknowledgment; silent pivots |
| R4 | Contradictions replace the entire candidate pool, exempt from all caps; fallback text leaks `snake_case` value keys | `question_policy.py:422-424, 355, 649-662` | Cross-examination hijack; weird wording |
| R5 | Canned text ships on writer-fail / quality-gate-override / dedup — incl. `32767`-wrong pivots like `"Different angle on the same thing:"` after a topic change; `assistant_prefix` wiped | `turn_processor.py:138-143, 1285-1290`, `question_quality.py:59-128` | Weird/non-sequitur questions |
| R6 | Elicitation `pending_key` survives planner SWITCH → chips for a *different* family; facet banks unreachable (`execution:*`) | `turn_processor.py:823-835`, `elicitation_policy.py:114-120` | Random option chips mid-topic |
| R7 | `student_answer`/`refusal` prefix + blind next target appended | `turn_processor.py:401-430` + `assessment.py:1819-1821` | Answer about A → unrelated question about B |
| R8 | `matching_unavailable` bumps exposure for an unrealized target; abort lines rotate ignoring input | `turn_processor.py:1195-1262` | Dead-end loop |
| R9 | `memory` passed as whole row wrapper; `curated_intent` always `None` (BY_KEY keys ≠ target keys); no asked-questions ledger in writer context | `context_builder.py:45-87`, `question_library.py` | Composer under-informed → context mismatch (Copilot-documented failure mode) |
| R10 | `uncompacted_tokens` counts the WHOLE transcript → compactor runs every turn past ~6k tokens | `turn_processor.py:1591` | Wasted LLM calls, latency |

## 2. Design (pattern borrowed from MockMate/Parlant/Rasa)

The architecture stays **deterministic planner → binding directive → LLM writer** — the mainstream production split. The fix is giving the directive the fields the writer actually needs (MockMate `<orchestrator_directive>`, Rasa "active slot"), decomposing the writer output into a turn contract (Parlant ARQ + canned-preamble ack), and letting topics close gracefully instead of hard-switching (ENLG 2015: marked transitions beat silent ones).

### PlannerDecision v2 (extends `question_policy.py:130-136`)
```python
@dataclass(frozen=True)
class PlannerDecision:
    target: Target
    action: PlannerAction
    phase: DiscoveryPhase
    reason: str
    avoid_topics: tuple[str, ...] = ()
    # NEW:
    closure: bool = False              # exiting a topic after budget → micro-summary beat
    acknowledgment: str = "auto"       # none|brief|repair|validate|auto (planner owns the decision)
    collect: str | None = None         # student-vocabulary goal ("which game", "what kept you going")
    bridge_hint: str | None = None     # planner-owned transition seed for non-FOLLOW_UP actions
    probes_left_on_key: int = 0        # budget transparency for writer + gate
```

### `QuestionResponse` v2 (`contracts/assessment.py:150`)
```python
class QuestionResponse(StrictModel):
    student_point: str | None          # <=160, one clause: what the student's last message said
    acknowledgment: str | None         # <=160, required iff directive.acknowledgment != none
    bridge: str | None                 # <=140, required iff action in {SWITCH, BRIDGE, CLARIFY, GATE} w/ bridge_hint
    question: str                      # 1..320 — the ask (existing rules)
```
Server assembles `text = " ".join(filter(None, [ack, bridge, question]))` — **storage/transport contract unchanged** (still one assistant message string). `student_point` is the ARQ reasoning-echo: forces the model to ground the reply in the student's actual last message before composing; the quality gate can string-match it.

### Writer context additions (`context_builder.question_writer`)
- `asked_questions`: last 12 `{target_key, text}` from `assessment.questions` ⨝ messages (cheap — `asked_by_key` query already runs per turn; extend to fetch text).
- `memory`: unwrap to `content` only (stable_preferences/commitments/unresolved_threads/boundary_sequence).
- `planner_decision`: extended fields above.
- `curated_intent` fixed: `question_library` gets a `BY_TARGET` map (target key → intent), reviving question_class guidance and supplying `collect`/`bridge_hint` seed text.
- `post_answer_pivot: bool` when `assistant_prefix` exists (student-answer turn) → writer must bridge from the answer to the new target.

### Prompt `question_writer/v4` (new version dir — v3 kept untouched)
Rewrite around the turn contract; keep the good hard rules (no stacked questions, no jargon, repair corrections, autonomy protection, ≤320 chars). Per-action table:

| action | ack | bridge | question targets |
|---|---|---|---|
| FOLLOW_UP | auto/brief | none | same subject, deeper |
| BRIDGE | brief | required (use bridge_hint semantics) | new target, linked category |
| SWITCH + closure | brief micro-summary of the closed topic | required metatalk ("Different direction —") | new target |
| SWITCH (rejection/friction) | repair | required | new target, drop rejected premise |
| CLARIFY | validate ("both can be true") | required | the two sides, humanized |
| GATE | brief | optional | the hard variable |

## 3. Workstreams

**W7.1 Contracts** — `QuestionResponse` v2 + `AckMode`/`BridgeMode` as plain strings (keep StrictModel); `QuestionWriter.write` returns the full response; assembly + pairing validation.

**W7.2 Planner decision v2** (`question_policy.py`):
- Extend `PlannerDecision` (new fields above, all defaulted — back-compat).
- `plan_next(student_text, last_target_key, ..., last_turn_accepted: bool)` — new param fed by caller's `accepted_count>0`. Semantic-stay rule: when budget would force `topic_budget_reached` but the last ask on this topic yielded accepted evidence, allow depth up to `ABSOLUTE_MAX_TOPIC_DEPTH` (one extra probe) before switching; trace the reason `topic_yielding_extended`.
- On every forced SWITCH (budget/yield/exhaustion): `closure=True`, `acknowledgment="brief"`, `bridge_hint` seeded from target's intent.
- BRIDGE gets `bridge_hint` always; CLARIFY gets `acknowledgment="validate"`.
- `select_next`: contradictions no longer replace the pool — they stay in `candidates` with a `contradiction_resolution` value boost (they normally win), BUT a contradiction whose dim was the *immediately previous* target is deferred one turn unless the student explicitly raised it (prevents consecutive cross-examination; dismissal lifecycle `_MAX_CLARIFICATION_ATTEMPTS` unchanged).

**W7.3 Humanized contradiction wording** — `question_policy.py:649-662` `contradiction_fallback` + `_seeded_for`: map `value_key` → human label via `elicitation_policy` option banks where available; fallback wording via writer path preferred; template becomes "Earlier you said X, and just now Y — which fits better?" style with real labels, never raw keys.

**W7.4 Elicitation pending-key fix** (`turn_processor.py:823-835`): pending key only continues while `pending_key == elicitation_dimension_family(target.key)`; on family mismatch → clear pending, restart `attempts=1` on the current family. Chips always describe the dimension just asked.

**W7.5 Dedup transitions** (`turn_processor.py:138-143, 1285-1290`): `_transition_line(action, rotation, question)` — per-action line banks; never assert "same thing" on SWITCH; keep prefix-wipe (prevents stacked text).

**W7.6 Writer context** (`context_builder.py` + `repository/assessment.py`): `tx.asked_questions(limit=12)`; `memory` → `content` only; `post_answer_pivot`; `planner_decision` extended; `curated_intent` via `BY_TARGET`.

**W7.7 Exposure bug** (`turn_processor.py:1251-1262`): exempt `matching_unavailable` (and any kind whose question was replaced by canned text) from `_bump_exposure`.

**W7.8 Compaction bug** (`turn_processor.py:1591`): `uncompacted_tokens` counts only messages with `sequence > latest snapshot boundary` (extend `student_response_stats` to return `last_boundary_sequence`).

**W7.9 Prompt v4** (`prompts/question_writer/v4/system.txt` + call-site bump in `azure_openai.py`): turn contract, per-action table, ack-uniqueness rule (pass last assistant texts tail), keep rules on jargon/autonomy/corrections. `LocalFallbackLLM` path unchanged (templates still answer `{question}` shape).

**W7.10 Quality gate pairing** (`question_quality.py`): validate `acknowledgment is None ↔ directive.acknowledgment=="none"`; `bridge` present iff required; `student_point` present (warn-only); existing rewrites unchanged.

## 4. Test plan (per workstream; no eval runs)

- Unit: `test_question_policy.py` — decision v2 fields per action; semantic-stay extension; contradiction deferral; elicitation family reset; exposure exemption; asked_questions query; compaction boundary math.
- Contract: `QuestionResponse` parse, assembly, pairing validation.
- Prompt: versioned dir exists, call-site loads v4.
- Gates: `pytest apps/api/tests -q` (all 263+ new green), `ruff`, `mypy`, `compileall`, `npm run build`, `test:e2e` subset (student-chat/learning-chat).
- Manual: user drives a live session.

## 5. Rejected / out of scope

- No new LLM calls in the hot path (latency budget already p50≈5.5s; `student_point` echo rides inside the existing writer call — zero extra requests).
- No migration — all new state fits existing `core.sessions` counters + in-memory decisions.
- No eval-threshold or assertion changes; no assessment-semantics changes (planner decisions are presentation/ordering, evidence path untouched).
- `matching_unavailable` redesign limited to the exposure-bug fix — the abstain loop stays deterministic by design (A-assertions depend on it).
