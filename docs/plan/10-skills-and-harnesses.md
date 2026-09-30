# Plan 10 — Skill acquisition and harness usage (Phase 10)

> **Status: DONE** (2026-09-30) · Owner: whoever starts Phase 8 · Depends on: Plan 02 (local `/frontend-ui` and `/web-e2e` already exist)
> **Goal:** put a small set of UI skills where agents will actually read them, and write down which harness runs at which gate. This phase installs skills and edits the two local skill files. It does not change the app, the CSS, or the lesson JSON.

Installed 2026-09-30. `npx skills add -a cursor` (skills CLI 1.7.0) wrote the four skills into `.agents/skills/` and labeled that path as the Cursor copy. No second copy under `.cursor/skills/`. `migrate-radix-to-base` was not installed. compileall + pytest 263 passed.

## 10.1 Non-goals

- Do not install skills into `~/.cursor/skills-cursor/`. Cursor’s `create-skill` skill reserves that directory for built-ins.
- Do not pass `-g` / `--global` to `npx skills`. That writes the user profile (`~/.cursor/skills/`), which will not travel with this repo.
- Do not replace `.devin/skills/frontend-ui/SKILL.md` or `.devin/skills/web-e2e/SKILL.md` with an upstream file. Extend them.
- Do not install the skills listed under “Leave these out” in §10.3.
- Do not change `apps/web`, `content/`, or `apps/api` in this phase.

## 10.2 What is already local

Repo skills (Devin layout, referenced by root `AGENTS.md` as slash commands):

| Skill | File | Role |
|---|---|---|
| `/verify` | `.devin/skills/verify/SKILL.md` | compileall + pytest + optional web build. Windows python is `.venv/Scripts/python`. |
| `/eval-suite` | `.devin/skills/eval-suite/SKILL.md` | Live conversation suite. The file still says 21 scenarios and A1–A18. Phase 6 extended the suite to 28 scenarios and A19–A23. When this phase touches the skill, update that description so agents do not stop at A18. Do not lower any threshold. |
| `/state-report` | `.devin/skills/state-report/SKILL.md` | Git timeline, pytest count, latest eval verdict, pending docs. |
| `/research` | `.devin/skills/research/SKILL.md` | Parallel web + GitHub research, then a short recommendation. |
| `/frontend-ui` | `.devin/skills/frontend-ui/SKILL.md` | Binding UI procedure: `apps/web/AGENTS.md`, `FlowActionBar`, tokens, a11y, Motion + `prefers-reduced-motion`, build + Playwright. |
| `/web-e2e` | `.devin/skills/web-e2e/SKILL.md` | Playwright: API seed, `?slide=` / `?q=` deep links, session id in localStorage, no weakened assertions. |

`apps/web/AGENTS.md` is always-on for web work. It already requires server components, Server Actions, URL search params for position, the canon tokens, shadcn, lucide, Motion, the bottom action bar, focus on the step heading, and `aria-live` step announcements. Third-party skills do not override it.

Cursor built-ins that matter here live under the user’s `skills-cursor` directory (`create-skill`, and the browser tools are MCP, not a skill). Read `create-skill` before adding a skill file by hand. Do not copy built-ins into the repo.

## 10.3 Skills to acquire

Verified against GitHub on 2026-09-30 (API listings and raw `SKILL.md` files). Install into the **project**, agent `cursor`.

The skills CLI documents Cursor’s project directory as `.agents/skills/` (`vercel-labs/skills` README). Cursor’s own `create-skill` doc says project skills live in `.cursor/skills/`. W10.1 resolves that with one trial install before the rest.

### Acquire

| Skill | Source | What it covers | When an agent reads it |
|---|---|---|---|
| `frontend-design` | https://github.com/anthropics/skills/tree/main/skills/frontend-design | Deliberate type, hierarchy, line length, and a critique pass. Warns against generic generated tells (all-caps eyebrows, arrow-suffixed links, Inter-like defaults). | Start of Plan 08 type work, and when judging Plan 09 copy on the page. **Canon hex tokens win** where the skill would push a new palette. The existing paper/ink/accent look stays. |
| `web-design-guidelines` | https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines | Review UI against the living rules in https://github.com/vercel-labs/web-interface-guidelines (`command.md`). Keyboard, visible focus, hit targets (24px, 44px on mobile), URL as state, Back/Forward, no dead ends, `prefers-reduced-motion`, links as `<a>`. | After Plan 08 edits, before claiming the phase done. Output is `file:line` findings. Fix the findings; do not argue the local a11y contract down. |
| `shadcn` | https://github.com/shadcn-ui/ui/tree/main/skills/shadcn | Add and compose shadcn components. This repo already has `apps/web/components.json` (`style: new-york`, `rsc: true`, `iconLibrary: lucide`). | When Plan 08 composes the ghost Back button. Use `npx shadcn@latest` only to **search or print docs**. Do not `init`, do not switch preset, do not hand-edit `components/ui/`. |
| `vercel-react-best-practices` | https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices | Next.js server/client performance: waterfalls, bundle size, Suspense, server actions. | When Plan 08 touches `app/layout.tsx` or a client boundary (`LessonPlayer`, `QuizRunner`, `StudentChat`, `SessionBootstrap`). Ignore `client-swr-dedup` and any rule that grows localStorage. Progress stays on the server. |

Install commands (from the repo root, no `--global`):

```bash
npx skills add https://github.com/anthropics/skills --skill frontend-design -a cursor -y
npx skills add https://github.com/vercel-labs/agent-skills --skill web-design-guidelines --skill vercel-react-best-practices -a cursor -y
npx skills add https://github.com/shadcn-ui/ui --skill shadcn -a cursor -y
```

`shadcn-ui/ui` also contains `migrate-radix-to-base`. The `--skill shadcn` filter must be present so that migration skill is not installed.

If `npx skills` is interactive, the `-y` flag is the CLI’s non-interactive switch (see the vercel-labs/skills README). If a prompt still appears, stop and install that one skill by copying its `SKILL.md` (and any `rules/` directory it links) into the project skill folder by hand. Do not answer a prompt by installing every skill in the upstream repo.

### Leave these out

| Skill | Why it stays out |
|---|---|
| `theme-factory` (anthropics/skills) | Applies one of ten preset palettes and font pairings. It would fight `--ink/--paper/--accent`. |
| `webapp-testing` (anthropics/skills) | Python Playwright helpers and `with_server.py`. This repo’s e2e is `apps/web` Playwright under `/web-e2e`. A second runner will drift. |
| `migrate-radix-to-base` (shadcn-ui/ui) | Rewrites `@radix-ui/react-*`, which `apps/web/package.json` and `components/ui/button.tsx` already use. |
| `vercel-composition-patterns` | Useful later if a component grows a pile of boolean props. Not needed for Back and type. |
| `aurorascharff/nextjs-app-architecture-skill` and other “Next.js 16+” skills | This app is `next` 15.1.4 (`apps/web/package.json`). A Next 16 skill will recommend APIs this repo does not run. `vercel-react-best-practices` is the Next.js skill that fits. |

### How each acquired skill is used with the local ones

- `/frontend-ui` remains the procedure (order of work, tokens, action bar, a11y checklist, “never weaken e2e”). Add a paragraph that points at `frontend-design`, `web-design-guidelines`, and `shadcn`, and add the Plan 08 back-navigation rule (every non-root route; first slide Back leaves the flow).
- `/web-e2e` remains the procedure (API seed, deep link, axe). Add the Plan 08 cases: route-level Back button, and keep the existing `page.goBack()` history test. `web-design-guidelines` is the review checklist; Playwright is the proof.
- `/verify` is unchanged except agents must run it. Baseline in the skill text is stale (it says 79 tests). Do not “fix” the count downward. The gate is “all tests that exist pass”.
- `/eval-suite` is for policy and learning-assertion changes. Plans 08 and 09 skip it. Update the skill’s scenario count when editing the file, so the next policy change runs the 28-scenario suite.
- `/research` is how to refresh this table if a raw URL 404s. It is not a substitute for reading `SKILL.md`.
- `/state-report` runs once at the end of Phase 8 and once at the end of Phase 9.

## 10.4 MCP and commands

Namespaces visible to the Cursor session that wrote this plan:

| Namespace | Tools that matter | Phase 8–10 use |
|---|---|---|
| `cursor-ide-browser` | `browser_navigate`, `browser_lock`, `browser_snapshot`, `browser_click`, `browser_take_screenshot` | UI proof. Click through chat → Learning → slide 1 → Back, and Teacher sections. Desktop and 390px. A screenshot with no click is not proof. |
| `cursor` | `WebSearch`, `WebFetch`, `ReadLints`, `Task`, `TodoWrite` | Skill URL checks, lints, mapping. `Task` only for a genuine parallel exploration, not for editing the same file twice. |
| `cursor-origin-readonly` | Origin git host read APIs | Skip unless the repo remote is on `origin.cursor.com`. A GitHub remote is invisible here. |
| `cursor-app-control` | Workspace, chat title, automations | Skip for these phases. |
| `cursor-subscriptions` | PR and CI subscriptions | Skip until someone opens a PR. |
| Postgres MCP | Configured for Devin in `.devin/mcp_config.json` (restricted, `crystaldba/postgres-mcp`) | Not attached to the session that wrote this plan. Use it in a session that has it, after a real seed, to confirm row counts. Otherwise use the seed script’s own summary and the learning API. |

Commands, from the repo root on Windows:

```bash
.venv/Scripts/python -m compileall -q apps/api/app
.venv/Scripts/python -m pytest apps/api/tests -q
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
.venv/Scripts/python scripts/seed_learning_content.py --dry-run
.venv/Scripts/python scripts/seed_learning_content.py
```

`test:e2e` needs Postgres and the API on port 8000. Quiz remediation specs need `LEARNING_QUIZ_COOLDOWN_SECONDS=0` when they are in the run (root `AGENTS.md`).

## 10.5 Work packages

**W10.1 — One trial install.** Run the `frontend-design` command from §10.3. See whether the files landed in `.agents/skills/` or `.cursor/skills/`. Open the `SKILL.md` and confirm the `name` is `frontend-design`. If they landed only in `.agents/skills/` and Cursor does not list the skill, copy that folder to `.cursor/skills/frontend-design/` as `create-skill` describes. Do not keep two diverging copies; pick the directory Cursor loads and note it at the top of `.devin/skills/frontend-ui/SKILL.md`.

**W10.2 — The other three.** Install `web-design-guidelines`, `vercel-react-best-practices`, and `shadcn` the same way. Confirm `migrate-radix-to-base` is absent.

**W10.3 — Point the local skills at them.** Edit `.devin/skills/frontend-ui/SKILL.md` and `.devin/skills/web-e2e/SKILL.md` as §10.3 describes. Edit `.devin/skills/eval-suite/SKILL.md` only to correct the scenario count to 28 and the assertion range to A1–A23, matching Plan 06. Do not change thresholds.

**W10.4 — Stop.** Hand Phase 08 to the next session. Do not start visual edits in the same unreviewed install if the skill files failed to load.

## 10.6 Harness usage for this phase itself

| Harness | This phase |
|---|---|
| `/frontend-ui`, `/web-e2e` | Edited, not executed against the app. |
| `/verify` | Run once after the skill-file edits so a markdown-only change did not surprise the tree. Expect pytest and compileall green. Web build is optional because no `apps/web` source changed. |
| `/eval-suite` | Skip. The skill text change does not change the harness code. |
| `/state-report` | Skip until Phase 8 or 9 completes. |
| `/research` | Already used to choose this list. Re-run only if an install URL 404s. |
| `cursor-ide-browser` | Skip. No UI change. |
| Browser, seed, Playwright | Skip. |
| `create-skill` | Follow its storage rules while placing files. Do not author a new skill that duplicates `frontend-design`. |

Phases 08 and 09 each repeat this table with their own run/skip column. Those columns are the ones that execute.

## 10.7 Hard rules (still binding after skills are installed)

1. LLMs propose; `process_student_turn` is the only assessment write. Skills that suggest client-side state, SWR caches, or a CMS do not create a second write path.
2. Raw messages are the source of truth. Snapshots are disposable.
3. Profile transitions keep versioned snapshots, change records, and evidence tied to quotes. This phase does not touch them.
4. Student answers never write profile state. Quiz and check-in writes stay on the learning routes.
5. Research findings never override evidence. A skill’s design opinion never overrides `apps/web/AGENTS.md` or the canon tokens.
6. Project text without citations is a conversation-policy rule. It is not relaxed by a UI skill.
7. No client persistence of progress. Session id only.
8. No fake-green e2e. No hand-edits under `components/ui/`. Prompts are versioned directories. Migrations are append-only. No student PII to an LLM.

## 10.8 Acceptance

- The four skills from §10.3 are present in the project skill directory Cursor loads, and `migrate-radix-to-base` is not.
- `.devin/skills/frontend-ui/SKILL.md` names those skills and states the Plan 08 back-navigation rule.
- `.devin/skills/web-e2e/SKILL.md` names the new Back-button cases and still forbids weakening assertions.
- `.devin/skills/eval-suite/SKILL.md` describes 28 scenarios and A1–A23.
- No diff under `apps/`, `content/`, or `migrations/`.
- `/verify` compileall + pytest green.

## 10.9 Risks

| Risk | Mitigation |
|---|---|
| `npx skills add` without `--skill` installs an entire upstream pack, including the Radix migration | The commands in §10.3 pass `--skill`. W10.2 checks the folder list. |
| Two skill directories diverge | W10.1 picks one directory and records it in `/frontend-ui`. |
| A skill’s “semantic colors” or “SWR” advice contradicts the architecture | §10.7. `AGENTS.md` wins. Call that out in the `/frontend-ui` paragraph added in W10.3. |
| `eval-suite` skill text updated carelessly | Touch only the count and the assertion range. Leave the “new trace directory” and “never weaken thresholds” rules in place. |
