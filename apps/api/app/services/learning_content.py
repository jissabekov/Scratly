"""Deterministic ids for versioned in-repo learning content.

Content lives in the repository as JSON (``content/modules/**/module.json``) and
is seeded by ``scripts/seed_learning_content.py``. Row ids are uuid5 of the
natural key, so reseeding the same content never changes an id — which keeps
``learning.slide_completions`` valid across content re-seeds (reproducibility
contract). No hidden state: the id is a pure function of the content identity.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID, uuid5

from app.contracts.learning import LearningModuleContent
from app.contracts.learning_quiz import LearningQuizContent

# Fixed namespace for every learning-content id. Changing it would orphan all
# completions, so treat it as immutable once shipped.
LEARNING_NAMESPACE = uuid5(
    UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"),  # NAMESPACE_URL
    "https://scratly.dev/learning",
)

# Modules authored under content/modules/shared/ are expanded into every
# archetype (plus this generic bucket) at seed time.
GENERIC_ARCHETYPE_KEY = "generic"


def module_id(archetype_key: str, slug: str) -> UUID:
    """Stable id for a module identified by its archetype and slug."""
    return uuid5(LEARNING_NAMESPACE, f"module:{archetype_key}:{slug}")


def objective_id(module_id: UUID, code: str) -> UUID:
    """Stable id for a module objective identified by its code."""
    return uuid5(LEARNING_NAMESPACE, f"objective:{module_id}:{code}")


def lesson_id(module_id: UUID, seq: int) -> UUID:
    """Stable id for a lesson identified by its module and sequence."""
    return uuid5(LEARNING_NAMESPACE, f"lesson:{module_id}:{seq}")


def slide_id(lesson_id: UUID, seq: int) -> UUID:
    """Stable id for a slide identified by its lesson and sequence."""
    return uuid5(LEARNING_NAMESPACE, f"slide:{lesson_id}:{seq}")


def quiz_item_id(module_id: UUID, form_id: int, seq: int) -> UUID:
    """Stable id for a quiz item identified by its module, form and sequence."""
    return uuid5(LEARNING_NAMESPACE, f"quiz_item:{module_id}:{form_id}:{seq}")


def ordered_slide_ids(archetype_key: str, module: LearningModuleContent) -> list[UUID]:
    """Slide ids in player order (lesson seq, then slide seq) — index 1-based."""
    mid = module_id(archetype_key, module.slug)
    ids: list[UUID] = []
    for lesson in sorted(module.lessons, key=lambda lesson: lesson.seq):
        lid = lesson_id(mid, lesson.seq)
        for slide in sorted(lesson.slides, key=lambda slide: slide.seq):
            ids.append(slide_id(lid, slide.seq))
    return ids


def parse_module_content(payload: object) -> LearningModuleContent:
    """Validate raw content JSON into the typed module model.

    Raises ``pydantic.ValidationError`` on malformed content so a bad content
    file fails the seed loudly instead of shipping broken slides.
    """
    return LearningModuleContent.model_validate(payload)


def parse_quiz_content(payload: object) -> LearningQuizContent:
    """Validate raw quiz JSON into the typed quiz model."""
    return LearningQuizContent.model_validate(payload)


def validate_quiz_against_module(quiz: LearningQuizContent, module: LearningModuleContent) -> None:
    """Cross-file invariants the quiz cannot check alone.

    Every item must name a real objective, ``slide_ref`` must point at a real
    slide, and every critical objective must appear in every form — otherwise
    the pass rule ("at least one on every critical objective") is unsatisfiable.
    """
    if quiz.slug != module.slug:
        raise ValueError(f"quiz slug {quiz.slug!r} does not match module {module.slug!r}")
    slide_count = sum(len(lesson.slides) for lesson in module.lessons)
    objective_by_code = {objective.code: objective for objective in module.objectives}
    critical = {code for code, objective in objective_by_code.items() if objective.is_critical}
    for form in quiz.forms:
        covered = {item.objective for item in form.items}
        unknown = covered - set(objective_by_code)
        if unknown:
            raise ValueError(
                f"form {form.form_id} references unknown objectives: {sorted(unknown)}"
            )
        missing = critical - covered
        if missing:
            raise ValueError(
                f"form {form.form_id} does not cover critical objectives: {sorted(missing)}"
            )
        for item in form.items:
            if item.slide_ref > slide_count:
                raise ValueError(
                    f"form {form.form_id} item {item.seq} slide_ref {item.slide_ref} "
                    f"exceeds {slide_count} slides"
                )
            declared = objective_by_code[item.objective].is_critical
            if item.is_critical != declared:
                raise ValueError(
                    f"form {form.form_id} item {item.seq} is_critical={item.is_critical} "
                    f"but objective {item.objective!r} is_critical={declared}"
                )


def discover_content_files(
    content_dir: Path, archetype_keys: Sequence[str]
) -> list[tuple[str, Path]]:
    """Pair each ``module.json`` with the archetype it is seeded under.

    Layout is ``<content_dir>/<group>/<slug>/module.json``. ``shared/`` modules
    are expanded into every supplied archetype key plus ``generic``; any other
    group name is used verbatim as the archetype key. Deterministic order.
    """
    targets = sorted({*archetype_keys, GENERIC_ARCHETYPE_KEY})
    pairs: list[tuple[str, Path]] = []
    for path in sorted(content_dir.glob("*/*/module.json")):
        group = path.parent.parent.name
        if group == "shared":
            pairs.extend((key, path) for key in targets)
        else:
            pairs.append((group, path))
    return pairs
