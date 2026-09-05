"""Tests for the chroma.py color engine (OKLCH conversion + WCAG math)."""

import math

import pytest

import chroma


# ---------------------------------------------------------------------------
# Hex parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("6366f1", (0x63 / 255, 0x66 / 255, 0xF1 / 255)),
        ("#6366f1", (0x63 / 255, 0x66 / 255, 0xF1 / 255)),
        ("639", (0x66 / 255, 0x33 / 255, 0x99 / 255)),
        ("#639", (0x66 / 255, 0x33 / 255, 0x99 / 255)),
        ("000000", (0.0, 0.0, 0.0)),
        ("FFFFFF", (1.0, 1.0, 1.0)),
    ],
)
def test_parse_hex_valid_forms(value, expected):
    assert chroma.parse_hex(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["", "#", "12345", "1234567", "gggggg", "12g", "12", None])
def test_parse_hex_rejects_invalid(value):
    with pytest.raises(ValueError):
        chroma.parse_hex(value)


def test_rgb_to_hex_roundtrip_and_case():
    assert chroma.rgb_to_hex(chroma.parse_hex("10B981")) == "#10b981"
    assert chroma.rgb_to_hex((1.0, 1.0, 1.0)) == "#ffffff"


# ---------------------------------------------------------------------------
# HSL conversion
# ---------------------------------------------------------------------------


def test_rgb_to_hsl_known_value():
    hue, sat, light = chroma.rgb_to_hsl(chroma.parse_hex("6366f1"))
    assert hue == pytest.approx(239.0, abs=1.0)
    assert 0.0 <= sat <= 1.0
    assert 0.0 <= light <= 1.0


@pytest.mark.parametrize("rgb", [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (0.5, 0.5, 0.5), (0.9, 0.2, 0.7)])
def test_hsl_roundtrip(rgb):
    assert chroma.hsl_to_rgb(chroma.rgb_to_hsl(rgb)) == pytest.approx(rgb, abs=1e-9)


def test_hsl_gray_has_zero_saturation():
    hue, sat, _ = chroma.rgb_to_hsl((0.5, 0.5, 0.5))
    assert sat == 0.0
    assert hue == 0.0


# ---------------------------------------------------------------------------
# OKLCH conversion
# ---------------------------------------------------------------------------


def test_oklch_achromatic_chroma_zero():
    _, chroma_val, _ = chroma.rgb_to_oklch((0.5, 0.5, 0.5))
    assert chroma_val == pytest.approx(0.0, abs=1e-6)


def test_oklch_hue_bounds():
    for value in ("6366f1", "10b981", "ef4444", "f59e0b", "06b6d4"):
        _, _, hue = chroma.rgb_to_oklch(chroma.parse_hex(value))
        assert 0.0 <= hue < 360.0


@pytest.mark.parametrize(
    "rgb",
    [
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
        (1, 1, 1),
        (0, 0, 0),
        (0.63, 0.4, 0.945),
        (0.5, 0.5, 0.5),
        (0.05, 0.3, 0.6),
    ],
)
def test_oklch_roundtrip(rgb):
    assert chroma.oklch_to_rgb(chroma.rgb_to_oklch(rgb)) == pytest.approx(rgb, abs=0.001)


def test_oklch_to_rgb_clamps_gamut():
    rgb = chroma.oklch_to_rgb((0.7, 0.4, 200.0))
    assert all(-1e-9 <= c <= 1.0 + 1e-9 for c in rgb)


# ---------------------------------------------------------------------------
# WCAG luminance / contrast
# ---------------------------------------------------------------------------


def test_relative_luminance_extremes():
    assert chroma.relative_luminance((0, 0, 0)) == pytest.approx(0.0, abs=1e-12)
    assert chroma.relative_luminance((1, 1, 1)) == pytest.approx(1.0, abs=1e-12)


def test_contrast_ratio_extremes():
    assert chroma.contrast_ratio((0, 0, 0), (1, 1, 1)) == pytest.approx(21.0, abs=1e-6)
    assert chroma.contrast_ratio((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)) == pytest.approx(1.0, abs=1e-6)


def test_contrast_ratio_is_symmetric():
    white = (1, 1, 1)
    dark = (0.1, 0.1, 0.1)
    assert chroma.contrast_ratio(white, dark) == pytest.approx(chroma.contrast_ratio(dark, white))


def test_parse_and_contrast_black_white():
    assert chroma.contrast_ratio(chroma.parse_hex("000000"), chroma.parse_hex("ffffff")) == pytest.approx(
        21.0, abs=1e-6
    )


# ---------------------------------------------------------------------------
# Semantic token system
# ---------------------------------------------------------------------------

BRANDS = ("6366f1", "10b981", "ef4444", "f59e0b", "111827", "f8fafc", "06b6d4", "0ea5e9", "8b5cf6", "f472b6")


def test_theme_structure_has_all_token_families():
    themes = chroma.build_themes("6366f1")
    expected = set(chroma.NEUTRAL_TOKEN_STEPS) | {
        "intent-primary",
        "intent-primary-hover",
        "intent-primary-active",
        "intent-on-primary",
        "intent-focus-ring",
    }
    for theme_name in ("light", "dark"):
        assert set(themes[theme_name]) == expected
        for value in themes[theme_name].values():
            assert len(value) == 7 and value.startswith("#")


def test_neutral_lightness_is_monotonic():
    for theme_name in ("dark", "light"):
        theme = chroma.THEMES[theme_name]
        for group, steps in (
            ("surface", ["surface-root", "surface-subtle", "surface-default", "surface-elevated", "surface-active"]),
            ("border", ["border-subtle", "border-default", "border-strong"]),
            ("text", ["text-muted", "text-secondary", "text-primary"]),
        ):
            values = [chroma._interp(theme.lightness_controls, (chroma.NEUTRAL_TOKEN_STEPS[name] - 1) / 11.0) for name in steps]
            if theme_name == "dark":
                assert values == sorted(values), (theme_name, group)
            else:
                assert values == sorted(values, reverse=True), (theme_name, group)


@pytest.mark.parametrize("brand", BRANDS)
def test_neutral_hue_locked_to_brand(brand):
    _, _, brand_hue = chroma.rgb_to_oklch(chroma.parse_hex(brand))
    for theme_name in ("light", "dark"):
        scale = chroma.neutral_scale(chroma.THEMES[theme_name], brand_hue)
        for name, (_, _, hue) in scale.items():
            assert hue == pytest.approx(brand_hue, abs=1e-9), name


@pytest.mark.parametrize("brand", BRANDS)
def test_surface_lightness_bands(brand):
    _, _, brand_hue = chroma.rgb_to_oklch(chroma.parse_hex(brand))
    for theme_name in ("light", "dark"):
        scale = chroma.neutral_scale(chroma.THEMES[theme_name], brand_hue)
        surfaces = [scale[name][0] for name in chroma.NEUTRAL_TOKEN_STEPS if name.startswith("surface")]
        if theme_name == "dark":
            assert max(surfaces) <= 0.32
            assert chroma.neutral_scale(chroma.THEMES[theme_name], brand_hue)["surface-root"][0] <= 0.20
        else:
            assert min(surfaces) >= 0.93


@pytest.mark.parametrize("brand", BRANDS)
def test_neutral_chroma_caps(brand):
    _, _, brand_hue = chroma.rgb_to_oklch(chroma.parse_hex(brand))
    for theme_name in ("light", "dark"):
        scale = chroma.neutral_scale(chroma.THEMES[theme_name], brand_hue)
        chromas = [value[1] for value in scale.values()]
        cap = 0.04 if theme_name == "dark" else 0.015
        assert max(chromas) <= cap


@pytest.mark.parametrize("brand", BRANDS)
def test_aaa_contrast_guarantees(brand):
    themes = chroma.build_themes(brand)
    report = chroma.verify_contrast(themes)
    for theme_name in ("light", "dark"):
        for pairing, ratio in report[theme_name].items():
            if pairing.startswith("text-muted"):
                continue
            if pairing.startswith("text-secondary"):
                assert ratio >= 4.5, (brand, theme_name, pairing, ratio)
            else:
                assert ratio >= 7.0, (brand, theme_name, pairing, ratio)


def test_intent_on_color_polarity():
    # Dark navy prefers white on-color; bright emerald prefers black.
    dark_brand = chroma.build_themes("111827")
    bright_brand = chroma.build_themes("10b981")
    assert dark_brand["light"]["intent-on-primary"] == "#ffffff"
    assert bright_brand["light"]["intent-on-primary"] == "#000000"


def test_intent_preserves_brand_hue_and_is_vivid():
    themes = chroma.build_themes("10b981")
    assert themes["light"]["intent-primary"] == "#10b981"  # already AAA with black text -> unchanged


def test_generation_is_deterministic():
    assert chroma.build_themes("6366f1") == chroma.build_themes("6366f1")
