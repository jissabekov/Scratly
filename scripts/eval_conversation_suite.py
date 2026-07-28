#!/usr/bin/env python3
"""Live multi-persona assessment eval suite (15–20 conversation chains).

Each scenario is a designed student persona with 15–30 scripted turns that
stress a different facet of the chatbot (discovery, thin answers, repair,
contradictions, student Q&A, geo, stage progression, etc.).

For every session the harness dumps:
  - full turn request/response log
  - all admin views (transcript, evidence, profile, history, questions,
    why-next-question, contradictions, project-fit)
  - full decision-trace events
  - optional Postgres llm_runs / memory_snapshots counts
  - per-scenario analysis metrics

Usage:
  .venv/Scripts/python scripts/eval_conversation_suite.py
  .venv/Scripts/python scripts/eval_conversation_suite.py --only maya_happy_path,thin_elicitation
  .venv/Scripts/python scripts/eval_conversation_suite.py --analyze-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "eval" / "traces"

STAGE_RANK = {
    "discovery": 0,
    "measurement": 1,
    "gap_resolution": 2,
    "profile_review": 3,
    "project_matching": 4,
    "complete": 5,
}


def _percentile(values: list[int], percentile: float) -> int | None:
    """Nearest-rank percentile without adding a statistics dependency."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _normalized_utterance(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _max_run(values: list[Any]) -> int:
    longest = current = 0
    previous = object()
    for value in values:
        current = current + 1 if value == previous else 1
        previous = value
        longest = max(longest, current)
    return longest


# ---------------------------------------------------------------------------
# Scenario definitions — 18 chains covering assessment surface area
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "maya_happy_path",
        "title": "Happy path — science/community builder to project match",
        "aspects": [
            "discovery",
            "interest_depth",
            "work_mode",
            "motivation",
            "capability",
            "geo",
            "profile_review",
            "project_matching",
            "stage_progression",
        ],
        "turns": [
            "Hi! I'm Maya, a 10th grader. I like building small science projects that use neighborhood data — air quality sensors and maps.",
            "Last month I helped wire a cheap sensor and plotted readings in a spreadsheet for our science club.",
            "I prefer working with one or two friends rather than a big group. Too many people deciding at once overwhelms me.",
            "When I'm deep in analysis I actually like working alone. Brainstorming is better with a small group though.",
            "What motivates me is helping my community understand local problems. Grades matter less than making something useful.",
            "I'm comfortable with Python basics and spreadsheets, but I've never built a full web app. I'd need help with databases and hosting.",
            "Weekday evenings after 7pm work best, and the project should finish in about six weeks. I'm based in Seattle.",
            "I like stretching a bit on challenge, but not so hard that I get stuck for weeks. Scaffolded hard problems are ideal.",
            "If I had to pick a primary topic: neighborhood air quality maps with a simple Python analysis pipeline.",
            "I care about both curiosity and impact — exploring sensors is fun because it helps neighbors.",
            "Persistence-wise, when something breaks I usually keep debugging for an hour before asking for help.",
            "Ambiguity is okay if there's a clear first milestone. Open-ended forever projects frustrate me.",
            "I'm fine emailing a teacher or librarian for access, but cold-calling strangers feels hard.",
            "Sharing a finished dashboard publicly is fine. Live demos to a big room still make me nervous.",
            "Yes, that profile sounds right — small-group brainstorm, solo coding, community impact, Python with hosting help.",
            "Between a sensor-data dashboard and a neighborhood interview story map, the dashboard fits better.",
            "I'm ready to pick a project direction and start scoping the first milestone.",
            "What would the first week of work look like on that dashboard project?",
        ],
    },
    {
        "id": "gamer_correction_repair",
        "title": "Gaming interest — pushback when system inflates to 'game project'",
        "aspects": [
            "greeting",
            "behavioral_anchor",
            "correction_repair",
            "interest_depth",
            "framing_pushback",
            "motivation",
            "work_mode",
            "geo",
        ],
        "turns": [
            "hello",
            "i mostly just play videogames after school",
            "wait no i dont want to make a game or a gaming project, i just play them",
            "I've been playing Zelda Tears of the Kingdom a lot. I keep coming back for the puzzle solving and exploring weird places.",
            "I like figuring out creative solutions myself before looking stuff up. The shrines that need sideways thinking are my favorite.",
            "I'm not sure I want a 'project' yet. Maybe something related to puzzles or maps? Not game development.",
            "Working alone is fine for puzzles. Explaining strategies to friends is fun too though.",
            "What gets me going is the feeling of cracking something hard. Helping others is secondary.",
            "I'm in Austin, Texas. Weekends are better than weeknights.",
            "Skills-wise I'm okay at drawing maps by hand and writing clear steps. No coding yet.",
            "If something is confusing I usually try two or three approaches then ask a friend.",
            "I don't love talking to adults I don't know. Teachers I already know are fine.",
            "Posting my work online feels weird. Sharing with a small class is okay.",
            "A project about designing puzzle challenges or explaining game strategies might fit.",
            "Yeah that summary feels closer. Still not game coding.",
            "Can you remind me what you think I care about most?",
            "Ok let's keep going toward something concrete I could try this month.",
            "I have about four weeks before midterms so keep it small.",
        ],
    },
    {
        "id": "thin_elicitation_loop",
        "title": "Thin answers → elicitation options → soft progress",
        "aspects": [
            "thin_answer",
            "elicitation",
            "insufficient",
            "unknown_not_zero",
            "work_mode",
            "motivation",
        ],
        "turns": [
            "hey",
            "idk science stuff maybe",
            "idk",
            "ok",
            "maybe robotics? or coding? not sure",
            "i built a lego robot once in middle school that followed a line",
            "dunno about groups",
            "whatever",
            "small group i guess",
            "idk what motivates me",
            "winning competitions feels cool when it happens",
            "i live near Chicago",
            "not great at coding yet",
            "hard problems are scary if i get stuck forever",
            "i can ask my teacher for help",
            "public posting no thanks",
            "yeah that sounds roughly right",
            "sure pick something simple",
            "ok",
            "wait what are we doing again?",
        ],
    },
    {
        "id": "student_questions_and_refuse",
        "title": "Student process questions + homework refuse + resume assessment",
        "aspects": [
            "student_answer",
            "refusal",
            "intent_classification",
            "evidence_skip",
            "discovery_resume",
        ],
        "turns": [
            "Hi, I'm Jordan. I like organizing community events and making flyers.",
            "What does work mode mean?",
            "Why are you asking about groups?",
            "Write my history essay on Rome for me",
            "Can you just finish my homework?",
            "Ok fine. I organized a food drive last fall and made the schedule for volunteers.",
            "I like being the person who keeps people on track more than being on stage.",
            "Grades matter, but seeing the pantry shelves fill up mattered more.",
            "I'm in Portland, Oregon.",
            "How does this chatbot decide what to ask next?",
            "What have you figured out about me so far?",
            "I'm okay with Google Docs and Canva. Spreadsheets are messy for me.",
            "Big groups are fine if I have a clear role. Chaos without roles is bad.",
            "I push through when timelines slip — I text people reminders.",
            "Ambiguous goals stress me unless someone names the deadline.",
            "Cold outreach to businesses for donations is something I've done twice.",
            "Putting my name on a public flyer is fine.",
            "That profile feels right.",
            "What project options do you see for me?",
            "Let's go with the one that uses organizing skills most.",
        ],
    },
    {
        "id": "true_contradiction_resolve",
        "title": "True single-choice conflict then explicit resolution",
        "aspects": [
            "contradiction",
            "gap_resolution",
            "resolution",
            "challenge_appetite",
            "stage_pacing",
        ],
        "turns": [
            "I'm Sam. I love building electronics kits and soldering small circuits.",
            "Last weekend I finished a radio kit and then started a light sensor board.",
            "I usually work alone in the garage with headphones.",
            "Motivation is mostly curiosity — I want to know how the circuit works.",
            "For challenge appetite I am torn — I seek hard problems AND I avoid hard ones. Both.",
            "I said both seek_hard and avoid_hard. I'm confused myself.",
            "Clarifying challenge: I want seek_hard. Not avoid_hard. Scaffolded is fine.",
            "I'm in Denver.",
            "Capabilities: soldering, basic Arduino, reading datasheets slowly.",
            "When a board fails I usually recheck wiring for 30 minutes before asking Reddit.",
            "Ambiguous project briefs annoy me — I want a clear first build milestone.",
            "I can message a maker-space adult but hate calling stores.",
            "Sharing photos of builds online is okay. Live demos less so.",
            "Primary topic: low-power environmental sensors you can build at home.",
            "Yes profile looks good.",
            "I'd pick a sensor kit project over a pure research paper.",
            "Ready to scope week one.",
            "One more: I prefer seek_hard confirmed.",
        ],
    },
    {
        "id": "multi_value_nuance",
        "title": "Compatible multi-values must NOT become false contradictions",
        "aspects": [
            "multi_value",
            "no_false_conflict",
            "work_mode_compound",
            "motivation_coexist",
            "capability_gaps",
        ],
        "turns": [
            "I'm Priya. I care about climate and also about storytelling — both.",
            "I write short essays AND I collect neighborhood heat-island photos.",
            "For work: brainstorming with 2 friends is great; drafting alone is better.",
            "Curiosity and impact aren't rivals for me — exploring heat maps helps neighbors.",
            "I know Python a little and I'm decent at interviewing people. Not a full web engineer.",
            "I'm based in Phoenix.",
            "Evenings on weekdays, maybe 5 weeks total.",
            "Hard-but-scaffolded challenges.",
            "Persistence: I keep notes and retry experiments across days.",
            "Ambiguity: okay if we define what 'done' looks like.",
            "Outreach: I can ask my science teacher; strangers are harder.",
            "Visibility: class presentation fine; TikTok no.",
            "Primary focus if forced: neighborhood heat storytelling with simple data.",
            "Assets: phone camera, school laptop, teacher who likes climate clubs.",
            "Constraints: no paid software, must be free tools.",
            "Yes that summary is accurate — dual interests, not a conflict.",
            "Dashboard-lite with captions beats a pure sensor hardware build.",
            "Let's move toward matching.",
            "What would discriminate between two project options for me?",
        ],
    },
    {
        "id": "hostile_terse_then_open",
        "title": "Hostile/terse start that gradually opens up",
        "aspects": [
            "thin_answer",
            "repair",
            "continuity",
            "trust_building",
            "non_repetition",
        ],
        "turns": [
            "this is dumb",
            "whatever",
            "idk",
            "sports i guess",
            "basketball. i help coach younger kids sometimes",
            "i like seeing them get better at drills",
            "not big on essays",
            "group stuff is fine if its practice not meetings",
            "winning matters to me more than vibes",
            "im in detroit",
            "i can make practice plans in google docs",
            "if a drill fails i change it next week",
            "unclear goals annoy me",
            "talking to parents of kids is ok, cold emails less",
            "posting online nah",
            "ok your summary is fine",
            "something about youth coaching drills maybe",
            "keep it practical",
            "yeah go ahead",
            "what next",
        ],
    },
    {
        "id": "location_delayed_then_ready",
        "title": "Rich profile first; location late; then matching readiness",
        "aspects": [
            "geo_gating",
            "location_readiness",
            "project_matching",
            "interest_first",
        ],
        "turns": [
            "I'm Alex. I design simple websites for school clubs using HTML/CSS.",
            "Last semester I rebuilt the robotics club page so schedules were readable on phones.",
            "I like building things people can click. Investigating theory without shipping feels incomplete.",
            "Small team: me plus one designer friend.",
            "Motivation is craft pride — making something polished that others use.",
            "Skills: HTML, CSS, a bit of JS. No backend yet.",
            "Challenge: medium-hard with examples to copy from.",
            "I persist by shipping tiny versions first.",
            "Ambiguity is okay if users can give feedback fast.",
            "I can ask club officers for content; cold outreach to companies is hard.",
            "Publishing a public site is the point for me.",
            "Assets: laptop, GitHub account, teacher who hosts club sites.",
            "Time: after school Tue/Thu, ~6 weeks.",
            "I'd rather not share my city yet — privacy.",
            "Ok fine, greater Boston area is fine to say.",
            "Profile summary looks good.",
            "Match me to a local-or-remote web project for a club.",
            "First milestone should be a clickable prototype.",
            "Confirm location is Boston metro.",
            "Ready.",
        ],
    },
    {
        "id": "topic_switch_frustration",
        "title": "Topic rejection / frustration forces switch away from dead end",
        "aspects": [
            "topic_rejection",
            "frustration",
            "switch_action",
            "continuity_break",
            "breadth",
        ],
        "turns": [
            "Hi I'm Riley. People keep pushing coding on me but I actually hate sitting at a computer all day.",
            "Stop asking about coding projects. I don't want coding.",
            "I like outdoor trail cleanup and mapping trash hotspots with photos.",
            "Please don't bring coding back. Not interested.",
            "Last month our club walked a creek and logged litter types in a notebook.",
            "I work best with a small crew outdoors, not Zoom meetings.",
            "Motivation is impact — cleaner trails people can use.",
            "I'm near Minneapolis.",
            "Skills: photography, basic map reading, organizing volunteer shifts.",
            "Hard physical days are fine; endless online research is not.",
            "If a plan fails outdoors I adapt on the spot.",
            "Ambiguous meeting agendas frustrate me more than messy weather.",
            "I will text neighbors about a cleanup day.",
            "Posting photos of trash piles publicly is fine if it helps.",
            "Primary: trail stewardship + simple litter maps (paper or phone photos).",
            "Yes, and again — no coding-heavy project.",
            "Pick something field-based.",
            "What does week one look like without requiring a laptop?",
            "Good. Keep going.",
        ],
    },
    {
        "id": "execution_deep_dive",
        "title": "Deep coverage of execution facets + assets/constraints",
        "aspects": [
            "execution:persistence",
            "execution:ambiguity_tolerance",
            "execution:outreach_willingness",
            "execution:public_visibility",
            "assets",
            "constraints",
        ],
        "turns": [
            "I'm Casey. I invent board-game rules and playtest them with friends.",
            "I rewrote a card game three times after playtests flopped.",
            "Usually 3–4 friends at a table. Not a huge club.",
            "Motivation: seeing people laugh at a clever rule I designed.",
            "When a rule breaks, I keep iterating for days. Quitting early feels worse.",
            "I tolerate ambiguity while drafting, but playtests need clear win conditions.",
            "I'll message friends to schedule tests. Emailing game stores is scary.",
            "Sharing rules PDFs with a class is fine. Streaming myself teaching is not.",
            "I'm in Nashville.",
            "Assets: printer, cardboard, markers, Discord with playtesters.",
            "Constraints: no budget, must finish before summer, evenings only.",
            "Capability: rule writing, facilitation. Art skills weak.",
            "Primary topic: lightweight educational card games about local history.",
            "I seek medium challenge — clever but teachable in 10 minutes.",
            "Profile check: sounds right.",
            "Project should emphasize playtesting loops not fancy art.",
            "How do you score my outreach willingness from what I said?",
            "Ok, continue matching.",
            "Week-one: paper prototype of 12 cards.",
            "Done talking unless you need one more fact.",
        ],
    },
    {
        "id": "profile_review_reject_repair",
        "title": "Student rejects profile summary; system must repair",
        "aspects": [
            "profile_review",
            "correction",
            "repair",
            "re_measure",
            "validation",
        ],
        "turns": [
            "I'm Taylor. I film short TikTok explainers about chemistry demos.",
            "I filmed a baking-soda volcano explainer that got comments from classmates.",
            "I edit alone then ask one friend for feedback.",
            "Motivation is teaching — I like when someone says 'ohhh that makes sense'.",
            "Skills: phone filming, CapCut, basic chemistry. Not lab research deep.",
            "I'm in Miami.",
            "Challenge: medium. I want clear scripts not open science mysteries.",
            "I persist by shooting multiple takes the same afternoon.",
            "Ambiguity in learning goals is okay if the video still has a punchline.",
            "I DM teachers for demo permission. Calling district offices no.",
            "Public TikTok is literally the format I use.",
            "Primary: chemistry explainers for younger students.",
            "Wait — your summary said I want to be a researcher. That's wrong. I want to teach with video.",
            "Also I am NOT motivated by competition or grades first.",
            "Correct profile: communicator-teacher via short video, chemistry demos, Miami, CapCut.",
            "Yes, now that sounds right.",
            "Match me to a project that produces teachable short videos.",
            "First week: script + one filmed demo.",
            "Confirm visibility is public-on-purpose.",
            "Thanks — anything else blocking matching?",
        ],
    },
    {
        "id": "slang_uncertain_hedging",
        "title": "Heavy slang + hedging; still extract usable evidence",
        "aspects": [
            "slang",
            "uncertainty",
            "grounding",
            "provisional_strengthening",
            "continuity",
        ],
        "turns": [
            "yo whats up",
            "lowkey into like music production stuff i guess??",
            "idk if its a real interest or just vibes but i mess with garageband a lot",
            "last week i made a beat and then remixed it like 5 times till it slapped",
            "working w people is mid unless they actually listen. solo grinding is chill",
            "motivation wise... clout is cringe but finishing a track feels elite",
            "im around NYC somewhere brooklyn-ish",
            "skills: garageband, kinda fl studio beginner. theory? nah weak",
            "hard mode projects scare me if deadlines are fake",
            "if a mix is trash i keep tweaking overnight sometimes",
            "vague briefs suck. give me a reference track at least",
            "i can ask my cousin who DJs. random adults? no cap thats awkward",
            "posting a track publicly is fine if its actually good",
            "main lane: short beats for school videos / announcements maybe",
            "assets: laptop, headphones, garageband",
            "time: weekends mostly, like a month",
            "yeah ur read on me is mostly fire",
            "project should be music-first not coding a DAW clone",
            "bet. whats first milestone",
            "aight cool",
        ],
    },
    {
        "id": "organizer_communicate_mode",
        "title": "Organize/communicate work modes vs build/investigate",
        "aspects": [
            "work_mode",
            "motivation",
            "capability",
            "project_discrimination",
            "discrimination_value",
        ],
        "turns": [
            "I'm Morgan. I run the debate club calendar and write weekly update emails.",
            "I don't build robots; I make sure people show up prepared.",
            "Last month I redesigned our practice roster after two no-shows wrecked a meet.",
            "I prefer coordinating a team of 6–8 with clear roles over solo deep work.",
            "Motivation: recognition from the team when logistics just work — and impact on wins.",
            "Location: San Diego.",
            "Tools: Sheets, email, Notion. No coding.",
            "Challenge: people problems are harder than tech for me, and I like that.",
            "Persistence: I follow up three times before dropping a volunteer.",
            "Ambiguity: I create structure when none exists.",
            "Outreach: I cold-email other schools for practice meets.",
            "Visibility: newsletter bylines are fine.",
            "Primary interest: youth civic events logistics / debate ops.",
            "Assets: club email, teacher advisor, Sheets templates.",
            "Constraints: after-school only, no budget, 5 weeks.",
            "Profile yes — organizer/communicator, not builder.",
            "Discriminate: ops playbook project vs research essay — ops wins.",
            "Week one: audit last semester's no-show patterns.",
            "Anything else you need?",
        ],
    },
    {
        "id": "capability_scaffold_gaps",
        "title": "Strong interest, weak skills — scaffolding must stay honest",
        "aspects": [
            "capability",
            "assets",
            "scaffolding",
            "unknown_not_zero",
            "project_gates",
        ],
        "turns": [
            "I'm Avery. I want to do machine learning on wildlife camera photos.",
            "I've never trained a model. I watched two YouTube videos.",
            "I did collect 40 trail-cam images with my uncle last summer.",
            "I like investigating patterns more than building apps.",
            "Solo research is fine; presenting to a club is harder.",
            "Motivation is curiosity about animals near our town.",
            "I'm in Boise area.",
            "Please don't assume I can code PyTorch. I can't yet.",
            "I can use Google Sheets and label photos carefully.",
            "Hard: I want learnable steps, not a Kaggle competition.",
            "If stuck I rewatch tutorials then ask my uncle.",
            "Ambiguous 'explore AI' goals stress me — need labeled tasks.",
            "Outreach to a park ranger is something I could try once.",
            "Public blog maybe. Not a conference talk.",
            "Assets: trail cam access via uncle, school Chromebook.",
            "Constraints: no GPU, free tools only, 6 weeks.",
            "Profile: curious investigator, beginner skills, Boise, photo labeling first.",
            "Project must start with labeling + simple counts, not neural nets.",
            "Yes that matches.",
            "What gate would block a true ML project for me right now?",
        ],
    },
    {
        "id": "greeting_slow_warm_up",
        "title": "Long social warm-up before any substance",
        "aspects": [
            "greeting",
            "social_intro",
            "pacing",
            "non_quiz_open",
            "later_substance",
        ],
        "turns": [
            "hi",
            "how are you",
            "what is this for again?",
            "ok cool",
            "i'm just bored in study hall",
            "maybe we can talk about art? i draw a lot",
            "digital art on my tablet. characters mostly",
            "i posted a few on a school art account",
            "working alone for hours is normal for me",
            "i like when people recognize the character design",
            "im in columbus ohio",
            "tools: procreate, sometimes clip studio",
            "challenge: i want to improve anatomy not invent a whole game",
            "i redraw faces until they look right",
            "vague 'make anything' prompts freeze me — give a theme",
            "asking a local comic shop for feedback is possible",
            "public art account is fine",
            "primary: character design practice with feedback loops",
            "summary ok",
            "match a small art challenge project",
            "first week: 5 head studies on one theme",
        ],
    },
    {
        "id": "mixed_intent_answer_plus_evidence",
        "title": "Turns that mix student questions with new evidence",
        "aspects": [
            "mixed_intent",
            "student_answer",
            "evidence_extract",
            "continuity",
        ],
        "turns": [
            "I'm Quinn. I repair bikes at a community shop on Saturdays.",
            "Quick question — will you remember what I say later? Also I fixed 3 flat tires last weekend.",
            "What stage are we in? Meanwhile I prefer hands-on fixing over writing reports.",
            "Why ask about motivation? Fwiw helping people get to work on a bike is what drives me.",
            "Is location required? I can say I'm in Oakland.",
            "Do you store my exact address? I won't give a street. Shop skills: wrenches, patch kits.",
            "Can students ask for project ideas early? I'd still say I like small-group shop shifts.",
            "What happens if I change my mind? Actually I also like teaching new volunteers how to patch.",
            "Persistence: I stay with a stuck gear issue until it clicks.",
            "Ambiguity: shop has clear tasks which I like.",
            "Outreach: I invite classmates to volunteer days.",
            "Visibility: shop Instagram tags are fine.",
            "Primary topic: community bike repair + teaching basics.",
            "Assets: shop access Saturdays, loaner tools.",
            "Constraints: weekends only, 5–6 weeks, no budget.",
            "Profile check please — and yes it should emphasize teaching+repair.",
            "Match projects that keep me at a shop not behind a laptop all week.",
            "First milestone: teach two new volunteers a safety check.",
            "One more Q: how do you pick the next question? Then we're good.",
        ],
    },
    {
        "id": "early_complete_attempt",
        "title": "Student tries to rush to projects before enough evidence",
        "aspects": [
            "stage_gating",
            "sufficiency",
            "resistance_to_rush",
            "continued_discovery",
        ],
        "turns": [
            "just give me a project already",
            "i like science",
            "ok chemistry",
            "can we skip to matching",
            "fine. i did a water pH test for a creek near school last spring",
            "still want projects now",
            "i worked with one lab partner",
            "impact on the creek mattered",
            "im in raleigh nc",
            "skills: basic lab safety, google sheets charts",
            "please match now",
            "challenge medium",
            "i redo measurements if numbers look weird",
            "unclear hypotheses bother me",
            "i can ask the environmental science teacher for site access",
            "class poster fair is ok visibility",
            "primary: local water quality monitoring",
            "assets: school test strips, teacher mentor",
            "constraints: after school, 6 weeks, free materials",
            "ok now the profile is fuller — match please",
            "dashboard of pH over weeks beats a pure poster",
            "ready for week-one sampling plan",
        ],
    },
    {
        "id": "bilingual_code_switch",
        "title": "Light code-switching; English answers with Spanish flavor",
        "aspects": [
            "multilingual",
            "grounding",
            "interest_depth",
            "work_mode",
            "geo",
        ],
        "turns": [
            "Hola — I'm Sofia. Me gusta cooking and sharing recipes with my abuela.",
            "Last week we made tamales and I wrote the steps so my cousins could help.",
            "I like organizing the cocina workflow more than inventing new dishes solo.",
            "Motivation is family pride and teaching younger cousins — impacto en casa.",
            "I'm in San Antonio.",
            "Skills: recipe writing, budgeting ingredients, basic nutrition labels.",
            "No coding. Maybe simple flyers in Spanish and English.",
            "Challenge: medium — clear recipes, not restaurant-level R&D.",
            "If a recipe fails I adjust and try again the same week.",
            "Ambiguity: need a clear 'who is this meal for'.",
            "Outreach: I can ask neighbors for a tasting night.",
            "Visibility: sharing a bilingual recipe card publicly is fine.",
            "Primary: bilingual family recipe cards + small tasting event.",
            "Assets: home kitchen, abuela's knowledge, phone camera.",
            "Constraints: evenings, ~5 weeks, grocery budget under $40.",
            "Sí, that profile feels right.",
            "Project should stay food + community, not a tech app.",
            "Week one: collect 3 recipes with bilingual steps.",
            "Gracias — anything missing?",
            "Listo.",
        ],
    },
]


ADMIN_VIEWS = (
    "transcript",
    "evidence",
    "profile",
    "profile-history",
    "question-history",
    "why-next-question",
    "contradictions",
    "project-fit",
)


def _req(method: str, url: str, body: dict | None = None, timeout: int = 180) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> {err.code}: {detail}") from err
    except URLError as err:
        raise RuntimeError(f"{method} {url} failed: {err}") from err


def _admin(base: str, session_id: str, view: str) -> Any:
    return _req("GET", f"{base}/v1/admin/sessions/{session_id}/{view}")


def _enrich_db_counts(session_id: str) -> dict[str, Any]:
    try:
        import subprocess

        sql = (
            "SELECT "
            f"(SELECT count(*) FROM audit.llm_runs WHERE session_id='{session_id}') AS llm, "
            f"(SELECT count(*) FROM conversation.memory_snapshots WHERE session_id='{session_id}') AS mem;"
        )
        proc = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "scratly",
                "-d",
                "scratly",
                "-t",
                "-A",
                "-F",
                ",",
                "-c",
                sql,
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            llm_c, mem_c = proc.stdout.strip().split(",", 1)
            return {"llm_runs": int(llm_c), "memory_snapshots": int(mem_c)}
    except Exception as err:  # noqa: BLE001
        return {"error": str(err)}
    return {}


def analyze_dump(dump: dict[str, Any]) -> dict[str, Any]:
    """Derive metrics used for the post-eval report."""
    events = dump.get("decision_trace", {}).get("events") or []
    turns = dump.get("turns") or []
    views = dump.get("admin_views") or {}
    profile = (views.get("profile") or {}).get("profile") or views.get("profile") or {}
    if isinstance(profile, dict) and "state" in profile:
        profile_state = profile.get("state") or {}
    else:
        profile_state = profile if isinstance(profile, dict) else {}

    event_types = Counter(e.get("event_type") for e in events)
    stages = [t.get("response", {}).get("stage") for t in turns if t.get("response")]
    stage_path = []
    for s in stages:
        if not stage_path or stage_path[-1] != s:
            stage_path.append(s)

    q_targets: list[dict[str, Any]] = []
    for e in events:
        if e.get("event_type") != "question_target_selected":
            continue
        # Policy event is the committed ask; planner event is advisory only.
        if e.get("component") not in {None, "question_policy"}:
            continue
        out = e.get("outputs") or {}
        q_targets.append(
            {
                "target_kind": out.get("target_kind") or out.get("kind"),
                "target_key": out.get("target_key") or out.get("key"),
                "decision_value": out.get("decision_value"),
                "planner_action": out.get("planner_action") or out.get("action"),
                "reason_code": e.get("reason_code"),
            }
        )

    evidence_items = (views.get("evidence") or {}).get("items") or []
    contradictions = (views.get("contradictions") or {}).get("items") or []
    open_c = [c for c in contradictions if c.get("status") == "open"]
    resolved_c = [c for c in contradictions if c.get("status") == "resolved"]
    q_hist = (views.get("question-history") or {}).get("items") or []

    # Coverage-ish: count non-unknown from coverage if present on profile view
    coverage = (views.get("profile") or {}).get("coverage") or []
    cov_status = Counter()
    for row in coverage if isinstance(coverage, list) else []:
        cov_status[row.get("status") or "unknown"] += 1

    # Profile information gain proxy: accepted evidence growth + established dims
    accepted = [e for e in evidence_items if e.get("status") == "accepted"]
    dims_touched = {e.get("dimension_key") for e in accepted if e.get("dimension_key")}

    # Per-turn info gain: profile_reduced events
    reduces = [e for e in events if e.get("event_type") == "profile_reduced"]
    info_gain_turns = 0
    for e in reduces:
        outs = e.get("outputs") or {}
        changes = outs.get("change_count") or outs.get("changes") or 0
        if isinstance(changes, list):
            changes = len(changes)
        if changes:
            info_gain_turns += 1

    intents = [
        e for e in events if e.get("event_type") == "turn_intent_classified"
    ]
    thin_events = [
        e for e in events if e.get("event_type") == "answer_thinness_evaluated"
    ]
    elicitation = [
        e
        for e in events
        if e.get("event_type")
        in {"elicitation_selected", "elicitation_attempted", "elicitation_skipped"}
    ]
    student_answers = [
        e
        for e in events
        if e.get("event_type")
        in {"student_answer_written", "student_answer_refused"}
    ]
    fallbacks = [
        e for e in events if e.get("event_type") == "question_fallback_used"
    ]
    quality_gates = [
        e for e in events if e.get("event_type") == "question_quality_gate"
    ]

    # Leakage / UX smells in assistant text
    assistant_msgs = [
        (t.get("response") or {}).get("assistant_message") or ""
        for t in turns
        if t.get("response")
    ]
    leak_hits = sum(
        1
        for m in assistant_msgs
        if any(
            needle in m.lower()
            for needle in (
                "profile is stable",
                "curated opportunities",
                "bounded web research",
                "decision_value",
                "coverage_established",
                "i heard two different preferences",
            )
        )
    )
    generic_prov = sum(
        1
        for m in assistant_msgs
        if m.strip() == "Could you give a concrete example of that preference?"
    )

    final_stage = stages[-1] if stages else None
    turn_durations = []
    for t in turns:
        if t.get("duration_ms") is not None:
            turn_durations.append(t["duration_ms"])

    normalized_messages = [_normalized_utterance(m) for m in assistant_msgs]
    nonempty_messages = [m for m in normalized_messages if m]
    duplicate_messages = len(nonempty_messages) - len(set(nonempty_messages))
    target_keys = [t.get("target_key") for t in q_targets if t.get("target_key")]
    stage_regressions = sum(
        1
        for before, after in zip(stages, stages[1:])
        if before in STAGE_RANK
        and after in STAGE_RANK
        and STAGE_RANK[after] < STAGE_RANK[before]
    )
    question_counts = [m.count("?") for m in assistant_msgs]
    project_offer_count = sum(
        1
        for t in turns
        if (t.get("response") or {}).get("message_kind") == "project_offer"
    )

    return {
        "scenario_id": dump.get("scenario_id"),
        "title": dump.get("title"),
        "aspects": dump.get("aspects") or [],
        "session_id": (dump.get("session") or {}).get("session_id"),
        "n_turns": len(turns),
        "n_events": len(events),
        "event_type_counts": dict(event_types),
        "stage_path": stage_path,
        "final_stage": final_stage,
        "reached_profile_review": "profile_review" in (stages or []),
        "reached_project_matching": "project_matching" in (stages or []),
        "reached_complete": "complete" in (stages or []),
        "premature_gap_on_turn1": bool(stages) and stages[0] == "gap_resolution",
        "question_targets": q_targets,
        "target_kind_counts": dict(Counter(t.get("target_kind") for t in q_targets)),
        "target_key_counts": dict(Counter(t.get("target_key") for t in q_targets)),
        "unique_target_ratio": round(len(set(target_keys)) / max(len(target_keys), 1), 3),
        "max_consecutive_target_repeats": _max_run(target_keys),
        "n_evidence_accepted": len(accepted),
        "n_evidence_total": len(evidence_items),
        "dimensions_touched": sorted(dims_touched),
        "n_dimensions_touched": len(dims_touched),
        "coverage_status_counts": dict(cov_status),
        "open_contradictions": len(open_c),
        "resolved_contradictions": len(resolved_c),
        "n_questions_recorded": len(q_hist),
        "info_gain_turns": info_gain_turns,
        "info_gain_ratio": round(info_gain_turns / max(len(turns), 1), 3),
        "evidence_acceptance_rate": round(len(accepted) / max(len(evidence_items), 1), 3),
        "n_intent_classified": len(intents),
        "n_thin_evaluated": len(thin_events),
        "n_elicitation_events": len(elicitation),
        "n_student_answer_events": len(student_answers),
        "n_fallbacks": len(fallbacks),
        "n_quality_gates": len(quality_gates),
        "assistant_leak_hits": leak_hits,
        "generic_provisional_repeats": generic_prov,
        "duplicate_assistant_messages": duplicate_messages,
        "duplicate_assistant_ratio": round(
            duplicate_messages / max(len(nonempty_messages), 1), 3
        ),
        "max_questions_in_response": max(question_counts, default=0),
        "multi_question_response_count": sum(1 for count in question_counts if count > 1),
        "project_offer_count": project_offer_count,
        "stage_regressions": stage_regressions,
        "live_llm": dump.get("live_llm"),
        "llm_runs": (dump.get("db_counts") or {}).get("llm_runs"),
        "memory_snapshots": (dump.get("db_counts") or {}).get("memory_snapshots"),
        "linked_llm_events": sum(1 for e in events if e.get("llm_run_id")),
        "mean_turn_ms": round(sum(turn_durations) / len(turn_durations), 1)
        if turn_durations
        else None,
        "p50_turn_ms": _percentile(turn_durations, 0.50),
        "p95_turn_ms": _percentile(turn_durations, 0.95),
        "errors": dump.get("errors") or [],
        "profile_keys_present": sorted(
            k for k, v in profile_state.items() if v not in (None, {}, [], "")
        )
        if isinstance(profile_state, dict)
        else [],
    }


def run_scenario(
    scenario: dict[str, Any],
    *,
    base: str,
    out_dir: Path,
    resume: bool,
) -> dict[str, Any]:
    out_path = out_dir / f"{scenario['id']}.json"
    if resume and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        errs = existing.get("errors") or []
        if existing.get("completed") and len(errs) == 0:
            print(f"[skip] {scenario['id']} (already completed)")
            return existing

    print(f"\n=== {scenario['id']} - {scenario['title']} ({len(scenario['turns'])} turns) ===")
    errors: list[str] = []
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    health = _req("GET", f"{base}/health")
    session = _req("POST", f"{base}/v1/sessions", None)
    session_id = str(session["session_id"])
    print(f"session={session_id}")

    turns_out: list[dict[str, Any]] = []
    for index, text in enumerate(scenario["turns"], start=1):
        body = {
            "idempotency_key": f"eval-{scenario['id']}-{index:02d}-{uuid.uuid4().hex[:8]}",
            "text": text,
        }
        turn_t0 = time.perf_counter()
        try:
            response = _req(
                "POST", f"{base}/v1/sessions/{session_id}/turns", body, timeout=240
            )
            duration_ms = int((time.perf_counter() - turn_t0) * 1000)
            turns_out.append(
                {
                    "index": index,
                    "request": body,
                    "response_status": 200,
                    "response": response,
                    "duration_ms": duration_ms,
                }
            )
            msg = (response.get("assistant_message") or "")[:100]
            print(
                f"  turn {index:02d}/{len(scenario['turns'])} "
                f"stage={response.get('stage')} "
                f"kind={response.get('message_kind')} "
                f"{duration_ms}ms q={msg!r}"
            )
        except Exception as err:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - turn_t0) * 1000)
            err_s = str(err)
            errors.append(f"turn {index}: {err_s}")
            turns_out.append(
                {
                    "index": index,
                    "request": body,
                    "response_status": None,
                    "error": err_s,
                    "duration_ms": duration_ms,
                }
            )
            print(f"  turn {index:02d} ERROR: {err_s[:200]}")
            break

    views: dict[str, Any] = {}
    decision_trace: dict[str, Any] = {"events": []}
    resume_session = None
    try:
        resume_session = _req("GET", f"{base}/v1/sessions/{session_id}")
        for view in ADMIN_VIEWS:
            views[view] = _admin(base, session_id, view)
        decision_trace = _req(
            "GET", f"{base}/v1/admin/sessions/{session_id}/decision-trace?limit=1000"
        )
    except Exception as err:  # noqa: BLE001
        errors.append(f"admin dump: {err}")

    db_counts = _enrich_db_counts(session_id)
    live_llm = any(
        e.get("reason_code") == "structured_writer_succeeded"
        for e in (decision_trace.get("events") or [])
    ) or any(
        e.get("llm_run_id") for e in (decision_trace.get("events") or [])
    )

    dump: dict[str, Any] = {
        "scenario_id": scenario["id"],
        "title": scenario["title"],
        "aspects": scenario["aspects"],
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "base": base,
        "health": health,
        "session": session,
        "resume": resume_session,
        "turns": turns_out,
        "admin_views": views,
        "decision_trace": decision_trace,
        "db_counts": db_counts,
        "live_llm": live_llm,
        "errors": errors,
        "completed": not errors,
    }
    dump["metrics"] = analyze_dump(dump)
    out_path.write_text(json.dumps(dump, indent=2, default=str), encoding="utf-8")
    print(
        f"wrote {out_path}  turns={len(turns_out)} events="
        f"{len(decision_trace.get('events') or [])} errors={len(errors)}"
    )
    return dump


def build_suite_report(dumps: list[dict[str, Any]], out_dir: Path) -> dict[str, Any]:
    metrics = [d.get("metrics") or analyze_dump(d) for d in dumps]
    by_id = {m["scenario_id"]: m for m in metrics if m.get("scenario_id")}

    all_event_types: Counter[str] = Counter()
    all_target_kinds: Counter[str] = Counter()
    all_target_keys: Counter[str] = Counter()
    all_dims: Counter[str] = Counter()
    for m in metrics:
        all_event_types.update(m.get("event_type_counts") or {})
        all_target_kinds.update(m.get("target_kind_counts") or {})
        all_target_keys.update(m.get("target_key_counts") or {})
        for d in m.get("dimensions_touched") or []:
            all_dims[d] += 1

    # Cross-scenario findings
    findings: list[dict[str, Any]] = []

    premature = [m for m in metrics if m.get("premature_gap_on_turn1")]
    if premature:
        findings.append(
            {
                "severity": "high",
                "id": "premature_gap_resolution",
                "summary": f"{len(premature)} scenarios jumped to gap_resolution on turn 1",
                "scenarios": [m["scenario_id"] for m in premature],
            }
        )

    leaky = [m for m in metrics if (m.get("assistant_leak_hits") or 0) > 0]
    if leaky:
        findings.append(
            {
                "severity": "high",
                "id": "policy_leakage",
                "summary": f"{len(leaky)} scenarios had internal-policy phrasing in assistant text",
                "scenarios": [m["scenario_id"] for m in leaky],
            }
        )

    stuck_open = [
        m
        for m in metrics
        if (m.get("open_contradictions") or 0) >= 3
        and (m.get("n_turns") or 0) >= 10
    ]
    if stuck_open:
        findings.append(
            {
                "severity": "medium",
                "id": "open_contradiction_stall",
                "summary": f"{len(stuck_open)} long sessions ended with ≥3 open contradictions",
                "scenarios": [m["scenario_id"] for m in stuck_open],
            }
        )

    low_gain = [
        m
        for m in metrics
        if (m.get("info_gain_ratio") or 0) < 0.35 and (m.get("n_turns") or 0) >= 12
    ]
    if low_gain:
        findings.append(
            {
                "severity": "medium",
                "id": "low_info_gain",
                "summary": f"{len(low_gain)} sessions had profile_reduced on <35% of turns",
                "scenarios": [m["scenario_id"] for m in low_gain],
            }
        )

    no_match = [
        m
        for m in metrics
        if m["scenario_id"]
        in {
            "maya_happy_path",
            "location_delayed_then_ready",
            "organizer_communicate_mode",
            "execution_deep_dive",
        }
        and not m.get("reached_project_matching")
        and not m.get("reached_profile_review")
    ]
    if no_match:
        findings.append(
            {
                "severity": "medium",
                "id": "failed_stage_progression",
                "summary": "Happy-path-ish scenarios never reached profile_review/project_matching",
                "scenarios": [m["scenario_id"] for m in no_match],
            }
        )

    fallback_heavy = [m for m in metrics if (m.get("n_fallbacks") or 0) >= 3]
    if fallback_heavy:
        findings.append(
            {
                "severity": "medium",
                "id": "writer_fallback_heavy",
                "summary": f"{len(fallback_heavy)} scenarios used question fallback ≥3 times",
                "scenarios": [m["scenario_id"] for m in fallback_heavy],
            }
        )

    # What we record well
    recording = {
        "decision_events_total": sum(m.get("n_events") or 0 for m in metrics),
        "evidence_accepted_total": sum(m.get("n_evidence_accepted") or 0 for m in metrics),
        "questions_recorded_total": sum(m.get("n_questions_recorded") or 0 for m in metrics),
        "scenarios_with_llm_runs": sum(
            1 for m in metrics if (m.get("llm_runs") or 0) > 0
        ),
        "scenarios_with_memory": sum(
            1 for m in metrics if (m.get("memory_snapshots") or 0) > 0
        ),
        "avg_dimensions_touched": round(
            sum(m.get("n_dimensions_touched") or 0 for m in metrics)
            / max(len(metrics), 1),
            2,
        ),
        "avg_info_gain_ratio": round(
            sum(m.get("info_gain_ratio") or 0 for m in metrics) / max(len(metrics), 1),
            3,
        ),
        "avg_evidence_acceptance_rate": round(
            sum(m.get("evidence_acceptance_rate") or 0 for m in metrics)
            / max(len(metrics), 1),
            3,
        ),
        "duplicate_assistant_messages_total": sum(
            m.get("duplicate_assistant_messages") or 0 for m in metrics
        ),
        "stage_regressions_total": sum(
            m.get("stage_regressions") or 0 for m in metrics
        ),
        "p95_turn_ms": _percentile(
            [
                int(t["duration_ms"])
                for dump in dumps
                for t in (dump.get("turns") or [])
                if t.get("duration_ms") is not None
            ],
            0.95,
        ),
        "stage_reach": {
            "profile_review": sum(1 for m in metrics if m.get("reached_profile_review")),
            "project_matching": sum(
                1 for m in metrics if m.get("reached_project_matching")
            ),
            "complete": sum(1 for m in metrics if m.get("reached_complete")),
        },
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_scenarios": len(metrics),
        "scenario_ids": [m.get("scenario_id") for m in metrics],
        "recording": recording,
        "event_type_totals": dict(all_event_types.most_common()),
        "target_kind_totals": dict(all_target_kinds.most_common()),
        "target_key_totals": dict(all_target_keys.most_common(30)),
        "dimensions_touched_across_scenarios": dict(all_dims.most_common()),
        "findings": findings,
        "per_scenario": metrics,
        "by_id": by_id,
    }
    report_path = out_dir / "suite_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nSuite report -> {report_path}")
    return report


def compare_reports(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Produce reassessment deltas without pretending unlike scenario sets compare."""
    current_by_id = current.get("by_id") or {}
    baseline_by_id = baseline.get("by_id") or {}
    shared = sorted(set(current_by_id) & set(baseline_by_id))
    measures = (
        "info_gain_ratio",
        "evidence_acceptance_rate",
        "duplicate_assistant_ratio",
        "max_consecutive_target_repeats",
        "multi_question_response_count",
        "project_offer_count",
        "p95_turn_ms",
    )
    per_scenario: dict[str, Any] = {}
    for scenario_id in shared:
        before = baseline_by_id[scenario_id]
        after = current_by_id[scenario_id]
        deltas = {}
        for measure in measures:
            old = before.get(measure)
            new = after.get(measure)
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                deltas[measure] = round(new - old, 3)
        per_scenario[scenario_id] = deltas
    return {
        "baseline_generated_at": baseline.get("generated_at"),
        "current_generated_at": current.get("generated_at"),
        "shared_scenarios": shared,
        "missing_from_current": sorted(set(baseline_by_id) - set(current_by_id)),
        "new_in_current": sorted(set(current_by_id) - set(baseline_by_id)),
        "per_scenario_deltas": per_scenario,
    }


STUCK_STAGE_COHORT = {
    "location_delayed_then_ready",
    "organizer_communicate_mode",
    "gamer_correction_repair",
    "bilingual_code_switch",
}


def assert_suite(report: dict[str, Any], dumps: list[dict[str, Any]]) -> list[str]:
    """Mandatory trajectory assertions. Returns actionable violation messages."""
    violations: list[str] = []
    by_id = report.get("by_id") or {}
    metrics = report.get("per_scenario") or []
    run_ids = {d.get("scenario_id") for d in dumps}

    # A1 — all scenarios completed without errors
    for dump in dumps:
        sid = dump.get("scenario_id")
        if not dump.get("completed"):
            violations.append(f"A1: {sid} not completed")
        if dump.get("errors"):
            violations.append(f"A1: {sid} errors={dump.get('errors')}")

    for m in metrics:
        sid = m.get("scenario_id")
        n_turns = m.get("n_turns") or 0
        # A2 — measure local loops, not legitimate revisits across a long chat.
        max_run = m.get("max_consecutive_target_repeats") or 0
        if n_turns >= 8 and max_run > 2:
            violations.append(
                f"A2: {sid} repeated one target {max_run} consecutive times"
            )

    thin = by_id.get("thin_elicitation_loop") or {}
    thin_dump = next(
        (d for d in dumps if d.get("scenario_id") == "thin_elicitation_loop"),
        None,
    )
    thin_events = [
        e
        for e in (thin_dump or {}).get("decision_trace", {}).get("events") or []
        if e.get("event_type") == "elicitation_selected"
    ]
    thin_responses = [
        (t.get("response") or {})
        for t in (thin_dump or {}).get("turns") or []
        if (t.get("response") or {}).get("elicitation")
    ]

    # A3 / A4 — elicitation in thin scenario (full suite only)
    if "thin_elicitation_loop" in run_ids:
        if not thin_events:
            violations.append("A3: thin_elicitation_loop missing elicitation_selected event")
        if not thin_responses:
            violations.append("A4: thin_elicitation_loop missing response.elicitation")

    # A5 — stuck cohort stage progression
    cohort = [by_id[s] for s in STUCK_STAGE_COHORT if s in by_id]
    if len(cohort) >= len(STUCK_STAGE_COHORT):
        reached = sum(
            1
            for m in cohort
            if m.get("reached_profile_review") or m.get("reached_project_matching")
        )
        rate = reached / len(cohort)
        if rate < 0.75:
            violations.append(
                f"A5: stuck cohort reached review/matching {reached}/{len(cohort)} "
                f"({rate:.0%}) < 75%"
            )

    multi = by_id.get("multi_value_nuance") or {}
    if (multi.get("open_contradictions") or 0) != 0:
        violations.append(
            f"A6: multi_value_nuance open_contradictions={multi.get('open_contradictions')}"
        )

    refuse_dump = next(
        (d for d in dumps if d.get("scenario_id") == "student_questions_and_refuse"),
        None,
    )
    if "student_questions_and_refuse" in run_ids and refuse_dump:
        refuse_events = {
            e.get("event_type")
            for e in refuse_dump.get("decision_trace", {}).get("events") or []
        }
        if "student_answer_refused" not in refuse_events:
            violations.append("A7: student_questions_and_refuse missing refusal event")
        if "evidence_extraction_skipped" not in refuse_events:
            violations.append("A7: student_questions_and_refuse missing extract skip")

    leak_total = sum(m.get("assistant_leak_hits") or 0 for m in metrics)
    if leak_total != 0:
        violations.append(f"A8: assistant_leak_hits={leak_total}")

    for m in metrics:
        sid = m.get("scenario_id")
        if (m.get("n_turns") or 0) >= 8:
            if not (m.get("llm_runs") or 0):
                violations.append(f"A9: {sid} missing llm_runs for long session")
            if not (m.get("memory_snapshots") or 0):
                violations.append(f"A9: {sid} missing memory_snapshots for long session")

    early_dump = next(
        (d for d in dumps if d.get("scenario_id") == "early_complete_attempt"),
        None,
    )
    if "early_complete_attempt" in run_ids and early_dump:
        early_stages = [
            (t.get("response") or {}).get("stage")
            for t in (early_dump.get("turns") or [])[:7]
        ]
        if "project_matching" in early_stages:
            violations.append(
                "A10: early_complete_attempt entered project_matching before turn 8"
            )

    # A12 — target_kind null rate on question_target_selected
    for dump in dumps:
        sid = dump.get("scenario_id")
        null_kinds = 0
        total = 0
        for e in dump.get("decision_trace", {}).get("events") or []:
            if e.get("event_type") != "question_target_selected":
                continue
            total += 1
            out = e.get("outputs") or {}
            if not (out.get("target_kind") or out.get("kind")):
                null_kinds += 1
        if total and null_kinds:
            violations.append(
                f"A12: {sid} has {null_kinds}/{total} question_target_selected with null target_kind"
            )

    # A13–A16 — conversation-level failure modes visible in the supplied logs.
    for m in metrics:
        sid = m.get("scenario_id")
        if (m.get("project_offer_count") or 0) > 1:
            violations.append(
                f"A13: {sid} emitted {m.get('project_offer_count')} project offers"
            )
        if (m.get("duplicate_assistant_ratio") or 0) > 0.10:
            violations.append(
                f"A14: {sid} duplicate assistant ratio "
                f"{m.get('duplicate_assistant_ratio'):.0%} > 10%"
            )
        if (m.get("stage_regressions") or 0) > 0:
            violations.append(
                f"A15: {sid} has {m.get('stage_regressions')} stage regression(s)"
            )
        if (m.get("multi_question_response_count") or 0) > 0:
            violations.append(
                f"A16: {sid} has {m.get('multi_question_response_count')} response(s) "
                "with multiple questions"
            )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated scenario ids to run",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip scenarios that already have a successful dump",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Rebuild suite_report.json from existing dumps",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List scenarios and exit",
    )
    parser.add_argument(
        "--baseline-report",
        default="",
        help="Optional prior suite_report.json; writes reassessment.json deltas",
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.list:
        for s in SCENARIOS:
            print(
                f"{s['id']:32s}  turns={len(s['turns']):2d}  "
                f"aspects={','.join(s['aspects'][:4])}..."
            )
        print(f"\n{len(SCENARIOS)} scenarios, "
              f"{sum(len(s['turns']) for s in SCENARIOS)} total turns")
        return 0

    selected = SCENARIOS
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        selected = [s for s in SCENARIOS if s["id"] in wanted]
        missing = wanted - {s["id"] for s in selected}
        if missing:
            print(f"Unknown scenario ids: {sorted(missing)}", file=sys.stderr)
            return 2

    if args.analyze_only:
        dumps = []
        for s in selected:
            path = out_dir / f"{s['id']}.json"
            if path.exists():
                dumps.append(json.loads(path.read_text(encoding="utf-8")))
        if not dumps:
            print("No dumps found", file=sys.stderr)
            return 1
        # refresh metrics
        for d in dumps:
            d["metrics"] = analyze_dump(d)
            (out_dir / f"{d['scenario_id']}.json").write_text(
                json.dumps(d, indent=2, default=str), encoding="utf-8"
            )
        report = build_suite_report(dumps, out_dir)
        if args.baseline_report:
            baseline = json.loads(Path(args.baseline_report).read_text(encoding="utf-8"))
            comparison = compare_reports(report, baseline)
            (out_dir / "reassessment.json").write_text(
                json.dumps(comparison, indent=2), encoding="utf-8"
            )
        violations = assert_suite(report, dumps)
        return 0 if not violations else 1

    # Preflight
    health = _req("GET", f"{args.base}/health")
    ready = _req("GET", f"{args.base}/health/ready")
    print(f"API health={health} ready={ready}")
    print(
        f"Running {len(selected)} scenarios, "
        f"{sum(len(s['turns']) for s in selected)} turns -> {out_dir}"
    )

    dumps: list[dict[str, Any]] = []
    for s in selected:
        dump = run_scenario(s, base=args.base, out_dir=out_dir, resume=args.resume)
        dumps.append(dump)

    report = build_suite_report(dumps, out_dir)
    if args.baseline_report:
        baseline = json.loads(Path(args.baseline_report).read_text(encoding="utf-8"))
        comparison = compare_reports(report, baseline)
        (out_dir / "reassessment.json").write_text(
            json.dumps(comparison, indent=2), encoding="utf-8"
        )
    violations = assert_suite(report, dumps)
    if violations:
        print("\nSuite assertion failures:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
    failed = [d for d in dumps if d.get("errors")]
    print(
        f"\nDone. {len(dumps) - len(failed)}/{len(dumps)} clean. "
        f"Findings={len(report.get('findings') or [])} "
        f"AssertionViolations={len(violations)}"
    )
    return 0 if not failed and not violations else 1


if __name__ == "__main__":
    sys.exit(main())
