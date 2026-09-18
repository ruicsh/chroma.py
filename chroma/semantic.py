"""Semantic status domain: the four status families' anchored 12-step ramps.

Each status family (success / warning / danger / info) carries a fixed,
independent OKLCH anchor — a culturally verified absolute coordinate that does
not move with the brand — plus an explicit on-color polarity. The anchor sits
at step 9 of the family ramp (the high-contrast interactive target); steps
10-12 darken past it while keeping the locked hue and chroma.

The brand blends into the surface foundations (steps 1-3) through a decay
matrix (15% / 10% / 5%) with shortest-path hue interpolation and a chroma cap,
so alert tints carry the brand without losing family recognition. Steps 4-12
are brand-isolated and stay locked to the anchor.
"""

from __future__ import annotations

from typing import TypedDict

from chroma.color import (
    _interp,
    _normalize_lightness,
    mix_oklch,
    rgb_to_oklch,
)
from chroma.taxonomy import STATUS_FAMILIES
from chroma.theme import ThemeSpec

_STATUS_AA = 4.5  # status solid / text on-color floor (WCAG AA)
_STATUS_TARGET = _STATUS_AA + 0.2  # headroom for status hover/active chroma shifts

# anchor — a culturally verified absolute coordinate that does not move with the
# brand — plus an explicit on-color polarity, so success/danger/info read as
# vivid dark solids under white labels while the amber warning stays light under
# a black label.
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


def status_scale() -> dict[str, tuple[float, float, float]]:
    """Build the status family solid coordinates as ``{token: (L, C, H)}``.

    The four status families carry fixed, independent anchor coordinates. The
    solid (and its hover/active) is theme-independent, like the accent: its
    lightness starts from the anchor's ``L`` and is normalized only if the
    on-color label fails to clear WCAG AA. Subtle/border/text are derived from
    the 12-step status shade scales, so this helper only emits the 4-token
    solid set.
    """

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
