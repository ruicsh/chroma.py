"""Atmos three-tier token system: global -> semantic -> component, in OKLCH.

``chroma`` layers tokens across three abstraction tiers so application code
stays decoupled from branding changes:

    [ 1. GLOBAL TOKENS ]        [ 2. SEMANTIC TOKENS ]      [ 3. COMPONENT TOKENS ]
    Raw palette (the math)      Functional meaning          Explicit UI placements
    e.g. step-3, accent         e.g. bg-surface-default     e.g. bg-grid-row-hover

The raw math follows the Radix UI 12-step protocol: each step is evaluated
from an explicit, monotonic interpolation curve in OKLCH (lightness and chroma
are piecewise-linear functions of the normalized step position
``t = (step-1)/11``) while hue is held constant at the locked brand
coordinate. No step is a sampled array entry. Semantic tokens bind functional
intent (Atmos naming) to those steps, and component tokens pin hyper-localized
UI elements to semantic tokens.
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

_AAA_SOLID = 7.0  # accent solid vs its on-color label

STEP_KEYS: tuple[str, ...] = tuple(f"step-{step}" for step in range(1, 13))

ACCENT_TOKEN_NAMES: tuple[str, ...] = (
    "accent",
    "accent-hover",
    "accent-active",
    "accent-on",
    "accent-focus",
)


@dataclass(frozen=True)
class ThemeSpec:
    """Per-theme interpolation controls for the neutral 12-step scale."""

    name: str
    lightness_controls: tuple[tuple[float, float], ...]
    chroma_controls: tuple[tuple[float, float], ...]
    focus_lightness: float
    overlay_lightness: float
    overlay_chroma: float


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
    overlay_lightness=0.36,
    overlay_chroma=0.014,
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
    overlay_lightness=1.00,
    overlay_chroma=0.0,
)

THEMES: dict[str, ThemeSpec] = {theme.name: theme for theme in (DARK, LIGHT)}

# ---------------------------------------------------------------------------
# Layer 2 -> Layer 1: semantic token (Atmos functional intent) resolves to a
# global token (a Radix neutral step or a brand accent value).
# ---------------------------------------------------------------------------

SEMANTIC_TO_GLOBAL: dict[str, str] = {
    "bg-surface-root": "step-1",
    "bg-surface-default": "step-2",
    "bg-surface-subtle": "step-3",
    "bg-surface-hover": "step-4",
    "bg-surface-active": "step-5",
    "border-subtle": "step-6",
    "border-default": "step-7",
    "border-strong": "step-8",
    "text-disabled": "step-8",  # recessed inactive text matches structural borders
    "text-muted": "step-10",
    "text-secondary": "step-11",
    "text-primary": "step-12",
    "text-on-accent": "accent-on",
    "bg-action-primary": "accent",
    "bg-action-hover": "accent-hover",
    "bg-action-active": "accent-active",
}

# ---------------------------------------------------------------------------
# Layer 3 -> Layer 2: component token (explicit UI placement) resolves to a
# semantic token.
# ---------------------------------------------------------------------------

COMPONENT_TO_SEMANTIC: dict[str, str] = {
    "bg-grid-header": "bg-surface-subtle",
    "bg-grid-row-hover": "bg-surface-hover",
    "bg-grid-row-selected": "bg-surface-active",
    "border-grid-cell": "border-subtle",
    "text-grid-value": "text-primary",
    "bg-input-field": "bg-surface-subtle",
    "border-input-default": "border-default",
    "border-input-focus": "border-strong",
    "text-input-placeholder": "text-disabled",
    "bg-btn-primary-default": "bg-action-primary",
    "bg-btn-primary-hover": "bg-action-hover",
    "text-btn-primary-glyph": "text-on-accent",
}


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


def neutral_steps(
    theme: ThemeSpec, hue: float
) -> dict[str, tuple[float, float, float]]:
    """Evaluate the 12 neutral steps as ``{step-N: (L, C, H)}`` in OKLCH."""
    return {
        f"step-{step}": (
            _interp(theme.lightness_controls, (step - 1) / 11.0),
            _interp(theme.chroma_controls, (step - 1) / 11.0),
            hue,
        )
        for step in range(1, 13)
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


def accent_scale(
    brand_rgb: tuple[float, float, float], focus_lightness: float
) -> dict[str, tuple[float, float, float]]:
    """Build the brand accent tokens as ``{token: (L, C, H)}`` in OKLCH.

    ``accent`` keeps the brand hue and chroma but has its lightness normalized
    so the on-color label clears strict AAA (>=7:1). Hover/active vary chroma
    (perceived vibrancy) while keeping the same lightness, so the AAA
    guarantee is preserved across interaction states.
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
        "accent": (primary, chroma, hue),
        "accent-hover": (primary, min(chroma * 1.10, 0.35), hue),
        "accent-active": (primary, max(chroma * 0.90, 0.0), hue),
        "accent-on": rgb_to_oklch(on_rgb),
        "accent-focus": (focus_lightness, min(chroma, 0.15), hue),
    }


def build_layers(hex_value: str) -> dict[str, dict[str, dict[str, str]]]:
    """Compile the full three-tier dual-theme token map from a brand hex.

    Returns ``{theme: {layer: {token: hex}}}`` where ``layer`` is one of
    ``global`` / ``semantic`` / ``component``. All neutral tokens carry the
    locked brand hue (chromatic grays); the accent is the brand color
    normalized to clear WCAG AAA against its on-color label.
    """
    brand = parse_hex(hex_value)
    _, _, hue = rgb_to_oklch(brand)
    layers: dict[str, dict[str, dict[str, str]]] = {}
    for theme in (DARK, LIGHT):
        global_tokens = {
            name: oklch_to_hex(*oklch)
            for name, oklch in {
                **neutral_steps(theme, hue),
                **accent_scale(brand, theme.focus_lightness),
            }.items()
        }
        semantic = {
            name: global_tokens[source] for name, source in SEMANTIC_TO_GLOBAL.items()
        }
        semantic["bg-surface-overlay"] = oklch_to_hex(
            theme.overlay_lightness, theme.overlay_chroma, hue
        )
        component = {
            name: semantic[source] for name, source in COMPONENT_TO_SEMANTIC.items()
        }
        layers[theme.name] = {
            "global": global_tokens,
            "semantic": semantic,
            "component": component,
        }
    return layers


def verify_contrast(
    layers: dict[str, dict[str, dict[str, str]]],
) -> dict[str, dict[str, float]]:
    """Report the WCAG contrast of every structural text/background pairing.

    The returned map mirrors ``layers`` (``theme -> pairing -> ratio``) for the
    pairings the system guarantees: ``text-*`` on every ``bg-surface-*`` and
    the accent on-color label against every action state.
    """
    surfaces = (
        "bg-surface-root",
        "bg-surface-default",
        "bg-surface-subtle",
        "bg-surface-hover",
        "bg-surface-active",
        "bg-surface-overlay",
    )
    texts = ("text-primary", "text-secondary", "text-muted")
    report: dict[str, dict[str, float]] = {}
    for theme_name, theme in layers.items():
        semantic = theme["semantic"]
        report[theme_name] = {}
        for surface in surfaces:
            for text in texts:
                report[theme_name][f"{text}/{surface}"] = contrast_ratio(
                    parse_hex(semantic[text]), parse_hex(semantic[surface])
                )
        for state in ("bg-action-primary", "bg-action-hover", "bg-action-active"):
            report[theme_name][f"text-on-accent/{state}"] = contrast_ratio(
                parse_hex(semantic["text-on-accent"]), parse_hex(semantic[state])
            )
    return report
