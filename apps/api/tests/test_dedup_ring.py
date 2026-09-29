"""Unit proofs for outgoing duplicate-reply control (Plan 01 W1.2, fixes A14)."""

from app.services.turn_processor import (
    _ABSTENTION_LINES,
    _DEDUP_RING_SIZE,
    _TRANSITION_LINES,
    _near_duplicate_reason,
    _normalized_words,
    _post_match_reply,
    _transition_line,
)


def test_exact_repeat_is_detected():
    previous = "Does this description of your preferences feel accurate?"
    assert _near_duplicate_reason(previous, [previous]) == "exact_repeat"


def test_near_duplicate_short_reply_over_jaccard_threshold():
    previous = "I couldn't verify two relevant project directions, so I won't guess."
    near = "I couldn't verify two relevant project directions, so I won't fill gaps."
    assert _near_duplicate_reason(near, [previous]) == "near_duplicate"


def test_distinct_reply_is_not_flagged():
    recent = ["What have you been spending time on lately?"]
    assert _near_duplicate_reason("Which part did you enjoy most?", recent) is None


def test_ring_fixture_rewrites_injected_duplicate():
    ring = [
        "Does this description of your preferences feel accurate?",
        "What should I fix about what you're looking for?",
        "What matters most to you in a project?",
        "Nice — what do you enjoy most about it?",
        "How do you usually spend a free afternoon?",
        "What would you want to build first?",
        "Who else would use something like that?",
        "What makes a project feel worth doing for you?",
    ]
    assert len(ring) == _DEDUP_RING_SIZE
    injected = "Nice — what do you enjoy most about organization?"
    assert _near_duplicate_reason(injected, ring) == "near_duplicate"
    rewritten = _transition_line(len(ring), "What do you enjoy most about organization?")
    assert _near_duplicate_reason(rewritten, ring) is None


def test_transition_lines_are_distinct_and_ask_one_question():
    assert len(set(_TRANSITION_LINES)) == len(_TRANSITION_LINES) >= 4
    variants = [_transition_line(i, "What do you enjoy most about it?") for i in range(6)]
    assert all(line.count("?") == 1 for line in variants)


def test_abstention_bank_has_four_distinct_variants():
    assert len(_ABSTENTION_LINES) >= 4
    signatures = {tuple(_normalized_words(line)) for line in _ABSTENTION_LINES}
    assert len(signatures) == len(_ABSTENTION_LINES)


def test_post_match_templates_vary_by_intent():
    projects = [{"title": "Lunch Rush Tracker", "summary": "A stall ordering tracker."}]
    replies = {
        _post_match_reply("the second one please", projects),
        _post_match_reply("can we make it smaller?", projects),
        _post_match_reply("how would grading work for this?", projects),
        _post_match_reply("this fits what I needed", projects),
    }
    assert len(replies) >= 4
