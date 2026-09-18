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

The theme interpolation controls live in ``chroma.theme`` and the semantic
status domain (anchors, brand-decay blending, status solids/scales) in
``chroma.semantic``; this module owns the neutral/brand/accent ramps and the
two-tier compilation (``build_layers``, ``verify_contrast``).
"""

from __future__ import annotations

from chroma.color import (
    _interp,
    _normalize_lightness,
    contrast_ratio,
    oklch_to_hex,
    oklch_to_rgb,
    parse_hex,
    relative_luminance,
    rgb_to_oklch,
)
from chroma.semantic import (
    BRAND_DECAY_WEIGHTS,
    SEMANTIC_ANCHORS,
    STATUS_COORD_NAMES,
    STATUS_SCALE_NAMES,
    STATUS_SPECS,
    STATUS_TOKEN_NAMES,
    SURFACE_CHROMA_CAP,
    status_scale,
    status_scale_steps,
)
from chroma.taxonomy import (
    ACTION_CONCEPTS,
    CONTRAST_SURFACES,
    STATUS_FAMILIES,
    get_taxonomy,
)
from chroma.theme import DARK, LIGHT, THEMES, ThemeSpec

__all__ = [
    "ACCENT_TOKEN_NAMES",
    "BRAND_DECAY_WEIGHTS",
    "BRAND_SCALE_NAMES",
    "CANONICAL_SEMANTIC_TO_GLOBAL",
    "CONTRAST_SURFACES",
    "DARK",
    "LIGHT",
    "SCALE_STEP_LEGEND",
    "SEMANTIC_ANCHORS",
    "SEMANTIC_TO_GLOBAL",
    "STATUS_COORD_NAMES",
    "STATUS_FAMILIES",
    "STATUS_SCALE_NAMES",
    "STATUS_SPECS",
    "STATUS_TOKEN_NAMES",
    "STEP_KEYS",
    "SURFACE_CHROMA_CAP",
    "THEMES",
    "accent_scale",
    "brand_scale_names",
    "brand_scale_steps",
    "build_layers",
    "color_ramp",
    "neutral_scale_names",
    "neutral_steps",
    "semantic_to_global",
    "status_scale",
    "status_scale_steps",
    "verify_contrast",
]

_AAA_SOLID = 7.0  # accent solid vs its on-color label
_AAA_TARGET = _AAA_SOLID + 0.2  # headroom so hover/active chroma shifts stay AAA
_ON_TINT_CHROMA = 0.015  # brand-hue chroma for the dark "chromatic gray" on-color

STEP_KEYS: tuple[str, ...] = tuple(f"step-{step}" for step in range(1, 13))

ACCENT_TOKEN_NAMES: tuple[str, ...] = (
    "accent",
    "accent-hover",
    "accent-active",
    "accent-on",
)

BRAND_SCALE_NAMES: tuple[str, ...] = tuple(f"brand-{step}" for step in range(1, 13))

# Adapted step legend: the article's 50–950 guide collapsed onto chroma's 1–12
# Radix protocol. Each index's intent is documented here and on the preview
# ramp cells. Source: Atmos Step 2.
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
                **status_scale(),
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

    surfaces = tuple(n(c) for c in CONTRAST_SURFACES)
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
        for state in ACTION_CONCEPTS:
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
