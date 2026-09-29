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
from app.contracts.learning_checkin import LearningCheckinContent  # noqa: E402
from app.contracts.learning_quiz import LearningQuizContent  # noqa: E402
from app.services.learning_content import (  # noqa: E402
    checkin_item_id,
    discover_content_files,
    lesson_id,
    module_id,
    objective_id,
    ordered_slide_ids,
    parse_checkin_content,
    parse_module_content,
    parse_quiz_content,
    quiz_item_id,
    slide_id,
    validate_checkins_against_module,
    validate_quiz_against_module,
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
) -> list[
    tuple[
        str,
        LearningModuleContent,
        LearningQuizContent | None,
        LearningCheckinContent | None,
    ]
]:
    """Validate every content file and pair it with its target archetype.

    ``quiz.json`` and ``checkins.json`` are optional per module; when present
    they are validated against the module (critical-objective coverage, slide
    refs, objective coverage) before any write.
    """
    loaded: list[
        tuple[
            str,
            LearningModuleContent,
            LearningQuizContent | None,
            LearningCheckinContent | None,
        ]
    ] = []
    for archetype_key, path in discover_content_files(content_dir, archetype_keys):
        module = parse_module_content(json.loads(path.read_text(encoding="utf-8")))
        quiz_path = path.parent / "quiz.json"
        quiz = None
        if quiz_path.is_file():
            quiz = parse_quiz_content(json.loads(quiz_path.read_text(encoding="utf-8")))
            validate_quiz_against_module(quiz, module)
        checkins_path = path.parent / "checkins.json"
        checkins = None
        if checkins_path.is_file():
            checkins = parse_checkin_content(json.loads(checkins_path.read_text(encoding="utf-8")))
            validate_checkins_against_module(checkins, module)
        loaded.append((archetype_key, module, quiz, checkins))
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
        counts = {
            "modules": len(loaded),
            "objectives": 0,
            "lessons": 0,
            "slides": 0,
            "quiz_items": 0,
            "checkin_items": 0,
        }
        if dry_run:
            for _, module, quiz, checkins in loaded:
                counts["objectives"] += len(module.objectives)
                for lesson in module.lessons:
                    counts["lessons"] += 1
                    counts["slides"] += len(lesson.slides)
                if quiz is not None:
                    counts["quiz_items"] += sum(len(form.items) for form in quiz.forms)
                if checkins is not None:
                    counts["checkin_items"] += sum(
                        len(bank.items) for bank in checkins.objectives
                    )
            return counts

        async with connection.transaction():
            for archetype_key, module, quiz, checkins in loaded:
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

                slide_order = ordered_slide_ids(archetype_key, module)
                item_ids = []
                for form in quiz.forms if quiz is not None else []:
                    for item in form.items:
                        iid = quiz_item_id(mid, form.form_id, item.seq)
                        item_ids.append(iid)
                        await connection.execute(
                            """
                            INSERT INTO learning.quiz_items
                                (id, module_id, objective_id, form_id, seq, kind, stem,
                                 options, answer, difficulty, hint_text,
                                 feedback_correct, feedback_wrong, slide_ref, is_critical)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb,
                                    $10, $11, $12, $13, $14, $15)
                            ON CONFLICT (id) DO UPDATE SET
                                objective_id = EXCLUDED.objective_id,
                                form_id = EXCLUDED.form_id,
                                seq = EXCLUDED.seq,
                                kind = EXCLUDED.kind,
                                stem = EXCLUDED.stem,
                                options = EXCLUDED.options,
                                answer = EXCLUDED.answer,
                                difficulty = EXCLUDED.difficulty,
                                hint_text = EXCLUDED.hint_text,
                                feedback_correct = EXCLUDED.feedback_correct,
                                feedback_wrong = EXCLUDED.feedback_wrong,
                                slide_ref = EXCLUDED.slide_ref,
                                is_critical = EXCLUDED.is_critical
                            """,
                            iid,
                            mid,
                            objective_by_code[item.objective],
                            form.form_id,
                            item.seq,
                            item.kind,
                            item.stem,
                            json.dumps([option.model_dump() for option in item.options]),
                            json.dumps(item.answer),
                            item.difficulty,
                            item.hint_text,
                            item.feedback_correct,
                            item.feedback_wrong,
                            slide_order[item.slide_ref - 1],
                            item.is_critical,
                        )
                await connection.execute(
                    "DELETE FROM learning.quiz_items WHERE module_id = $1 AND NOT (id = ANY($2::uuid[]))",
                    mid,
                    item_ids,
                )

                checkin_ids = []
                checkin_version = (
                    checkins.version if checkins is not None else module.version
                )
                for bank in checkins.objectives if checkins is not None else []:
                    oid = objective_by_code[bank.objective]
                    for item in bank.items:
                        cid = checkin_item_id(oid, item.seq)
                        checkin_ids.append(cid)
                        await connection.execute(
                            """
                            INSERT INTO learning.checkin_items
                                (id, objective_id, seq, kind, prompt, payload, content_version)
                            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                            ON CONFLICT (id) DO UPDATE SET
                                objective_id = EXCLUDED.objective_id,
                                seq = EXCLUDED.seq,
                                kind = EXCLUDED.kind,
                                prompt = EXCLUDED.prompt,
                                payload = EXCLUDED.payload,
                                content_version = EXCLUDED.content_version
                            """,
                            cid,
                            oid,
                            item.seq,
                            item.kind.value,
                            item.prompt,
                            json.dumps(
                                {
                                    "scale": item.scale.model_dump() if item.scale else None,
                                    "options": [o.model_dump() for o in item.options],
                                    "answer": list(item.answer),
                                    "explanation": item.explanation,
                                    "rubric": item.rubric.model_dump() if item.rubric else None,
                                }
                            ),
                            checkin_version,
                        )
                for oid in objective_by_code.values():
                    await connection.execute(
                        """
                        DELETE FROM learning.checkin_items
                         WHERE objective_id = $1 AND NOT (id = ANY($2::uuid[]))
                        """,
                        oid,
                        checkin_ids,
                    )

                counts["objectives"] += len(objective_ids)
                counts["lessons"] += len(lesson_ids)
                counts["slides"] += len(slide_ids)
                counts["quiz_items"] += len(item_ids)
                counts["checkin_items"] += len(checkin_ids)
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
        f"lessons={counts['lessons']} slides={counts['slides']} "
        f"quiz_items={counts['quiz_items']} checkin_items={counts['checkin_items']}"
    )


if __name__ == "__main__":
    main()
