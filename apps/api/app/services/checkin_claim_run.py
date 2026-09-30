"""Seeded measurement of the deterministic check-in pipeline (Plan 05 §5.6).

The timed path is the pure scheduler and scorer: gate, trigger, kind, item,
then a score. It does not call the LLM and does not touch the database.
Check-ins with ``quiz_active`` must not deliver an item.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from app.contracts.learning_checkin import (
    DETERMINISTIC_PIPELINE_P95_MS,
    RESPONSE_RATE_TARGET,
    CheckinGate,
)
from app.services.claim_stats import verify_percentile, verify_wilson_ci
from app.services.learning_checkin_engine import (
    CheckinContext,
    checkin_gate,
    choose_item,
    choose_kind,
    score_likert,
    score_mcq,
    score_rubric,
    select_trigger,
)

NOW = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)
_CONTENT_ROOT = Path(__file__).resolve().parents[4] / "content" / "modules"
_BANK_RELATIVE = Path("shared") / "how-apps-work" / "checkins.json"


def load_checkin_bank(path: Path | None = None) -> list[dict[str, Any]]:
    """Flatten one authored check-in bank. Read-only; content files stay put."""
    source = path or (_CONTENT_ROOT / _BANK_RELATIVE)
    payload = json.loads(source.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    for bank in payload["objectives"]:
        for item in bank["items"]:
            items.append(
                {
                    "kind": item["kind"],
                    "seq": item["seq"],
                    "answer": list(item.get("answer") or []),
                    "rubric": item.get("rubric") or {},
                    "scale": item.get("scale") or {"min": 1, "max": 5},
                }
            )
    if not items:
        raise ValueError(f"no check-in items in {source}")
    return items


def context_for(index: int) -> CheckinContext:
    """Fixed mix of gates and triggers. Slot 0 is an active quiz."""
    slot = index % 7
    if slot == 0:
        return CheckinContext(now=NOW, checkins_used=0, quiz_active=True, section_completed=True)
    if slot == 1:
        return CheckinContext(now=NOW, checkins_used=index % 3, section_completed=True)
    if slot == 2:
        return CheckinContext(
            now=NOW,
            checkins_used=1,
            section_completed=True,
            last_delivered_at=NOW - timedelta(seconds=30),
        )
    if slot == 3:
        return CheckinContext(now=NOW, checkins_used=3, section_completed=True)
    if slot == 4:
        return CheckinContext(now=NOW, checkins_used=0, milestone_passed=True)
    if slot == 5:
        return CheckinContext(now=NOW, checkins_used=0, recent_wrong=3, recent_fast_wrong=3)
    return CheckinContext(now=NOW, checkins_used=0, retention_due=True, section_completed=True)


def run_deterministic_pipeline(context: CheckinContext, items: list[dict[str, Any]]) -> bool:
    """One scheduler+score pass. True only when an item is actually delivered."""
    gate, _retry = checkin_gate(context)
    if gate != CheckinGate.AVAILABLE:
        return False
    trigger = select_trigger(context)
    if trigger is None:
        return False
    kind = choose_kind(trigger, context.checkins_used)
    item = choose_item(items, kind, context.checkins_used)
    if item is None:
        return False
    _score_item(item)
    return True


def _score_item(item: dict[str, Any]) -> float:
    kind = item["kind"]
    if kind == "likert":
        scale = item["scale"]
        return score_likert(3, int(scale["min"]), int(scale["max"]))
    if kind == "mcq":
        answer = [str(key) for key in item["answer"]]
        return score_mcq(answer, answer)
    criteria = list((item.get("rubric") or {}).get("criteria") or [])
    return score_rubric(1 if criteria else 0, len(criteria))


def measure_seeded_pipeline(
    *, n: int = 2000, warmup: int = 50, items: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Time ``n`` seeded pipeline calls. Warmup samples are not in the percentile."""
    if n < 1:
        raise ValueError("n must be at least 1")
    bank = items if items is not None else load_checkin_bank()
    for index in range(warmup):
        run_deterministic_pipeline(context_for(index), bank)
    elapsed_ms: list[float] = []
    quiz_samples = 0
    quiz_deliveries = 0
    delivered = 0
    for index in range(n):
        context = context_for(index)
        started = perf_counter()
        did_deliver = run_deterministic_pipeline(context, bank)
        elapsed_ms.append((perf_counter() - started) * 1000.0)
        if did_deliver:
            delivered += 1
        if context.quiz_active:
            quiz_samples += 1
            if did_deliver:
                quiz_deliveries += 1
    p50 = verify_percentile(elapsed_ms, 0.50)
    p95 = verify_percentile(elapsed_ms, 0.95)
    return {
        "n": n,
        "warmup_excluded": warmup,
        "delivered": delivered,
        "quiz_samples": quiz_samples,
        "quiz_deliveries": quiz_deliveries,
        "quiz_target_met": quiz_deliveries == 0,
        "p50_ms": p50["value"],
        "p95_ms": p95["value"],
        "p50": p50,
        "p95": p95,
        "min_ms": min(elapsed_ms),
        "max_ms": max(elapsed_ms),
        "target_ms": DETERMINISTIC_PIPELINE_P95_MS,
        "target_met": float(p95["value"]) < DETERMINISTIC_PIPELINE_P95_MS,
    }


def response_rate_claim(responded: int, delivered: int) -> dict[str, Any]:
    """Wilson interval for answered/delivered. ``n == 0`` is blocked, not 0%."""
    if delivered <= 0:
        return {
            "blocked": True,
            "reason": "no delivered check-ins to measure",
            "responded": responded,
            "delivered": delivered,
            "target": RESPONSE_RATE_TARGET,
            "target_met": False,
        }
    interval = verify_wilson_ci(responded, delivered)
    point = float(interval["point"])
    lower = float(interval["lower"])
    return {
        "blocked": False,
        "responded": responded,
        "delivered": delivered,
        "dismissed_or_open_are_non_responses": True,
        "point": point,
        "lower": lower,
        "upper": float(interval["upper"]),
        "z": interval["z"],
        "method": interval["method"],
        "n": delivered,
        "target": RESPONSE_RATE_TARGET,
        "target_met": point > RESPONSE_RATE_TARGET,
        "lower_bound_clears_target": lower > RESPONSE_RATE_TARGET,
    }
