"""Tests for the Atmos semantic-layer taxonomy (semantic -> global)."""

import unittest

from chroma import SEMANTIC_TO_GLOBAL, STATUS_FAMILIES, build_layers

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


if __name__ == "__main__":
    unittest.main()
