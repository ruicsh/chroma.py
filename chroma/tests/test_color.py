"""Tests for the OKLCH color engine (conversion + WCAG math)."""

import unittest
from typing import cast

from chroma.color import (
    contrast_ratio,
    hsl_to_rgb,
    oklch_to_rgb,
    parse_hex,
    relative_luminance,
    rgb_to_hex,
    rgb_to_hsl,
    rgb_to_oklch,
)


def assert_rgb_approx(test, actual, expected, abs_tol=1e-6):
    test.assertEqual(len(actual), 3)
    for got, want in zip(actual, expected):
        test.assertAlmostEqual(got, want, delta=abs_tol)


class TestParseHex(unittest.TestCase):
    def test_valid_forms(self):
        cases = {
            "6366f1": (0x63 / 255, 0x66 / 255, 0xF1 / 255),
            "#6366f1": (0x63 / 255, 0x66 / 255, 0xF1 / 255),
            "639": (0x66 / 255, 0x33 / 255, 0x99 / 255),
            "#639": (0x66 / 255, 0x33 / 255, 0x99 / 255),
            "000000": (0.0, 0.0, 0.0),
            "FFFFFF": (1.0, 1.0, 1.0),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                assert_rgb_approx(self, parse_hex(value), expected)

    def test_rejects_invalid(self):
        for value in ("", "#", "12345", "1234567", "gggggg", "12g", "12"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_hex(value)
        # Non-string input (e.g. None) is rejected by the same guard.
        with self.assertRaises(ValueError):
            parse_hex(cast(str, None))

    def test_rgb_to_hex_roundtrip_and_case(self):
        self.assertEqual(rgb_to_hex(parse_hex("10B981")), "#10b981")
        self.assertEqual(rgb_to_hex((1.0, 1.0, 1.0)), "#ffffff")


class TestHSL(unittest.TestCase):
    def test_known_value(self):
        hue, sat, light = rgb_to_hsl(parse_hex("6366f1"))
        self.assertAlmostEqual(hue, 239.0, delta=1.0)
        self.assertTrue(0.0 <= sat <= 1.0)
        self.assertTrue(0.0 <= light <= 1.0)

    def test_roundtrip(self):
        for rgb in (
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 1, 0),
            (0.5, 0.5, 0.5),
            (0.9, 0.2, 0.7),
        ):
            with self.subTest(rgb=rgb):
                assert_rgb_approx(self, hsl_to_rgb(rgb_to_hsl(rgb)), rgb, abs_tol=1e-9)

    def test_gray_has_zero_saturation(self):
        hue, sat, _ = rgb_to_hsl((0.5, 0.5, 0.5))
        self.assertEqual(sat, 0.0)
        self.assertEqual(hue, 0.0)


class TestOKLCH(unittest.TestCase):
    def test_achromatic_chroma_zero(self):
        _, chroma_val, _ = rgb_to_oklch((0.5, 0.5, 0.5))
        self.assertAlmostEqual(chroma_val, 0.0, delta=1e-6)

    def test_hue_bounds(self):
        for value in ("6366f1", "10b981", "ef4444", "f59e0b", "06b6d4"):
            with self.subTest(value=value):
                _, _, hue = rgb_to_oklch(parse_hex(value))
                self.assertTrue(0.0 <= hue < 360.0)

    def test_roundtrip(self):
        for rgb in (
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 1, 1),
            (0, 0, 0),
            (0.63, 0.4, 0.945),
            (0.5, 0.5, 0.5),
            (0.05, 0.3, 0.6),
        ):
            with self.subTest(rgb=rgb):
                assert_rgb_approx(
                    self, oklch_to_rgb(rgb_to_oklch(rgb)), rgb, abs_tol=0.001
                )

    def test_to_rgb_clamps_gamut(self):
        rgb = oklch_to_rgb((0.7, 0.4, 200.0))
        for channel in rgb:
            self.assertGreaterEqual(channel, -1e-9)
            self.assertLessEqual(channel, 1.0 + 1e-9)


class TestContrast(unittest.TestCase):
    def test_luminance_extremes(self):
        self.assertAlmostEqual(relative_luminance((0, 0, 0)), 0.0, delta=1e-12)
        self.assertAlmostEqual(relative_luminance((1, 1, 1)), 1.0, delta=1e-12)

    def test_contrast_extremes(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (1, 1, 1)), 21.0, delta=1e-6)
        self.assertAlmostEqual(
            contrast_ratio((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)), 1.0, delta=1e-6
        )

    def test_contrast_is_symmetric(self):
        white = (1, 1, 1)
        dark = (0.1, 0.1, 0.1)
        self.assertAlmostEqual(contrast_ratio(white, dark), contrast_ratio(dark, white))

    def test_parse_and_contrast_black_white(self):
        self.assertAlmostEqual(
            contrast_ratio(parse_hex("000000"), parse_hex("ffffff")), 21.0, delta=1e-6
        )


if __name__ == "__main__":
    unittest.main()
