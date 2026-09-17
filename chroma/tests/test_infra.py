"""Consistency checks across the project harness (pyproject, Makefile, CI)."""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    path = ROOT / relpath
    assert path.exists(), f"{relpath} does not exist"
    return path.read_text()


class TestInfra(unittest.TestCase):
    def test_requires_python_floor_is_in_ci_matrix(self):
        pyproject = _read("pyproject.toml")
        match = re.search(r'requires-python\s*=\s*">=([0-9.]+)"', pyproject)
        self.assertIsNotNone(match, "requires-python floor not found in pyproject.toml")
        floor = match.group(1)
        ci = _read(".github/workflows/ci.yml")
        self.assertIn(
            f'"{floor}"', ci, f"CI matrix does not cover requires-python {floor}"
        )

    def test_ci_runs_same_gates_as_make_check(self):
        ci = _read(".github/workflows/ci.yml")
        for step in (
            "ruff check chroma/",
            "ruff format --check chroma/",
            "pyright chroma/",
            "unittest discover",
        ):
            self.assertIn(step, ci, f"CI is missing gate: {step}")

    def test_make_check_target_covers_all_gates(self):
        makefile = _read("Makefile")
        match = re.search(r"^check:(.*)$", makefile, re.MULTILINE)
        self.assertIsNotNone(match, "check target not found in Makefile")
        prerequisites = match.group(1)
        for gate in ("lint", "format", "typecheck", "test"):
            self.assertIn(gate, prerequisites, f"check target is missing gate: {gate}")

    def test_hatch_version_source_matches_package(self):
        pyproject = _read("pyproject.toml")
        match = re.search(
            r"\[tool\.hatch\.version\]\s*\n\s*path\s*=\s*\"([^\"]+)\"", pyproject
        )
        self.assertIsNotNone(match, "hatch version path not found in pyproject.toml")
        source = ROOT / match.group(1)
        self.assertTrue(
            source.exists(), f"version source {match.group(1)} does not exist"
        )
        version = re.search(r'__version__\s*=\s*"([^"]+)"', source.read_text())
        self.assertIsNotNone(version, f"__version__ not found in {match.group(1)}")
        self.assertRegex(version.group(1), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
