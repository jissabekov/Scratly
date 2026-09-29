"""WCAG 2.2 AA contrast verification for the Scratly token canon (Plan 02 W2.3).

Reproducibility: exact token values live in apps/web/app/globals.css; this
script re-derives contrast ratios from those values with no hidden state.

Formula (WCAG 2.2): L = 0.2126*R + 0.7152*G + 0.0722*B with sRGB
linearization (c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)^2.4);
ratio = (L_lighter + 0.05) / (L_darker + 0.05).

Assumptions: AA normal text >= 4.5:1, large text (>=24px or >=18.66px bold)
>= 3:1, non-text UI (borders/focus) >= 3:1.

Usage: .venv/Scripts/python scripts/check_token_contrast.py [--min 4.5]
Exits non-zero if any REQUIRED pair fails its threshold.
"""

from __future__ import annotations

import argparse
import sys

LIGHT = {
    "ink": "#1a1f16",
    "paper": "#f3efe4",
    "panel": "#fffdf7",
    "line": "#c9c0a8",
    "line_strong": "#8a8266",
    "accent": "#2f5d50",
    "muted": "#5c6456",
    "warn": "#8a4b2c",
    "accent_contrast": "#f7fbf8",
    "accent_tint": "#e7efdf",
    "success": "#3f6d4e",
    "warning": "#755c17",
    "info": "#2f5470",
    "success_tint": "#e3eee2",
    "warning_tint": "#f2ecd7",
    "info_tint": "#e1eaf1",
}

DARK = {
    "ink": "#e9e4d6",
    "paper": "#151811",
    "panel": "#1e231a",
    "line": "#3f4536",
    "line_strong": "#6e7562",
    "accent": "#93c3ae",
    "muted": "#a7af9e",
    "warn": "#dfa070",
    "accent_contrast": "#10241b",
    "accent_tint": "#1e2c23",
    "success": "#9fd4ae",
    "warning": "#e2c06a",
    "info": "#a3c6ea",
    "success_tint": "#1a2a1d",
    "warning_tint": "#2b2414",
    "info_tint": "#16222e",
}

# (foreground, background, threshold, role, required)
# required=False rows are WCAG 1.4.11-exempt decoration (panel/card borders):
# they are reported for information only and never fail the run.
PAIRS = [
    ("ink", "paper", 4.5, "body text", True),
    ("ink", "panel", 4.5, "bubble text", True),
    ("muted", "paper", 4.5, "secondary text", True),
    ("muted", "panel", 4.5, "kind labels", True),
    ("accent", "paper", 4.5, "links/eyebrow", True),
    ("accent", "panel", 4.5, "links on panel", True),
    ("accent_contrast", "accent", 4.5, "button/student-bubble text", True),
    ("warn", "paper", 4.5, "error text", True),
    ("warn", "panel", 4.5, "error text on panel", True),
    ("accent_contrast", "warn", 4.5, "retry text on failed bubble", True),
    ("success", "paper", 4.5, "success text", True),
    ("success", "panel", 4.5, "success text on panel", True),
    ("warning", "paper", 4.5, "warning text", True),
    ("warning", "panel", 4.5, "warning text on panel", True),
    ("info", "paper", 4.5, "info text", True),
    ("info", "panel", 4.5, "info text on panel", True),
    ("ink", "success_tint", 4.5, "text on success wash", True),
    ("ink", "warning_tint", 4.5, "text on warning wash", True),
    ("ink", "info_tint", 4.5, "text on info wash", True),
    ("line_strong", "paper", 3.0, "input boundary vs page (non-text)", True),
    ("line_strong", "panel", 3.0, "input boundary vs panel (non-text)", True),
    ("accent", "panel", 3.0, "focus ring vs panel (non-text)", True),
    ("line", "paper", 3.0, "decorative panel border (exempt)", False),
    ("line", "panel", 3.0, "decorative panel border (exempt)", False),
]


def srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    rgb = (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    linear = [srgb_to_linear(c / 255) for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=float, default=None, help="override AA minimum")
    args = parser.parse_args()

    failures: list[str] = []
    for mode, tokens in (("light", LIGHT), ("dark", DARK)):
        print(f"== {mode} ==")
        for fg_key, bg_key, aa_min, role, required in PAIRS:
            threshold = args.min if args.min else aa_min
            ratio = contrast_ratio(tokens[fg_key], tokens[bg_key])
            if required:
                verdict = "PASS" if ratio >= threshold else "FAIL"
                if verdict == "FAIL":
                    failures.append(
                        f"{mode}: {fg_key} on {bg_key} ({role}) {ratio:.2f} < {threshold}"
                    )
            else:
                verdict = "INFO"
            label = f"{verdict:<4}" if required else f"{verdict:<4}"
            print(
                f"  {label} {fg_key:>16} on {bg_key:<15} {ratio:5.2f}:1"
                f"  (need {threshold}:1, {role})"
            )
    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("\nAll token pairs meet WCAG 2.2 AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
