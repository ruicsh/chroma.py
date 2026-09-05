"""Atmos two-tier token system: global -> semantic, in OKLCH.

``chroma`` layers tokens across two abstraction tiers so application code
stays decoupled from branding changes:

    [ 1. GLOBAL TOKENS ]        [ 2. SEMANTIC TOKENS ]
    Raw palette (the math)      Functional meaning
    e.g. step-3, accent         e.g. bg-surface-default

The raw math follows the Radix UI 12-step protocol: each step is evaluated
from an explicit, monotonic interpolation curve in OKLCH (lightness and chroma
are piecewise-linear functions of the normalized step position
``t = (step-1)/11``) while hue is held constant at the locked brand
coordinate. No step is a sampled array entry. Semantic tokens bind functional
intent (Atmos naming) to those steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from chroma.color import (
    contrast_ratio,
    oklch_to_hex,
    oklch_to_rgb,
    parse_hex,
    relative_luminance,
    rgb_to_oklch,
)

_AAA_SOLID = 7.0  # accent solid vs its on-color label
_AAA_TARGET = _AAA_SOLID + 0.2  # headroom so hover/active chroma shifts stay AAA
_ON_TINT_CHROMA = 0.015  # brand-hue chroma for the dark "chromatic gray" on-color

_STATUS_AA = 4.5  # status solid / text on-color floor (WCAG AA)
_STATUS_TARGET = _STATUS_AA + 0.2  # headroom for status hover/active chroma shifts

STEP_KEYS: tuple[str, ...] = tuple(f"step-{step}" for step in range(1, 13))

ACCENT_TOKEN_NAMES: tuple[str, ...] = (
    "accent",
    "accent-hover",
    "accent-active",
    "accent-on",
)

# The four semantic status families. Each carries a fixed canonical OKLCH hue
# (independent of the brand coordinate) and an explicit on-color polarity, so
# success/danger/info read as vivid dark solids under white labels while the
# amber warning stays light under a black label.
STATUS_FAMILIES: tuple[str, ...] = ("success", "warning", "danger", "info")


class _StatusSpec(TypedDict):
    hue: float
    chroma: float
    on: str


STATUS_SPECS: dict[str, _StatusSpec] = {
    "success": {"hue": 152.0, "chroma": 0.120, "on": "white"},
    "warning": {"hue": 95.0, "chroma": 0.130, "on": "black"},
    "danger": {"hue": 25.0, "chroma": 0.160, "on": "white"},
    "info": {"hue": 250.0, "chroma": 0.130, "on": "white"},
}

# Full global token name set for the status families (solid + interaction +
# tint coordinates), used by the tests and the exports.
STATUS_TOKEN_NAMES: tuple[str, ...] = tuple(
    name
    for family in STATUS_FAMILIES
    for name in (
        family,
        f"{family}-hover",
        f"{family}-active",
        f"{family}-on",
        f"{family}-subtle",
        f"{family}-border",
        f"{family}-text",
    )
)

# ---------------------------------------------------------------------------
# Full 12-step shade scales (Radix 1–12) for the brand and each status family.
# These are the raw ramps Step 2 of the Atmos article builds — the neutral
# ``step-1…12`` already existed; brand + status scales are additive.
# ---------------------------------------------------------------------------

BRAND_SCALE_NAMES: tuple[str, ...] = tuple(f"brand-{step}" for step in range(1, 13))

STATUS_SCALE_NAMES: tuple[str, ...] = tuple(
    f"{family}-{step}" for family in STATUS_FAMILIES for step in range(1, 13)
)

# The four solid status coordinates (theme-independent, AA-solved) without the
# tint helpers — after B1 the tints are derived from scale steps instead.
STATUS_COORD_NAMES: tuple[str, ...] = tuple(
    name
    for family in STATUS_FAMILIES
    for name in (
        family,
        f"{family}-hover",
        f"{family}-active",
        f"{family}-on",
    )
)

# Adapted step legend: the article's 50–950 guide collapsed onto chroma's 1–12
# Radix protocol. Each index's intent is documented here, on the preview ramp
# cells, and in the README Global Tokens table. Source: Atmos Step 2.
SCALE_STEP_LEGEND: tuple[tuple[int, str], ...] = (
    (1, "Near-white, subtle background tints — app canvas / surface root"),
    (2, "Light backgrounds, panels / default surfaces"),
    (3, "Subtle tints, inputs / form fields"),
    (4, "Hover surfaces"),
    (5, "Selected / active surfaces, main brand tone (500)"),
    (6, "Low-contrast borders, dividers"),
    (7, "Component boundaries"),
    (8, "Disabled text, focus outlines"),
    (9, "Mid ramp · placeholder / muted mid"),
    (10, "Muted text, metadata / labels"),
    (11, "Secondary / body text — strong emphasis"),
    (12, "Primary / headings — near-black, high-contrast text · darkest surfaces"),
)

# Rebind STATUS_TOKEN_NAMES to the full current status global set (coords + scales).
# The original 7-token set (including subtle/border/text) is now represented via
# scale steps; keeping the rebind avoids breaking the public export while the
# concrete global set expands to brand + status scales.
STATUS_TOKEN_NAMES = tuple(list(STATUS_COORD_NAMES) + list(STATUS_SCALE_NAMES))  # type: ignore[no-redef]


@dataclass(frozen=True)
class ThemeSpec:
    """Per-theme interpolation controls for the neutral 12-step scale."""

    name: str
    lightness_controls: tuple[tuple[float, float], ...]
    chroma_controls: tuple[tuple[float, float], ...]
    overlay_lightness: float
    overlay_chroma: float
    status_subtle_lightness: float
    status_subtle_chroma: float
    status_border_lightness: float
    status_border_chroma: float
    status_text_lightness: float


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
    overlay_lightness=0.36,
    overlay_chroma=0.014,
    status_subtle_lightness=0.16,
    status_subtle_chroma=0.03,
    status_border_lightness=0.42,
    status_border_chroma=0.05,
    status_text_lightness=0.78,
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
    overlay_lightness=1.00,
    overlay_chroma=0.0,
    status_subtle_lightness=0.96,
    status_subtle_chroma=0.03,
    status_border_lightness=0.82,
    status_border_chroma=0.05,
    status_text_lightness=0.42,
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

for _family in STATUS_FAMILIES:
    SEMANTIC_TO_GLOBAL[f"bg-{_family}-subtle"] = f"{_family}-2"
    SEMANTIC_TO_GLOBAL[f"bg-{_family}-strong"] = _family
    SEMANTIC_TO_GLOBAL[f"border-{_family}"] = f"{_family}-6"
    SEMANTIC_TO_GLOBAL[f"text-{_family}"] = f"{_family}-11"
    SEMANTIC_TO_GLOBAL[f"text-on-{_family}"] = f"{_family}-on"


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


def _scale_back(theme: ThemeSpec) -> float:
    """Dark theme chroma scale-back (article Step 6: reduce saturation on dark)."""
    return 0.9 if theme.name == "dark" else 1.0


def color_ramp(
    theme: ThemeSpec, hue: float, peak_chroma: float, prefix: str
) -> dict[str, tuple[float, float, float]]:
    """Generic 12-step chromatic ramp sharing the neutral lightness ladder.

    Chroma peaks mid-scale at ``peak_chroma`` and tapers at the ends; dark
    theme scales it back ~10% per the article.
    """
    back = _scale_back(theme)
    p = peak_chroma * back
    chroma_controls: tuple[tuple[float, float], ...] = (
        (0.00, 0.30 * p),
        (0.50, p),
        (1.00, 0.72 * p),
    )
    return {
        f"{prefix}-{step}": (
            _interp(theme.lightness_controls, (step - 1) / 11.0),
            _interp(chroma_controls, (step - 1) / 11.0),
            hue,
        )
        for step in range(1, 13)
    }


def brand_scale_steps(
    theme: ThemeSpec, brand_rgb: tuple[float, float, float]
) -> dict[str, tuple[float, float, float]]:
    """12-step brand shade scale (``brand-1…12``) at the brand hue/chroma."""
    _, peak_chroma, hue = rgb_to_oklch(brand_rgb)
    # Keep a floor so near-gray brands still produce a visible tint ramp.
    peak_chroma = max(peak_chroma, 0.01)
    return color_ramp(theme, hue, peak_chroma, "brand")


def status_scale_steps(
    theme: ThemeSpec,
) -> dict[str, tuple[float, float, float]]:
    """12-step shade scale per status family (``{s}-1…12``)."""
    out: dict[str, tuple[float, float, float]] = {}
    for family, spec in STATUS_SPECS.items():
        out.update(color_ramp(theme, spec["hue"], spec["chroma"], family))
    return out


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
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _on_tint_lightness(
    accent_lightness: float,
    accent_states: tuple[tuple[float, float, float], ...],
    hue: float,
) -> float:
    """Lightest dark on-color lightness that still clears AAA vs the accent.

    The on-color is a "chromatic gray": the brand hue at a restrained chroma.
    Its lightness is binary-searched upward from near-black to the highest
    value that keeps ``contrast_ratio(accent, on) >= _AAA_TARGET`` for *every*
    accent state (base, hover, active) — the lightest dark tint that reads as
    AAA against the whole action stack.
    """

    def contrast_at(lightness: float) -> float:
        on_rgb = oklch_to_rgb((lightness, _ON_TINT_CHROMA, hue))
        ratios = [
            contrast_ratio(oklch_to_rgb(state), on_rgb) for state in accent_states
        ]
        return min(ratios)

    lo, hi = 0.02, accent_lightness
    for _ in range(48):
        mid = (lo + hi) / 2
        if contrast_at(mid) >= _AAA_TARGET:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def accent_scale(
    brand_rgb: tuple[float, float, float],
    preserve_vibrancy: bool = False,
) -> dict[str, tuple[float, float, float]]:
    """Build the brand accent tokens as ``{token: (L, C, H)}`` in OKLCH.

    By default ``accent`` keeps the brand hue and chroma but has its lightness
    normalized so the on-color label clears strict AAA (>=7:1). With
    ``preserve_vibrancy`` the accent lightness/chroma/hue are locked exactly to
    the brand and the on-color is solved instead: a bright accent gets an
    ultra-dark "chromatic gray" tint (brand hue, small chroma, lightest shade
    still clearing AAA), a dark accent keeps white. Mid-bright brands for which
    no on-color can clear AAA fall back to the normalized path.

    Hover/active vary chroma (perceived vibrancy) while keeping the same
    lightness, so the AAA guarantee is preserved across interaction states.
    """
    lightness, chroma, hue = rgb_to_oklch(brand_rgb)
    lum = relative_luminance(brand_rgb)
    # Choose the on-color that already wins contrast at the original brand
    # luminance. Contrast is equal when lum ~= 0.179: below that white text is
    # stronger, above it black text is. This keeps mid-bright brands vivid
    # instead of forcing them toward black/white.
    on_rgb = (1.0, 1.0, 1.0) if lum <= 0.179 else (0.0, 0.0, 0.0)

    if preserve_vibrancy:
        accent_rgb = oklch_to_rgb((lightness, chroma, hue))
        hover = (lightness, min(chroma * 1.10, 0.35), hue)
        active = (lightness, max(chroma * 0.90, 0.0), hue)
        # Bright neon accent: lock it, and solve a dark chromatic-gray on-color
        # that clears AAA against the whole action stack (base, hover, active).
        if contrast_ratio(accent_rgb, (0.0, 0.0, 0.0)) >= _AAA_TARGET:
            on_oklch = (
                _on_tint_lightness(
                    lightness, ((lightness, chroma, hue), hover, active), hue
                ),
                _ON_TINT_CHROMA,
                hue,
            )
            return {
                "accent": (lightness, chroma, hue),
                "accent-hover": hover,
                "accent-active": active,
                "accent-on": on_oklch,
            }
        # Dark accent: white already clears AAA at the locked lightness.
        if contrast_ratio(accent_rgb, (1.0, 1.0, 1.0)) >= _AAA_TARGET:
            return {
                "accent": (lightness, chroma, hue),
                "accent-hover": hover,
                "accent-active": active,
                "accent-on": rgb_to_oklch((1.0, 1.0, 1.0)),
            }
        # Mid-bright: impossible to clear AAA without shifting lightness; fall
        # through to the normalized path below (the CLI warns on this).

    primary = _normalize_lightness(lightness, chroma, hue, on_rgb, _AAA_TARGET)
    return {
        "accent": (primary, chroma, hue),
        "accent-hover": (primary, min(chroma * 1.10, 0.35), hue),
        "accent-active": (primary, max(chroma * 0.90, 0.0), hue),
        "accent-on": rgb_to_oklch(on_rgb),
    }


def status_scale(
    theme: ThemeSpec,
) -> dict[str, tuple[float, float, float]]:
    """Build the status family solid coordinates as ``{token: (L, C, H)}``.

    The four status families carry fixed canonical hues — independent of the
    brand coordinate. The solid (and its hover/active) is theme-independent,
    like the accent: its lightness is normalized until the on-color label
    clears WCAG AA. Subtle/border/text are now derived from the 12-step
    status shade scales (B1), so this helper only emits the 4-token solid set.
    """

    _ = theme  # theme-independent solids; kept for call-site symmetry
    tokens: dict[str, tuple[float, float, float]] = {}
    for family, spec in STATUS_SPECS.items():
        hue = spec["hue"]
        chroma = spec["chroma"]
        on_rgb = (1.0, 1.0, 1.0) if spec["on"] == "white" else (0.0, 0.0, 0.0)
        solid_lightness = _normalize_lightness(
            0.60, chroma, hue, on_rgb, _STATUS_TARGET
        )
        tokens[family] = (solid_lightness, chroma, hue)
        tokens[f"{family}-hover"] = (
            solid_lightness,
            min(chroma * 1.10, 0.30),
            hue,
        )
        tokens[f"{family}-active"] = (
            solid_lightness,
            max(chroma * 0.90, 0.0),
            hue,
        )
        tokens[f"{family}-on"] = rgb_to_oklch(on_rgb)
    return tokens


def build_layers(
    hex_value: str, preserve_vibrancy: bool = False
) -> dict[str, dict[str, dict[str, str]]]:
    """Compile the two-tier dual-theme token map from a brand hex.

    Returns ``{theme: {layer: {token: hex}}}`` where ``layer`` is one of
    ``global`` / ``semantic``. All neutral tokens carry the locked brand hue
    (chromatic grays); the accent is the brand color normalized to clear WCAG
    AAA against its on-color label (or, with ``preserve_vibrancy``, locked to
    the brand with the on-color solved instead). The four status families
    carry their canonical hues with AA-guaranteed on-colors.
    """
    brand = parse_hex(hex_value)
    _, _, hue = rgb_to_oklch(brand)
    layers: dict[str, dict[str, dict[str, str]]] = {}
    for theme in (DARK, LIGHT):
        global_tokens = {
            name: oklch_to_hex(*oklch)
            for name, oklch in {
                **neutral_steps(theme, hue),
                **accent_scale(brand, preserve_vibrancy=preserve_vibrancy),
                **brand_scale_steps(theme, brand),
                **status_scale(theme),
                **status_scale_steps(theme),
            }.items()
        }
        semantic = {
            name: global_tokens[source] for name, source in SEMANTIC_TO_GLOBAL.items()
        }
        semantic["bg-surface-overlay"] = oklch_to_hex(
            theme.overlay_lightness, theme.overlay_chroma, hue
        )
        layers[theme.name] = {
            "global": global_tokens,
            "semantic": semantic,
        }
    return layers


def verify_contrast(
    layers: dict[str, dict[str, dict[str, str]]],
) -> dict[str, dict[str, float]]:
    """Report the WCAG contrast of every structural text/background pairing.

    The returned map mirrors ``layers`` (``theme -> pairing -> ratio``) for the
    pairings the system guarantees: ``text-*`` on every ``bg-surface-*``, the
    accent on-color label against every action state, and the status text and
    on-color labels against their expected surfaces (WCAG AA).
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
        global_tokens = theme["global"]
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
        for family in STATUS_FAMILIES:
            for state in (family, f"{family}-hover", f"{family}-active"):
                report[theme_name][f"text-on-{family}/{state}"] = contrast_ratio(
                    parse_hex(semantic[f"text-on-{family}"]),
                    parse_hex(global_tokens[state]),
                )
            for surface in surfaces:
                report[theme_name][f"text-{family}/{surface}"] = contrast_ratio(
                    parse_hex(semantic[f"text-{family}"]),
                    parse_hex(semantic[surface]),
                )
    return report
