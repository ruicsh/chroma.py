"""Tests for the Atmos semantic-layer taxonomy (semantic -> global)."""

import unittest

from chroma import SEMANTIC_TO_GLOBAL, build_layers

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


if __name__ == "__main__":
    unittest.main()
