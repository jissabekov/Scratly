# Plan 08 — Navigation, buttons, rendering, and type (Phase 8)

> **Status: PLANNED** · Owner: frontend · Depends on: Plan 02 (tokens, `FlowActionBar`, shadcn) and Plan 10 (skills on disk)
> **Goal:** every student and teacher destination that is not the chat root offers a visible way back, controls look and hit like buttons, diagrams render their steps, and type is a loaded pair on the existing token palette.

## 8.1 Non-goals

- No new routes. No new color token names beside the canon in `apps/web/app/globals.css` (`--ink`, `--paper`, `--panel`, `--line`, `--accent`, `--muted`, `--warn`, plus the W2.3 status/motion/spacing additions).
- No rebrand. Anthropic `frontend-design` lists warm paper, hairline rules, and zero radius as common generated defaults. This product already chose that editorial palette in Phase 2. The brief wins: keep the hex values.
- No client progress store. Session id stays in `localStorage['scratly.student.session_id']` via `lib/session.ts` only.
- No lesson-copy edits. Slide text is Plan 09.
- No Radix → Base UI migration. Do not run the `migrate-radix-to-base` skill. Do not hand-edit `apps/web/components/ui/`.
- No assessment, prompt, or migration changes. `/eval-suite` is not a gate for this phase.

## 8.2 Current state (evidence)

There is no tablist component. The surfaces the student treats as tabs are header links and separate routes. `app/layout.tsx` is a bare `<body>{children}</body>` with no shared shell.

### Destinations and the back control that exists today

| Route | File | What “back” is today |
|---|---|---|
| `/` chat | `app/page.tsx` → `components/chat/StudentChat.tsx` | Root. Header actions are `New chat` (a `<button>`), plus `<Link className="teacher-link">` to `/modules?session=` labeled **Learning** (only when `learning_enabled`) and to `/teacher` labeled **Teacher**. `.teacher-link` in `app/globals.css` is 0.8rem muted text with a transparent bottom border, not a button. |
| `/modules` hub, loaded | `app/modules/page.tsx` | Happy path has **no link back to chat**. Header only offers `Progress →` (`/progress?session=`). `main` uses `pb-32` as if a `FlowActionBar` were fixed to the bottom; none is rendered. |
| `/modules` hub, error | same file | Underline link “Back to the chat” to `/`. |
| `/modules` hub, no `?session=` | `components/learn/SessionBootstrap.tsx` | Underline “Go to the chat”. If a session id is in localStorage, `router.replace` always goes to `/modules?session=`, even when this component was rendered by `/progress` or the quiz page. |
| `/progress` loaded | `app/progress/page.tsx` | Header link reads **Learning path →** and points at `/modules?session=`. It is the way back, labeled as a forward step. No link to chat. Same unused `pb-32`. |
| `/progress` error | same file | “Back to the learning path” points at `/modules` **without** `?session=`, so the next page falls into `SessionBootstrap`. |
| `/modules/[moduleId]` player | `components/learn/LessonPlayer.tsx` | Top link “← Learning path” (`text-sm text-muted-foreground underline`). `FlowActionBar` `onBack` is set only when `index > 1` (`LessonPlayer.tsx` around the action bar). On slide 1 the bar renders an empty `<span className="w-16">` (`components/flow/FlowActionBar.tsx`). Keyboard ArrowLeft is also a no-op on slide 1. |
| `/modules/[moduleId]/quiz` | `components/learn/QuizRunner.tsx` | Same pattern: “← Learning path” text link; action-bar Back only when `index > 1`. The empty-draw branch (`if (!item)`) renders “This quiz has no questions.” and **no** back link at all. Gate notices in `app/modules/[moduleId]/quiz/page.tsx` use an underline link, not `FlowActionBar`. |
| Quiz result / celebration | `components/learn/QuizResult.tsx`, `components/learn/ModuleCelebration.tsx` | Underline links back to the hub, not the ghost button. |
| `/teacher` | `app/teacher/page.tsx` | “Back to student chat” is an inline `<Link href="/">` inside the lede paragraph, not a button. The `<nav>` is eleven hash jumps (`Profile` through `Interventions`, from the `VIEWS` array) plus `#Decision-trace`. All sections stay on one scrolling page. After a jump, the only return is scrolling back to that sentence in the lede. The page is a single client component. |

`e2e/learning.spec.ts` “deep link, completion persistence, refresh, and Back” uses `page.goBack()` (browser history) after Continue moves `?slide=` from 1 to 2. It does not look for a button named Back. `learning.spec.ts` also clicks the hub link `/Behind the Swipe/` and expects `Step 1 of N`. No spec asserts a route-level Back control. Do not delete the `goBack` assertion.

### Rendering and type

- Canon colors live in `:root` in `app/globals.css`. `@theme inline` maps them to Tailwind (`--color-ink`, `--color-paper`, …). `--radius`, `--radius-sm`, `--radius-md`, `--radius-lg`, and `--radius-xl` are all `0px` (Phase 2 sharp-corner choice). shadcn `Button` uses `rounded-md`, so the ghost Back button is square. That is acceptable if the control is visibly a button (border, padding, focus ring). The missing piece is the control itself, not a new radius system.
- Body type is set on `:root` inside `@layer base`: `"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif`. There is no `@font-face`, no `next/font`, and no `@theme` font token. Iowan Old Style is not a Windows face, so Windows falls through to Palatino Linotype or Georgia. Utility chrome (nav, chat header actions, buttons) hard-codes `"Segoe UI", ui-sans-serif, sans-serif` in many `globals.css` rules. Lesson pages inherit the serif and use Tailwind `font-semibold` with no loaded family.
- Lesson eyebrows use all-caps tracking (`LessonPlayer.tsx`: `text-xs tracking-wide … uppercase`). `frontend-design` treats all-caps labels as a generated tell. Phase 8 may drop the uppercase on those eyebrows. Do not change the token palette to “fix” it.
- Diagrams: `components/learn/SlideBlock.tsx` `case 'diagram'` renders `block.asset` as the text inside a dashed box (`role="img"`). Asset keys such as `event-record-fields` and `swipe-request-flow` occur only inside `content/modules/shared/how-apps-work/module.json`. No SVG or image files exist for them. The ordered `steps` already render under that placeholder. The figure should be the steps, with `alt` as the accessible name. Do not invent illustration files in this phase unless a step list cannot carry the idea.
- Text blocks render as one `<p>` (`SlideBlock.tsx`). A newline in JSON collapses. Plan 09 will add paragraphs only after W8.5 splits on `\n\n` into multiple `<p>` elements (still plain text, never HTML).

## 8.3 Work packages

**W8.1 — Read the skills, then extend the local one.** Before editing UI, read Plan 10’s acquired skills and `.devin/skills/frontend-ui/SKILL.md`. Add a short “leaving a flow” subsection to that local skill: every non-root route has a Back ghost; on the first slide, Back goes to the parent route; browser history Back keeps working because `?slide=` / `?q=` stay in the URL. Do not paste the third-party skills into the local file.

**W8.2 — One back control.** Add a small server-friendly back link component under `components/flow/` (name it for the job, for example `RouteBackLink`) that renders the existing shadcn `Button` `variant="ghost"` via `asChild` + `next/link`, so it is a real `<a>` (open-in-new-tab, middle-click) and a visible button. Minimum height 44px. Label **Back** plus the destination in the accessible name (`Back to chat`, `Back to learning path`, `Back to module`). Use it on:

- Hub happy path → `/` (chat). Keep `?session=` off the chat URL; the session id is already in `localStorage`.
- Progress happy path and error path → `/modules?session=` when the session is known. Error path must not drop the query.
- Player and quiz, including the empty-quiz branch and gate notices → hub `?session=`.
- Teacher header → `/`, as a button, not a clause inside the lede. Add a “Back to top” control on the teacher `<nav>` that returns focus to the h1. Hash targets need `scroll-margin-top` so the heading is not hidden under a sticky bar if one is added.

`SessionBootstrap` must `router.replace` onto the **current pathname** plus `?session=`, not always `/modules`.

**W8.3 — Action bar on the first step.** When `index === 1`, `LessonPlayer` and `QuizRunner` pass an `onBack` that navigates to the hub (Link-equivalent: `router.push(hubHref)`). The spacer span goes away. ArrowLeft on slide 1 does the same move. Primary CTA stays Continue / Check. Completing slide 1 still writes through the existing Server Action; Back must not call complete.

**W8.4 — Type pair, same palette.** In `app/layout.tsx` (server component), load two families with `next/font/google` (no new npm dependency). Recommended pair for a reading-heavy lesson UI, chosen because it is not Inter/Roboto and it has a real text face plus a UI face: **Source Serif 4** for lesson body and slide headings, **Source Sans 3** for buttons, nav, eyebrows, and the chat chrome. Expose them as `--font-display` and `--font-body` in `@theme inline`, and point the `:root` stack and the Segoe UI rules at those variables so Windows and macOS render the same files. Keep `--ink` and the rest of the canon hex values. Line length of lesson text stays under about 80 characters (`max-w-3xl` already approximates this; check at 1280px). Set `leading-relaxed` on body copy. Do not set a third accent color.

**W8.5 — Diagram and paragraph rendering.** In `SlideBlock.tsx`:

- Diagram: remove the dashed box that prints `block.asset`. Render `steps` as the figure (ordered list, already there) and keep `aria-label={block.alt}` on the figure. Caption stays.
- Text: if `block.text` contains a blank line, render one `<p>` per paragraph. Do not interpret markdown or HTML.

**W8.6 — Tests.** Extend Playwright; do not weaken `page.goBack()` in `e2e/learning.spec.ts`.

- New assertions: from a seeded hub, the Back control returns to the chat; from progress, Back returns to the hub with the same `session` query; from slide 1, the button named Back returns to the hub; from slide 2, the button named Back returns to slide 1 **and** a subsequent `goBack()` assertion still holds for history.
- Keep the axe helper in `e2e/helpers.ts` on hub, player, progress, and teacher.
- `learning.spec.ts` assumes the first hub module’s slide 1 is a plain text slide (`Continue` is enabled). Phase 9 must leave `how-apps-work` slide seq 1 as `kind: "text"`. If that ever changes, point this spec at the first text slide via the API detail payload and keep the completion, refresh, and `goBack` assertions.

## 8.4 Harness usage

Use every harness below on purpose. “Skip” means the harness does not apply to this diff, not that it was forgotten.

| Harness | This phase |
|---|---|
| `/frontend-ui` (`.devin/skills/frontend-ui/SKILL.md`) | Binding. Read it first. W8.1 extends it with the back-navigation rule. |
| Acquired `frontend-design` | W8.4 type scale and the self-critique pass. Palette stays canon. |
| Acquired `web-design-guidelines` | Review gate after W8.2–W8.5. Fetch `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` the way that skill says. Fix hit targets, focus, “no dead ends”, and `<Link>` for navigation. |
| Acquired `shadcn` | Composing `Button` ghost + `asChild`. `apps/web/components.json` exists (`style: new-york`, `rsc: true`). Do not run `shadcn init` or a preset switch. Package runner is npm. |
| Acquired `vercel-react-best-practices` | When touching `app/layout.tsx` and server/client boundaries. Ignore its SWR and localStorage-schema rules. Session id only; Server Actions stay in `lib/actions.ts`. |
| `/web-e2e` | W8.6. API on :8000, Postgres up, `npm --prefix apps/web run test:e2e`. |
| `/verify` | Before claiming done: `.venv/Scripts/python -m compileall -q apps/api/app` and `.venv/Scripts/python -m pytest apps/api/tests -q` (expect green even if API files did not change) plus `npm --prefix apps/web run build`. |
| `/eval-suite` | Skip. This phase does not change policy, prompts, or assertions A1–A23. |
| `/state-report` | Once, when the phase is marked done in this master file. |
| `/research` | Skip unless a font file fails to load at build time. Then research a substitute pair; do not swap in Inter by default. |
| `cursor-ide-browser` | Required visual proof. `browser_navigate` to chat → Learning → a module slide 1 → Back, and chat → Teacher → a hash section → Back. `browser_lock` around the pass. Snapshot and click, not a single screenshot. Repeat at desktop width and at 390px. Confirm the Back control is visible, focusable, and returns to the expected URL. |
| `cursor` MCP (`ReadLints`, `WebSearch`) | Lints after edits. WebSearch only if a skill URL 404s. |
| `cursor-origin-readonly`, `cursor-app-control`, `cursor-subscriptions` | Skip. |
| `postgres` MCP (`.devin/mcp_config.json`) | Skip. No schema change. |
| Learning seed | Skip. No `content/modules` edits. |
| Cursor `create-skill` | Already applied in Phase 10. Do not create a second UI skill here. |

## 8.5 Hard rules

1. LLMs propose; the reducer owns assessment state. This phase does not call the reducer.
2. Raw messages stay the source of truth. Do not persist slide position, quiz answers, or mastery in localStorage.
3. Student answers never write profile state. Learning writes stay on the learning routes.
4. No free-form HTML in slide content. The paragraph split is a renderer change, not a new block type.
5. Do not weaken Playwright or pytest assertions. Do not edit `components/ui/` by hand.
6. Prompts stay versioned; this phase does not touch `apps/api/prompts/`. Migrations stay append-only; this phase adds none.
7. No student PII to an LLM. Browser snapshots of local demo sessions are fine; do not paste transcript text into a prompt.

## 8.6 Acceptance

- From chat, Learning, a module (slide 1 and a later slide), the quiz (question 1), progress, and teacher, a visible Back control returns to the parent route. Teacher hash sections can return focus to the top.
- `SessionBootstrap` preserves `/progress` and `/modules/[moduleId]/quiz` when it only needed to attach `?session=`.
- Diagram slides show steps, not the asset slug string.
- Computed font-family on a slide heading and on a button is the loaded pair, on Windows as well as macOS.
- `npm --prefix apps/web run build` green. Full `npm --prefix apps/web run test:e2e` green, including the existing `goBack` test and the new Back-button tests, plus axe on the touched pages.
- `/verify` compileall + pytest green.
- Browser pass completed at both widths, with the Back click actually changing the URL.

## 8.7 Risks

| Risk | Mitigation |
|---|---|
| `router.push` on slide-1 Back fights the history stack the e2e `goBack` test depends on | Slide-1 Back goes to the hub (a new history entry). Slide-to-slide Back stays `?slide=` replace-or-push exactly as `LessonPlayer` does today. The history test stays on slide 2 → slide 1. |
| `next/font` download fails in CI without network | Fonts are fetched at build time. If CI is offline, document the failure; do not silently fall back to an unlicensed file committed into the repo. |
| Sticky teacher bar covers the focused heading | `scroll-margin-top` on the article headings; check with the browser, not by eye in the editor. |
| Phase 9 lands long paragraphs before W8.5 | Phase 9 acceptance screenshots wait until W8.5 is in. In-place text that is one paragraph still renders correctly before that. |
