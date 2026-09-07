"""Tests for the multi-tenant taxonomy registry and the two-tier rename."""

import unittest

from chroma import (
    CANONICAL_SEMANTIC,
    STATUS_FAMILIES,
    TAXONOMIES,
    TAXONOMY_REGISTRY,
    build_layers,
    get_taxonomy,
    sanitize_token,
    semantic_to_global,
)

BRANDS = ("6366f1", "10b981", "ef4444", "f59e0b", "111827")


class TestTaxonomyRegistry(unittest.TestCase):
    def test_registry_has_all_taxonomies(self):
        self.assertEqual(set(TAXONOMY_REGISTRY), set(TAXONOMIES))

    def test_spec_required_fields(self):
        for name in TAXONOMIES:
            with self.subTest(name=name):
                spec = TAXONOMY_REGISTRY[name]
                self.assertTrue(spec.prefix)
                self.assertIn(spec.delimiter, ("-", "."))
                for step in range(1, 13):
                    self.assertTrue(spec.neutral(step))
                    self.assertTrue(spec.brand(step))

    def test_semantic_covers_all_canonical_concepts(self):
        for name in TAXONOMIES:
            spec = TAXONOMY_REGISTRY[name]
            with self.subTest(name=name):
                self.assertEqual(set(spec.semantic), set(CANONICAL_SEMANTIC))

    def test_unknown_taxonomy_raises(self):
        with self.assertRaises(KeyError):
            get_taxonomy("nonexistent")


class TestSanitizeToken(unittest.TestCase):
    def test_repeated_delimiters_collapse(self):
        cases = {
            "a..b": "a.b",
            "a--b": "a-b",
            "a...b": "a.b",
            "a.-b": "a.b",
            "a-.b": "a-b",
            "a..-..b": "a.b",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sanitize_token(raw), expected)

    def test_illegal_chars_removed(self):
        self.assertEqual(sanitize_token("foo bar/baz"), "foobarbaz")
        self.assertEqual(sanitize_token("x#y$z"), "xyz")

    def test_leading_trailing_delimiters_stripped(self):
        self.assertEqual(sanitize_token("-lead"), "lead")
        self.assertEqual(sanitize_token("trail."), "trail")

    def test_well_formed_names_unchanged(self):
        for name in ("neutral-scale-1", "palette.blue.20", "sys-color-on-surface"):
            self.assertEqual(sanitize_token(name), name)


class TestPrimitiveNaming(unittest.TestCase):
    def test_atmos_neutral_brand_scale_names(self):
        spec = TAXONOMY_REGISTRY["atmos"]
        self.assertEqual(spec.neutral(1), "neutral-scale-1")
        self.assertEqual(spec.neutral(12), "neutral-scale-12")
        self.assertEqual(spec.brand(1), "brand-scale-1")
        self.assertEqual(spec.brand(12), "brand-scale-12")

    def test_m3_sequential_primitive_names(self):
        spec = TAXONOMY_REGISTRY["m3"]
        self.assertEqual(spec.neutral(1), "md-ref-palette-neutral-1")
        self.assertEqual(spec.neutral(12), "md-ref-palette-neutral-12")
        self.assertEqual(spec.brand(1), "md-ref-palette-primary-1")
        self.assertEqual(spec.brand(9), "md-ref-palette-primary-9")
        neutral_names = [spec.neutral(n) for n in range(1, 13)]
        self.assertEqual(
            neutral_names,
            [f"md-ref-palette-neutral-{n}" for n in range(1, 13)],
        )
        brand_names = [spec.brand(n) for n in range(1, 13)]
        self.assertEqual(
            brand_names,
            [f"md-ref-palette-primary-{n}" for n in range(1, 13)],
        )

    def test_padded_hundreds_taxonomies(self):
        atlassian = TAXONOMY_REGISTRY["atlassian"]
        self.assertEqual(atlassian.neutral(2), "palette.neutral.20")
        self.assertEqual(atlassian.brand(12), "palette.blue.120")
        spectrum = TAXONOMY_REGISTRY["spectrum"]
        self.assertEqual(spectrum.neutral(2), "gray-200")
        self.assertEqual(spectrum.brand(12), "blue-1200")

    def test_slds_primitives(self):
        slds = TAXONOMY_REGISTRY["slds"]
        self.assertEqual(slds.neutral(1), "primitive-color-neutral-1")
        self.assertEqual(slds.brand(9), "primitive-color-brand-9")


class TestSemanticAnchors(unittest.TestCase):
    def test_exact_registry_anchors(self):
        anchors = {
            "atmos": {
                "root": "bg-surface-root",
                "default": "bg-surface-default",
                "text": "text-foreground-primary",
                "action": "bg-action-primary",
            },
            "m3": {
                "root": "sys-color-surface-container-lowest",
                "default": "sys-color-surface-container-low",
                "text": "sys-color-on-surface",
                "action": "sys-color-primary",
            },
            "atlassian": {
                "root": "background.sunken",
                "default": "background.elevation.surface",
                "text": "text.default",
                "action": "background.selected.bold",
            },
            "slds": {
                "root": "color-neutral-base-10",
                "default": "color-neutral-base-20",
                "text": "color-neutral-base-95",
                "action": "color-brand-base-50",
            },
            "spectrum": {
                "root": "core-color-background-layer-lowest",
                "default": "core-color-background-layer-low",
                "text": "core-color-content-primary",
                "action": "core-color-background-accent-high",
            },
        }
        for taxonomy, mapping in anchors.items():
            with self.subTest(taxonomy=taxonomy):
                spec = TAXONOMY_REGISTRY[taxonomy]
                self.assertEqual(spec.semantic["bg-surface-root"], mapping["root"])
                self.assertEqual(
                    spec.semantic["bg-surface-default"], mapping["default"]
                )
                self.assertEqual(
                    spec.semantic["text-foreground-primary"], mapping["text"]
                )
                self.assertEqual(spec.semantic["bg-action-primary"], mapping["action"])


class TestTwoTierLayers(unittest.TestCase):
    def test_semantic_values_match_alias_sources(self):
        for taxonomy in TAXONOMIES:
            layers = build_layers("6366f1", taxonomy=taxonomy)
            aliases = semantic_to_global(taxonomy)
            for theme_name in ("light", "dark"):
                with self.subTest(taxonomy=taxonomy, theme=theme_name):
                    semantic = layers[theme_name]["semantic"]
                    global_tokens = layers[theme_name]["global"]
                    for semantic_name, global_name in aliases.items():
                        self.assertEqual(
                            semantic[semantic_name],
                            global_tokens[global_name],
                            (semantic_name, global_name),
                        )

    def test_overlay_is_literal_not_alias(self):
        for taxonomy in TAXONOMIES:
            layers = build_layers("6366f1", taxonomy=taxonomy)
            spec = TAXONOMY_REGISTRY[taxonomy]
            overlay_name = spec.semantic["bg-surface-overlay"]
            with self.subTest(taxonomy=taxonomy):
                self.assertNotIn(overlay_name, semantic_to_global(taxonomy))
                for theme_name in ("light", "dark"):
                    value = layers[theme_name]["semantic"][overlay_name]
                    self.assertTrue(value.startswith("#"))

    def test_m3_output_has_no_tonal_tokens(self):
        layers = build_layers("6366f1", taxonomy="m3")
        old_tokens = {
            "ref-palette-neutral10",
            "ref-palette-neutral12",
            "ref-palette-neutral22",
            "ref-palette-neutral26",
            "ref-palette-neutral30",
            "ref-palette-neutral33",
            "ref-palette-neutral36",
            "ref-palette-neutral38",
            "ref-palette-neutral40",
            "ref-palette-neutral60",
            "ref-palette-neutral80",
            "ref-palette-neutral95",
            "ref-palette-primary40",
        }
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                global_keys = set(layers[theme_name]["global"])
                self.assertFalse(old_tokens & global_keys)
                self.assertIn("md-ref-palette-neutral-1", global_keys)
                self.assertIn("md-ref-palette-neutral-12", global_keys)
                self.assertIn("md-ref-palette-primary-9", global_keys)

    def test_text_disabled_matches_structural_borders(self):
        for brand in BRANDS:
            layers = build_layers(brand)
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    semantic = layers[theme_name]["semantic"]
                    self.assertEqual(
                        semantic["text-foreground-disabled"],
                        semantic["border-strong"],
                    )

    def test_text_on_accent_matches_accent_on(self):
        for brand in BRANDS:
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    body = build_layers(brand)[theme_name]
                    self.assertEqual(
                        body["semantic"]["text-on-accent"],
                        body["global"]["accent-on"],
                    )

    def test_status_tokens_resolve_to_global_sources(self):
        for brand in BRANDS:
            layers = build_layers(brand)
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    global_tokens = layers[theme_name]["global"]
                    semantic = layers[theme_name]["semantic"]
                    for family in STATUS_FAMILIES:
                        self.assertEqual(
                            semantic[f"bg-{family}-subtle"],
                            global_tokens[f"{family}-2"],
                        )
                        self.assertEqual(
                            semantic[f"bg-{family}-strong"], global_tokens[family]
                        )
                        self.assertEqual(
                            semantic[f"border-{family}"],
                            global_tokens[f"{family}-6"],
                        )
                        self.assertEqual(
                            semantic[f"text-{family}"], global_tokens[f"{family}-11"]
                        )
                        self.assertEqual(
                            semantic[f"text-on-{family}"],
                            global_tokens[f"{family}-on"],
                        )

    def test_semantic_to_global_constant_resolves(self):
        from chroma import SEMANTIC_TO_GLOBAL

        layers = build_layers("6366f1")
        for theme_name in ("light", "dark"):
            semantic = layers[theme_name]["semantic"]
            global_tokens = layers[theme_name]["global"]
            for semantic_name, global_name in SEMANTIC_TO_GLOBAL.items():
                self.assertEqual(semantic[semantic_name], global_tokens[global_name])

    def test_non_atmos_semantic_names_unique(self):
        for taxonomy in TAXONOMIES:
            layers = build_layers("6366f1", taxonomy=taxonomy)
            for theme_name in ("light", "dark"):
                with self.subTest(taxonomy=taxonomy, theme=theme_name):
                    semantic = layers[theme_name]["semantic"]
                    self.assertEqual(len(semantic), len(set(semantic)))


if __name__ == "__main__":
    unittest.main()
