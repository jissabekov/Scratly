#!/usr/bin/env python3
"""Measure Plan 05 §5.6 check-in claims.

One command, from the repo root::

    .venv/Scripts/python scripts/measure_checkin_claims.py

Prints:

* p50/p95 of the deterministic scheduler+scorer over a seeded workload,
  recomputed with ``verify_percentile`` (numpy linear). Target: p95 < 100 ms.
* How many of those quiz-active samples delivered an item. Target: 0.
* Response rate on stored ``learning.checkin_events`` (answered / delivered),
  with ``verify_wilson_ci`` (Wilson, z=1.96). Target: point estimate > 0.60.
  Dismissed and still-open deliveries count as non-responses. If nothing has
  been delivered, the response-rate claim is blocked rather than reported as 0.
* When Postgres is reachable, wall-clock p95 of ``CheckinRepository.deliver``
  on thrown-away sessions (rolled back, then deleted). Those sessions are not
  included in the response-rate sample.

The response rate is whatever is already stored. This script does not insert
answered check-ins and does not change the 0.60 threshold.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_dsn(explicit: str | None) -> str:
    if explicit:
        return explicit
    for path in (ROOT / "apps" / "api" / ".env", ROOT / ".env"):
        value = _read_env_file(path).get("DATABASE_URL")
        if value:
            return value
    return "postgresql+asyncpg://scratly:scratly_local_only@localhost:5432/scratly"


def to_sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql+asyncpg://"):
        return dsn
    if dsn.startswith("postgresql://"):
        return "postgresql+asyncpg://" + dsn[len("postgresql://") :]
    return dsn


os.environ["DATABASE_URL"] = to_sqlalchemy_dsn(resolve_dsn(os.environ.get("DATABASE_URL")))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.repository.assessment import AssessmentRepository  # noqa: E402
from app.repository.learning_checkin import CheckinRepository  # noqa: E402
from app.services.checkin_claim_run import (  # noqa: E402
    measure_seeded_pipeline,
    response_rate_claim,
)
from app.services.claim_stats import verify_percentile  # noqa: E402
from app.services.learning_progress import (  # noqa: E402
    XAPI_OBJECT_SLIDE,
    XAPI_VERB_COMPLETED,
    xapi_statement,
)

MEASURE_PREFIX = "measure-checkin-"


def _json(value: object) -> str:
    return json.dumps(value, default=str)


async def _counts(session) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT count(*) FILTER (WHERE e.delivered_at IS NOT NULL) AS delivered,
                       count(*) FILTER (
                           WHERE e.delivered_at IS NOT NULL AND e.responded_at IS NOT NULL
                       ) AS responded,
                       count(*) FILTER (WHERE e.dismissed) AS dismissed
                  FROM learning.checkin_events e
                  JOIN core.sessions s ON s.id = e.session_id
                  JOIN core.students st ON st.id = s.student_id
                 WHERE st.external_ref IS NULL
                    OR st.external_ref NOT LIKE :prefix
                """
                ),
                {"prefix": MEASURE_PREFIX + "%"},
            )
        )
        .mappings()
        .one()
    )
    during = (
        await session.execute(
            text(
                """
                SELECT count(*) AS during_quiz
                  FROM learning.checkin_events e
                  JOIN learning.quiz_attempts q ON q.session_id = e.session_id
                  JOIN core.sessions s ON s.id = e.session_id
                  JOIN core.students st ON st.id = s.student_id
                 WHERE e.delivered_at >= q.started_at
                   AND (q.submitted_at IS NULL OR e.delivered_at < q.submitted_at)
                   AND (st.external_ref IS NULL OR st.external_ref NOT LIKE :prefix)
                """
            ),
            {"prefix": MEASURE_PREFIX + "%"},
        )
    ).scalar_one()
    return {
        "delivered": int(row["delivered"] or 0),
        "responded": int(row["responded"] or 0),
        "dismissed": int(row["dismissed"] or 0),
        "during_quiz": int(during or 0),
    }


async def _content_anchor(session) -> dict | None:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT s.id AS slide_id, m.id AS module_id
                  FROM learning.slides s
                  JOIN learning.checkin_items i ON i.objective_id = s.objective_id
                  JOIN learning.lessons l ON l.id = s.lesson_id
                  JOIN learning.modules m ON m.id = l.module_id
                 LIMIT 1
                """
                )
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def _profile_writes(session, session_id) -> int:
    evidence = (
        await session.execute(
            text("SELECT count(*) FROM assessment.evidence WHERE session_id = :sid"),
            {"sid": session_id},
        )
    ).scalar_one()
    snapshots = (
        await session.execute(
            text("SELECT count(*) FROM assessment.profile_snapshots WHERE session_id = :sid"),
            {"sid": session_id},
        )
    ).scalar_one()
    return int(evidence or 0) + int(snapshots or 0)


async def _delete_session(session, session_id, student_id) -> None:
    await session.execute(
        text("DELETE FROM core.sessions WHERE id = :sid"),
        {"sid": session_id},
    )
    await session.execute(
        text("DELETE FROM core.students WHERE id = :sid"),
        {"sid": student_id},
    )
    await session.commit()


async def _seed_section(session, student_id, session_id, slide_id) -> None:
    statement = xapi_statement(
        actor_name=str(student_id),
        verb_id=XAPI_VERB_COMPLETED,
        object_id=f"slide:{slide_id}",
        object_type=XAPI_OBJECT_SLIDE,
        object_name="section",
    )
    request_id = f"measure-slide-{uuid4()}"
    await session.execute(
        text(
            """
            INSERT INTO learning.learning_events
                (student_id, session_id, actor, verb, object, result, context, request_id)
            VALUES (:student_id, :session_id, CAST(:actor AS jsonb), CAST(:verb AS jsonb),
                    CAST(:object AS jsonb), NULL, CAST(:context AS jsonb), :request_id)
            """
        ),
        {
            "student_id": student_id,
            "session_id": session_id,
            "actor": _json(statement["actor"]),
            "verb": _json(statement["verb"]),
            "object": _json(statement["object"]),
            "context": _json(statement["context"]),
            "request_id": request_id,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO learning.slide_completions
                (student_id, session_id, slide_id, request_id)
            VALUES (:student_id, :session_id, :slide_id, :request_id)
            """
        ),
        {
            "student_id": student_id,
            "session_id": session_id,
            "slide_id": slide_id,
            "request_id": request_id,
        },
    )


async def measure_deliver_path(*, samples: int, quiz_samples: int) -> dict:
    """Time real ``deliver`` calls. Inserts are rolled back; sessions are deleted."""
    durations: list[float] = []
    quiz_deliveries = 0
    profile_writes = 0
    delivered = 0
    async with SessionLocal() as session:
        anchor = await _content_anchor(session)
    if anchor is None:
        return {
            "measured": False,
            "reason": "no seeded slide with a check-in item; deliver path not timed",
        }
    total = samples + quiz_samples
    # A few untimed calls warm the pool. They are rolled back like the rest.
    for index in range(total + 3):
        timed = index >= 3
        quiz = timed and index >= 3 + samples
        result = None
        elapsed_ms = 0.0
        writes = 0
        async with SessionLocal() as session:
            created = await AssessmentRepository(session).create_session(
                external_ref=f"{MEASURE_PREFIX}{uuid4()}",
                learning_enabled=True,
            )
            session_id = created["session_id"]
            student_id = created["student_id"]
            try:
                await _seed_section(session, student_id, session_id, anchor["slide_id"])
                if quiz:
                    await session.execute(
                        text(
                            """
                            INSERT INTO learning.quiz_attempts
                                (student_id, session_id, module_id, attempt_no, form_id, item_ids)
                            VALUES (:student_id, :session_id, :module_id, 1, 1, '[]'::jsonb)
                            """
                        ),
                        {
                            "student_id": student_id,
                            "session_id": session_id,
                            "module_id": anchor["module_id"],
                        },
                    )
                before = await _profile_writes(session, session_id)
                started = perf_counter()
                result = await CheckinRepository(session).deliver(session_id, commit=False)
                elapsed_ms = (perf_counter() - started) * 1000.0
                writes = await _profile_writes(session, session_id) - before
            finally:
                await session.rollback()
                await _delete_session(session, session_id, student_id)
        if not timed or result is None:
            continue
        profile_writes += writes
        if quiz:
            if result.item is not None:
                quiz_deliveries += 1
            continue
        durations.append(elapsed_ms)
        if result.item is not None:
            delivered += 1
    if not durations:
        return {"measured": False, "reason": "no deliver samples completed"}
    p95 = verify_percentile(durations, 0.95)
    p50 = verify_percentile(durations, 0.50)
    return {
        "measured": True,
        "n": len(durations),
        "warmup_excluded": 3,
        "delivered": delivered,
        "quiz_samples": quiz_samples,
        "quiz_deliveries": quiz_deliveries,
        "assessment_profile_writes": profile_writes,
        "p50_ms": p50["value"],
        "p95_ms": p95["value"],
        "p50": p50,
        "p95": p95,
        "min_ms": min(durations),
        "max_ms": max(durations),
    }


async def measure_stored_traffic() -> dict:
    async with SessionLocal() as session:
        counts = await _counts(session)
    claim = response_rate_claim(counts["responded"], counts["delivered"])
    claim["population"] = (
        "learning.checkin_events already stored in local Postgres, "
        "excluding external_ref measure-checkin-*"
    )
    claim["dismissed"] = counts["dismissed"]
    claim["during_quiz"] = counts["during_quiz"]
    claim["during_quiz_target_met"] = counts["during_quiz"] == 0
    return claim


def _round_ms(value: object) -> str:
    return f"{float(value):.4f}"


def _round_rate(value: object) -> str:
    return f"{float(value):.3f}"


async def _run(args: argparse.Namespace) -> dict:
    try:
        return await _collect(args)
    finally:
        await engine.dispose()


async def _collect(args: argparse.Namespace) -> dict:
    pipeline = measure_seeded_pipeline(n=args.pipeline_samples, warmup=args.warmup)
    try:
        stored = await measure_stored_traffic()
    except Exception as exc:
        reason = f"postgres unread: {type(exc).__name__}: {exc}"
        stored = {"blocked": True, "reason": reason, "target_met": False}
        return {
            "pipeline": pipeline,
            "stored_response_rate": stored,
            "deliver_path": {"measured": False, "reason": reason},
            "stored_response_rate_after_deliver_samples": {
                "delivered": None,
                "responded": None,
                "unchanged": False,
            },
        }
    try:
        deliver = await measure_deliver_path(
            samples=args.deliver_samples, quiz_samples=args.quiz_samples
        )
    except Exception as exc:
        deliver = {"measured": False, "reason": f"{type(exc).__name__}: {exc}"}
    try:
        stored_after = await measure_stored_traffic()
    except Exception:
        stored_after = stored
    return {
        "pipeline": pipeline,
        "stored_response_rate": stored,
        "deliver_path": deliver,
        "stored_response_rate_after_deliver_samples": {
            "delivered": stored_after.get("delivered"),
            "responded": stored_after.get("responded"),
            "unchanged": (
                stored.get("delivered") == stored_after.get("delivered")
                and stored.get("responded") == stored_after.get("responded")
            ),
        },
    }


def _print_report(report: dict) -> None:
    pipeline = report["pipeline"]
    stored = report["stored_response_rate"]
    deliver = report["deliver_path"]
    print("deterministic pipeline (seeded engine calls, no LLM, no DB)")
    print(
        f"  n={pipeline['n']} warmup_excluded={pipeline['warmup_excluded']} "
        f"p50={_round_ms(pipeline['p50_ms'])} ms "
        f"p95={_round_ms(pipeline['p95_ms'])} ms "
        f"target<{pipeline['target_ms']} ms met={pipeline['target_met']}"
    )
    print(
        f"  verify_percentile p95 method={pipeline['p95']['method']} "
        f"q={pipeline['p95']['q']} unique={pipeline['p95']['unique']}"
    )
    print(
        f"  quiz_samples={pipeline['quiz_samples']} "
        f"quiz_deliveries={pipeline['quiz_deliveries']} "
        f"met={pipeline['quiz_target_met']}"
    )
    print("stored check-in response rate")
    if stored.get("blocked"):
        print(f"  BLOCKED {stored.get('reason')}")
    else:
        print(
            f"  responded={stored['responded']} delivered={stored['delivered']} "
            f"dismissed={stored['dismissed']} "
            f"point={_round_rate(stored['point'])} "
            f"wilson95=[{_round_rate(stored['lower'])}, {_round_rate(stored['upper'])}] "
            f"target>{stored['target']} met={stored['target_met']} "
            f"lower_bound_clears_target={stored['lower_bound_clears_target']}"
        )
        print(
            f"  verify_wilson_ci method={stored['method']} z={stored['z']} "
            f"during_quiz={stored['during_quiz']} met={stored['during_quiz_target_met']}"
        )
        print(f"  population: {stored['population']}")
    print("repository deliver() wall clock (rolled back)")
    if not deliver.get("measured"):
        print(f"  not measured: {deliver.get('reason')}")
    else:
        print(
            f"  n={deliver['n']} warmup_excluded={deliver['warmup_excluded']} "
            f"p50={_round_ms(deliver['p50_ms'])} ms "
            f"p95={_round_ms(deliver['p95_ms'])} ms "
            f"quiz_deliveries={deliver['quiz_deliveries']} "
            f"assessment_profile_writes={deliver['assessment_profile_writes']}"
        )
    unchanged = report["stored_response_rate_after_deliver_samples"]["unchanged"]
    print(f"stored counts unchanged by deliver samples: {unchanged}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-samples", type=int, default=2000)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--deliver-samples", type=int, default=40)
    parser.add_argument("--quiz-samples", type=int, default=10)
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    _print_report(report)
    print("JSON")
    print(json.dumps(report, default=str))


if __name__ == "__main__":
    main()
