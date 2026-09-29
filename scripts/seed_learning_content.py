#!/usr/bin/env python3
"""Seed versioned in-repo learning content into the ``learning`` schema.

Content is authored as JSON under ``content/modules/<group>/<slug>/module.json``
and validated against the typed contract before any row is written. Modules in
``shared/`` are expanded into every active archetype (plus ``generic``). Row ids
are deterministic (uuid5 of the natural key), so re-running this script is
idempotent and never orphans ``learning.slide_completions``.

Usage:
  .venv/Scripts/python scripts/seed_learning_content.py
  .venv/Scripts/python scripts/seed_learning_content.py --dry-run
  .venv/Scripts/python scripts/seed_learning_content.py --dsn postgresql://...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.contracts.learning import LearningModuleContent  # noqa: E402
from app.services.learning_content import (  # noqa: E402
    discover_content_files,
    lesson_id,
    module_id,
    objective_id,
    parse_module_content,
    slide_id,
)

DEFAULT_CONTENT_DIR = ROOT / "content" / "modules"


def _read_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE reader (no interpolation, no python-dotenv dep)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_dsn(explicit: str | None) -> str:
    """Resolve the Postgres DSN for the seed, preferring explicit config."""
    if explicit:
        return explicit
    for path in (ROOT / "apps" / "api" / ".env", ROOT / ".env"):
        value = _read_env_file(path).get("DATABASE_URL")
        if value:
            return value
    env = {**_read_env_file(ROOT / ".env"), **os.environ}
    user = env.get("POSTGRES_USER", "scratly")
    password = env.get("POSTGRES_PASSWORD", "scratly_local_only")
    database = env.get("POSTGRES_DB", "scratly")
    host = env.get("POSTGRES_HOST", "127.0.0.1")
    port = env.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def to_asyncpg_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


def load_content(
    content_dir: Path, archetype_keys: list[str]
) -> list[tuple[str, LearningModuleContent]]:
    """Validate every content file and pair it with its target archetype."""
    loaded: list[tuple[str, LearningModuleContent]] = []
    for archetype_key, path in discover_content_files(content_dir, archetype_keys):
        payload = json.loads(path.read_text(encoding="utf-8"))
        module = parse_module_content(payload)
        loaded.append((archetype_key, module))
    return loaded


async def seed(dsn: str, content_dir: Path, dry_run: bool) -> dict[str, int]:
    """Upsert all content in one transaction; return per-table row counts."""
    try:
        import asyncpg
    except ImportError as err:  # pragma: no cover - dependency is pinned
        raise SystemExit("asyncpg is required: pip install asyncpg") from err

    connection = await asyncpg.connect(to_asyncpg_dsn(dsn))
    try:
        archetype_keys = [
            row["key"]
            for row in await connection.fetch(
                "SELECT key FROM matching.project_archetypes WHERE active ORDER BY key"
            )
        ]
        loaded = load_content(content_dir, archetype_keys)
        counts = {"modules": len(loaded), "objectives": 0, "lessons": 0, "slides": 0}
        if dry_run:
            for _, module in loaded:
                counts["objectives"] += len(module.objectives)
                for lesson in module.lessons:
                    counts["lessons"] += 1
                    counts["slides"] += len(lesson.slides)
            return counts

        async with connection.transaction():
            for archetype_key, module in loaded:
                mid = module_id(archetype_key, module.slug)
                await connection.execute(
                    """
                    INSERT INTO learning.modules
                        (id, archetype_key, slug, seq, title, description,
                         est_minutes, status, content_version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'published', $8)
                    ON CONFLICT (id) DO UPDATE SET
                        archetype_key = EXCLUDED.archetype_key,
                        slug = EXCLUDED.slug,
                        seq = EXCLUDED.seq,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        est_minutes = EXCLUDED.est_minutes,
                        status = EXCLUDED.status,
                        content_version = EXCLUDED.content_version,
                        updated_at = now()
                    """,
                    mid,
                    archetype_key,
                    module.slug,
                    module.seq,
                    module.title,
                    module.description,
                    module.est_minutes,
                    module.version,
                )

                objective_ids = []
                for objective in module.objectives:
                    oid = objective_id(mid, objective.code)
                    objective_ids.append(oid)
                    await connection.execute(
                        """
                        INSERT INTO learning.objectives
                            (id, module_id, code, label, is_critical, ordinal)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (id) DO UPDATE SET
                            code = EXCLUDED.code,
                            label = EXCLUDED.label,
                            is_critical = EXCLUDED.is_critical,
                            ordinal = EXCLUDED.ordinal
                        """,
                        oid,
                        mid,
                        objective.code,
                        objective.label,
                        objective.is_critical,
                        objective.ordinal,
                    )
                objective_by_code = {
                    objective.code: objective_id(mid, objective.code)
                    for objective in module.objectives
                }

                lesson_ids = []
                slide_ids = []
                for lesson in module.lessons:
                    lid = lesson_id(mid, lesson.seq)
                    lesson_ids.append(lid)
                    await connection.execute(
                        """
                        INSERT INTO learning.lessons (id, module_id, seq, title)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (id) DO UPDATE SET
                            seq = EXCLUDED.seq,
                            title = EXCLUDED.title
                        """,
                        lid,
                        mid,
                        lesson.seq,
                        lesson.title,
                    )
                    for slide in lesson.slides:
                        sid = slide_id(lid, slide.seq)
                        slide_ids.append(sid)
                        content = json.dumps([block.model_dump() for block in slide.blocks])
                        await connection.execute(
                            """
                            INSERT INTO learning.slides
                                (id, lesson_id, seq, kind, title, content, objective_id)
                            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                            ON CONFLICT (id) DO UPDATE SET
                                lesson_id = EXCLUDED.lesson_id,
                                seq = EXCLUDED.seq,
                                kind = EXCLUDED.kind,
                                title = EXCLUDED.title,
                                content = EXCLUDED.content,
                                objective_id = EXCLUDED.objective_id
                            """,
                            sid,
                            lid,
                            slide.seq,
                            slide.kind,
                            slide.title,
                            content,
                            objective_by_code.get(slide.objective or ""),
                        )

                await connection.execute(
                    """
                    DELETE FROM learning.slides s
                     USING learning.lessons l
                     WHERE s.lesson_id = l.id
                       AND l.module_id = $1
                       AND NOT (s.id = ANY($2::uuid[]))
                    """,
                    mid,
                    slide_ids,
                )
                await connection.execute(
                    "DELETE FROM learning.lessons WHERE module_id = $1 AND NOT (id = ANY($2::uuid[]))",
                    mid,
                    lesson_ids,
                )
                await connection.execute(
                    "DELETE FROM learning.objectives WHERE module_id = $1 AND NOT (id = ANY($2::uuid[]))",
                    mid,
                    objective_ids,
                )
                counts["objectives"] += len(objective_ids)
                counts["lessons"] += len(lesson_ids)
                counts["slides"] += len(slide_ids)
        return counts
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    parser.add_argument("--dsn", default=None, help="Override DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no writes")
    args = parser.parse_args()

    counts = asyncio.run(seed(resolve_dsn(args.dsn), args.content_dir, args.dry_run))
    mode = "validated (dry-run)" if args.dry_run else "seeded"
    print(
        f"learning content {mode}: "
        f"modules={counts['modules']} objectives={counts['objectives']} "
        f"lessons={counts['lessons']} slides={counts['slides']}"
    )


if __name__ == "__main__":
    main()
