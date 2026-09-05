"""CLI entry point for the chroma token engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chroma.serializers import emit_tailwind, serialize_json
from chroma.tokens import build_layers


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
        choices=("json", "tailwind"),
        default="tailwind",
        help="The configuration file target standard (Default: tailwind)",
    )
    args = parser.parse_args(argv)

    try:
        layers = build_layers(args.hex)
    except ValueError as exc:
        print(f"chroma: error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        payload = serialize_json(layers, args.hex)
        if args.output:
            Path(args.output).write_text(payload)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(payload)
    else:
        emit_tailwind(layers, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
