"""Location readiness helpers for project matching gates."""

from __future__ import annotations

from typing import Any, Iterable

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
    }
)

GEO_VALUE_KEYS = GEO_REGION_KEYS | GEO_PLACE_KEYS


def is_geo_value_key(value_key: str | None) -> bool:
    if not value_key:
        return False
    return value_key in GEO_VALUE_KEYS or value_key.startswith("geo_")


def location_established_from_values(value_keys: Iterable[str | None]) -> bool:
    return any(is_geo_value_key(v) for v in value_keys)


def location_established_from_profile(profile: dict[str, Any]) -> bool:
    """True when public/matching profile carries an established geo constraint."""
    dims = profile.get("dimensions") or []
    for dim in dims:
        if dim.get("key") != "constraints":
            continue
        status = dim.get("status")
        if status not in {"established", "provisional"}:
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
    for dim in profile.get("dimensions") or []:
        if dim.get("key") != "constraints":
            continue
        for raw in [dim.get("value"), *(dim.get("values") or [])]:
            if raw in GEO_REGION_KEYS or (isinstance(raw, str) and raw.startswith("geo_region")):
                regions.add(raw.replace("geo_region:", "") if isinstance(raw, str) else raw)
            elif raw in GEO_PLACE_KEYS or (isinstance(raw, str) and raw.startswith("geo_place")):
                places.add(raw.replace("geo_place:", "") if isinstance(raw, str) else raw)
            elif raw in GEO_REGION_KEYS:
                regions.add(raw)
            elif raw in GEO_PLACE_KEYS:
                places.add(raw)
    for r in profile.get("geo_regions") or []:
        regions.add(r)
    for p in profile.get("geo_places") or []:
        places.add(p)
    constraints = profile.get("constraints") or {}
    if isinstance(constraints, dict):
        for k, v in constraints.items():
            candidate = v if is_geo_value_key(v) else k
            if candidate in GEO_REGION_KEYS:
                regions.add(candidate)
            elif candidate in GEO_PLACE_KEYS:
                places.add(candidate)
    return {"geo_regions": sorted(regions), "geo_places": sorted(places)}
