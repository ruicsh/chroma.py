"""Tests for the CLI and serializers."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from chroma.cli import main


class TestCLI(unittest.TestCase):
    def test_json_to_stdout(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["6366f1", "-f", "json"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["meta"]["input"], "6366f1")
        self.assertEqual(set(payload["meta"]["themes"]), {"light", "dark"})
        self.assertEqual(
            set(payload["meta"]["layers"]), {"global", "semantic", "component"}
        )
        for layer in ("global", "semantic", "component"):
            self.assertIn("light", payload[layer])
            self.assertIn("dark", payload[layer])
        self.assertIn("oklch", payload)
        self.assertIn("bg-surface-root", payload["semantic"]["light"])
        self.assertIn("bg-grid-header", payload["component"]["light"])
        self.assertIn("step-12", payload["global"]["light"])

    def test_json_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "branding-tokens.json"
            err = io.StringIO()
            with redirect_stderr(err):
                code = main(["10b981", "-f", "json", "-o", str(target)])
            self.assertEqual(code, 0)
            payload = json.loads(target.read_text())
            self.assertEqual(
                payload["semantic"]["light"]["bg-action-primary"], "#10b981"
            )
            self.assertIn("wrote", err.getvalue())

    def test_tailwind_default_is_v4_css(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["6366f1"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("@import 'tailwindcss';", text)
        self.assertIn("@theme inline", text)
        self.assertIn("@custom-variant dark", text)
        self.assertIn(".dark {", text)
        self.assertIn("--color-surface-root: var(--bg-surface-root);", text)
        self.assertIn("--color-foreground-primary: var(--text-primary);", text)
        self.assertIn("--bg-surface-root: var(--step-1);", text)
        self.assertIn("--bg-grid-header: var(--bg-surface-subtle);", text)

    def test_tailwind_v4_css_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.css"
            code = main(["6366f1", "-o", str(target)])
            self.assertEqual(code, 0)
            css = target.read_text()
            self.assertIn("@theme inline", css)
            self.assertIn(":root {", css)
            self.assertIn(".dark {", css)
            self.assertIn("--bg-surface-overlay: #ffffff;", css)

    def test_tailwind_v3_config_and_companion(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tailwind.config.js"
            code = main(["6366f1", "-o", str(target)])
            self.assertEqual(code, 0)
            config = target.read_text()
            companion = target.with_suffix(".css")
            self.assertTrue(companion.exists())
            css = companion.read_text()
            self.assertIn("module.exports", config)
            self.assertIn("darkMode: 'class'", config)
            self.assertIn("surface: { root: 'var(--bg-surface-root)'", config)
            self.assertIn("foreground: { primary: 'var(--text-primary)'", config)
            self.assertIn("action: { primary: 'var(--bg-action-primary)'", config)
            self.assertIn("grid: { header: 'var(--bg-grid-header)'", config)
            self.assertIn(":root {", css)
            self.assertIn(".dark {", css)
            self.assertIn("--accent: #d7e8ff;", css)
            self.assertIn("--bg-surface-root: var(--step-1);", css)

    def test_tailwind_unknown_extension_becomes_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "branding"  # no extension
            code = main(["6366f1", "-o", str(target)])
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "branding.js").exists())
            self.assertTrue((Path(tmp) / "branding.css").exists())

    def test_invalid_hex_exits_2(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["notacolor"])
        self.assertEqual(code, 2)
        self.assertIn("error", err.getvalue().lower())

    def test_help_exits_zero(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(out):
                main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("usage:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
