---
name: state-report
description: Generate a current-state report of Scratly from git history, eval artifacts, and tests
allowed-tools:
  - exec
  - read
  - grep
  - glob
---

Produce a markdown current-state report with sections: Timeline / What exists / How it works / What was tested / Current eval verdict / Pending.

1. Timeline: `git log --pretty=format:"%h|%ad|%an|%s" --date=format:"%Y-%m-%d %H:%M" --stat` — reconstruct the development sequence from commit timestamps (note PR merges and eval-artifact commits).
2. Working tree: `git status`, `git log -1`, branch list, unmerged branches.
3. Tests: `.venv/Scripts/python -m pytest apps/api/tests -q` — report the pass count.
4. Latest eval: parse `eval/traces/latest/suite_report.json` — report the `recording` block and per-scenario `final_stage`, `max_consecutive_target_repeats`, `duplicate_assistant_ratio`, `p95_turn_ms`; read the tail of `eval/suite_run_latest.log` for the `Findings=`/`AssertionViolations=` line and quote A2/A14/A18 violation lines.
5. Pending work: read `docs/eval-findings-and-fix-plan.md` (§Definition of done), `docs/eval-assessment-2026-07-28.md`, `docs/eval-risk-remediation-2026-07-28.md`, `docs/latest-eval-remediation-2026-07-28.md`; list open items with evidence.
6. Note file timestamps for anything outside git (`.env`, logs) to spot post-commit activity.
