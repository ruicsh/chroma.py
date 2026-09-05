"""Tests for the project harness (mirrors payday's infra checks)."""

import pathlib
import unittest


class TestInfra(unittest.TestCase):
    def test_pyproject_toml_exists(self):
        path = pathlib.Path("pyproject.toml")
        self.assertTrue(path.exists(), "pyproject.toml does not exist")

    def test_pyproject_toml_requires_python_310(self):
        content = pathlib.Path("pyproject.toml").read_text()
        self.assertIn('requires-python = ">=3.10"', content)

    def test_makefile_present(self):
        self.assertTrue(pathlib.Path("Makefile").exists())

    def test_ci_workflow_present(self):
        path = pathlib.Path(".github/workflows/ci.yml")
        self.assertTrue(path.exists(), "ci.yml does not exist")


if __name__ == "__main__":
    unittest.main()
