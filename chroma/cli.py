"""CLI entry point for the chroma token engine."""

from __future__ import annotations

import argparse
import sys

from chroma.color import parse_hex, rgb_to_hex
from chroma.serializers import (
    emit_css,
    emit_dtcg,
    emit_figma,
    emit_json,
    emit_less,
    emit_preview,
    emit_sass,
    emit_stylus,
    emit_ts,
    emit_tailwind,
    emit_tailwind_v3,
    serialize_preview,
)
from chroma.tokens import STATUS_FAMILIES, build_layers, verify_contrast


def _report_accent(
    hex_value: str, layers: dict[str, dict[str, dict[str, str]]]
) -> None:
    """Warn + report the on-color and its contrast when vibrancy is preserved.

    A preserved accent is defined as the emitted brand accent matching the
    input hex exactly; when it doesn't, the brand was mid-bright and chroma
    fell back to the lightness-normalized path. The achieved text-on-accent
    ratio is reported against every action state for both themes.
    """
    brand = rgb_to_hex(parse_hex(hex_value))
    preserved = layers["light"]["global"]["accent"] == brand
    if not preserved:
        print(
            "chroma: warning: this brand is mid-bright, so no on-color can clear "
            "WCAG AAA while preserving its vibrancy — fell back to lightness "
            "normalization.",
            file=sys.stderr,
        )
    report = verify_contrast(layers)
    for theme_name, pairings in report.items():
        for state in ("bg-action-primary", "bg-action-hover", "bg-action-active"):
            pairing = f"text-on-accent/{state}"
            ratio = pairings[pairing]
            print(
                f"chroma: [{theme_name}] {pairing}: {ratio:.2f}:1",
                file=sys.stderr,
            )
        for family in STATUS_FAMILIES:
            for state in (family, f"{family}-hover", f"{family}-active"):
                pairing = f"text-on-{family}/{state}"
                ratio = pairings[pairing]
                print(
                    f"chroma: [{theme_name}] {pairing}: {ratio:.2f}:1",
                    file=sys.stderr,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chroma",
        description="Systematic UI CLI Engine: Compile a complete dual-theme semantic token system from one brand color hex.",
    )
    parser.add_argument(
        "hex",
        help="The primary brand hex code to extract hue coordinate from (e.g. 6366f1)",
    )
    parser.add_argument(
        "-o", "--output", help="Output file path instead of writing to stdout"
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=(
            "json",
            "tailwind",
            "tailwind-v3",
            "css",
            "ts",
            "dtcg",
            "figma",
            "sass",
            "less",
            "stylus",
            "preview",
        ),
        default="tailwind",
        help="The configuration file target standard (Default: tailwind)",
    )
    parser.add_argument(
        "--preserve-vibrancy",
        action="store_true",
        help="Lock the brand accent exactly and solve the on-color label for AAA "
        "instead of shifting accent lightness (bright accents get an ultra-dark "
        "chromatic-gray label; mid-bright brands fall back to normalization)",
    )
    args = parser.parse_args(argv)

    try:
        layers = build_layers(args.hex, preserve_vibrancy=args.preserve_vibrancy)
    except ValueError as exc:
        print(f"chroma: error: {exc}", file=sys.stderr)
        return 2

    if args.preserve_vibrancy:
        _report_accent(args.hex, layers)

    if args.format == "json":
        emit_json(
            layers,
            args.hex,
            args.output,
            preserve_vibrancy=args.preserve_vibrancy,
        )
    elif args.format == "css":
        emit_css(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "ts":
        emit_ts(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "dtcg":
        emit_dtcg(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "figma":
        emit_figma(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "sass":
        emit_sass(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "less":
        emit_less(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "stylus":
        emit_stylus(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "tailwind-v3":
        emit_tailwind_v3(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)
    elif args.format == "preview":
        emit_preview(
            layers, args.output, args.hex, preserve_vibrancy=args.preserve_vibrancy
        )
    else:
        emit_tailwind(layers, args.output, preserve_vibrancy=args.preserve_vibrancy)

    # When a theme file is created, also emit a visual preview alongside it.
    if args.output is not None and args.format != "preview":
        from pathlib import Path

        out_path = Path(args.output)
        preview_path = out_path.parent / "preview.html"
        # Avoid overwriting the main output if it is already preview.html
        try:
            is_same = preview_path.resolve() == out_path.resolve()
        except Exception:
            is_same = str(preview_path) == str(out_path)
        if not is_same:
            preview_path.write_text(
                serialize_preview(
                    layers, args.hex, preserve_vibrancy=args.preserve_vibrancy
                )
            )
            print(f"wrote {preview_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
