#!/usr/bin/env python3
"""Live assessment conversation sim with quality assertions.

Usage (host API + compose Postgres; Azure via az login):
  .venv/Scripts/python scripts/sim_assessment_conversation.py --turns 5
  .venv/Scripts/python scripts/sim_assessment_conversation.py --turns 12 --out sim-conversation-dump.json
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAYA_TURNS = [
    "Hi! I am Maya, a 10th grader. I really like building small science projects that use neighborhood data — like air quality sensors and maps.",
    "I prefer working with one or two friends rather than a big group. I get overwhelmed when too many people are deciding at once.",
    "What motivates me is helping my community understand local problems. Grades matter less than making something useful people can actually use.",
    "I am pretty comfortable with Python basics and spreadsheets, but I have never built a full web app. I would need help with databases and hosting.",
    "Actually I changed my mind a bit — I also enjoy working alone when I am deep in analysis. Group work is fine for brainstorming but not for coding.",
    "For constraints, weekday evenings after 7pm are best, and the project should stay small enough to finish in about six weeks. I am based in Seattle.",
    "I care about both curiosity and impact together — exploring sensors is fun because it helps neighbors. They are not competing goals for me.",
    "Challenge-wise I like stretching a bit, but not so hard that I get stuck for weeks. Scaffolded hard problems are ideal.",
    "If I had to pick a primary topic right now, neighborhood air quality maps with a simple Python analysis pipeline.",
    "Yes, that profile sounds right — small-group brainstorming, solo coding, community impact, Python/spreadsheets with help on hosting.",
    "Between a sensor-data dashboard and a neighborhood interview story map, the dashboard fits better because I already know Python.",
    "I am ready to pick a project direction and start scoping the first milestone.",
]

STUDENT_QUESTION_PROBE = [
    "What does work mode mean?",
    "Write my history essay on Rome",
    "Why are you asking about groups?",
]

THIN_ANSWER_PROBE = [
    "idk",
    "ok",
]

PROJECT_MATCHING_PROBE = [
    "I live in the Seattle metro area.",
    "Yes, that profile summary feels accurate.",
]

EXTENDED = [
    "One more thing: for challenge level I want seek_hard problems, not avoid_hard ones — I prefer X not Y there.",
    "To clarify challenge: I definitely want seek_hard. avoid_hard is wrong for me.",
    "Please remind me what you think my top motivation is before we lock a project.",
]

# Force a true single-choice conflict then resolve (appended when --conflict-probe).
CONFLICT_PROBE = [
    "For challenge appetite I am torn between seeking hard problems and avoiding hard ones — I said both.",
    "Clarifying challenge: I want seek_hard. Not avoid_hard.",
]


def _req(method: str, url: str, body: dict | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> {err.code}: {detail}") from err
    except URLError as err:
        raise RuntimeError(f"{method} {url} failed: {err}") from err


def _admin(base: str, session_id: str, view: str) -> Any:
    return _req("GET", f"{base}/v1/admin/sessions/{session_id}/{view}")


def run_assertions(dump: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    contradictions = dump["admin_views"]["contradictions"]["items"]
    open_rows = [c for c in contradictions if c.get("status") == "open"]
    stages = [t["response"]["stage"] for t in dump["turns"] if t.get("response")]
    turn1_stage = stages[0] if stages else None

    # P0: no false multi-support opens on Maya-like openings.
    false_dims = {"motivation", "topics", "capability"}
    open_false = [
        c for c in open_rows if c.get("dimension_key") in false_dims
    ]
    if open_false and len(dump["turns"]) >= 1:
        # After full Maya script these should not remain open from false multi-support.
        failures.append(
            f"unexpected open contradictions on multi-value dims: "
            f"{[c.get('dimension_key') for c in open_false]}"
        )

    if turn1_stage == "gap_resolution":
        failures.append("turn 1 jumped straight to gap_resolution")

    if "I heard two different preferences" in json.dumps(
        [t.get("response", {}).get("assistant_message", "") for t in dump["turns"]]
    ):
        failures.append("generic contradiction fallback leaked into assistant messages")

    events = dump.get("decision_trace", {}).get("events", [])
    if events:
        extract_write = [
            e
            for e in events
            if e.get("event_type") in {"evidence_proposed", "question_written"}
        ]
        linked = [e for e in extract_write if e.get("llm_run_id")]
        if dump.get("live_llm") and extract_write and not linked:
            failures.append("live LLM but extract/write events missing llm_run_id")

    llm_runs = dump.get("llm_runs", {}).get("count", 0)
    if dump.get("live_llm") and llm_runs < 1:
        failures.append("live LLM but audit.llm_runs empty")

    if len(dump["turns"]) >= 8:
        mem = dump.get("memory_snapshots", {}).get("count", 0)
        if mem < 1:
            failures.append("expected memory snapshot after >=8 student responses")

    # Should not stall with many opens after a clarifying Maya script.
    if len(dump["turns"]) >= 5 and len(open_rows) >= 6:
        failures.append(f"stalled with {len(open_rows)} open contradictions")

    fallback_msgs = [
        t.get("response", {}).get("assistant_message", "")
        for t in dump["turns"]
        if t.get("response")
    ]
    generic_prov = sum(
        1
        for m in fallback_msgs
        if m == "Could you give a concrete example of that preference?"
    )
    if generic_prov >= 3:
        failures.append(f"provisional fallback repeated {generic_prov} times")

    stages = [t["response"]["stage"] for t in dump["turns"] if t.get("response")]
    if stages and stages[0] not in {"discovery", "measurement"}:
        failures.append(f"turn 1 stage not discovery/measurement: {stages[0]}")

    events = dump.get("decision_trace", {}).get("events", [])
    event_types = {e.get("event_type") for e in events}

    if dump.get("probe") == "student_questions":
        if "turn_intent_classified" not in event_types:
            failures.append("student-questions probe missing turn_intent_classified")
        if "student_answer_refused" not in event_types:
            failures.append("student-questions probe missing refuse for homework ask")
        # Pure process question should not invent evidence on that turn alone —
        # check the first probe turn evidence delta via decision reasons.
        skipped = [
            e
            for e in events
            if e.get("event_type") == "evidence_extraction_skipped"
        ]
        if not skipped:
            failures.append("expected evidence_extraction_skipped for pure student Q")

    if dump.get("probe") == "thin_answer":
        if "answer_thinness_evaluated" not in event_types:
            failures.append("thin-answer probe missing thinness event")
        if "elicitation_selected" not in event_types:
            failures.append("thin-answer probe missing elicitation_selected")
        msgs = [
            t.get("response", {}).get("assistant_message", "").lower()
            for t in dump["turns"]
            if t.get("response")
        ]
        if not any(
            "small group" in m
            or "independent" in m
            or "option" in m
            or "which is closer" in m
            or "or something else" in m
            for m in msgs
        ):
            failures.append("thin-answer probe expected option-style elicitation wording")
        evidence_items = dump["admin_views"]["evidence"]["items"]
        oppose_idk = [
            e
            for e in evidence_items
            if e.get("polarity") == "oppose"
            and "idk" in (e.get("exact_source_quote") or "").lower()
        ]
        if oppose_idk:
            failures.append("idk produced oppose evidence")

    if dump.get("probe") == "project_matching":
        pf_items = dump["admin_views"]["project-fit"]["items"]
        if not isinstance(pf_items, list):
            failures.append("project-fit admin view should return a list")
        geo_events = [
            e
            for e in events
            if e.get("event_type") == "location_readiness_checked"
        ]
        if not geo_events:
            failures.append("project-matching probe missing location_readiness_checked")
        ready = [e for e in events if e.get("reason_code") == "location_ready"]
        if dump.get("expect_location_ready") and not ready:
            failures.append("expected location_ready after Seattle constraint")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--out", default="sim-conversation-dump.json")
    parser.add_argument("--extend", action="store_true", help="Add post-resume turns")
    parser.add_argument(
        "--conflict-probe",
        action="store_true",
        help="Append true challenge conflict + resolution turns",
    )
    parser.add_argument(
        "--student-questions",
        action="store_true",
        help="Probe process Q + homework refuse + resume",
    )
    parser.add_argument(
        "--thin-answer-probe",
        action="store_true",
        help="Probe idk/ok elicitation options",
    )
    parser.add_argument(
        "--project-matching-probe",
        action="store_true",
        help="Probe geo readiness and project matching artifacts",
    )
    args = parser.parse_args()

    script = MAYA_TURNS[: max(1, min(args.turns, len(MAYA_TURNS)))]
    if args.turns > len(MAYA_TURNS):
        script = MAYA_TURNS + EXTENDED[: max(0, args.turns - len(MAYA_TURNS))]
    if args.extend:
        script = script + EXTENDED
    if args.conflict_probe:
        script = script + CONFLICT_PROBE
    probe = None
    if args.student_questions:
        script = script + STUDENT_QUESTION_PROBE
        probe = "student_questions"
    if args.thin_answer_probe:
        # Ask a work-mode question context then thin answers
        script = script[:2] + THIN_ANSWER_PROBE
        probe = "thin_answer"
    if args.project_matching_probe:
        script = script + PROJECT_MATCHING_PROBE
        probe = "project_matching"

    health = _req("GET", f"{args.base}/health")
    session = _req("POST", f"{args.base}/v1/sessions", None)
    session_id = str(session["session_id"])

    turns_out: list[dict[str, Any]] = []
    for index, text in enumerate(script, start=1):
        body = {
            "idempotency_key": f"live-turn-{index:02d}-{uuid.uuid4().hex[:8]}",
            "text": text,
        }
        response = _req(
            "POST", f"{args.base}/v1/sessions/{session_id}/turns", body
        )
        turns_out.append(
            {
                "request": body,
                "response_status": 200,
                "response": response,
            }
        )
        print(
            f"turn {index:02d} stage={response.get('stage')} "
            f"q={response.get('assistant_message', '')[:90]!r}"
        )

    resume = _req("GET", f"{args.base}/v1/sessions/{session_id}")
    views = {}
    for view in (
        "transcript",
        "evidence",
        "profile",
        "profile-history",
        "question-history",
        "why-next-question",
        "contradictions",
        "project-fit",
    ):
        views[view] = _admin(args.base, session_id, view)

    decision_trace = _req(
        "GET", f"{args.base}/v1/admin/sessions/{session_id}/decision-trace"
    )

    # Direct DB-ish admin counts via contradictions + optional SQL through docker is
    # outside HTTP; approximate llm/memory via decision-trace + postgres helper later.
    live_llm = any(
        e.get("reason_code") == "structured_writer_succeeded"
        for e in decision_trace.get("events", [])
    )
    linked_runs = sum(
        1 for e in decision_trace.get("events", []) if e.get("llm_run_id")
    )

    dump: dict[str, Any] = {
        "mode": "host API + compose postgres",
        "health": health,
        "session": session,
        "turns": turns_out,
        "resume": resume,
        "admin_views": views,
        "decision_trace": decision_trace,
        "live_llm": live_llm,
        "llm_runs": {"linked_decision_events": linked_runs},
        "memory_snapshots": {"count": None},
        "probe": probe,
        "expect_location_ready": bool(args.project_matching_probe),
        "assertions": {},
    }

    # Optional enrichment from local docker postgres.
    try:
        import subprocess

        sql = (
            f"SELECT "
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
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            llm_c, mem_c = proc.stdout.strip().split(",", 1)
            dump["llm_runs"] = {
                "count": int(llm_c),
                "linked_decision_events": linked_runs,
            }
            dump["memory_snapshots"] = {"count": int(mem_c)}
    except Exception as err:  # noqa: BLE001
        dump["enrichment_error"] = str(err)

    failures = run_assertions(dump)
    dump["assertions"] = {
        "passed": not failures,
        "failures": failures,
    }
    out_path = Path(args.out)
    out_path.write_text(json.dumps(dump, indent=2, default=str), encoding="utf-8")
    print(json.dumps(dump["assertions"], indent=2))
    print(f"wrote {out_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
