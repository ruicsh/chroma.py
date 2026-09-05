"""Tests for the css / ts / dtcg output formats and the committed samples."""

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from chroma import build_layers
from chroma.cli import main
from chroma.serializers import (
    serialize_css,
    serialize_dtcg,
    serialize_json,
    serialize_tailwind_v4_css,
    serialize_ts,
)

BRAND = "6366f1"


def camel(token: str) -> str:
    """Mirror the serializer's kebab -> camelCase mapping for assertions."""
    head, *tail = token.split("-")
    return head + "".join(part.capitalize() for part in tail)


def _semantic_camel_keys() -> set[str]:
    return {camel(name) for name in build_layers(BRAND)["light"]["semantic"]}


def _count_token_leaves(node: dict) -> int:
    if "$value" in node:
        return 1
    return sum(
        _count_token_leaves(child) for child in node.values() if isinstance(child, dict)
    )


class TestCssFormat(unittest.TestCase):
    def test_css_to_stdout_is_vanilla(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "css"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertNotIn("@import", text)
        self.assertNotIn("@theme", text)
        self.assertNotIn("@custom-variant", text)
        self.assertIn(":root {", text)
        self.assertIn(".dark {", text)
        light_step_1 = build_layers(BRAND)["light"]["global"]["step-1"]
        self.assertIn(f"--step-1: {light_step_1};", text)
        self.assertIn("--bg-surface-root: var(--step-1);", text)

    def test_css_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.css"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "css", "-o", str(target)])
            self.assertEqual(code, 0)
            text = target.read_text()
            self.assertNotIn("@theme", text)
            self.assertIn(":root {", text)
            self.assertIn(".dark {", text)
            self.assertIn("wrote", err.getvalue())


class TestTsFormat(unittest.TestCase):
    def test_ts_to_file_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.ts"
            code = main([BRAND, "-f", "ts", "-o", str(target)])
            self.assertEqual(code, 0)
            text = target.read_text()
            self.assertIn("export const chromaTheme = {", text)
            self.assertIn("} as const;", text)
            self.assertIn("export type ChromaTheme = typeof chromaTheme;", text)
            self.assertIn("bgSurfaceRoot:", text)

    def test_ts_value_equality_matrix(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "ts"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        dark = text.split("dark: {", 1)[1]
        match = re.search(r"bgSurfaceRoot: '#([0-9a-f]{6})'", dark)
        self.assertIsNotNone(match)
        assert match is not None
        ts_hex = "#" + match.group(1)
        expected = build_layers(BRAND)["dark"]["semantic"]["bg-surface-root"]
        self.assertEqual(ts_hex, expected)
        # The Tailwind sheet resolves --color-surface-root -> --bg-surface-root
        # -> --step-1, so the dark terminal hex must match the TS value exactly.
        tw_out = io.StringIO()
        with redirect_stdout(tw_out):
            code = main([BRAND])
        self.assertEqual(code, 0)
        dark_tw = tw_out.getvalue().split(".dark {", 1)[1]
        step = re.search(r"--step-1: (#[0-9a-f]{6});", dark_tw)
        self.assertIsNotNone(step)
        assert step is not None
        self.assertEqual(step.group(1), expected)

    def test_ts_keys_are_semantic_only(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "ts"])
        keys = set(re.findall(r"^    ([a-zA-Z][a-zA-Z0-9]*): ", out.getvalue(), re.M))
        self.assertEqual(keys, _semantic_camel_keys())


class TestDtcgFormat(unittest.TestCase):
    def test_dtcg_json_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.dtcg.json"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "dtcg", "-o", str(target)])
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text())
            self.assertEqual(set(payload), {"light", "dark"})
            root = payload["light"]["bg"]["surface"]["root"]
            self.assertEqual(root["$type"], "color")
            self.assertRegex(root["$value"], r"^#[0-9a-f]{6}$")
            self.assertIn("$description", root)
            self.assertIn("wrote", err.getvalue())
            semantic_count = len(build_layers(BRAND)["light"]["semantic"])
            for theme_name in ("light", "dark"):
                with self.subTest(theme=theme_name):
                    self.assertEqual(
                        _count_token_leaves(payload[theme_name]), semantic_count
                    )

    def test_dtcg_stdout_parses(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "dtcg"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertIn("bg", payload["dark"])

    def test_dtcg_tree_has_exact_semantic_domains(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "dtcg"])
        payload = json.loads(out.getvalue())
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                self.assertEqual(set(payload[theme_name]["bg"]), {"surface", "action"})
                self.assertEqual(
                    set(payload[theme_name]["border"]), {"subtle", "default", "strong"}
                )


class TestSampleSync(unittest.TestCase):
    def _expected_samples(self):
        layers = build_layers(BRAND)
        yield "tailwind-v4.css", serialize_tailwind_v4_css(layers)
        yield "chroma.css", serialize_css(layers)
        yield "chroma-theme.ts", serialize_ts(layers)
        yield "chroma-theme.dtcg.json", serialize_dtcg(layers)
        yield "chroma-tokens.json", serialize_json(layers, BRAND)

    def test_samples_up_to_date(self):
        root = Path(__file__).resolve().parents[2]
        for filename, expected in self._expected_samples():
            with self.subTest(filename=filename):
                self.assertEqual((root / "samples" / filename).read_text(), expected)


if __name__ == "__main__":
    unittest.main()
