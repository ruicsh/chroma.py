"""chroma.py — deterministic semantic theme generation for enterprise frontends.

Weave a complete, dual-theme (Light/Dark) semantic token configuration from a
single structural brand hue coordinate, compiled in OKLCH across three Atmos
tiers: global (raw math), semantic (functional intent) and component (explicit
UI placements).
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
    ACCENT_TOKEN_NAMES,
    DARK,
    LIGHT,
    SEMANTIC_TO_GLOBAL,
    STEP_KEYS,
    THEMES,
    accent_scale,
    build_layers,
    neutral_steps,
    verify_contrast,
)

__all__ = [
    "ACCENT_TOKEN_NAMES",
    "DARK",
    "LIGHT",
    "SEMANTIC_TO_GLOBAL",
    "STEP_KEYS",
    "THEMES",
    "accent_scale",
    "build_layers",
    "contrast_ratio",
    "hsl_to_rgb",
    "neutral_steps",
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
