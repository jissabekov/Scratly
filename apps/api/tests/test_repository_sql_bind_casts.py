"""Guard against a latent SQLAlchemy ``text()`` bug (Phase 6 regression test).

SQLAlchemy's ``text()`` parser does not recognise a bind parameter that is
immediately followed by a Postgres cast shorthand (``:param::jsonb``). The
statement is sent to asyncpg with the placeholder unresolved, and Postgres
fails with ``syntax error at or near ":"`` — a runtime 500 on a code path that
no unit test could catch, because the pure engines never build SQL.

Phase 6 exposed three such statements in ``repository/learning_checkin.py``
(check-in respond, the xAPI event insert, and the intervention insert). Use
``CAST(:param AS jsonb)`` instead. This test scans every SQL string in the
repository and service layers so the pattern cannot come back unnoticed.
"""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# A bind parameter immediately followed by the `::type` cast shorthand.
BAD_CAST = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)::")


def _python_sources() -> list[Path]:
    return sorted(path for path in APP.rglob("*.py") if "__pycache__" not in path.parts)


def test_no_bind_parameter_uses_the_double_colon_cast_shorthand() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if BAD_CAST.search(line):
                offenders.append(f"{path.relative_to(APP.parent.parent)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "use CAST(:param AS type) instead of :param::type — SQLAlchemy text() "
        "does not resolve the placeholder:\n" + "\n".join(offenders)
    )


def test_the_guard_actually_matches_the_known_bad_shape() -> None:
    """Sanity-check the regex so the guard cannot silently stop matching."""
    assert BAD_CAST.search("SET response = :response::jsonb")
    assert not BAD_CAST.search("SET response = CAST(:response AS jsonb)")
