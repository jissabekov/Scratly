# Student model (V1)

Human-auditable profile used to design course projects (app / product / website).
Numeric ladders are behavioral evidence scores — not personality decimals.

The model predicts project fit; it does not assign a personality type. It has four layers: **attraction** (what repeatedly captures attention), **operating style** (how the student acts in context), **reward** (what sustains effort), and **project reality** (skills, access, people, time, willingness, environment, and broad location). Topics provide context, but a shared topic must never imply a shared project mode.

Each signal is unknown, provisional, established/supported, or contested/contradicted. State retains an estimate and separate confidence, supporting and contradicting evidence counts, evidence diversity, contextual tags, sources, and update boundary. Evidence retains type, polarity, strength, extraction confidence, exact quote, source messages, acceptance decision, and rejection reason. Reliability descends from repeated behavior and concrete examples through tradeoffs and stated preferences to self-description and hypotheticals. An insufficient answer is missing information, never negative evidence.

Conditional signals are first-class: for example, leadership in a high-interest, concrete group can coexist with avoidance of mandatory, unfocused group work. Contradictions remain explicit until a follow-up identifies the context; they are never averaged into a meaningless midpoint. Capabilities and feasibility change project scope, scaffolding, or eligibility—not a student's worth.

The application also maintains a private probability distribution over currently plausible project modes. Question selection reduces uncertainty only when it can change that distribution or resolve a required constraint. Numeric internal state and project probabilities are teacher-only.

Related: [scoring-rules.md](scoring-rules.md) · [conversation-policy.md](conversation-policy.md) · [docs index](README.md)

---

## Profile shape

```json
{
  "interests": [{"topic": "basketball", "score": 4, "evidence_count": 3, "examples": ["..."], "status": "supported"}],
  "work_modes": {"investigate": 3, "build": 2, "organize": null, "communicate": 4},
  "work_mode_status": {"investigate": "supported", "build": "provisional", "organize": "unknown", "communicate": "supported"},
  "motivation": {"primary": "competition_achievement", "secondary": "recognition_influence", "status": "provisional"},
  "execution": {"persistence": 3, "ambiguity_tolerance": 2, "outreach_willingness": null, "public_visibility": 4},
  "capabilities": [{"name": "video_editing", "level": 3, "evidence": "..."}],
  "assets": ["plays organized basketball"],
  "constraints": {"geo": ["remote_ok"]}
}
```

**UNKNOWN ≠ 0.** A never-discussed facet stays `null` / `unknown`. Zero means positive evidence of avoidance or strong dislike.

---

## Dimensions

| Key | Required | Role |
|---|---|---|
| `topics` | yes | Interests with depth score 0–4 |
| `work_mode` | yes | Investigate / Build / Organize / Communicate (each 0–4 or null) |
| `motivation` | yes | Primary + secondary reward from five keys |
| `capability` | no | Skills 0–3 (scaffolding only) |
| `constraints` | yes | Must-haves + geo value keys |
| `execution` | yes | Persistence, ambiguity, outreach, visibility (0–4 or null) |
| `assets` | no | Freeform access (no numeric score) |

Legacy dims **removed:** `collaboration`, `challenge`, dimension `impact`.

### Interest depth (0–4)

| Score | Meaning |
|---|---|
| 0 | Actively dislikes / avoids |
| 1 | Mild interest; occasional consumption |
| 2 | Repeated voluntary time |
| 3 | Actively participates / creates / practices |
| 4 | Sustained deep involvement + substantial knowledge |

### Work modes (0–4 each)

`investigate` · `build` · `organize` · `communicate`

### Motivation rewards (exactly five)

`discovery_mastery` · `competition_achievement` · `impact_usefulness` · `recognition_influence` · `belonging_responsibility`

Store primary + secondary only.

### Execution (0–4)

`persistence` · `ambiguity_tolerance` · `outreach_willingness` · `public_visibility`

Used as **PASS/FAIL gates** in matching. Unknown does not fail a gate.

### Capabilities (0–3)

Extensible skill names. Affect scaffolding (`scaffold:…`), never eligibility.

### Assets / access

Freeform strings. No score.

---

## Status

| Status | Meaning |
|---|---|
| `unknown` | No accepted evidence |
| `provisional` | Thin / single-example evidence |
| `supported` | Repeated behavioral evidence |
| `contradicted` | Open true conflict |

---

## Evidence

Proposals include `dimension_key`, optional `value_key`, `polarity`, `strength` (0–1 mapping confidence), optional `score_band` (0–4 behavioral ladder), owned `source_message_ids`, and `exact_source_quote`.

Motivation keys must be in the five-reward vocabulary. Work-mode values must be the four facets. Each evidence item also carries an `evidence_type` (repeated_behavior → behavioral_example → forced_tradeoff → stated_preference → self_description → hypothetical), an extraction `confidence`, and optional `context_tags`; the reducer weights facet buckets by reliability × confidence.
