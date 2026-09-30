# Plan 09 — Lesson explanations from the week markdown (Phase 9)

> **Status: PLANNED** · Owner: content + a thin renderer check · Depends on: Plan 03 (schema, seed, player) and Plan 08 (type and paragraph rendering for the acceptance screenshots)
> **Goal:** shared-module slides teach the mechanism. The source is the week markdown already in the repo. Punchlines stay one sentence. The slide schema, objective codes, and quiz banks stay as they are.

## 9.1 Non-goals

- Do not put the teaching source into `content/`. It is not there today. `content/modules/**` is JSON only (`module.json`, `quiz.json`, `checkins.json`). The markdown lives in `docs/AI_Course_Weeks_02-11/`.
- Do not paste teacher stage directions, minute-by-minute timings, “put this on screen”, or the in-class census into slides. Those are instructor notes. Slides get the student-facing mechanism: the question, what happens, the name of the concept, and the punchline that is already in the JSON.
- Do not rewrite `quiz.json` or `checkins.json`. Pass rule stays 4/5 and every critical objective. Explanations on `check` blocks stay the short reason the keyed answer is right; the lesson itself moves into `text` blocks.
- Do not add a block type, raise `max_length`, or add a migration. `Text` is already 1–4000 characters (`apps/api/app/contracts/learning.py`). A slide holds 1–3 blocks. `kind` must match the first block’s `type`.
- Do not renumber an existing slide or lesson `seq`. See §9.4.
- Archetype modules with no week file are out of scope until someone supplies source prose. See the table in §9.3.
- No prompt edits, no reducer edits, no `/eval-suite` run for copy changes.

## 9.2 Where content lives

| Piece | Path |
|---|---|
| Teaching source (markdown) | `docs/AI_Course_Weeks_02-11/week_02.md` … `week_11.md`. Index: `docs/AI_Course_Weeks_02-11/README.md`. |
| Slide JSON | `content/modules/<group>/<slug>/module.json` |
| Contract | `apps/api/app/contracts/learning.py` — `TextBlock.text`, `CalloutBlock.text`, `DiagramBlock.steps` (each step is `ShortText`, max 300), `WorkedExampleBlock.steps` (max 8, each `Text`), `CheckBlock` |
| Ids | `apps/api/app/services/learning_content.py` — `slide_id(lesson_id, seq)` is uuid5 of `slide:{lesson_id}:{seq}` |
| Seed | `scripts/seed_learning_content.py`. `--dry-run` validates and prints counts. A real run upserts and **deletes** slides whose ids are no longer in the file (`DELETE FROM learning.slides … AND NOT (s.id = ANY($2))`). `learning.slide_completions.slide_id` references `learning.slides` `ON DELETE CASCADE` (`migrations/017_learning_content.sql`). |
| Renderer | `apps/web/components/learn/SlideBlock.tsx` — one `<p>` per text block until Plan 08 W8.5 splits blank lines |
| Player | `apps/web/components/learn/LessonPlayer.tsx` |
| Validation tests | `apps/api/tests/test_learning_content.py` (`test_every_shipped_module_validates` parametrizes every `*/*/module.json`) |

`shared/` modules are expanded into every archetype plus `generic` by the seed. Edit the shared JSON once.

## 9.3 How thin the slides are

Measured from the shipped JSON (text + callout `text` lengths, characters). The week files are the lectures those slides were compressed from.

| Week file | Words | Module slug | JSON | Slides | Lessons | Avg text/callout chars | Min | Max |
|---|---:|---|---|---:|---:|---:|---:|---:|
| `week_02.md` | 4762 | `how-apps-work` | `content/modules/shared/how-apps-work/module.json` | 14 | 3 | 132 | 49 | 263 |
| `week_03.md` | 3969 | `how-apps-remember` | `content/modules/shared/how-apps-remember/module.json` | 14 | 3 | 175 | 55 | 347 |
| `week_04.md` | 4529 | `invisible-conversation` | `content/modules/shared/invisible-conversation/module.json` | 14 | 3 | 203 | 72 | 386 |
| `week_05.md` | 4236 | `frontend` | `content/modules/shared/frontend/module.json` | 14 | 3 | 227 | 59 | 396 |
| `week_06.md` | 4767 | `backend` | `content/modules/shared/backend/module.json` | 14 | 3 | 216 | 71 | 345 |
| `week_07.md` | 3360 | `databases` | `content/modules/shared/databases/module.json` | 14 | 3 | 250 | 64 | 481 |
| `week_08.md` | 3978 | `apis-integrations` | `content/modules/shared/apis-integrations/module.json` | 14 | 3 | 267 | 46 | 420 |
| `week_09.md` | 6369 | `files-and-search` | `content/modules/shared/files-and-search/module.json` | 14 | 3 | 214 | 76 | 394 |
| `week_10.md` | 3912 | `ai-models-agents` | `content/modules/shared/ai-models-agents/module.json` | 15 | 3 | 287 | 51 | 438 |
| `week_11.md` | 4215 | `production-reality` | `content/modules/shared/production-reality/module.json` | 15 | 3 | 288 | 126 | 524 |

`week_11.md` keeps the source heading **Week 13** (“Your Code Works. Now Make It Survive Reality.”). The module title is “Make It Survive Reality”. Treat them as the same lesson. Do not rename the slug.

Worked example of the gap, week 2. The markdown opens with the driving question “How does TikTok decide what to show you next?”, the action → event → request → state → computation → response loop, and the punchline “Software is not a screen. Software is a loop that responds to events and changes state.” The matching slide `how-apps-work` lesson seq 1, slide seq 1 (`kind: "text"`, title “Three seconds, then a swipe”) is one sentence:

> You watch a short video for about three seconds, then swipe away. The next video seems to guess something about you. What did the application actually receive in those three seconds?

Lesson seq 3, slide seq 1 stores the streak idea in one text block (about 180 characters) plus a callout whose `text` is “Events are what happened. State is what is true now.” The callout is the right length for a punchline. The text block is not long enough to teach state, timing rules, and why the emoji is only the render.

The same pattern repeats: a short `text` or `diagram` slide, often followed by a `callout` whose `title` is `"Punchline"` and whose `text` is one sentence. Diagram `steps` are labels (`ShortText`, max 300). They are not the explanation.

### Archetype modules with no markdown source

These files are three slides each (one text, one check, one punchline callout). Average text length is about 88–112 characters. No week file maps to them. Leave them until a source exists. Do not invent a lecture.

| JSON | Title |
|---|---|
| `content/modules/community_storytelling/story-craft/module.json` | Story Craft: Making Data Mean Something |
| `content/modules/generic/next-steps/module.json` | From Idea to First Step |
| `content/modules/local_investigation/field-work/module.json` | Field Work: Getting Useful Data |
| `content/modules/prototype_builder/shipping-a-prototype/module.json` | Shipping a Prototype |
| `content/modules/supportive_coordination/running-a-team/module.json` | Running a Team Without Running Yourself Down |

## 9.4 How to expand a slide without breaking ids

Prefer this order:

1. **Lengthen the existing `text` block** on that slide, same `seq`, same `kind`, same `objective`. One idea. Under 4000 characters. Two or three short paragraphs separated by a blank line, once Plan 08 W8.5 is in. Before that, keep a single paragraph or add a second `text` block (the slide may hold three blocks; the first block’s type must still match `kind`).
2. **Leave punchline callouts alone** except to fix a factual mismatch with the week file. They are the “name the concept” beat the week structure asks for (`Predict → Reveal → Challenge → Name`).
3. **Append a new slide** only when the idea does not fit the existing slide. Give it a new `seq` strictly greater than every current seq in that lesson. Do not renumber seq 1..n. New ids are new rows. Old ids stay, so completions stay.
4. **Never reuse a seq for a different idea**, and never insert at seq 2 by shifting the old seq 2 to seq 3. That changes `slide_id`, the seed deletes the old row, and completions cascade away.

`how-apps-work` lesson 1 slide 1 must remain `kind: "text"` so `e2e/learning.spec.ts` can press Continue on step 1. The hub link name “Behind the Swipe” must remain the module title.

Bump each edited module’s `version` string (today `1.0.0`) so the diff is reviewable. The seed does not branch on that field; tests only require it to be 1–40 characters.

Map each week section onto fields like this:

| Week markdown | Slide field |
|---|---|
| The mechanism paragraph after a reveal | `blocks[].text` where `type` is `text` |
| The one-sentence name-the-concept line | existing `callout` with `title` “Punchline” |
| A numbered flow the student should see | `diagram.steps` (one short label each, ≤300 chars) plus a real explanation in a `text` block on that slide or the previous one. `asset` may stay as a key; Plan 08 stops printing it as the picture |
| A fully worked trace (streak, seat 14C, one tool call) | `worked_example.steps` (already used; each step may grow up to 4000 chars, max 8 steps) |
| A prediction question | existing `check` — do not add a second check on the same slide |
| Timing table, teacher script, product census | do not import |

Shared objective `code` values stay (`events`, `state`, `loop`, `ai_component` on `how-apps-work`, and the codes already in the other nine files). New slides set `objective` to one of those codes. `test_every_shipped_module_validates` rejects an unknown code.

## 9.5 Work packages

**W9.1 — Week 2, the template.** Expand `how-apps-work` only. Read `week_02.md` beside the module. For each lesson, write the missing mechanism into the text blocks that already sit on that idea (swipe → event record, the loop, state vs emoji, where AI sits). Keep one idea per slide. Dry-run the seed. Read the player in the browser for this module only. Use the result as the pattern for W9.2.

**W9.2 — Weeks 3–11.** Repeat for the other nine shared modules, one module per change so a bad slide is easy to revert. Order: `how-apps-remember`, `invisible-conversation`, `frontend`, `backend`, `databases`, `apis-integrations`, `files-and-search`, `ai-models-agents`, `production-reality`.

**W9.3 — Reseed and read.** After `--dry-run` is clean, run the seed against local Postgres. Open one slide from each module at 1280px and 390px. A slide fails review if a student who has not read the week file still cannot say what the concept is and why the punchline follows.

## 9.6 Harness usage

| Harness | This phase |
|---|---|
| `/frontend-ui` | When checking the player against longer copy (line length, focus on the h2, action bar). Content JSON edits do not need a component rewrite. |
| Acquired `frontend-design` | Copy voice only: plain sentences, one job per line, active voice. It must not restyle tokens. |
| Acquired `web-design-guidelines` | “Resilient to long content” and “no dead ends” on a long slide. Run after W9.1, again at the end. |
| Acquired `shadcn` | Skip unless W8’s button work is still open. |
| Acquired `vercel-react-best-practices` | Skip. No data-fetch changes. |
| `/web-e2e` | Run the existing learning and quiz specs after the first module and again at the end. Update a selector only when the visible title actually changed, and keep the `goBack`, completion, and axe assertions. Do not delete them to go green. |
| `/verify` | Required. compileall + pytest. `test_learning_content.py` and `test_learning_quiz_content.py` must pass. Web build required because the player is how the copy is judged, even if TS did not change. |
| `/eval-suite` | Skip. Learning assertions A19–A23 do not depend on slide prose. Run them only if a quiz item or unlock rule changes, which this phase forbids. |
| `/state-report` | Once, when all ten shared modules are expanded and the master status flips. |
| `/research` | Skip. The source prose is already in `docs/AI_Course_Weeks_02-11/`. |
| `cursor-ide-browser` | Required for W9.1 and for a sample of W9.2. Open `/modules/<id>?session=&slide=1`, read the slide, advance, confirm the punchline still lands after the explanation. Check 390px for overflow. This is a reading pass, not a screenshot-only pass. |
| `cursor` MCP | `ReadLints` if TS changes. Otherwise skip. |
| `cursor-origin-readonly`, `cursor-app-control`, `cursor-subscriptions` | Skip. |
| `postgres` MCP | Optional after the real seed, to confirm slide row counts. If it is not attached, trust the seed script’s printed counts plus `GET /v1/sessions/{id}/learning/modules/{mid}`. |
| Seed | `.venv/Scripts/python scripts/seed_learning_content.py --dry-run` before every module lands. Real seed only after dry-run is clean and Postgres is up (`docker compose up -d --wait postgres`). |
| `/create-skill` (Cursor) | Skip. Phase 10 already decided the skill set. |

Quiz e2e that retries immediately needs the API started with `LEARNING_QUIZ_COOLDOWN_SECONDS=0` (root `AGENTS.md`). This phase should not need that path if quiz JSON is untouched. If a full `test:e2e` run includes the remediation spec, start the API that way rather than editing the spec.

## 9.7 Hard rules

1. LLMs may be used to draft slide sentences from the week file. A person or a follow-up read checks that the draft matches the markdown and introduces no new technical claim. The reducer is not involved. Nothing in this phase writes `assessment.*`.
2. Slide completion stays on `POST /v1/sessions/{id}/learning/slides/{sid}/complete` through the Server Action. Longer text does not change that contract.
3. Student quiz answers still do not write profile evidence.
4. Typed blocks only. No HTML, no markdown images, no raw `<script>` in JSON.
5. Do not weaken `test_every_shipped_module_validates` or the Playwright learning specs.
6. No new migration. No prompt version bump.
7. Week files mention real product names (TikTok, Snapchat, and so on) as classroom examples. Slides may keep those examples. Do not add student names, schools, or other PII, and do not send student chat transcripts to a model to “personalize” a slide.

## 9.8 Acceptance

- Each of the ten shared modules has text blocks that state the mechanism, not only the hook and the punchline. A reader can point at the week section each new paragraph came from.
- No existing slide `seq` changed. Append-only seqs if any new slides exist. `python scripts/seed_learning_content.py --dry-run` exits 0.
- `test_every_shipped_module_validates` passes for every `module.json`.
- `how-apps-work` slide 1 is still a text slide titled so the hub link “Behind the Swipe” and the Continue-on-step-1 e2e still apply.
- Archetype-only modules are unchanged.
- `/verify` and `npm --prefix apps/web run test:e2e` are green.
- Browser read of week 2 and at least one later week at 1280px and 390px, with no horizontal overflow and the punchline still visible after the explanation.

## 9.9 Risks

| Risk | Mitigation |
|---|---|
| A draft copies the whole 4,000–6,000 word lecture onto one slide | One idea per slide. Stop at the mechanism and the name. The schema’s 3-block cap will reject a dump only if someone tries to exceed it; the cap will not stop a 3,900-character wall. Review against the week section, not against the character max. |
| Renumbering seq to “make room” | Forbidden in §9.4. Dry-run does not catch this; it only validates shape. Diff `seq` values before seeding for real. |
| Shared JSON expands into every archetype | Expected. One edit updates every archetype’s copy of that module. Do not fork a second copy under an archetype folder. |
| Paragraph breaks invisible until W8.5 | Acceptance screenshots wait for Plan 08. W9.1 can still land single-paragraph text before that. |
| `quiz.json` `slide_ref` pointed at a seq that moved | Do not move seq, and do not edit quiz files, so refs stay valid. |
