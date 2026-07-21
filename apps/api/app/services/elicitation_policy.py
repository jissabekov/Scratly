"""Deterministic elicitation option banks for thin answers."""

from __future__ import annotations

from app.contracts import ElicitationOption, ElicitationSpec
from app.services.question_policy import Target

_OPTION_BANKS: dict[str, list[tuple[str, str]]] = {
    "work_mode": [
        ("small_group", "small group"),
        ("independent", "independent / alone"),
        ("both_situational", "both in different situations"),
    ],
    "topics": [
        ("data", "data / maps / analysis"),
        ("technology", "building tech / prototypes"),
        ("community", "community / civic impact"),
    ],
    "motivation": [
        ("impact", "helping others / impact"),
        ("curiosity", "curiosity / exploring"),
        ("mastery", "getting really skilled"),
    ],
    "constraints": [
        ("time_limited", "strict time limit"),
        ("tools_limited", "limited tools / software"),
        ("geo_needed", "must fit where I am based"),
    ],
    "collaboration": [
        ("solo", "mostly solo"),
        ("pair", "with one partner"),
        ("small_group", "small group"),
    ],
    "challenge": [
        ("seek_hard", "stretch with hard problems"),
        ("keep_comfortable", "keep it comfortable"),
        ("scaffolded_hard", "hard but scaffolded"),
    ],
    "impact": [
        ("local_community", "local community benefit"),
        ("learning_artifact", "something I can show / learn from"),
        ("public_info", "public information / awareness"),
    ],
    "capability": [
        ("python_basics", "Python basics"),
        ("design", "design / visuals"),
        ("writing", "writing / research"),
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
            f"For {dimension_key.replace('_', ' ')}, which is closer: "
            f"{labels[0]}, {labels[1]}"
            + (f", or {labels[2]}" if len(labels) > 2 else "")
            + " — or something else?"
        )
    else:
        template = f"For {dimension_key.replace('_', ' ')}, which option fits best?"
    return ElicitationSpec(
        options=options,
        allow_both=dimension_key in {"work_mode", "collaboration", "topics"},
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
