"""chroma.py — deterministic semantic theme generation for enterprise frontends.

Weave a complete, dual-theme (Light/Dark) semantic token configuration from a
single structural brand hue coordinate, compiled in OKLCH.
"""

__version__ = "1.0.0"

from chroma.color import (
    contrast_ratio,
    hsl_to_rgb,
    oklch_to_hex,
    oklch_to_rgb,
    parse_hex,
    relative_luminance,
    rgb_to_hex,
    rgb_to_hsl,
    rgb_to_oklch,
)
from chroma.serializers import (
    serialize_json,
    serialize_tailwind_v3_config,
    serialize_tailwind_v3_css,
    serialize_tailwind_v4_css,
)
from chroma.tokens import (
    DARK,
    LIGHT,
    NEUTRAL_TOKEN_STEPS,
    THEMES,
    build_themes,
    intent_scale,
    neutral_scale,
    verify_contrast,
)

__all__ = [
    "DARK",
    "LIGHT",
    "NEUTRAL_TOKEN_STEPS",
    "THEMES",
    "build_themes",
    "contrast_ratio",
    "hsl_to_rgb",
    "intent_scale",
    "neutral_scale",
    "oklch_to_hex",
    "oklch_to_rgb",
    "parse_hex",
    "relative_luminance",
    "rgb_to_hex",
    "rgb_to_hsl",
    "rgb_to_oklch",
    "serialize_json",
    "serialize_tailwind_v3_config",
    "serialize_tailwind_v3_css",
    "serialize_tailwind_v4_css",
    "verify_contrast",
]
