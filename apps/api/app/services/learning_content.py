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


def parse_module_content(payload: object) -> LearningModuleContent:
    """Validate raw content JSON into the typed module model.

    Raises ``pydantic.ValidationError`` on malformed content so a bad content
    file fails the seed loudly instead of shipping broken slides.
    """
    return LearningModuleContent.model_validate(payload)


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
