"""Tests for the css / ts / dtcg / sass / less / stylus output formats and the committed samples."""

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
    serialize_figma_mode,
    serialize_json,
    serialize_less,
    serialize_sass,
    serialize_stylus,
    serialize_tailwind_v3_config,
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
                self.assertEqual(
                    set(payload[theme_name]["bg"]),
                    {"surface", "action", "success", "warning", "danger", "info"},
                )
                self.assertEqual(
                    set(payload[theme_name]["border"]),
                    {
                        "subtle",
                        "default",
                        "strong",
                        "success",
                        "warning",
                        "danger",
                        "info",
                    },
                )
                for family in ("success", "warning", "danger", "info"):
                    with self.subTest(family=family):
                        self.assertEqual(
                            set(payload[theme_name]["bg"][family]),
                            {"subtle", "strong"},
                        )


class TestTailwindV3Format(unittest.TestCase):
    def test_v3_config_to_stdout(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "tailwind-v3"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("module.exports = {", text)
        self.assertIn("darkMode: 'class'", text)
        self.assertIn("colors: {", text)
        self.assertIn("// actions - brand execution buttons", text)
        self.assertIn("surface: {", text)
        self.assertIn("foreground: {", text)
        self.assertIn("border: {", text)
        self.assertIn("on: {", text)

    def test_v3_writes_config_and_companion(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tailwind.config.js"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "tailwind-v3", "-o", str(target)])
            self.assertEqual(code, 0)
            config = target.read_text()
            self.assertIn("module.exports = {", config)
            self.assertIn("darkMode: 'class'", config)
            companion = target.with_suffix(".css")
            self.assertTrue(companion.exists())
            self.assertEqual(companion.read_text(), serialize_css(build_layers(BRAND)))
            self.assertIn("wrote", err.getvalue())


class TestFigmaFormat(unittest.TestCase):
    def test_figma_stdout_is_single_mode(self):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([BRAND, "-f", "figma"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertNotIn("light", payload)
        self.assertNotIn("dark", payload)
        root = payload["bg"]["surface"]["root"]
        self.assertEqual(root["$type"], "color")
        self.assertRegex(root["$value"], r"^#[0-9a-f]{6}$")
        self.assertIn("$description", root)
        self.assertIn("dark mode not shown on stdout", err.getvalue())

    def test_figma_writes_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.json"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "figma", "-o", str(target)])
            self.assertEqual(code, 0)
            light = json.loads((Path(tmp) / "theme.light.json").read_text())
            dark = json.loads((Path(tmp) / "theme.dark.json").read_text())
            self.assertEqual(set(light), set(dark))
            self.assertIn("wrote", err.getvalue())
            self.assertIn("theme.light.json", err.getvalue())
            self.assertIn("theme.dark.json", err.getvalue())

    def test_figma_mode_values_match_layers(self):
        layers = build_layers(BRAND)
        for theme_name in ("light", "dark"):
            with self.subTest(theme=theme_name):
                payload = json.loads(serialize_figma_mode(layers, theme_name))
                self.assertEqual(
                    _count_token_leaves(payload), len(layers[theme_name]["semantic"])
                )
                self.assertEqual(
                    payload["bg"]["surface"]["root"]["$value"],
                    layers[theme_name]["semantic"]["bg-surface-root"],
                )
                self.assertEqual(
                    payload["text"]["on"]["accent"]["$value"],
                    layers[theme_name]["semantic"]["text-on-accent"],
                )

    def test_figma_dark_differs_from_light(self):
        layers = build_layers(BRAND)
        light = json.loads(serialize_figma_mode(layers, "light"))
        dark = json.loads(serialize_figma_mode(layers, "dark"))
        self.assertNotEqual(
            light["bg"]["surface"]["root"]["$value"],
            dark["bg"]["surface"]["root"]["$value"],
        )


class TestSassFormat(unittest.TestCase):
    def test_sass_stdout_structure(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "sass"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("$chroma-theme: (", text)
        self.assertIn("  light: (", text)
        self.assertIn("  dark: (", text)
        self.assertIn("// The 12-Step Mathematical Gray Ramp", text)
        self.assertIn("// Semantic Structural Mapping Matrix", text)
        self.assertIn("step-1: #fbfcfe,", text)
        self.assertIn("bg-surface-root: #fbfcfe,", text)

    def test_sass_values_match_layers(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "sass"])
        text = out.getvalue()
        layers = build_layers(BRAND)
        for theme_name in ("light", "dark"):
            for token, value in layers[theme_name]["semantic"].items():
                with self.subTest(theme=theme_name, token=token):
                    self.assertIn(f"{token}: {value},", text)

    def test_sass_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.scss"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "sass", "-o", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("$chroma-theme: (", target.read_text())
            self.assertIn("wrote", err.getvalue())


class TestLessFormat(unittest.TestCase):
    def test_less_stdout_structure(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "less"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("@chroma-theme: {", text)
        self.assertIn("  @light: {", text)
        self.assertIn("  @dark: {", text)
        self.assertIn("// Semantic Structural Mapping Matrix", text)
        self.assertIn("@step-1: #fbfcfe;", text)
        self.assertIn("@bg-surface-root: #fbfcfe;", text)

    def test_less_values_match_layers(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "less"])
        text = out.getvalue()
        layers = build_layers(BRAND)
        for theme_name in ("light", "dark"):
            for token, value in layers[theme_name]["semantic"].items():
                with self.subTest(theme=theme_name, token=token):
                    self.assertIn(f"@{token}: {value};", text)

    def test_less_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.less"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "less", "-o", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("@chroma-theme: {", target.read_text())
            self.assertIn("wrote", err.getvalue())


class TestStylusFormat(unittest.TestCase):
    def test_stylus_stdout_structure(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([BRAND, "-f", "stylus"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("chroma-theme = {", text)
        self.assertIn("  light: {", text)
        self.assertIn("  dark: {", text)
        self.assertIn("// Semantic Structural Mapping Matrix", text)
        self.assertIn("'step-1': #fbfcfe,", text)
        self.assertIn("'bg-surface-root': #fbfcfe,", text)

    def test_stylus_values_match_layers(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "stylus"])
        text = out.getvalue()
        layers = build_layers(BRAND)
        for theme_name in ("light", "dark"):
            for token, value in layers[theme_name]["semantic"].items():
                with self.subTest(theme=theme_name, token=token):
                    self.assertIn(f"'{token}': {value},", text)

    def test_stylus_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.styl"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main([BRAND, "-f", "stylus", "-o", str(target)])
            self.assertEqual(code, 0)
            self.assertIn("chroma-theme = {", target.read_text())
            self.assertIn("wrote", err.getvalue())


class TestStatusFormats(unittest.TestCase):
    def test_css_emits_status_ramp_and_semantics(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "css"])
        text = out.getvalue()
        layers = build_layers(BRAND)
        light = layers["light"]
        self.assertIn("/* The Four Semantic Status Coordinates */", text)
        self.assertIn("/* Brand Shade Scale", text)
        self.assertIn("/* Status Shade Scales", text)
        for family in ("success", "warning", "danger", "info"):
            with self.subTest(family=family):
                self.assertIn(f"--{family}: {light['global'][family]};", text)
                self.assertIn(f"--bg-{family}-subtle: var(--{family}-2);", text)
                self.assertIn(f"--border-{family}: var(--{family}-6);", text)
                self.assertIn(f"--text-{family}: var(--{family}-11);", text)
                self.assertIn(f"--bg-{family}-strong: var(--{family});", text)

    def test_tailwind_exposes_status_groups(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND])
        text = out.getvalue()
        for family in ("success", "warning", "danger", "info"):
            with self.subTest(family=family):
                self.assertIn(
                    f"--color-surface-{family}-subtle: var(--bg-{family}-subtle);",
                    text,
                )
                self.assertIn(
                    f"--color-foreground-{family}: var(--text-{family});", text
                )
                self.assertIn(f"--color-border-{family}: var(--border-{family});", text)
                self.assertIn(f"--color-on-{family}: var(--text-on-{family});", text)

    def test_ts_emits_status_keys(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "ts"])
        text = out.getvalue()
        layers = build_layers(BRAND)
        for family in ("success", "warning", "danger", "info"):
            with self.subTest(family=family):
                self.assertIn(f"bg{family.capitalize()}Subtle:", text)
                self.assertIn(f"bg{family.capitalize()}Strong:", text)
                self.assertIn(f"border{family.capitalize()}:", text)
                self.assertIn(f"text{family.capitalize()}:", text)
                self.assertIn(f"textOn{family.capitalize()}:", text)
                self.assertIn(
                    f"bg{family.capitalize()}Subtle: "
                    f"'{layers['light']['semantic'][f'bg-{family}-subtle']}',",
                    text,
                )

    def test_dtcg_status_tree_nests_cleanly(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "dtcg"])
        payload = json.loads(out.getvalue())
        for theme_name in ("light", "dark"):
            for family in ("success", "warning", "danger", "info"):
                with self.subTest(theme=theme_name, family=family):
                    self.assertEqual(
                        set(payload[theme_name]["bg"][family]), {"subtle", "strong"}
                    )
                    self.assertIn("$value", payload[theme_name]["text"][family])
                    self.assertIn("$value", payload[theme_name]["text"]["on"][family])

    def test_sass_emits_status_section(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([BRAND, "-f", "sass"])
        text = out.getvalue()
        self.assertIn("// The Four Semantic Status Coordinates", text)
        layers = build_layers(BRAND)
        for family in ("success", "warning", "danger", "info"):
            with self.subTest(family=family):
                self.assertIn(f"{family}: {layers['light']['global'][family]},", text)


class TestSampleSync(unittest.TestCase):
    def _expected_samples(self):
        layers = build_layers(BRAND)
        yield "tailwind-v4.css", serialize_tailwind_v4_css(layers)
        yield "tailwind-v3.js", serialize_tailwind_v3_config()
        yield "theme.css", serialize_css(layers)
        yield "theme.ts", serialize_ts(layers)
        yield "theme.dtcg.json", serialize_dtcg(layers)
        yield "figma.light.json", serialize_figma_mode(layers, "light")
        yield "figma.dark.json", serialize_figma_mode(layers, "dark")
        yield "tokens.json", serialize_json(layers, BRAND)
        yield "theme.scss", serialize_sass(layers)
        yield "theme.less", serialize_less(layers)
        yield "theme.styl", serialize_stylus(layers)

    def test_samples_up_to_date(self):
        root = Path(__file__).resolve().parents[2]
        for filename, expected in self._expected_samples():
            with self.subTest(filename=filename):
                self.assertEqual((root / "samples" / filename).read_text(), expected)


if __name__ == "__main__":
    unittest.main()
