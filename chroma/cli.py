"""CLI entry point for the chroma token engine."""

from __future__ import annotations

import argparse
import sys

from chroma.color import parse_hex, rgb_to_hex
from chroma.serializers import FORMATS, emit, serialize_preview, write_output
from chroma.taxonomy import STATUS_FAMILIES, TAXONOMIES, get_taxonomy
from chroma.tokens import build_layers, verify_contrast


def _report_accent(
    hex_value: str,
    layers: dict[str, dict[str, dict[str, str]]],
    taxonomy: str = "atmos",
) -> None:
    """Warn + report the on-color and its contrast when vibrancy is preserved.

    A preserved accent is defined as the emitted brand accent matching the
    input hex exactly; when it doesn't, the brand was mid-bright and chroma
    fell back to the lightness-normalized path. The achieved text-on-accent
    ratio is reported against every action state for both themes.
    """
    spec = get_taxonomy(taxonomy)
    brand = rgb_to_hex(parse_hex(hex_value))
    preserved = layers["light"]["global"][spec.global_primitive("accent")] == brand
    if not preserved:
        print(
            "chroma: warning: this brand is mid-bright, so no on-color can clear "
            "WCAG AAA while preserving its vibrancy — fell back to lightness "
            "normalization.",
            file=sys.stderr,
        )
    report = verify_contrast(layers, taxonomy)
    action_states = ("bg-action-primary", "bg-action-hover", "bg-action-active")
    on_accent = spec.semantic_name("text-on-accent")
    for theme_name, pairings in report.items():
        for state in action_states:
            pairing = f"{on_accent}/{spec.semantic_name(state)}"
            ratio = pairings[pairing]
            print(
                f"chroma: [{theme_name}] {pairing}: {ratio:.2f}:1",
                file=sys.stderr,
            )
        for family in STATUS_FAMILIES:
            for state in (family, f"{family}-hover", f"{family}-active"):
                pairing = (
                    f"{spec.semantic_name(f'text-on-{family}')}/"
                    f"{spec.global_primitive(state)}"
                )
                ratio = pairings[pairing]
                print(
                    f"chroma: [{theme_name}] {pairing}: {ratio:.2f}:1",
                    file=sys.stderr,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chroma",
        description="Generate a dual-theme (light/dark) semantic token set from a single brand color hex.",
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
        choices=tuple(FORMATS),
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
    parser.add_argument(
        "-t",
        "--taxonomy",
        choices=TAXONOMIES,
        default="atmos",
        help="The target design-system token taxonomy (Default: atmos)",
    )
    args = parser.parse_args(argv)

    try:
        layers = build_layers(
            args.hex,
            preserve_vibrancy=args.preserve_vibrancy,
            taxonomy=args.taxonomy,
        )
    except ValueError as exc:
        print(f"chroma: error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"chroma: error: {exc}", file=sys.stderr)
        return 1

    if args.preserve_vibrancy:
        _report_accent(args.hex, layers, taxonomy=args.taxonomy)

    emit(
        args.format,
        layers,
        args.output,
        args.hex,
        preserve_vibrancy=args.preserve_vibrancy,
        taxonomy=args.taxonomy,
    )

    # When a theme file is created, also emit a visual preview alongside it.
    # The preview renders the active taxonomy's token names.
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
            write_output(
                preview_path,
                serialize_preview(
                    layers,
                    args.hex,
                    preserve_vibrancy=args.preserve_vibrancy,
                    taxonomy=args.taxonomy,
                ),
            )
            print(f"wrote {preview_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
