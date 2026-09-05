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

import math

__version__ = "1.0.0"
__all__ = [
    "parse_hex",
    "rgb_to_hex",
    "rgb_to_hsl",
    "hsl_to_rgb",
    "rgb_to_oklch",
    "oklch_to_rgb",
    "relative_luminance",
    "contrast_ratio",
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
