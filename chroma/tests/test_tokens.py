"""Tests for the token system (curves, Radix mapping, contrast guarantees)."""

import unittest

from chroma import build_layers, verify_contrast
from chroma.color import parse_hex, relative_luminance, rgb_to_oklch
from chroma.tokens import (
    ACCENT_TOKEN_NAMES,
    STEP_KEYS,
    THEMES,
    _interp,
    accent_scale,
    neutral_steps,
)

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


class TestLayerStructure(unittest.TestCase):
    def test_two_tiers_present(self):
        layers = build_layers("6366f1")
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                self.assertEqual(set(layers[theme_name]), {"global", "semantic"})
                self.assertEqual(
                    set(layers[theme_name]["global"]),
                    set(STEP_KEYS) | set(ACCENT_TOKEN_NAMES),
                )
                for value in layers[theme_name]["global"].values():
                    self.assertEqual(len(value), 7)
                    self.assertTrue(value.startswith("#"))


class TestCurves(unittest.TestCase):
    def test_lightness_is_monotonic(self):
        for theme_name in ("dark", "light"):
            theme = THEMES[theme_name]
            values = [
                _interp(theme.lightness_controls, (step - 1) / 11.0)
                for step in range(1, 13)
            ]
            with self.subTest(theme=theme_name):
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


class TestNeutralSteps(unittest.TestCase):
    def test_hue_locked_to_brand(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
                for theme_name in ("light", "dark"):
                    steps = neutral_steps(THEMES[theme_name], brand_hue)
                    for _, (_, _, hue) in steps.items():
                        self.assertAlmostEqual(hue, brand_hue, delta=1e-9)

    def test_surface_lightness_bands(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
                for theme_name in ("light", "dark"):
                    steps = neutral_steps(THEMES[theme_name], brand_hue)
                    surface_lightness = [steps[f"step-{n}"][0] for n in range(1, 6)]
                    if theme_name == "dark":
                        self.assertLessEqual(max(surface_lightness), 0.32)
                        self.assertLessEqual(steps["step-1"][0], 0.20)
                    else:
                        self.assertGreaterEqual(min(surface_lightness), 0.93)

    def test_chroma_caps(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
                for theme_name in ("light", "dark"):
                    steps = neutral_steps(THEMES[theme_name], brand_hue)
                    chromas = [value[1] for value in steps.values()]
                    cap = 0.04 if theme_name == "dark" else 0.015
                    self.assertLessEqual(max(chromas), cap)


class TestAccent(unittest.TestCase):
    def test_on_color_polarity(self):
        dark_brand = build_layers("111827")
        bright_brand = build_layers("10b981")
        self.assertEqual(dark_brand["light"]["global"]["accent-on"], "#ffffff")
        self.assertEqual(bright_brand["light"]["global"]["accent-on"], "#000000")

    def test_accent_preserves_brand_hue_and_is_vivid(self):
        layers = build_layers("10b981")
        self.assertEqual(layers["light"]["global"]["accent"], "#10b981")

    def test_accent_hue_locked(self):
        brand = parse_hex("6366f1")
        _, _, brand_hue = rgb_to_oklch(brand)
        scale = accent_scale(brand)
        for name, (_, _, hue) in scale.items():
            if name == "accent-on":  # black/white carry no hue
                continue
            self.assertAlmostEqual(hue, brand_hue, delta=1e-9)


class TestPreserveVibrancy(unittest.TestCase):
    def test_bright_accent_locked_with_dark_chromatic_gray_label(self):
        layers = build_layers("00ffff", preserve_vibrancy=True)
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                global_tokens = layers[theme_name]["global"]
                self.assertEqual(global_tokens["accent"], "#00ffff")
                self.assertNotEqual(global_tokens["accent-on"], "#000000")
                self.assertEqual(global_tokens["accent-on"], "#3f4b4b")
                on_l, on_c, on_h = rgb_to_oklch(parse_hex(global_tokens["accent-on"]))
                _, _, brand_hue = rgb_to_oklch(parse_hex("00ffff"))
                # 8-bit hex quantization makes hue ill-conditioned on near-gray
                # tints, so allow a few degrees of drift from the brand hue.
                self.assertAlmostEqual(on_h, brand_hue, delta=5.0)
                self.assertLessEqual(on_c, 0.02)
                self.assertLess(on_l, 0.5)

    def test_bright_accent_aaa_across_action_states(self):
        layers = build_layers("00ffff", preserve_vibrancy=True)
        report = verify_contrast(layers)
        for theme_name in ("light", "dark"):
            for state in ("bg-action-primary", "bg-action-hover", "bg-action-active"):
                with self.subTest(theme=theme_name, state=state):
                    self.assertGreaterEqual(
                        report[theme_name][f"text-on-accent/{state}"], 7.0
                    )

    def test_dark_accent_preserved_keeps_white_label(self):
        layers = build_layers("111827", preserve_vibrancy=True)
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                self.assertEqual(layers[theme_name]["global"]["accent"], "#111827")
                self.assertEqual(layers[theme_name]["global"]["accent-on"], "#ffffff")

    def test_mid_bright_falls_back_to_normalization(self):
        preserved = build_layers("6366f1", preserve_vibrancy=True)
        default = build_layers("6366f1")
        self.assertEqual(preserved, default)

    def test_default_path_unchanged(self):
        self.assertEqual(
            build_layers("00ffff"), build_layers("00ffff", preserve_vibrancy=False)
        )


class TestContrastGuarantees(unittest.TestCase):
    def test_aaa_guarantees(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                layers = build_layers(brand)
                report = verify_contrast(layers)
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

    def test_overlay_is_a_true_floating_layer(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                layers = build_layers(brand)
                dark = layers["dark"]["semantic"]
                light = layers["light"]["semantic"]
                dark_root_lum = relative_luminance(parse_hex(dark["bg-surface-root"]))
                dark_overlay_lum = relative_luminance(
                    parse_hex(dark["bg-surface-overlay"])
                )
                self.assertGreater(dark_overlay_lum, dark_root_lum)
                self.assertGreater(
                    relative_luminance(parse_hex(light["bg-surface-overlay"])), 0.95
                )


class TestDeterminism(unittest.TestCase):
    def test_generation_is_deterministic(self):
        self.assertEqual(build_layers("6366f1"), build_layers("6366f1"))


if __name__ == "__main__":
    unittest.main()
