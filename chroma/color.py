"""OKLCH color engine: sRGB/HSL/OKLCH conversion and WCAG contrast math.

Pure standard library, no dependencies. Conversions follow Björn Ottosson's
OKLab definitions (the perceptually uniform space standardized in CSS Color 4).
"""

from __future__ import annotations

import math

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


def _matvec(
    matrix: tuple[tuple[float, float, float], ...], vector: tuple[float, float, float]
) -> tuple[float, float, float]:
    values = [sum(row[i] * vector[i] for i in range(3)) for row in matrix]
    return (values[0], values[1], values[2])


def _srgb_gamma_decode(channel: float) -> float:
    """sRGB encoded (0..1) -> linear light (0..1)."""
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _srgb_gamma_encode(channel: float) -> float:
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
    return (channels[0] / 255.0, channels[1] / 255.0, channels[2] / 255.0)


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
    saturation = (
        delta / (2.0 - maximum - minimum)
        if lightness > 0.5
        else delta / (maximum + minimum)
    )
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
    linear = (
        _srgb_gamma_decode(rgb[0]),
        _srgb_gamma_decode(rgb[1]),
        _srgb_gamma_decode(rgb[2]),
    )
    lms = _matvec(_RGB_TO_LMS, linear)
    lms_p = (
        math.copysign(abs(lms[0]) ** (1.0 / 3.0), lms[0]),
        math.copysign(abs(lms[1]) ** (1.0 / 3.0), lms[1]),
        math.copysign(abs(lms[2]) ** (1.0 / 3.0), lms[2]),
    )
    return _matvec(_LMS_TO_OKLAB, lms_p)


def _oklab_to_rgb_linear(
    oklab: tuple[float, float, float],
) -> tuple[float, float, float]:
    lms_p = _matvec(_OKLAB_TO_LMS, oklab)
    lms = (lms_p[0] ** 3, lms_p[1] ** 3, lms_p[2] ** 3)
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
    return (
        _srgb_gamma_encode(linear[0]),
        _srgb_gamma_encode(linear[1]),
        _srgb_gamma_encode(linear[2]),
    )


def oklch_to_hex(lightness: float, chroma: float, hue: float) -> str:
    """Render an OKLCH coordinate as a ``#RRGGBB`` sRGB string."""
    return rgb_to_hex(oklch_to_rgb((lightness, chroma, hue)))


# ---------------------------------------------------------------------------
# WCAG relative luminance / contrast
# ---------------------------------------------------------------------------


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG 2.x relative luminance of an sRGB tuple (channels ``0..1``)."""
    linear = tuple(_srgb_gamma_decode(c) for c in rgb)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> float:
    """WCAG contrast ratio between two sRGB tuples, in ``1..21``."""
    lum_a = relative_luminance(first)
    lum_b = relative_luminance(second)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)
