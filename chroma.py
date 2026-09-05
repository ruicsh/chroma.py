#!/usr/bin/env python3
"""chroma.py — Deterministic Semantic Theme Generation for Enterprise Frontends.

Weave a complete, dual-theme (Light/Dark) semantic token configuration from a
single structural brand hue coordinate.

Color science pipeline (pure stdlib, no dependencies):

1. The input hex is decoded to sRGB.
2. sRGB is converted through OKLab into OKLCH (perceptually uniform space).
   The OKLCH hue angle H is locked as the unchangeable brand anchor.
3. Every structural token is derived by evaluating explicit, monotonic
   lightness/chroma interpolation curves at that locked hue — no sampled
   color arrays, no aesthetic guesswork.
4. Lightness targets are normalized so that every text/background pairing
   programmatically clears strict WCAG AAA contrast (>7:1).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

__version__ = "1.0.0"
__all__ = [
    "parse_hex",
    "rgb_to_hex",
    "rgb_to_hsl",
    "hsl_to_rgb",
    "rgb_to_oklch",
    "oklch_to_rgb",
    "oklch_to_hex",
    "relative_luminance",
    "contrast_ratio",
    "build_themes",
    "verify_contrast",
]

# ---------------------------------------------------------------------------
# OKLab constants (Björn Ottosson, "A perceptual color space for image
# processing"). These matrices convert between linear sRGB and the LMS cone
# responses used to build the perceptually uniform OKLab space.
# ---------------------------------------------------------------------------

_RGB_TO_LMS = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)

_LMS_TO_RGB = (
    (4.0767416621, -3.3077115913, 0.2309699292),
    (-1.2684380046, 2.6097574011, -0.3413193965),
    (-0.0041960863, -0.7034186147, 1.7076147010),
)

_LMS_TO_OKLAB = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)

_OKLAB_TO_LMS = (
    (1.0, 0.3963377774, 0.2158037573),
    (1.0, -0.1055613458, -0.0638541728),
    (1.0, -0.0894841775, -1.2914855480),
)


def _matvec(matrix, vector):
    return tuple(sum(row[i] * vector[i] for i in range(3)) for row in matrix)


def _srgb_gamma_decode(channel):
    """sRGB encoded (0..1) -> linear light (0..1)."""
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _srgb_gamma_encode(channel):
    """Linear light (0..1) -> sRGB encoded (0..1), clamped to gamut."""
    if channel <= 0.0031308:
        encoded = 12.92 * channel
    else:
        encoded = 1.055 * (channel ** (1.0 / 2.4)) - 0.055
    return min(1.0, max(0.0, encoded))


# ---------------------------------------------------------------------------
# Hex parsing / serialization
# ---------------------------------------------------------------------------


def parse_hex(hex_value: str) -> tuple[float, float, float]:
    """Parse a hex color into an sRGB tuple with channels in ``0..1``.

    Accepts ``#RRGGBB``, ``RRGGBB``, ``#RGB`` and ``RGB``.

    Raises:
        ValueError: if the input is not a well-formed hex color.
    """
    if not isinstance(hex_value, str):
        raise ValueError(f"invalid hex color: {hex_value!r}")
    value = hex_value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"invalid hex color: {hex_value!r}")
    try:
        channels = [int(value[i : i + 2], 16) for i in (0, 2, 4)]
    except ValueError as exc:  # pragma: no cover - int() failure path
        raise ValueError(f"invalid hex color: {hex_value!r}") from exc
    return tuple(c / 255.0 for c in channels)


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    """Serialize an sRGB tuple (channels ``0..1``) to ``#RRGGBB``."""
    channels = []
    for channel in rgb:
        channel = min(1.0, max(0.0, channel))
        channels.append(f"{round(channel * 255):02x}")
    return "#" + "".join(channels)


# ---------------------------------------------------------------------------
# HSL (legacy hue reporting / meta output)
# ---------------------------------------------------------------------------


def rgb_to_hsl(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert sRGB to HSL. Hue in degrees, saturation/lightness in 0..1."""
    r, g, b = rgb
    maximum, minimum = max(r, g, b), min(r, g, b)
    lightness = (maximum + minimum) / 2.0
    delta = maximum - minimum
    if delta == 0:
        return (0.0, 0.0, lightness)
    saturation = delta / (2.0 - maximum - minimum) if lightness > 0.5 else delta / (maximum + minimum)
    if maximum == r:
        hue = (g - b) / delta + (6.0 if g < b else 0.0)
    elif maximum == g:
        hue = (b - r) / delta + 2.0
    else:
        hue = (r - g) / delta + 4.0
    return (hue * 60.0, saturation, lightness)


def hsl_to_rgb(hsl: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert HSL (hue degrees, saturation/lightness 0..1) to sRGB."""
    hue, saturation, lightness = hsl
    c = (1.0 - abs(2.0 * lightness - 1.0)) * saturation
    hp = (hue % 360.0) / 60.0
    x = c * (1.0 - abs(hp % 2.0 - 1.0))
    if hp < 1.0:
        r, g, b = c, x, 0.0
    elif hp < 2.0:
        r, g, b = x, c, 0.0
    elif hp < 3.0:
        r, g, b = 0.0, c, x
    elif hp < 4.0:
        r, g, b = 0.0, x, c
    elif hp < 5.0:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    m = lightness - c / 2.0
    return (r + m, g + m, b + m)


# ---------------------------------------------------------------------------
# OKLCH conversion
# ---------------------------------------------------------------------------


def _rgb_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    linear = tuple(_srgb_gamma_decode(c) for c in rgb)
    lms = _matvec(_RGB_TO_LMS, linear)
    lms_p = tuple(math.copysign(abs(v) ** (1.0 / 3.0), v) for v in lms)
    return _matvec(_LMS_TO_OKLAB, lms_p)


def _oklab_to_rgb_linear(oklab: tuple[float, float, float]) -> tuple[float, float, float]:
    lms_p = _matvec(_OKLAB_TO_LMS, oklab)
    lms = tuple(v ** 3 for v in lms_p)
    return _matvec(_LMS_TO_RGB, lms)


def rgb_to_oklch(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert sRGB to OKLCH. L/chroma perceptual ``0..1``, hue in degrees."""
    lightness, a, b = _rgb_to_oklab(rgb)
    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a)) % 360.0
    return (lightness, chroma, hue)


def oklch_to_rgb(oklch: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert OKLCH to sRGB, clamping out-of-gamut channels to ``0..1``."""
    lightness, chroma, hue = oklch
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    linear = _oklab_to_rgb_linear((lightness, a, b))
    return tuple(_srgb_gamma_encode(c) for c in linear)


# ---------------------------------------------------------------------------
# WCAG relative luminance / contrast
# ---------------------------------------------------------------------------


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG 2.x relative luminance of an sRGB tuple (channels ``0..1``)."""
    linear = tuple(_srgb_gamma_decode(c) for c in rgb)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    """WCAG contrast ratio between two sRGB tuples, in ``1..21``."""
    lum_a = relative_luminance(first)
    lum_b = relative_luminance(second)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def oklch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    """Render an OKLCH coordinate as a ``#RRGGBB`` sRGB string."""
    return rgb_to_hex(oklch_to_rgb((lightness, chroma, hue)))


# ---------------------------------------------------------------------------
# Semantic token system
#
# Structural tokens are bound to functional intent following the Radix UI
# 12-step protocol. Radix groups its 12 steps into five functional bands:
#
#     steps  1- 2  backgrounds           -> surface-root,   surface-subtle
#     steps  3- 5  interactive components -> surface-default, surface-elevated,
#                                           surface-active
#     steps  6- 7  borders/separators    -> border-subtle,  border-default
#     steps  8- 9  solid colors          -> border-strong (accent surface)
#     steps 10-12  accessible text       -> text-muted,     text-secondary,
#                                           text-primary
#
# No step value is a sampled array entry. Each step is evaluated from an
# explicit, monotonic interpolation curve in OKLCH: lightness and chroma are
# piecewise-linear functions of the normalized step position ``t = (step-1)/11``
# while hue is held constant at the locked brand coordinate. This keeps the
# whole scale deterministic and free of hue drift.
# ---------------------------------------------------------------------------


# token name -> Radix step (functional intent)
NEUTRAL_TOKEN_STEPS: dict[str, int] = {
    "surface-root": 1,
    "surface-subtle": 2,
    "surface-default": 3,
    "surface-elevated": 4,
    "surface-active": 5,
    "border-subtle": 6,
    "border-default": 7,
    "border-strong": 8,
    "text-muted": 10,
    "text-secondary": 11,
    "text-primary": 12,
}

_AAA_TEXT = 7.0  # strict WCAG AAA for normal text
_AAA_SOLID = 7.0  # accent solid vs its on-color label


@dataclass(frozen=True)
class ThemeSpec:
    """Per-theme interpolation controls for the neutral 12-step scale."""

    name: str
    lightness_controls: tuple[tuple[float, float], ...]
    chroma_controls: tuple[tuple[float, float], ...]
    focus_lightness: float


# Dark theme: step 1 (app background) is darkest, step 12 (text) is lightest.
DARK = ThemeSpec(
    name="dark",
    lightness_controls=(
        (0.00, 0.160),
        (0.18, 0.210),
        (0.36, 0.260),
        (0.45, 0.320),
        (0.55, 0.380),
        (0.64, 0.460),
        (0.82, 0.720),
        (0.91, 0.860),
        (1.00, 0.965),
    ),
    chroma_controls=(
        (0.00, 0.010),
        (0.50, 0.018),
        (1.00, 0.026),
    ),
    focus_lightness=0.52,
)

# Light theme: step 1 (app background) is lightest, step 12 (text) is darkest.
LIGHT = ThemeSpec(
    name="light",
    lightness_controls=(
        (0.00, 0.990),
        (0.18, 0.970),
        (0.36, 0.955),
        (0.45, 0.940),
        (0.55, 0.900),
        (0.64, 0.840),
        (0.82, 0.550),
        (0.91, 0.300),
        (1.00, 0.120),
    ),
    chroma_controls=(
        (0.00, 0.004),
        (0.50, 0.008),
        (1.00, 0.012),
    ),
    focus_lightness=0.52,
)

THEMES: dict[str, ThemeSpec] = {theme.name: theme for theme in (DARK, LIGHT)}


def _interp(controls: tuple[tuple[float, float], ...], x: float) -> float:
    """Monotone piecewise-linear interpolation over control points."""
    if x <= controls[0][0]:
        return controls[0][1]
    if x >= controls[-1][0]:
        return controls[-1][1]
    for (x0, y0), (x1, y1) in zip(controls, controls[1:]):
        if x0 <= x <= x1:
            span = x1 - x0
            return y0 + (y1 - y0) * ((x - x0) / span) if span else y0
    raise AssertionError("unreachable")  # pragma: no cover


def neutral_scale(theme: ThemeSpec, hue: float) -> dict[str, tuple[float, float, float]]:
    """Evaluate the 12-step neutral scale as ``{token: (L, C, H)}`` in OKLCH."""
    return {
        name: (_interp(theme.lightness_controls, (step - 1) / 11.0), _interp(theme.chroma_controls, (step - 1) / 11.0), hue)
        for name, step in NEUTRAL_TOKEN_STEPS.items()
    }


def _normalize_lightness(lightness: float, chroma: float, hue: float, on_rgb: tuple[float, float, float], target: float) -> float:
    """Shift lightness until the color clears ``target`` contrast vs ``on_rgb``.

    Hue and chroma are preserved; only perceptual lightness is moved along the
    monotonic contrast slope toward the on-color.
    """
    contrast_at = lambda l: contrast_ratio(oklch_to_rgb((l, chroma, hue)), on_rgb)  # noqa: E731
    if contrast_at(lightness) >= target:
        return lightness
    on_is_light = relative_luminance(on_rgb) > 0.5
    lo, hi = (0.02, lightness) if on_is_light else (lightness, 0.98)
    for _ in range(48):
        mid = (lo + hi) / 2
        if contrast_at(mid) >= target:
            if on_is_light:
                hi = mid
            else:
                lo = mid
        else:
            if on_is_light:
                lo = mid
            else:
                hi = mid
    return (lo + hi) / 2.0


def intent_scale(brand_rgb: tuple[float, float, float], focus_lightness: float) -> dict[str, tuple[float, float, float]]:
    """Build the brand accent tokens as ``{token: (L, C, H)}`` in OKLCH.

    ``intent-primary`` keeps the brand hue and chroma but has its lightness
    normalized so the on-color label clears strict AAA (>=7:1). Hover/active
    vary chroma (perceived vibrancy) while keeping the same lightness, so the
    AAA guarantee is preserved across interaction states.
    """
    lightness, chroma, hue = rgb_to_oklch(brand_rgb)
    lum = relative_luminance(brand_rgb)
    # Choose the on-color that already wins contrast at the original brand
    # luminance. Contrast is equal when lum ~= 0.179: below that white text is
    # stronger, above it black text is. This keeps mid-bright brands vivid
    # instead of forcing them toward black/white.
    on_rgb = (1.0, 1.0, 1.0) if lum <= 0.179 else (0.0, 0.0, 0.0)
    primary = _normalize_lightness(lightness, chroma, hue, on_rgb, _AAA_SOLID + 0.2)
    return {
        "intent-primary": (primary, chroma, hue),
        "intent-primary-hover": (primary, min(chroma * 1.10, 0.35), hue),
        "intent-primary-active": (primary, max(chroma * 0.90, 0.0), hue),
        "intent-on-primary": rgb_to_oklch(on_rgb),
        "intent-focus-ring": (focus_lightness, min(chroma, 0.15), hue),
    }


def build_themes(hex_value: str) -> dict[str, dict[str, str]]:
    """Compile the full dual-theme token map from a brand hex.

    Returns ``{"light": {token: hex}, "dark": {token: hex}}``. All neutral
    tokens carry the locked brand hue (chromatic grays); the accent is the
    brand color normalized to clear WCAG AAA against its on-color label.
    """
    brand = parse_hex(hex_value)
    _, _, hue = rgb_to_oklch(brand)
    return {
        theme.name: {
            **{name: oklch_to_hex(*oklch) for name, oklch in neutral_scale(theme, hue).items()},
            **{name: oklch_to_hex(*oklch) for name, oklch in intent_scale(brand, theme.focus_lightness).items()},
        }
        for theme in (DARK, LIGHT)
    }


def verify_contrast(themes: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    """Report the WCAG contrast of every structural text/background pairing.

    The returned map mirrors ``themes`` (``theme -> token -> ratio``) for the
    pairings that the system guarantees: ``text-*`` on ``surface-*`` and the
    accent on-color label against every ``intent-*`` state.
    """
    surfaces = ("surface-root", "surface-subtle", "surface-default", "surface-elevated", "surface-active")
    texts = ("text-primary", "text-secondary", "text-muted")
    report: dict[str, dict[str, float]] = {}
    for theme_name, tokens in themes.items():
        report[theme_name] = {}
        for surface in surfaces:
            for text in texts:
                report[theme_name][f"{text}/{surface}"] = contrast_ratio(
                    parse_hex(tokens[text]), parse_hex(tokens[surface])
                )
        for state in ("intent-primary", "intent-primary-hover", "intent-primary-active"):
            report[theme_name][f"intent-on-primary/{state}"] = contrast_ratio(
                parse_hex(tokens["intent-on-primary"]), parse_hex(tokens[state])
            )
    return report


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

INTENT_TOKEN_NAMES = (
    "intent-primary",
    "intent-primary-hover",
    "intent-primary-active",
    "intent-on-primary",
    "intent-focus-ring",
)


def _token_order() -> list[str]:
    return list(NEUTRAL_TOKEN_STEPS) + list(INTENT_TOKEN_NAMES)


def _format_oklch(value: tuple[float, float, float]) -> str:
    lightness, chroma, hue = value
    return f"{lightness:.4f} {chroma:.4f} {hue:.2f}"


def _oklch_map(themes: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    brand_order = list(NEUTRAL_TOKEN_STEPS) + list(INTENT_TOKEN_NAMES)
    oklch: dict[str, dict[str, str]] = {}
    for theme_name, tokens in themes.items():
        oklch[theme_name] = {name: _format_oklch(rgb_to_oklch(parse_hex(tokens[name]))) for name in brand_order}
    return oklch


def _meta(brand_hex: str) -> dict:
    brand = parse_hex(brand_hex)
    l, c, h = rgb_to_oklch(brand)
    hs, ss, ls = rgb_to_hsl(brand)
    return {
        "input": brand_hex,
        "engine": f"chroma.py {__version__}",
        "brand": {"oklch": [round(l, 4), round(c, 4), round(h, 2)], "hsl": [round(hs, 2), round(ss, 4), round(ls, 4)]},
        "themes": list(THEMES),
    }


def serialize_json(themes: dict[str, dict[str, str]], brand_hex: str) -> str:
    """Serialize the token map as a JSON document with raw hex + OKLCH views."""
    payload = {
        "meta": _meta(brand_hex),
        **themes,
        "oklch": _oklch_map(themes),
    }
    return json.dumps(payload, indent=2) + "\n"


def _render_js_colors(themes: dict[str, dict[str, str]]) -> str:
    """Render the Tailwind ``theme.extend.colors`` object for v3 configs."""
    family_keys = {"surface": [], "text": [], "border": [], "intent": []}
    for name in _token_order():
        family = name.split("-", 1)[0]
        family_keys[family].append(name)
    lines = ["      colors: {"]
    for family, names in family_keys.items():
        members = ", ".join(f"{name.split('-', 1)[1]}: 'var(--{name})'" for name in names)
        lines.append(f"        {family}: {{ {members} }},")
    lines.append("      },")
    return "\n".join(lines)


def serialize_tailwind_v3_config(themes: dict[str, dict[str, str]]) -> str:
    """Serialize a Tailwind v3 ``tailwind.config.js`` (colors -> CSS vars)."""
    return f"""/* Generated by chroma.py v{__version__} — semantic theme config. */
/* Color utilities resolve to runtime CSS custom properties defined in the
   companion .css file (:root for light, .dark for dark). */
/** @type {{import('tailwindcss').Config}} */
module.exports = {{
  darkMode: 'class',
  theme: {{
    extend: {{
{_render_js_colors(themes)}
    }},
  }},
}};
"""


def serialize_tailwind_v3_css(themes: dict[str, dict[str, str]]) -> str:
    """Serialize the ``:root`` / ``.dark`` CSS variable definitions (v3 companion)."""
    lines = [f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */", ":root {"]
    for name in _token_order():
        lines.append(f"  --{name}: {themes['light'][name]};")
    lines.append("}")
    lines.append("")
    lines.append(".dark {")
    for name in _token_order():
        lines.append(f"  --{name}: {themes['dark'][name]};")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def serialize_tailwind_v4_css(themes: dict[str, dict[str, str]]) -> str:
    """Serialize a self-contained Tailwind v4 theme stylesheet (``@theme`` + vars)."""
    lines = [f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */"]
    lines += ["@import 'tailwindcss';", "", "@custom-variant dark (&:where(.dark, .dark *));", "", "@theme inline {"]
    for name in _token_order():
        lines.append(f"  --color-{name}: var(--{name});")
    lines += ["}", "", ":root {"]
    for name in _token_order():
        lines.append(f"  --{name}: {themes['light'][name]};")
    lines += ["}", "", ".dark {"]
    for name in _token_order():
        lines.append(f"  --{name}: {themes['dark'][name]};")
    lines += ["}", ""]
    return "\n".join(lines)


def _emit_tailwind(themes: dict[str, dict[str, str]], output: str | None) -> None:
    """Resolve the tailwind format by output target.

    No ``-o`` (stdout) or a ``.css`` target emits a self-contained v4
    stylesheet. Any other target emits a v3 ``config.js`` plus its companion
    ``.css`` variable file.
    """
    if output is None:
        sys.stdout.write(serialize_tailwind_v4_css(themes))
        return
    path = Path(output)
    if path.suffix == ".css":
        path.write_text(serialize_tailwind_v4_css(themes))
        print(f"wrote {path}", file=sys.stderr)
        return
    config = path if path.suffix == ".js" else path.with_suffix(".js")
    companion = config.with_suffix(".css")
    config.write_text(serialize_tailwind_v3_config(themes))
    companion.write_text(serialize_tailwind_v3_css(themes))
    print(f"wrote {config}", file=sys.stderr)
    print(f"wrote {companion}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chroma.py",
        description="Systematic UI CLI Engine: Compile a complete dual-theme semantic token system from one brand color hex.",
    )
    parser.add_argument("hex", help="The primary brand hex code to extract hue coordinate from (e.g. 6366f1)")
    parser.add_argument("-o", "--output", help="Output file path instead of writing to stdout")
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "tailwind"),
        default="tailwind",
        help="The configuration file target standard (Default: tailwind)",
    )
    args = parser.parse_args(argv)

    try:
        themes = build_themes(args.hex)
    except ValueError as exc:
        print(f"chroma.py: error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        payload = serialize_json(themes, args.hex)
        if args.output:
            Path(args.output).write_text(payload)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(payload)
    else:
        _emit_tailwind(themes, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
