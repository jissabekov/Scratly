"""Location readiness helpers for project matching gates."""

from __future__ import annotations

import re
from typing import Any, Iterable

_GEO_IN_TEXT = re.compile(
    r"(?:\b(?:i'?m|i am|we'?re|based|located|live|living)\s+(?:in|near|around)\s+"
    r"([A-Za-z][A-Za-z\s\-]{1,40}))"
    r"|(?:^\s*(?:in|near)\s+([A-Za-z][A-Za-z\s\-]{1,40})\s*[.!?]?\s*$)",
    re.IGNORECASE,
)

GEO_REGION_KEYS = frozenset(
    {
        "seattle_metro",
        "bay_area",
        "austin_metro",
        "nyc_metro",
        "remote_ok",
    }
)

GEO_PLACE_KEYS = frozenset(
    {
        "seattle",
        "bellevue",
        "san_francisco",
        "oakland",
        "san_jose",
        "berkeley",
        "austin",
        "new_york",
        "brooklyn",
        "nashville",
        "chicago",
    }
)

GEO_VALUE_KEYS = GEO_REGION_KEYS | GEO_PLACE_KEYS

# Constraint value_keys that are never geography (elicitation / schedule / tools).
NON_GEO_CONSTRAINT_KEYS = frozenset(
    {
        "time_limited",
        "tools_limited",
        "geo_needed",
        "evening_only",
        "schedule",
        "weekend_only",
        "no_weekend",
        "equipment",
        "software",
    }
)


def _normalize(value_key: str) -> str:
    return value_key.strip().lower().replace(" ", "_").replace("-", "_")


def is_non_geo_constraint(value_key: str | None) -> bool:
    if not value_key:
        return False
    return _normalize(value_key) in NON_GEO_CONSTRAINT_KEYS


def is_geo_value_key(value_key: str | None) -> bool:
    """True for curated metros/places, geo_* keys, or freeform city/region labels.

    Extractors often emit freeform labels like ``oklahoma`` / ``bristow`` when the
    student is outside the curated catalog. Those must still satisfy location
    readiness so we do not re-ask after a clear answer.
    """
    if not value_key:
        return False
    normalized = _normalize(value_key)
    if normalized in NON_GEO_CONSTRAINT_KEYS:
        return False
    if normalized in GEO_VALUE_KEYS or normalized.startswith("geo_"):
        return True
    # Freeform place/region/state: alphabetic tokens of reasonable length.
    compact = normalized.replace("_", "")
    return compact.isalpha() and 2 <= len(compact) <= 48


def location_established_from_values(value_keys: Iterable[str | None]) -> bool:
    return any(is_geo_value_key(v) for v in value_keys)


def infer_geo_from_text(text: str) -> str | None:
    """Best-effort city/region label from a clear place statement in free text."""
    raw = (text or "").strip()
    if not raw:
        return None
    match = _GEO_IN_TEXT.search(raw)
    if not match:
        return None
    place = (match.group(1) or match.group(2) or "").strip()
    if not place:
        return None
    normalized = _normalize(place)
    if is_non_geo_constraint(normalized):
        return None
    if is_geo_value_key(normalized):
        return normalized
    return None


def location_established_from_profile(profile: dict[str, Any]) -> bool:
    """True when public/matching profile carries a supported geo constraint."""
    dims = profile.get("dimensions") or []
    for dim in dims:
        if dim.get("key") != "constraints":
            continue
        status = dim.get("status")
        if status not in {"supported", "provisional"}:
            continue
        value = dim.get("value")
        if is_geo_value_key(value):
            return True
        values = dim.get("values") or []
        if location_established_from_values(values):
            return True
    # Matching-shaped profile
    constraints = profile.get("constraints") or {}
    if isinstance(constraints, dict):
        # Structured ConstraintProfile: {"geo": [...], "details": [...], "status": ...}
        geo = constraints.get("geo")
        if isinstance(geo, list) and location_established_from_values(geo):
            return True
        details = constraints.get("details")
        if isinstance(details, list) and location_established_from_values(details):
            return True
        if any(is_geo_value_key(k) or is_geo_value_key(v) for k, v in constraints.items()):
            return True
        if location_established_from_values(constraints.values()):
            return True
    geo_regions = profile.get("geo_regions") or []
    geo_places = profile.get("geo_places") or []
    return bool(geo_regions or geo_places)


def extract_geo_from_profile(profile: dict[str, Any]) -> dict[str, list[str]]:
    regions: set[str] = set()
    places: set[str] = set()

    def _absorb(raw: Any) -> None:
        if not isinstance(raw, str) or not is_geo_value_key(raw):
            return
        normalized = _normalize(raw)
        if normalized.startswith("geo_region"):
            regions.add(normalized.replace("geo_region:", "").replace("geo_region_", ""))
        elif normalized.startswith("geo_place"):
            places.add(normalized.replace("geo_place:", "").replace("geo_place_", ""))
        elif normalized in GEO_REGION_KEYS:
            regions.add(normalized)
        elif normalized in GEO_PLACE_KEYS:
            places.add(normalized)
        else:
            # Freeform city/state/region → treat as a place for matching filters.
            places.add(normalized)

    for dim in profile.get("dimensions") or []:
        if dim.get("key") != "constraints":
            continue
        _absorb(dim.get("value"))
        for raw in dim.get("values") or []:
            _absorb(raw)
    for r in profile.get("geo_regions") or []:
        regions.add(r)
    for p in profile.get("geo_places") or []:
        places.add(p)
    constraints = profile.get("constraints") or {}
    if isinstance(constraints, dict):
        for item in constraints.get("geo") or []:
            _absorb(item)
        for item in constraints.get("details") or []:
            _absorb(item)
        for k, v in constraints.items():
            if k in {"geo", "details", "status"}:
                continue
            candidate = v if is_geo_value_key(v) else k
            _absorb(candidate)
    return {"geo_regions": sorted(regions), "geo_places": sorted(places)}
