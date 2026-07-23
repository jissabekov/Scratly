# Student model (V1)

Human-auditable profile used to design course projects (app / product / website).
Numeric ladders are behavioral evidence scores — not personality decimals.

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

Motivation keys must be in the five-reward vocabulary. Work-mode values must be the four facets.
