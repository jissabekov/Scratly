#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_conversation_suite import assert_suite, build_suite_report

OUT = ROOT / "eval" / "traces" / (
    sys.argv[1] if len(sys.argv) > 1 else "post-fix-v2"
)

dumps = [
    json.load(open(p, encoding="utf-8"))
    for p in sorted(OUT.glob("*.json"))
    if p.name != "suite_report.json"
]
report = build_suite_report(dumps, OUT)
violations = assert_suite(report, dumps)

rows = []
for m in report["per_scenario"]:
    tc = m.get("target_key_counts") or {}
    max_freq = max(tc.values()) if tc else 0
    rows.append(
        {
            "id": m["scenario_id"],
            "turns": m["n_turns"],
            "final": m.get("final_stage"),
            "review": m.get("reached_profile_review"),
            "match": m.get("reached_project_matching"),
            "max_reask": max_freq,
            "unique_keys": len(tc),
            "elicitation": m.get("n_elicitation_events", 0),
            "open_c": m.get("open_contradictions", 0),
            "mean_ms": m.get("mean_turn_ms"),
            "errors": len(m.get("errors") or []),
        }
    )

print("=== WHY SLOW ===")
total_turns = sum(r["turns"] for r in rows)
mean_ms = sum(r["mean_ms"] or 0 for r in rows) / max(len(rows), 1)
# per scenario: turns + admin dump (5-10s overhead)
print(f"Scenarios: {len(rows)}  Total turns: {total_turns}")
print(f"Avg turn latency (LLM+DB): {mean_ms:.0f}ms (~{mean_ms/1000:.1f}s)")
print(
    f"Turn processing alone: ~{total_turns * mean_ms / 1000 / 60:.0f} min serial"
)
print(
    "Plus per session: 7 admin API calls + decision-trace dump (~5-15s each)"
)
print(f"Realistic wall clock: ~{total_turns * mean_ms / 1000 / 60 * 1.15 + 18 * 0.5:.0f}-"
      f"{total_turns * mean_ms / 1000 / 60 * 1.3 + 18 * 1:.0f} min")

print("\n=== STAGE REACH (post-fix) ===")
sr = report["recording"]["stage_reach"]
print(f"profile_review:  {sr['profile_review']}/18  (baseline: 5/18)")
print(f"project_matching: {sr['project_matching']}/18  (baseline: 7/18)")
print(f"complete:        {sr['complete']}/18  (baseline: 0/18)")

stuck_cohort = {
    "location_delayed_then_ready",
    "organizer_communicate_mode",
    "gamer_correction_repair",
    "bilingual_code_switch",
}
cohort = [r for r in rows if r["id"] in stuck_cohort]
cohort_reached = sum(1 for r in cohort if r["review"] or r["match"])
print(f"Stuck cohort review/match: {cohort_reached}/{len(cohort)} (A5 needs >=3/4)")

print("\n=== KEY FIX SIGNALS ===")
et = report.get("event_type_totals") or {}
print(f"question_target_blocked: {et.get('question_target_blocked', 0)}")
print(f"elicitation_selected:    {et.get('elicitation_selected', 0)}")
print(f"elicitation_rephrase:    {et.get('elicitation_rephrase', 0)}")
print(f"geo_inferred_from_text:  {et.get('geo_inferred_from_text', 0)}")
print(f"stage_gate_evaluated:    {et.get('stage_gate_evaluated', 0)}")
print(f"assistant_leak_hits total: {sum(m.get('assistant_leak_hits',0) for m in report['per_scenario'])}")

print("\n=== PER SCENARIO ===")
for r in rows:
    flags = []
    if r["max_reask"] > 4:
        flags.append(f"reask={r['max_reask']}")
    if not r["review"] and not r["match"]:
        flags.append("no_review/match")
    if r["elicitation"]:
        flags.append(f"elicit={r['elicitation']}")
    if r["open_c"]:
        flags.append(f"open_c={r['open_c']}")
    f = " | ".join(flags) if flags else "ok"
    print(
        f"{r['id']:35s} {r['turns']:2d}t  {str(r['final']):18s}  "
        f"keys={r['unique_keys']:2d}  {f}"
    )

print(f"\n=== ASSERTION VIOLATIONS ({len(violations)}) ===")
for v in violations:
    print(" ", v)
