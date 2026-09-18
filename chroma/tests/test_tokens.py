"""Tests for the token system (curves, Radix mapping, contrast guarantees)."""

import unittest

from chroma import build_layers, verify_contrast
from chroma.color import (
    _interp,
    parse_hex,
    relative_luminance,
    rgb_to_oklch,
)
from chroma.semantic import _semantic_ramp_theme
from chroma.tokens import (
    ACCENT_TOKEN_NAMES,
    BRAND_DECAY_WEIGHTS,
    BRAND_SCALE_NAMES,
    SEMANTIC_ANCHORS,
    STATUS_FAMILIES,
    STATUS_SPECS,
    STATUS_TOKEN_NAMES,
    SURFACE_CHROMA_CAP,
    THEMES,
    accent_scale,
    brand_scale_names,
    brand_scale_steps,
    neutral_scale_names,
    neutral_steps,
    status_scale,
    status_scale_steps,
)

BRAND_OKLCH = rgb_to_oklch(parse_hex("6366f1"))


def _family_ramp(
    family: str, theme_name: str, brand_oklch: tuple[float, float, float]
) -> dict[str, tuple[float, float, float]]:
    """Extract one family's 12-step ramp from ``status_scale_steps``."""
    steps = status_scale_steps(THEMES[theme_name], brand_oklch)
    return {f"step-{step}": steps[f"{family}-{step}"] for step in range(1, 13)}


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
                    set(neutral_scale_names())
                    | set(ACCENT_TOKEN_NAMES)
                    | set(brand_scale_names())
                    | set(STATUS_TOKEN_NAMES),
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


class TestStatusScale(unittest.TestCase):
    def test_hues_are_canonical(self):
        scale = status_scale()
        for family, spec in STATUS_SPECS.items():
            for name, (_, _, hue) in scale.items():
                if name.startswith(f"{family}-") and not name.endswith("-on"):
                    self.assertAlmostEqual(hue, spec["hue"], delta=1e-9)

    def test_solids_are_theme_independent(self):
        light = status_scale()
        dark = status_scale()
        for family in STATUS_FAMILIES:
            with self.subTest(family=family):
                for token in (
                    family,
                    f"{family}-hover",
                    f"{family}-active",
                    f"{family}-on",
                ):
                    self.assertEqual(light[token], dark[token])

    def test_on_color_polarity(self):
        layers = build_layers("6366f1")
        global_tokens = layers["light"]["global"]
        self.assertEqual(global_tokens["success-on"], "#ffffff")
        self.assertEqual(global_tokens["danger-on"], "#ffffff")
        self.assertEqual(global_tokens["info-on"], "#ffffff")
        self.assertEqual(global_tokens["warning-on"], "#000000")

    def test_on_color_aa_across_states(self):
        for brand in BRANDS:
            layers = build_layers(brand)
            report = verify_contrast(layers)
            with self.subTest(brand=brand):
                for theme_name in ("light", "dark"):
                    for family in STATUS_FAMILIES:
                        for state in (family, f"{family}-hover", f"{family}-active"):
                            self.assertGreaterEqual(
                                report[theme_name][f"text-on-{family}/{state}"],
                                4.5,
                                (brand, theme_name, family, state),
                            )

    def test_status_text_aa_on_surfaces(self):
        for brand in BRANDS:
            layers = build_layers(brand)
            report = verify_contrast(layers)
            with self.subTest(brand=brand):
                for theme_name in ("light", "dark"):
                    for family in STATUS_FAMILIES:
                        for surface in (
                            "bg-surface-root",
                            "bg-surface-default",
                            "bg-surface-subtle",
                        ):
                            self.assertGreaterEqual(
                                report[theme_name][f"text-{family}/{surface}"],
                                4.5,
                                (brand, theme_name, family, surface),
                            )

    def test_subtle_and_border_chroma_caps(self):
        # Under B1 the old subtle/border globals are removed; scale steps now
        # carry the tints. The blended surface steps (1-3) are capped to the
        # neutral surface chroma; the anchor steps (4-12) stay at or below the
        # family's locked chroma.
        scale = status_scale()
        for family in STATUS_FAMILIES:
            self.assertNotIn(f"{family}-subtle", scale)
            self.assertNotIn(f"{family}-border", scale)
            self.assertNotIn(f"{family}-text", scale)
        for theme_name in ("light", "dark"):
            steps = status_scale_steps(THEMES[theme_name], BRAND_OKLCH)
            with self.subTest(theme=theme_name):
                for family in STATUS_FAMILIES:
                    peak = STATUS_SPECS[family]["chroma"]
                    for step in range(1, 13):
                        c = steps[f"{family}-{step}"][1]
                        self.assertGreaterEqual(c, 0.0)
                        if step <= 3:
                            self.assertLessEqual(c, SURFACE_CHROMA_CAP + 1e-9)
                        else:
                            self.assertLessEqual(c, peak + 1e-9)


class TestColorRamps(unittest.TestCase):
    def test_brand_scale_hue_locked(self):
        for brand in BRANDS:
            _, _, brand_hue = rgb_to_oklch(parse_hex(brand))
            for theme_name in ("light", "dark"):
                ramp = brand_scale_steps(THEMES[theme_name], parse_hex(brand))
                with self.subTest(brand=brand, theme=theme_name):
                    for step in range(1, 13):
                        self.assertAlmostEqual(
                            ramp[f"brand-{step}"][2], brand_hue, delta=1e-9
                        )

    def test_status_scale_hue_locked(self):
        for theme_name in ("light", "dark"):
            ramp = status_scale_steps(THEMES[theme_name], BRAND_OKLCH)
            with self.subTest(theme=theme_name):
                for family, spec in STATUS_SPECS.items():
                    # Steps 4-12 are brand-isolated: hue stays locked to the
                    # anchor. Steps 1-3 are brand-blended, so their hue may move.
                    for step in range(4, 13):
                        self.assertAlmostEqual(
                            ramp[f"{family}-{step}"][2], spec["hue"], delta=1e-9
                        )

    def test_scales_are_deterministic(self):
        for theme_name in ("light", "dark"):
            brand = parse_hex("6366f1")
            self.assertEqual(
                brand_scale_steps(THEMES[theme_name], brand),
                brand_scale_steps(THEMES[theme_name], brand),
            )
            self.assertEqual(
                status_scale_steps(THEMES[theme_name], BRAND_OKLCH),
                status_scale_steps(THEMES[theme_name], BRAND_OKLCH),
            )

    def test_brand_scale_length(self):
        for theme_name in ("light", "dark"):
            ramp = brand_scale_steps(THEMES[theme_name], parse_hex("6366f1"))
            self.assertEqual(len(ramp), 12)
            self.assertEqual(set(ramp), set(BRAND_SCALE_NAMES))


class TestSemanticRamp(unittest.TestCase):
    def test_anchors_are_hardcoded_coordinates(self):
        expected = {
            "danger": (0.62, 0.22, 25.0),
            "warning": (0.79, 0.18, 85.0),
            "success": (0.65, 0.16, 145.0),
            "info": (0.60, 0.16, 250.0),
        }
        self.assertEqual(SEMANTIC_ANCHORS, expected)
        self.assertEqual(BRAND_DECAY_WEIGHTS, {1: 0.15, 2: 0.10, 3: 0.05})
        self.assertEqual(SURFACE_CHROMA_CAP, 0.026)
        # STATUS_SPECS is derived from the anchors: same lightness/hue/chroma.
        for family, anchor in SEMANTIC_ANCHORS.items():
            spec = STATUS_SPECS[family]
            self.assertEqual((spec["lightness"], spec["chroma"], spec["hue"]), anchor)

    def test_returns_twelve_steps(self):
        for family in SEMANTIC_ANCHORS:
            with self.subTest(family=family):
                ramp = _family_ramp(family, "light", BRAND_OKLCH)
                self.assertEqual(len(ramp), 12)
                self.assertEqual(set(ramp), {f"step-{i}" for i in range(1, 13)})

    def test_anchor_locked_at_step_nine(self):
        # Light and dark ramps must both land exactly on the anchor at step 9.
        for family, anchor in SEMANTIC_ANCHORS.items():
            with self.subTest(family=family):
                for theme_name in ("light", "dark"):
                    steps = status_scale_steps(THEMES[theme_name], BRAND_OKLCH)
                    self.assertEqual(steps[f"{family}-9"], anchor)

    def test_surface_steps_are_exact_weighted_average_of_brand(self):
        # The pure step is brand-independent, so the difference between two
        # brands' blended steps isolates the brand's contribution: it must be
        # exactly ``weight * (brand_b - brand_a)``. This only holds while the
        # monotonic clamp does not engage, so the brands are picked above the
        # clamp threshold for the info anchor (see test_lightness_is_monotonic).
        first = (0.30, 0.02, 200.0)
        second = (0.80, 0.04, 200.0)
        ramp_first = _family_ramp("info", "light", first)
        ramp_second = _family_ramp("info", "light", second)
        for step, weight in BRAND_DECAY_WEIGHTS.items():
            with self.subTest(step=step):
                self.assertAlmostEqual(
                    ramp_second[f"step-{step}"][0] - ramp_first[f"step-{step}"][0],
                    (second[0] - first[0]) * weight,
                    places=12,
                )

    def test_steps_four_to_twelve_are_brand_isolated(self):
        # Two wildly different brands must produce identical steps 4-12.
        first = _family_ramp("success", "light", (0.40, 0.30, 200.0))
        second = _family_ramp("success", "light", (0.90, 0.05, 20.0))
        for step in range(4, 13):
            with self.subTest(step=step):
                self.assertEqual(first[f"step-{step}"], second[f"step-{step}"])

    def test_hue_blend_takes_shortest_path(self):
        # Base hue 10, brand hue 350: naive interpolation sweeps +340 degrees;
        # the shortest path is -20, so step 1 lands just below 10 (near 0), not
        # near the 180-degree midpoint.
        base = (0.60, 0.20, 10.0)
        brand = (0.60, 0.20, 350.0)
        ramp = _semantic_ramp_theme(brand, base, THEMES["light"])
        hue = ramp["step-1"][2]
        self.assertGreater(hue, 0.0)
        self.assertLess(hue, 10.0)
        self.assertAlmostEqual(hue, 10.0 - 20.0 * BRAND_DECAY_WEIGHTS[1], delta=1e-9)

    def test_surface_chroma_is_capped(self):
        # A high-chroma brand must not push the surface steps past the cap in
        # either theme.
        brand = (0.70, 0.37, 330.0)
        for family in SEMANTIC_ANCHORS:
            for theme_name in ("light", "dark"):
                steps = status_scale_steps(THEMES[theme_name], brand)
                for step in (1, 2, 3):
                    with self.subTest(family=family, theme=theme_name, step=step):
                        self.assertLessEqual(
                            steps[f"{family}-{step}"][1], SURFACE_CHROMA_CAP
                        )

    def test_lightness_is_monotonic(self):
        # A very dark brand must not invert the surface ladder: steps 1-3 blend
        # toward the brand at 15%/10%/5%, which can drag step 1 past step 3 in
        # the light theme. Sweep brand lightness across both theme directions.
        for brand_lightness in (0.0, 0.1, 0.5, 1.0):
            brand = (brand_lightness, 0.10, 200.0)
            for theme_name in ("light", "dark"):
                ramp = status_scale_steps(THEMES[theme_name], brand)
                for family in STATUS_FAMILIES:
                    values = [ramp[f"{family}-{i}"][0] for i in range(1, 13)]
                    with self.subTest(
                        brand_lightness=brand_lightness,
                        theme=theme_name,
                        family=family,
                    ):
                        if theme_name == "dark":
                            self.assertEqual(values, sorted(values))
                        else:
                            self.assertEqual(values, sorted(values, reverse=True))


class TestContrastGuarantees(unittest.TestCase):
    def test_aaa_guarantees(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                layers = build_layers(brand)
                report = verify_contrast(layers)
                for theme_name in ("light", "dark"):
                    for pairing, ratio in report[theme_name].items():
                        if pairing.startswith("text-foreground-muted"):
                            continue
                        if pairing.startswith("text-foreground-secondary"):
                            self.assertGreaterEqual(
                                ratio, 4.5, (brand, theme_name, pairing)
                            )
                        elif any(
                            pairing.startswith(f"text-{family}")
                            or pairing.startswith(f"text-on-{family}")
                            for family in STATUS_FAMILIES
                        ):
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
