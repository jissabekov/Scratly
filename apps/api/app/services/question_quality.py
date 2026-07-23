from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionQuality:
    accepted: bool
    reasons: tuple[str, ...]


def validate_question(text: str) -> QuestionQuality:
    normalized = " ".join(text.lower().split())
    reasons = []
    if text.count('?') != 1:
        reasons.append('not_exactly_one_question')
    if len(text) > 500:
        reasons.append('too_long')
    if any(term in normalized for term in ('profile is stable', 'bounded web research', 'internal stage', 'evidence packet', 'question policy')):
        reasons.append('internal_policy_leak')
    if 'exact address' in normalized or 'street address' in normalized:
        reasons.append('overprecise_location_request')
    return QuestionQuality(not reasons, tuple(reasons))
