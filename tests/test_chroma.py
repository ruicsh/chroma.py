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
