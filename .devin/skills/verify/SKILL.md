---
name: verify
description: Run Scratly's full verification gate (compile check, unit tests, optional web build) and report pass/fail per gate
allowed-tools:
  - exec
  - read
  - grep
  - glob
---

Run each gate from the repo root and report results as a table. Do not fix code unless asked — report first.

1. Compile check: `.venv/Scripts/python -m compileall -q apps/api/app`
2. Unit tests: `.venv/Scripts/python -m pytest apps/api/tests -q` (expect all passing; baseline is 79 tests)
3. Optional, slower: web build `npm --prefix apps/web run build`

Notes:
- Windows: always `.venv/Scripts/python`, never `.venv/bin/python` (Makefile targets are Linux-style).
- If pytest fails, report failing test names and the first assertion error verbatim.
- A change is not done until gates 1–2 are green. Never claim a gate passed unless you ran it in this session.
