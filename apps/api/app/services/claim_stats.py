"""Statistics checks named in the phase plans (mathcheck contract).

``verify_percentile`` is the empirical percentile with numpy's linear method:
virtual index ``(n - 1) * q``, then linear interpolation between adjacent
order statistics. ``verify_wilson_ci`` is the Wilson score interval using the
normal approximation at z = 1.96 (95%). Those are the assumptions recorded
for the Phase 1 completion rates and the Phase 4 false-fail interval.

No numpy dependency: the formulas are implemented directly so a claim can be
recomputed from the measured sample.
"""

from __future__ import annotations

import math
from typing import Sequence

Z_95 = 1.96


def verify_percentile(values: Sequence[float], q: float) -> dict[str, float | int | str]:
    """Recompute an empirical percentile. ``q`` is in ``[0, 1]`` (0.95 = p95)."""
    if not values:
        raise ValueError("verify_percentile requires at least one value")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    n = len(ordered)
    if n == 1:
        value = ordered[0]
    else:
        index = (n - 1) * q
        lo = math.floor(index)
        hi = math.ceil(index)
        if lo == hi:
            value = ordered[lo]
        else:
            fraction = index - lo
            value = ordered[lo] * (1.0 - fraction) + ordered[hi] * fraction
    return {
        "value": value,
        "q": q,
        "n": n,
        "unique": len(set(ordered)),
        "method": "empirical numpy linear",
    }


def verify_wilson_ci(successes: int, n: int, *, z: float = Z_95) -> dict[str, float | int | str]:
    """Wilson score interval for ``successes`` out of ``n`` Bernoulli trials."""
    if n <= 0:
        raise ValueError("verify_wilson_ci requires n > 0")
    if successes < 0 or successes > n:
        raise ValueError("successes must be between 0 and n")
    point = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (point + z2 / (2.0 * n)) / denom
    margin = z * math.sqrt(point * (1.0 - point) / n + z2 / (4.0 * n * n)) / denom
    return {
        "point": point,
        "lower": center - margin,
        "upper": center + margin,
        "successes": successes,
        "n": n,
        "z": z,
        "method": "wilson score, normal-approx",
    }
