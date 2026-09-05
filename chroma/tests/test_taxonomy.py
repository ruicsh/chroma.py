"""Tests for the Atmos three-tier token taxonomy (global -> semantic -> component)."""

import unittest

from chroma import COMPONENT_TO_SEMANTIC, SEMANTIC_TO_GLOBAL, build_layers

BRANDS = ("6366f1", "10b981", "ef4444", "f59e0b", "111827")


class TestSemanticToGlobal(unittest.TestCase):
    def test_semantic_tokens_resolve_to_exact_global_sources(self):
        for brand in BRANDS:
            layers = build_layers(brand)
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    for semantic_token, global_token in SEMANTIC_TO_GLOBAL.items():
                        self.assertEqual(
                            layers[theme_name]["semantic"][semantic_token],
                            layers[theme_name]["global"][global_token],
                            (semantic_token, global_token),
                        )

    def test_text_disabled_matches_structural_borders(self):
        for brand in BRANDS:
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    semantic = build_layers(brand)[theme_name]["semantic"]
                    self.assertEqual(
                        semantic["text-disabled"], semantic["border-strong"]
                    )

    def test_text_on_accent_matches_accent_on(self):
        for brand in BRANDS:
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    body = build_layers(brand)[theme_name]
                    self.assertEqual(
                        body["semantic"]["text-on-accent"], body["global"]["accent-on"]
                    )


class TestComponentToSemantic(unittest.TestCase):
    def test_component_tokens_resolve_to_exact_semantic_sources(self):
        for brand in BRANDS:
            layers = build_layers(brand)
            for theme_name in ("light", "dark"):
                with self.subTest(brand=brand, theme=theme_name):
                    for (
                        component_token,
                        semantic_token,
                    ) in COMPONENT_TO_SEMANTIC.items():
                        self.assertEqual(
                            layers[theme_name]["component"][component_token],
                            layers[theme_name]["semantic"][semantic_token],
                            (component_token, semantic_token),
                        )

    def test_grid_value_is_primary_text(self):
        for brand in BRANDS:
            with self.subTest(brand=brand):
                body = build_layers(brand)["light"]
                self.assertEqual(
                    body["component"]["text-grid-value"],
                    body["semantic"]["text-primary"],
                )
                self.assertEqual(
                    body["component"]["text-btn-primary-glyph"],
                    body["semantic"]["text-on-accent"],
                )


if __name__ == "__main__":
    unittest.main()
