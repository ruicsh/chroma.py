"""chroma.py — deterministic semantic theme generation for enterprise frontends.

Weave a complete, dual-theme (Light/Dark) semantic token configuration from a
single structural brand hue coordinate, compiled in OKLCH across two Atmos
tiers: global (raw math) and semantic (functional intent).
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
    emit_css,
    emit_dtcg,
    emit_json,
    emit_less,
    emit_sass,
    emit_stylus,
    emit_ts,
    serialize_css,
    serialize_dtcg,
    serialize_json,
    serialize_less,
    serialize_sass,
    serialize_stylus,
    serialize_tailwind_v3_config,
    serialize_tailwind_v3_css,
    serialize_tailwind_v4_css,
    serialize_ts,
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
    "emit_css",
    "emit_dtcg",
    "emit_json",
    "emit_less",
    "emit_sass",
    "emit_stylus",
    "emit_ts",
    "hsl_to_rgb",
    "neutral_steps",
    "oklch_to_hex",
    "oklch_to_rgb",
    "parse_hex",
    "relative_luminance",
    "rgb_to_hex",
    "rgb_to_hsl",
    "rgb_to_oklch",
    "serialize_css",
    "serialize_dtcg",
    "serialize_json",
    "serialize_less",
    "serialize_sass",
    "serialize_stylus",
    "serialize_tailwind_v3_config",
    "serialize_tailwind_v3_css",
    "serialize_tailwind_v4_css",
    "serialize_ts",
    "verify_contrast",
]
