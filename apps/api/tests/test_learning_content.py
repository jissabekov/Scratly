"""Content-model tests: shipped content validates, ids are deterministic."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.learning_content import (
    GENERIC_ARCHETYPE_KEY,
    discover_content_files,
    lesson_id,
    module_id,
    objective_id,
    parse_module_content,
    slide_id,
)

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content" / "modules"


def _module_files() -> list[Path]:
    return sorted(CONTENT_DIR.glob("*/*/module.json"))


def test_content_directory_has_authored_modules():
    files = _module_files()
    assert files, "expected versioned content under content/modules"
    groups = {path.parent.parent.name for path in files}
    assert "shared" in groups, "the shared foundation track must be authored"


@pytest.mark.parametrize(
    "path", _module_files(), ids=lambda p: f"{p.parent.parent.name}/{p.parent.name}"
)
def test_every_shipped_module_validates(path: Path):
    module = parse_module_content(json.loads(path.read_text(encoding="utf-8")))
    assert module.slug == path.parent.name
    assert module.lessons
    for lesson in module.lessons:
        for slide in lesson.slides:
            assert slide.kind == slide.blocks[0].type


def test_shared_modules_expand_into_every_archetype_and_generic():
    pairs = discover_content_files(CONTENT_DIR, ["local_investigation", "prototype_builder"])
    shared_paths = {p for p in _module_files() if p.parent.parent.name == "shared"}
    for path in shared_paths:
        targets = {key for key, candidate in pairs if candidate == path}
        assert targets == {"local_investigation", "prototype_builder", GENERIC_ARCHETYPE_KEY}


def test_ids_are_deterministic_and_identity_scoped():
    mid = module_id("generic", "next-steps")
    assert mid == module_id("generic", "next-steps")
    assert mid != module_id("prototype_builder", "next-steps")
    assert isinstance(mid, UUID)
    lid = lesson_id(mid, 1)
    assert objective_id(mid, "scope_small") != objective_id(mid, "check_progress")
    assert slide_id(lid, 1) != slide_id(lid, 2)
    assert slide_id(lid, 1) == slide_id(lesson_id(mid, 1), 1)


def _minimal_module(**overrides) -> dict:
    payload = {
        "version": "1.0.0",
        "slug": "demo",
        "seq": 1,
        "title": "Demo",
        "objectives": [{"code": "one", "label": "One", "is_critical": True, "ordinal": 1}],
        "lessons": [
            {
                "seq": 1,
                "title": "Lesson",
                "slides": [
                    {
                        "seq": 1,
                        "kind": "text",
                        "objective": "one",
                        "blocks": [{"type": "text", "text": "A single idea."}],
                    }
                ],
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_content_validation_rejects_bad_shapes():
    with pytest.raises(ValidationError):
        parse_module_content(_minimal_module(extra_key=True))

    wrong_kind = _minimal_module()
    wrong_kind["lessons"][0]["slides"][0]["kind"] = "check"
    with pytest.raises(ValidationError):
        parse_module_content(wrong_kind)

    unknown_objective = _minimal_module()
    unknown_objective["lessons"][0]["slides"][0]["objective"] = "missing"
    with pytest.raises(ValidationError):
        parse_module_content(unknown_objective)


def test_check_block_requires_known_answer_and_objective():
    slide = {
        "seq": 1,
        "kind": "check",
        "objective": "one",
        "blocks": [
            {
                "type": "check",
                "question": "Pick one",
                "options": [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}],
                "answer_key": "c",
                "explanation": "Because.",
                "objective": "one",
            }
        ],
    }
    payload = _minimal_module()
    payload["lessons"][0]["slides"] = [slide]
    with pytest.raises(ValidationError):
        parse_module_content(payload)

    slide["blocks"][0]["answer_key"] = "a"
    slide.pop("objective")
    payload["lessons"][0]["slides"] = [slide]
    with pytest.raises(ValidationError):
        parse_module_content(payload)


def test_a_slide_holds_at_most_one_check():
    payload = _minimal_module()
    check = {
        "type": "check",
        "question": "Q",
        "options": [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}],
        "answer_key": "a",
        "explanation": "E",
        "objective": "one",
    }
    payload["lessons"][0]["slides"][0]["kind"] = "check"
    payload["lessons"][0]["slides"][0]["blocks"] = [check, check]
    with pytest.raises(ValidationError):
        parse_module_content(payload)
