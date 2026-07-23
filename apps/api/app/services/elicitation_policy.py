"""Deterministic elicitation option banks for thin answers (V1)."""

from __future__ import annotations

from app.contracts import ElicitationOption, ElicitationSpec
from app.services.question_policy import Target

_OPTION_BANKS: dict[str, list[tuple[str, str]]] = {
    "work_mode": [
        ("investigate", "figure out what's causing it"),
        ("build", "build something that might help"),
        ("organize", "get people organized around a change"),
        ("communicate", "explain it so people pay attention"),
    ],
    "topics": [
        ("games_online", "games or online stuff"),
        ("sports_active", "sports or being active"),
        ("creative_media", "music, shows, or making things"),
    ],
    "motivation": [
        ("discovery_mastery", "getting really good / understanding it"),
        ("competition_achievement", "beating a target / winning"),
        ("impact_usefulness", "someone actually benefiting"),
        ("recognition_influence", "being noticed / respected"),
        ("belonging_responsibility", "people depending on me"),
    ],
    "execution": [
        ("persistence", "sticking with hard work"),
        ("ambiguity_tolerance", "figuring out undefined problems"),
        ("outreach_willingness", "contacting new people/orgs"),
    ],
    "execution:outreach_willingness": [
        ("0", "I'd rather not contact outsiders"),
        ("2", "I can email with some help"),
        ("4", "I'd initiate and follow up myself"),
    ],
    "execution:public_visibility": [
        ("1", "submitted/recorded demo is enough"),
        ("2", "presenting to class/school is fine"),
        ("4", "I'd like a public pitch or demo"),
    ],
    "execution:persistence": [
        ("1", "I mostly continue when pushed"),
        ("3", "I've stuck with something hard on my own"),
        ("4", "I've done that repeatedly"),
    ],
    "execution:ambiguity_tolerance": [
        ("0", "I want clear step-by-step instructions"),
        ("2", "Goal + examples is enough"),
        ("4", "I like undefined problems"),
    ],
    "constraints": [
        ("time_limited", "strict time limit"),
        ("tools_limited", "limited tools / software"),
        ("geo_needed", "must fit where I am based"),
    ],
    "capability": [
        ("coding", "coding / scripting"),
        ("design_media", "design / media"),
        ("writing_research", "writing / research"),
    ],
    "assets": [
        ("people_access", "people / mentors I can ask"),
        ("org_access", "an org / team / club connection"),
        ("data_equipment", "datasets / equipment / tools"),
    ],
    "profile": [
        ("mostly_right", "mostly right"),
        ("needs_correction", "needs a correction"),
        ("too_early", "too early to say"),
    ],
}


def build_elicitation_spec(dimension_key: str) -> ElicitationSpec:
    bank = _OPTION_BANKS.get(dimension_key) or _OPTION_BANKS["topics"]
    options = [ElicitationOption(key=k, label=lbl) for k, lbl in bank[:3]]
    labels = [o.label for o in options]
    if len(labels) >= 2:
        template = (
            "No pressure — would any of these be close: "
            f"{labels[0]}, {labels[1]}"
            + (f", or {labels[2]}" if len(labels) > 2 else "")
            + " — or something else?"
        )
    else:
        template = (
            f"For {dimension_key.replace('_', ' ').replace(':', ' ')}, "
            "which option fits best?"
        )
    return ElicitationSpec(
        options=options,
        allow_both=dimension_key in {"work_mode", "topics", "motivation", "assets"},
        allow_skip=True,
        dimension_key=dimension_key,
        fallback_template=template,
    )


def elicitation_target(dimension_key: str) -> Target:
    spec = build_elicitation_spec(dimension_key)
    return Target(
        kind="elicitation",
        key=dimension_key,
        fallback_template=spec.fallback_template,
    )


def elicitation_options_present(question: str, spec: ElicitationSpec) -> bool:
    text = (question or "").lower()
    hits = sum(1 for o in spec.options if o.label.lower() in text or o.key in text)
    return hits >= 2


def should_offer_options(*, reply_signal: str, attempts: int) -> bool:
    """Use choices as a recovery aid, never as the default interview format."""
    return reply_signal == "insufficient" and attempts == 2
