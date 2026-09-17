"""Two-tier token system: global -> semantic, in OKLCH.

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
intent (the baseline Atmos naming) to those steps; the taxonomy layer renames
both tiers for the target design framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from chroma.color import (
    contrast_ratio,
    mix_oklch,
    oklch_to_hex,
    oklch_to_rgb,
    parse_hex,
    relative_luminance,
    rgb_to_oklch,
)
from chroma.taxonomy import (
    STATUS_FAMILIES,
    get_taxonomy,
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

# The four semantic status families. Each carries a fixed, independent OKLCH
# anchor — a culturally verified absolute coordinate that does not move with the
# brand — plus an explicit on-color polarity, so success/danger/info read as
# vivid dark solids under white labels while the amber warning stays light under
# a black label. (Defined canonically in chroma.taxonomy and re-exported here.)
#
# ``(L, C, H)``: the anchor sits at step 9 of the family ramp (the high-contrast
# interactive target); steps 10-12 darken past it while keeping the locked hue
# and chroma.
SEMANTIC_ANCHORS: dict[str, tuple[float, float, float]] = {
    "danger": (0.62, 0.22, 25.0),
    "warning": (0.79, 0.18, 85.0),
    "success": (0.65, 0.16, 145.0),
    "info": (0.60, 0.16, 250.0),
}

# On-color polarity per family (theme-independent, AA-solved).
STATUS_ON: dict[str, str] = {
    "success": "white",
    "warning": "black",
    "danger": "white",
    "info": "white",
}

# Brand-influence decay matrix: only the surface foundations (steps 1-3) receive
# a controlled percentage of the brand coordinate. Steps 4-12 are isolated so
# the family keeps universal recognition and its WCAG guarantees.
BRAND_DECAY_WEIGHTS: dict[int, float] = {1: 0.15, 2: 0.10, 3: 0.05}

# Maximum chroma allowed on a blended neutral surface step. Both themes must
# stay under this so alert tints never read as a saturated chromatic surface.
SURFACE_CHROMA_CAP = 0.026

# Landmark interpolation points on the 1..12 ladder (as t in 0..1): step 9 is
# the family anchor (the high-contrast interactive target), step 11 the strong
# text step. Semantic surfaces start at this fraction of the anchor chroma.
_ANCHOR_STEP_T = 8.0 / 11.0
_TEXT_STEP_T = 10.0 / 11.0
_SURFACE_CHROMA_FRACTION = 0.30


class _StatusSpec(TypedDict):
    lightness: float
    chroma: float
    hue: float
    on: str


# Solid identity is derived from the anchors so the ramp and the solid can never
# drift apart: lightness/hue/chroma are the locked anchor coordinates and ``on``
# is polarity.
STATUS_SPECS: dict[str, _StatusSpec] = {
    family: {
        "lightness": lightness,
        "chroma": chroma,
        "hue": hue,
        "on": STATUS_ON[family],
    }
    for family, (lightness, chroma, hue) in SEMANTIC_ANCHORS.items()
}

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

# Full current status global token name set (solid + interaction coordinates
# plus the 12-step shade scales), used by the tests and the exports.
STATUS_TOKEN_NAMES: tuple[str, ...] = tuple((*STATUS_COORD_NAMES, *STATUS_SCALE_NAMES))

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
# Layer 2 -> Layer 1: semantic concept (functional intent) resolves to a
# global primitive (a Radix neutral step, a brand accent, or a status step).
# This table is taxonomy-independent; the taxonomy only renames both sides.
# ---------------------------------------------------------------------------

# Canonical concept id -> canonical global primitive id.
CANONICAL_SEMANTIC_TO_GLOBAL: dict[str, str] = {
    "bg-surface-root": "step-1",
    "bg-surface-default": "step-2",
    "bg-surface-subtle": "step-3",
    "bg-surface-hover": "step-4",
    "bg-surface-active": "step-5",
    "border-subtle": "step-6",
    "border-default": "step-7",
    "border-strong": "step-8",
    "text-foreground-disabled": "step-8",  # recessed text matches structural borders
    "text-foreground-muted": "step-10",
    "text-foreground-secondary": "step-11",
    "text-foreground-primary": "step-12",
    "text-on-accent": "accent-on",
    "bg-action-primary": "accent",
    "bg-action-hover": "accent-hover",
    "bg-action-active": "accent-active",
}

for _family in STATUS_FAMILIES:
    CANONICAL_SEMANTIC_TO_GLOBAL[f"bg-{_family}-subtle"] = f"{_family}-2"
    CANONICAL_SEMANTIC_TO_GLOBAL[f"bg-{_family}-strong"] = _family
    CANONICAL_SEMANTIC_TO_GLOBAL[f"border-{_family}"] = f"{_family}-6"
    CANONICAL_SEMANTIC_TO_GLOBAL[f"text-{_family}"] = f"{_family}-11"
    CANONICAL_SEMANTIC_TO_GLOBAL[f"text-on-{_family}"] = f"{_family}-on"


def semantic_to_global(taxonomy: str = "atmos") -> dict[str, str]:
    """Map each taxonomy semantic token name to its primitive global name.

    The returned ``{semantic_name: global_name}`` aliases the Tier-2 semantic
    tokens (renamed by the taxonomy) onto the Tier-1 primitive names (also
    renamed by the taxonomy).
    """
    spec = get_taxonomy(taxonomy)
    mapping: dict[str, str] = {}
    for concept, source in CANONICAL_SEMANTIC_TO_GLOBAL.items():
        mapping[spec.semantic_name(concept)] = spec.global_primitive(source)
    return mapping


# Backwards-compatible alias for the baseline (atmos) taxonomy: actual emitted
# semantic token name -> actual emitted global token name. Consumers may use it
# against ``build_layers`` output directly (``layers[theme]['semantic'][k] ==
# layers[theme]['global'][SEMANTIC_TO_GLOBAL[k]]``).
SEMANTIC_TO_GLOBAL: dict[str, str] = semantic_to_global("atmos")


def neutral_scale_names(taxonomy: str = "atmos") -> tuple[str, ...]:
    """Return the 12 neutral primitive names for ``taxonomy`` (Tier 1)."""
    spec = get_taxonomy(taxonomy)
    return tuple(spec.global_primitive(f"step-{i}") for i in range(1, 13))


def brand_scale_names(taxonomy: str = "atmos") -> tuple[str, ...]:
    """Return the 12 brand primitive names for ``taxonomy`` (Tier 1)."""
    spec = get_taxonomy(taxonomy)
    return tuple(spec.global_primitive(f"brand-{i}") for i in range(1, 13))


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


def _semantic_lightness_controls(
    theme: ThemeSpec, anchor_lightness: float
) -> tuple[tuple[float, float], ...]:
    """Lightness control points pinning step 9 to the semantic anchor.

    Step 1 is the theme's extreme surface, step 9 the anchor (the high-contrast
    interactive target), and steps 10-12 continue to the theme's text end, so
    the ladder stays monotonic and the text steps keep their contrast headroom.
    """
    surface = _interp(theme.lightness_controls, 0.0)
    text = _interp(theme.lightness_controls, _TEXT_STEP_T)
    extreme = _interp(theme.lightness_controls, 1.0)
    return (
        (0.0, surface),
        (_ANCHOR_STEP_T, anchor_lightness),
        (_TEXT_STEP_T, text),
        (1.0, extreme),
    )


def _semantic_chroma_controls(
    anchor_chroma: float,
) -> tuple[tuple[float, float], ...]:
    """Chroma control points: ramp up to the anchor by step 9, then lock.

    Both themes share the anchor chroma exactly (no dark scale-back) so step 9
    is the anchor coordinate in either theme.
    """
    return (
        (0.0, _SURFACE_CHROMA_FRACTION * anchor_chroma),
        (_ANCHOR_STEP_T, anchor_chroma),
        (1.0, anchor_chroma),
    )


def _clamp_surface_chroma(
    oklch: tuple[float, float, float], cap: float = SURFACE_CHROMA_CAP
) -> tuple[float, float, float]:
    """Cap a blended surface step so it stays a near-neutral tint."""
    lightness, chroma, hue = oklch
    return (lightness, min(chroma, cap), hue)


def _semantic_ramp_theme(
    brand_oklch: tuple[float, float, float],
    semantic_base_oklch: tuple[float, float, float],
    theme: ThemeSpec,
) -> dict[str, tuple[float, float, float]]:
    """Evaluate one family's 12-step ramp for ``theme`` with brand blending.

    Steps 1-3 begin as the weighted average of the pure semantic step and the
    brand coordinate (shortest-path hue), clamped to ``SURFACE_CHROMA_CAP`` and
    held on the ladder's side of the following step so a very dark brand cannot
    invert the ramp. Steps 4-12 carry 0% brand influence and stay locked to the
    anchor.
    """
    anchor_lightness, anchor_chroma, anchor_hue = semantic_base_oklch
    lightness_controls = _semantic_lightness_controls(theme, anchor_lightness)
    chroma_controls = _semantic_chroma_controls(anchor_chroma)
    pure = [
        (
            _interp(lightness_controls, (step - 1) / 11.0),
            _interp(chroma_controls, (step - 1) / 11.0),
            anchor_hue,
        )
        for step in range(1, 13)
    ]
    # Light ramps descend from step 1; dark ramps ascend toward step 12. Walk
    # from the text end down so ``next_lightness`` is always the step below and
    # keep every blended surface step on the correct side of it.
    ascending = theme.name == "dark"
    computed: list[tuple[int, tuple[float, float, float]]] = []
    next_lightness: float | None = None
    for step in range(12, 0, -1):
        oklch = pure[step - 1]
        weight = BRAND_DECAY_WEIGHTS.get(step, 0.0)
        if weight:
            lightness, chroma, hue = _clamp_surface_chroma(
                mix_oklch(oklch, brand_oklch, weight)
            )
            if next_lightness is not None:
                lightness = (
                    min(lightness, next_lightness)
                    if ascending
                    else max(lightness, next_lightness)
                )
            oklch = (lightness, chroma, hue)
        computed.append((step, oklch))
        next_lightness = oklch[0]
    return {f"step-{step}": oklch for step, oklch in reversed(computed)}


def blend_semantic_ramp(
    brand_oklch: tuple[float, float, float],
    semantic_base_oklch: tuple[float, float, float],
) -> dict[str, tuple[float, float, float]]:
    """Build a 12-step semantic ramp with the brand blended into its surfaces.

    The scale runs light to dark (the light frame). Step 9 is the family's
    locked anchor (its high-contrast interactive target) and steps 10-12 darken
    past it. Steps 1-3 mix the brand coordinate in by the decay matrix
    (15% / 10% / 5%) with shortest-path hue interpolation, then clamp chroma to
    ``SURFACE_CHROMA_CAP``. Steps 4-12 carry 0% brand influence.
    """
    return _semantic_ramp_theme(brand_oklch, semantic_base_oklch, LIGHT)


def status_scale_steps(
    theme: ThemeSpec,
    brand_oklch: tuple[float, float, float],
) -> dict[str, tuple[float, float, float]]:
    """12-step shade scale per status family (``{s}-1…12``).

    Each family is anchored at its independent OKLCH coordinate (step 9) with
    the brand blended into its surface foundations (steps 1-3). The same decay
    matrix and chroma cap apply to both themes.
    """
    out: dict[str, tuple[float, float, float]] = {}
    for family, anchor in SEMANTIC_ANCHORS.items():
        ramp = _semantic_ramp_theme(brand_oklch, anchor, theme)
        for key, value in ramp.items():
            out[f"{family}-{key.removeprefix('step-')}"] = value
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

    The four status families carry fixed, independent anchor coordinates. The
    solid (and its hover/active) is theme-independent, like the accent: its
    lightness starts from the anchor's ``L`` and is normalized only if the
    on-color label fails to clear WCAG AA. Subtle/border/text are derived from
    the 12-step status shade scales, so this helper only emits the 4-token
    solid set.
    """

    _ = theme  # theme-independent solids; kept for call-site symmetry
    tokens: dict[str, tuple[float, float, float]] = {}
    for family, spec in STATUS_SPECS.items():
        hue = spec["hue"]
        chroma = spec["chroma"]
        on_rgb = (1.0, 1.0, 1.0) if spec["on"] == "white" else (0.0, 0.0, 0.0)
        solid_lightness = _normalize_lightness(
            spec["lightness"], chroma, hue, on_rgb, _STATUS_TARGET
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
    hex_value: str,
    preserve_vibrancy: bool = False,
    taxonomy: str = "atmos",
) -> dict[str, dict[str, dict[str, str]]]:
    """Compile the two-tier dual-theme token map from a brand hex.

    Returns ``{theme: {layer: {token: hex}}}`` where ``layer`` is one of
    ``global`` / ``semantic``. All neutral tokens carry the locked brand hue
    (chromatic grays); the accent is the brand color normalized to clear WCAG
    AAA against its on-color label (or, with ``preserve_vibrancy``, locked to
    the brand with the on-color solved instead). The four status families
    carry their canonical hues with AA-guaranteed on-colors.

    ``taxonomy`` selects the target naming framework (default ``atmos``). The
    underlying OKLCH math and functional bindings are identical for every
    taxonomy; only the emitted token names change, applied through a pure
    two-tier rename (Tier 1 primitives, then Tier 2 semantic aliases).
    """
    brand = parse_hex(hex_value)
    brand_oklch = rgb_to_oklch(brand)
    _, _, hue = brand_oklch
    spec = get_taxonomy(taxonomy)
    layers: dict[str, dict[str, dict[str, str]]] = {}
    for theme in (DARK, LIGHT):
        canonical_global = {
            name: oklch_to_hex(*oklch)
            for name, oklch in {
                **neutral_steps(theme, hue),
                **accent_scale(brand, preserve_vibrancy=preserve_vibrancy),
                **brand_scale_steps(theme, brand),
                **status_scale(theme),
                **status_scale_steps(theme, brand_oklch),
            }.items()
        }
        # Tier 1: rename primitive scale steps via the taxonomy naming.
        global_tokens = {
            spec.global_primitive(name): value
            for name, value in canonical_global.items()
        }
        # Tier 2: semantic concepts renamed by the taxonomy, aliasing the
        # renamed Tier-1 primitives. Overlay is a computed surface, not an alias.
        semantic: dict[str, str] = {}
        for concept, source in CANONICAL_SEMANTIC_TO_GLOBAL.items():
            semantic[spec.semantic_name(concept)] = global_tokens[
                spec.global_primitive(source)
            ]
        semantic[spec.semantic_name("bg-surface-overlay")] = oklch_to_hex(
            theme.overlay_lightness, theme.overlay_chroma, hue
        )
        layers[theme.name] = {
            "global": global_tokens,
            "semantic": semantic,
        }
    return layers


def verify_contrast(
    layers: dict[str, dict[str, dict[str, str]]],
    taxonomy: str = "atmos",
) -> dict[str, dict[str, float]]:
    """Report the WCAG contrast of every structural text/background pairing.

    The returned map mirrors ``layers`` (``theme -> pairing -> ratio``) for the
    pairings the system guarantees: ``text-*`` on every ``bg-surface-*``, the
    accent on-color label against every action state, and the status text and
    on-color labels against their expected surfaces (WCAG AA).

    Pairing labels are reported in the active taxonomy's naming.
    """
    spec = get_taxonomy(taxonomy)

    def n(concept: str) -> str:
        return spec.semantic_name(concept)

    def gp(primitive: str) -> str:
        return spec.global_primitive(primitive)

    surface_concepts = (
        "bg-surface-root",
        "bg-surface-default",
        "bg-surface-subtle",
        "bg-surface-hover",
        "bg-surface-active",
        "bg-surface-overlay",
    )
    surfaces = tuple(n(c) for c in surface_concepts)
    texts = tuple(
        n(c)
        for c in (
            "text-foreground-primary",
            "text-foreground-secondary",
            "text-foreground-muted",
        )
    )
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
            report[theme_name][f"{n('text-on-accent')}/{n(state)}"] = contrast_ratio(
                parse_hex(semantic[n("text-on-accent")]),
                parse_hex(semantic[n(state)]),
            )
        for family in STATUS_FAMILIES:
            for state in (family, f"{family}-hover", f"{family}-active"):
                report[theme_name][f"{n(f'text-on-{family}')}/{gp(state)}"] = (
                    contrast_ratio(
                        parse_hex(semantic[n(f"text-on-{family}")]),
                        parse_hex(global_tokens[gp(state)]),
                    )
                )
            for surface in surfaces:
                report[theme_name][f"{n(f'text-{family}')}/{surface}"] = contrast_ratio(
                    parse_hex(semantic[n(f"text-{family}")]),
                    parse_hex(semantic[surface]),
                )
    return report
