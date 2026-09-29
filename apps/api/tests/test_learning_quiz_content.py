"""Quiz content tests: every bank validates and can satisfy the pass rule."""

import json
from pathlib import Path

import pytest

from app.contracts.learning_quiz import FORM_SIZE, PASS_THRESHOLD
from app.services.learning_content import (
    parse_module_content,
    parse_quiz_content,
    validate_quiz_against_module,
)

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content" / "modules"


def _quiz_paths() -> list[Path]:
    return sorted(CONTENT_DIR.glob("*/*/quiz.json"))


def test_every_module_has_a_quiz_bank():
    module_count = len(list(CONTENT_DIR.glob("*/*/module.json")))
    assert len(_quiz_paths()) == module_count, "every module needs a quiz bank"


@pytest.mark.parametrize(
    "path", _quiz_paths(), ids=lambda p: f"{p.parent.parent.name}/{p.parent.name}"
)
def test_every_quiz_validates_against_its_module(path: Path):
    quiz = parse_quiz_content(json.loads(path.read_text(encoding="utf-8")))
    module = parse_module_content(
        json.loads((path.parent / "module.json").read_text(encoding="utf-8"))
    )
    validate_quiz_against_module(quiz, module)  # raises on any violation

    assert quiz.slug == path.parent.name
    assert len(quiz.forms) >= 2, "alternate forms are required for remediation"
    for form in quiz.forms:
        assert len(form.items) == FORM_SIZE
        # The pass rule must be reachable: enough items to clear the threshold
        # while still covering every critical objective.
        critical = {objective.code for objective in module.objectives if objective.is_critical}
        covered = {item.objective for item in form.items}
        assert critical <= covered


def test_shared_quiz_has_three_forms_for_form_rotation():
    quiz = parse_quiz_content(
        json.loads(
            (CONTENT_DIR / "shared" / "how-apps-work" / "quiz.json").read_text(encoding="utf-8")
        )
    )
    assert [form.form_id for form in quiz.forms] == [1, 2, 3]


def test_pass_rule_is_satisfiable_on_every_form():
    """A form must allow >=4/5 while covering all critical objectives."""
    for path in _quiz_paths():
        quiz = parse_quiz_content(json.loads(path.read_text(encoding="utf-8")))
        for form in quiz.forms:
            assert len(form.items) >= PASS_THRESHOLD
            assert len(form.items) - PASS_THRESHOLD == 1, "exactly one item may be missed"
