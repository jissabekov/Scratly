---
name: eval-suite
description: Run the 28-scenario live conversation eval harness, analyze results, and interpret assertions A1–A23
allowed-tools:
  - exec
  - read
  - grep
  - glob
---

Prereqs: Postgres running (`docker compose up -d --wait postgres`), API on :8000 (`cd apps/api && ../../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`), Azure OpenAI configured in `apps/api/.env`. Full suite takes ~65–80 min serial; partial runs are fine after targeted policy changes.

1. Always write traces to a NEW directory (never overwrite an existing one):
   `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/<date-label>`
2. Partial run: add `--only scenario_id1,scenario_id2` (IDs listed in docs/eval-suite.md).
3. Baseline comparison: `--analyze-only --out-dir <dir> --baseline-report eval/traces/latest/suite_report.json` (writes `reassessment.json`).
4. Summarize: `.venv/Scripts/python eval/analyze_post_fix.py <dir>`.
5. Interpret: exit code 1 = assertion violations or scenario errors. Key assertions: A2 = no target repeated >2 consecutive turns; A14 = duplicate assistant ratio ≤10%; A15 = no stage regressions; A18 = adaptive `sim_*` end-to-end rubric. Quote exact violation lines from the log tail.
6. Proof workflow: run affected `--only` scenarios after policy changes; run all 28 (assertions A1–A23) when touching stage/elicitation/repetition/matching; attach the `suite_report.json` diff or analyzer output to the PR; quote one decision-trace excerpt per closed finding.
