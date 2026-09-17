"""Theme definitions: the per-theme interpolation controls for the 12-step ladders.

Each ``ThemeSpec`` holds the monotonic OKLCH lightness/chroma control points
shared by the neutral, brand, and status ramps, plus the theme's surface
overlay and status text coordinates. The neutral 12-step scale is evaluated
from these curves; the semantic status ramps pin their anchor at step 9 and
continue to the theme's text end.
"""

from __future__ import annotations

from dataclasses import dataclass


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
