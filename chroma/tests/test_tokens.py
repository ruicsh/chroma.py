"""Tests for the semantic token system (curves, Radix mapping, contrast)."""

import unittest

from chroma import build_themes, verify_contrast
from chroma.color import parse_hex, rgb_to_oklch
from chroma.tokens import NEUTRAL_TOKEN_STEPS, THEMES, _interp, neutral_scale

BRANDS = (
    "6366f1",
    "10b981",
    "ef4444",
    "f59e0b",
    "111827",
    "f8fafc",
    "06b6d4",
    "0ea5e9",
    "8b5cf6",
    "f472b6",
)

SURFACE_STEPS = (
    "surface-root",
    "surface-subtle",
    "surface-default",
    "surface-elevated",
    "surface-active",
)
BORDER_STEPS = ("border-subtle", "border-default", "border-strong")
TEXT_STEPS = ("text-muted", "text-secondary", "text-primary")


class TestThemeStructure(unittest.TestCase):
    def test_all_token_families_present(self):
        themes = build_themes("6366f1")
        expected = set(NEUTRAL_TOKEN_STEPS) | {
            "intent-primary",
            "intent-primary-hover",
            "intent-primary-active",
            "intent-on-primary",
            "intent-focus-ring",
        }
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                self.assertEqual(set(themes[theme_name]), expected)
                for value in themes[theme_name].values():
                    self.assertEqual(len(value), 7)
                    self.assertTrue(value.startswith("#"))


class TestCurves(unittest.TestCase):
    def step_position(self, name):
        return (NEUTRAL_TOKEN_STEPS[name] - 1) / 11.0

    def test_lightness_is_monotonic(self):
        for theme_name in ("dark", "light"):
            theme = THEMES[theme_name]
            for group in (SURFACE_STEPS, BORDER_STEPS, TEXT_STEPS):
                values = [
                    _interp(theme.lightness_controls, self.step_position(name))
                    for name in group
                ]
                with self.subTest(theme=theme_name, group=group):
                    if theme_name == "dark":
                        self.assertEqual(values, sorted(values))
                    else:
                        self.assertEqual(values, sorted(values, reverse=True))

    def test_interp_edge_clamps(self):
        theme = THEMES["dark"]
        self.assertEqual(
            _interp(theme.lightness_controls, 0.0), theme.lightness_controls[0][1]
        )
        self.assertEqual(
            _interp(theme.lightness_controls, 1.0), theme.lightness_controls[-1][1]
        )


class TestNeutralScale(unittest.TestCase):
    def test_hue_locked_to_brand(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
                for theme_name in ("light", "dark"):
                    scale = neutral_scale(THEMES[theme_name], brand_hue)
                    for _, (_, _, hue) in scale.items():
                        self.assertAlmostEqual(hue, brand_hue, delta=1e-9)

    def test_surface_lightness_bands(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
                for theme_name in ("light", "dark"):
                    scale = neutral_scale(THEMES[theme_name], brand_hue)
                    surfaces = [scale[name][0] for name in SURFACE_STEPS]
                    if theme_name == "dark":
                        self.assertLessEqual(max(surfaces), 0.32)
                        self.assertLessEqual(scale["surface-root"][0], 0.20)
                    else:
                        self.assertGreaterEqual(min(surfaces), 0.93)

    def test_chroma_caps(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
                for theme_name in ("light", "dark"):
                    scale = neutral_scale(THEMES[theme_name], brand_hue)
                    chromas = [value[1] for value in scale.values()]
                    cap = 0.04 if theme_name == "dark" else 0.015
                    self.assertLessEqual(max(chromas), cap)


class TestContrastGuarantees(unittest.TestCase):
    def test_aaa_guarantees(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                themes = build_themes(brand)
                report = verify_contrast(themes)
                for theme_name in ("light", "dark"):
                    for pairing, ratio in report[theme_name].items():
                        if pairing.startswith("text-muted"):
                            continue
                        if pairing.startswith("text-secondary"):
                            self.assertGreaterEqual(
                                ratio, 4.5, (brand, theme_name, pairing)
                            )
                        else:
                            self.assertGreaterEqual(
                                ratio, 7.0, (brand, theme_name, pairing)
                            )

    def test_intent_on_color_polarity(self):
        dark_brand = build_themes("111827")
        bright_brand = build_themes("10b981")
        self.assertEqual(dark_brand["light"]["intent-on-primary"], "#ffffff")
        self.assertEqual(bright_brand["light"]["intent-on-primary"], "#000000")

    def test_intent_preserves_brand_hue_and_is_vivid(self):
        themes = build_themes("10b981")
        self.assertEqual(themes["light"]["intent-primary"], "#10b981")

    def test_generation_is_deterministic(self):
        self.assertEqual(build_themes("6366f1"), build_themes("6366f1"))


if __name__ == "__main__":
    unittest.main()
