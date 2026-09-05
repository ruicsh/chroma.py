"""Semantic token system: Radix-12-step informed dual-theme scale in OKLCH.

Structural tokens are bound to functional intent following the Radix UI
12-step protocol. Radix groups its 12 steps into five functional bands:

    steps  1- 2  backgrounds           -> surface-root,    surface-subtle
    steps  3- 5  interactive components -> surface-default, surface-elevated,
                                          surface-active
    steps  6- 7  borders/separators    -> border-subtle,   border-default
    steps  8- 9  solid colors          -> border-strong (accent surface)
    steps 10-12  accessible text       -> text-muted,      text-secondary,
                                          text-primary

No step value is a sampled array entry. Each step is evaluated from an
explicit, monotonic interpolation curve in OKLCH: lightness and chroma are
piecewise-linear functions of the normalized step position ``t = (step-1)/11``
while hue is held constant at the locked brand coordinate. This keeps the
whole scale deterministic and free of hue drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from chroma.color import (
    contrast_ratio,
    oklch_to_hex,
    oklch_to_rgb,
    parse_hex,
    relative_luminance,
    rgb_to_oklch,
)

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


def neutral_scale(
    theme: ThemeSpec, hue: float
) -> dict[str, tuple[float, float, float]]:
    """Evaluate the 12-step neutral scale as ``{token: (L, C, H)}`` in OKLCH."""
    return {
        name: (
            _interp(theme.lightness_controls, (step - 1) / 11.0),
            _interp(theme.chroma_controls, (step - 1) / 11.0),
            hue,
        )
        for name, step in NEUTRAL_TOKEN_STEPS.items()
    }


def _normalize_lightness(
    lightness: float,
    chroma: float,
    hue: float,
    on_rgb: tuple[float, float, float],
    target: float,
) -> float:
    """Shift lightness until the color clears ``target`` contrast vs ``on_rgb``.

    Hue and chroma are preserved; only perceptual lightness is moved along the
    monotonic contrast slope toward the on-color.
    """

    def contrast_at(lightness: float) -> float:
        return contrast_ratio(oklch_to_rgb((lightness, chroma, hue)), on_rgb)

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


def intent_scale(
    brand_rgb: tuple[float, float, float], focus_lightness: float
) -> dict[str, tuple[float, float, float]]:
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
            **{
                name: oklch_to_hex(*oklch)
                for name, oklch in neutral_scale(theme, hue).items()
            },
            **{
                name: oklch_to_hex(*oklch)
                for name, oklch in intent_scale(brand, theme.focus_lightness).items()
            },
        }
        for theme in (DARK, LIGHT)
    }


def verify_contrast(themes: dict[str, dict[str, str]]) -> dict[str, dict[str, float]]:
    """Report the WCAG contrast of every structural text/background pairing.

    The returned map mirrors ``themes`` (``theme -> token -> ratio``) for the
    pairings that the system guarantees: ``text-*`` on ``surface-*`` and the
    accent on-color label against every ``intent-*`` state.
    """
    surfaces = (
        "surface-root",
        "surface-subtle",
        "surface-default",
        "surface-elevated",
        "surface-active",
    )
    texts = ("text-primary", "text-secondary", "text-muted")
    report: dict[str, dict[str, float]] = {}
    for theme_name, tokens in themes.items():
        report[theme_name] = {}
        for surface in surfaces:
            for text in texts:
                report[theme_name][f"{text}/{surface}"] = contrast_ratio(
                    parse_hex(tokens[text]), parse_hex(tokens[surface])
                )
        for state in (
            "intent-primary",
            "intent-primary-hover",
            "intent-primary-active",
        ):
            report[theme_name][f"intent-on-primary/{state}"] = contrast_ratio(
                parse_hex(tokens["intent-on-primary"]), parse_hex(tokens[state])
            )
    return report
