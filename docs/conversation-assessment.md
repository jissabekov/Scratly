# Conversation-flow assessment and remediation plan

## Product objective

Scratly is not trying to understand a student's personality or complete every dimension. It should collect the **smallest sufficient set of high-quality behavioral observations** needed to predict which problems, work, rewards, environments, and projects are likely to activate that student. Every question must therefore earn its place by increasing project-choice information, confirming a weak inference, resolving a conflict, or establishing a real-world constraint.

## What was wrong

The supplied exchange exposed failures at every layer:

1. **The opening was an extraction prompt, not a human welcome.** It ignored “hello,” gave no brief orientation, and immediately demanded introspection with “When nobody was making you…”. That wording can feel evaluative and assumes the student has an impressive voluntary pursuit ready.
2. **The system converted an interest into an unsupported identity.** “Playing videogames” became “a game or gaming project.” It then offered building mods, making tools, team organization, and explaining—none of which the student mentioned. This is leading, raises cognitive load, and manufactures the very evidence the system is meant to observe.
3. **The forced-choice menu measured recognition, not behavior.** Students can select a flattering option without a real example. One concrete recent episode—what they did, why they returned, what frustrated them, or how they responded—is more discriminating.
4. **The correction was not repaired.** The assistant needed to own the assumption and abandon it. Instead, unrelated internal policy text appeared and the next question preserved the rejected “working on something” premise.
5. **Internal machinery leaked into the conversation.** “Profile is stable,” “curated opportunities,” “bounded web research,” citations, and invention policy are implementation language, not a response to the student. It breaks trust and continuity.
6. **There was no conversational state or discourse policy.** Deterministic selection ranked assessment targets, but it did not represent greeting, thin answer, correction, topic continuity, repetition, or topic-transition cost. The writer received a target and six messages without explicit repair or natural-dialogue constraints.
7. **Coverage rewarded questionnaire completion.** A 90% threshold encouraged sweeping across dimensions even when enough evidence existed to discriminate realistic projects. This conflicts with minimum sufficient evidence.
8. **Question quality was not measurable.** There were no tests for assumption inflation, one-question turns, repair, repeated questions, behavioral anchoring, or logistics wording.
9. **Location was absent from the model.** Broad city/region and country materially affect access, time zones, transport, local programs, legal/age constraints, and whether an opportunity should be local or remote. It belongs among hard variables, but should not be demanded as an exact address or necessarily used as the cold open.
10. **Production execution was incomplete.** The public turn route is still a scaffold, so even an improved policy is not yet an end-to-end student experience. The prompt files were only placeholders, and prompt loading depended on the process working directory.

## Intended conversation pattern

Each turn follows **listen → reflect/repair → probe → update → decide whether enough is known**:

- **Welcome:** greet the student, give a one-clause purpose, and ask a low-pressure question.
- **Anchor:** follow the first volunteered detail literally. “Gaming” leads to a game they return to and what keeps them returning—not a gaming project.
- **Deepen:** obtain one concrete example and distinguish the activating element (problem, process, reward, environment, or people).
- **Test only useful uncertainty:** ask a contrasting or confirming question only when it could change the shortlist or project scaffolding.
- **Gather constraints with context:** request broad location, availability, access, and other non-negotiables with a short explanation of why they affect realistic options.
- **Reflect and validate:** offer a tentative, evidence-linked synthesis in ordinary language and invite correction.
- **Stop:** proceed to project discrimination/review once the remaining uncertainty would not materially change the next decision. Do not complete a personality inventory for its own sake.

Good repair for the example is: “You’re right—I jumped from playing games to making them. What game have you been playing most lately, and what keeps you coming back to it?” This owns the mistake, uses the student's fact, and seeks behavioral evidence without forcing an identity.

## Implemented remediation

- Added deterministic reply-signal classification for greetings, corrections, thin answers, and substantive answers. These signals guide dialogue only and never become profile evidence.
- Added repair and behavioral-anchor intents, continuity/information-gain/repetition ranking metadata, and lowered the review threshold to reflect decision-relevant sufficiency rather than exhaustive coverage.
- Expanded bounded writer context with eight recent messages, the latest reply signal, and explicit safety/conversation constraints.
- Added writer and extractor prompts that prohibit inference inflation, compound menus, internal-policy leakage, and personality labeling; require one grounded Socratic question; and prescribe correction repair.
- Added broad location as a required assessment variable while explicitly disallowing exact-address collection.

## Remaining work before pilot

1. Wire the public session/turn routes to the transactional repository and turn processor.
2. Have `question_candidates()` calculate expected information gain, continuity, prior ask count, and whether an unknown can actually alter project ranking. It should create a repair candidate immediately after a correction and defer logistical questions until an initial behavioral anchor unless safety/eligibility requires them sooner.
3. Replace scalar coverage in `stage_inputs()` with a sufficiency decision: viable project alternatives, evidence strength, unresolved decision-changing conflicts, required constraints, and expected value of the next question.
4. Persist question outcome metadata (answered, dodged, corrected, repeated) so the system does not rephrase the same failed probe.
5. Add transcript-level evaluation fixtures for greetings, terse/hostile answers, corrections, slang, uncertainty, sensitive disclosures, location refusal, multilingual/code-switched replies, contradictions, and completion. Score acknowledgment, groundedness, single-focus, information gain, continuity, non-repetition, repair, and privacy.
6. Run model prompt evaluations on every prompt change, including adversarial checks that the writer cannot change the selected target or leak internal state. Human reviewers should include students from varied ages, regions, language fluencies, and access needs.
7. Define data retention, consent, location granularity, teacher visibility, safeguarding/escalation, and deletion policies before collecting student data.
