"""Serializers: JSON and Tailwind (v3 config + companion CSS, v4 stylesheet).

All three Atmos tiers (global -> semantic -> component) are emitted. The
Tailwind formats keep the tiers chained through CSS custom properties
(component -> semantic -> global), so swapping the raw global math re-themes
the whole stack without touching component code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chroma import __version__
from chroma.color import parse_hex, rgb_to_hsl, rgb_to_oklch
from chroma.tokens import COMPONENT_TO_SEMANTIC, SEMANTIC_TO_GLOBAL, THEMES

LAYERS = ("global", "semantic", "component")


def _tailwind_color_map() -> dict[str, dict[str, str]]:
    """Nested Tailwind ``colors`` shape: group -> member -> CSS var.

    Group members are utility-friendly (no ``bg-``/``text-``/``border-``
    prefix), so e.g. ``surface.root`` -> ``bg-surface-root`` and
    ``foreground.primary`` -> ``text-foreground-primary`` (never
    ``text-text-primary``). Border colors are the one accepted double prefix
    (``border-border-subtle``), matching the shadcn convention.
    """
    return {
        "surface": {
            "root": "var(--bg-surface-root)",
            "default": "var(--bg-surface-default)",
            "subtle": "var(--bg-surface-subtle)",
            "hover": "var(--bg-surface-hover)",
            "active": "var(--bg-surface-active)",
            "overlay": "var(--bg-surface-overlay)",
        },
        "foreground": {
            "primary": "var(--text-primary)",
            "secondary": "var(--text-secondary)",
            "muted": "var(--text-muted)",
            "disabled": "var(--text-disabled)",
        },
        "border": {
            "subtle": "var(--border-subtle)",
            "default": "var(--border-default)",
            "strong": "var(--border-strong)",
        },
        "on": {"accent": "var(--text-on-accent)"},
        "action": {
            "primary": "var(--bg-action-primary)",
            "hover": "var(--bg-action-hover)",
            "active": "var(--bg-action-active)",
        },
        "grid": {
            "header": "var(--bg-grid-header)",
            "row-hover": "var(--bg-grid-row-hover)",
            "row-selected": "var(--bg-grid-row-selected)",
            "cell": "var(--border-grid-cell)",
            "value": "var(--text-grid-value)",
        },
        "input": {
            "field": "var(--bg-input-field)",
            "default": "var(--border-input-default)",
            "focus": "var(--border-input-focus)",
            "placeholder": "var(--text-input-placeholder)",
        },
        "btn": {
            "primary-default": "var(--bg-btn-primary-default)",
            "primary-hover": "var(--bg-btn-primary-hover)",
            "primary-glyph": "var(--text-btn-primary-glyph)",
        },
    }


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def _transpose_layers(
    layers: dict[str, dict[str, dict[str, str]]],
) -> dict[str, dict[str, dict[str, str]]]:
    return {
        layer: {theme: layers[theme][layer] for theme in layers} for layer in LAYERS
    }


def _oklch_map(
    layers: dict[str, dict[str, dict[str, str]]],
) -> dict[str, dict[str, dict[str, str]]]:
    oklch: dict[str, dict[str, dict[str, str]]] = {}
    for layer in LAYERS:
        oklch[layer] = {}
        for theme in layers:
            oklch[layer][theme] = {
                name: _format_oklch(rgb_to_oklch(parse_hex(value)))
                for name, value in layers[theme][layer].items()
            }
    return oklch


def _format_oklch(value: tuple[float, float, float]) -> str:
    lightness, chroma, hue = value
    return f"{lightness:.4f} {chroma:.4f} {hue:.2f}"


def _meta(brand_hex: str) -> dict:
    brand = parse_hex(brand_hex)
    lightness, chroma, hue = rgb_to_oklch(brand)
    hs, ss, ls = rgb_to_hsl(brand)
    return {
        "input": brand_hex,
        "engine": f"chroma.py {__version__}",
        "brand": {
            "oklch": [round(lightness, 4), round(chroma, 4), round(hue, 2)],
            "hsl": [round(hs, 2), round(ss, 4), round(ls, 4)],
        },
        "themes": list(THEMES),
        "layers": list(LAYERS),
    }


def serialize_json(layers: dict[str, dict[str, dict[str, str]]], brand_hex: str) -> str:
    """Serialize the three-tier token map as a JSON document."""
    payload = {
        "meta": _meta(brand_hex),
        **_transpose_layers(layers),
        "oklch": _oklch_map(layers),
    }
    return json.dumps(payload, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Tailwind
# ---------------------------------------------------------------------------


def _render_js_object(obj: dict[str, dict[str, str]], indent: str) -> str:
    lines = []
    for group, members in obj.items():
        rendered = ", ".join(f"{key}: '{value}'" for key, value in members.items())
        lines.append(f"{indent}{group}: {{ {rendered} }},")
    return "\n".join(lines)


def serialize_tailwind_v3_config() -> str:
    """Serialize a Tailwind v3 ``tailwind.config.js`` (colors -> CSS vars)."""
    return f"""/* Generated by chroma.py v{__version__} — semantic theme config. */
/* Color utilities resolve to runtime CSS custom properties defined in the
   companion .css file (:root for light, .dark for dark). The three Atmos
   tiers are chained via var(): component -> semantic -> global. */
/** @type {{import('tailwindcss').Config}} */
module.exports = {{
  darkMode: 'class',
  theme: {{
    extend: {{
      colors: {{
{_render_js_object(_tailwind_color_map(), "        ")}
      }},
    }},
  }},
}};
"""


def _var_block(
    lines: list[str], layers: dict[str, dict[str, dict[str, str]]], theme_name: str
) -> None:
    """Emit CSS variables, chaining tiers: component -> semantic -> global.

    Only the global layer carries concrete hex values; semantic and component
    tokens resolve through ``var()`` so swapping the raw math re-themes the
    entire stack.
    """
    for layer in LAYERS:
        for name, value in layers[theme_name][layer].items():
            if layer == "semantic":
                rendered = (
                    f"var(--{SEMANTIC_TO_GLOBAL[name]})"
                    if name in SEMANTIC_TO_GLOBAL
                    else value
                )
            elif layer == "component":
                rendered = f"var(--{COMPONENT_TO_SEMANTIC[name]})"
            else:
                rendered = value
            lines.append(f"  --{name}: {rendered};")


def serialize_tailwind_v3_css(layers: dict[str, dict[str, dict[str, str]]]) -> str:
    """Serialize the ``:root`` / ``.dark`` CSS variable definitions (v3 companion)."""
    lines = [
        f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */",
        ":root {",
    ]
    _var_block(lines, layers, "light")
    lines.append("}")
    lines.append("")
    lines.append(".dark {")
    _var_block(lines, layers, "dark")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def serialize_tailwind_v4_css(layers: dict[str, dict[str, dict[str, str]]]) -> str:
    """Serialize a self-contained Tailwind v4 theme stylesheet (``@theme`` + vars)."""
    lines = [f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */"]
    lines += [
        "@import 'tailwindcss';",
        "",
        "@custom-variant dark (&:where(.dark, .dark *));",
        "",
        "@theme inline {",
    ]
    for group, members in _tailwind_color_map().items():
        for key, value in members.items():
            lines.append(f"  --color-{group}-{key}: {value};")
    lines += ["}", "", ":root {"]
    _var_block(lines, layers, "light")
    lines += ["}", "", ".dark {"]
    _var_block(lines, layers, "dark")
    lines += ["}", ""]
    return "\n".join(lines)


def emit_tailwind(
    layers: dict[str, dict[str, dict[str, str]]], output: str | None
) -> None:
    """Resolve the tailwind format by output target.

    No ``-o`` (stdout) or a ``.css`` target emits a self-contained v4
    stylesheet. Any other target emits a v3 ``config.js`` plus its companion
    ``.css`` variable file.
    """
    if output is None:
        sys.stdout.write(serialize_tailwind_v4_css(layers))
        return
    path = Path(output)
    if path.suffix == ".css":
        path.write_text(serialize_tailwind_v4_css(layers))
        print(f"wrote {path}", file=sys.stderr)
        return
    config = path if path.suffix == ".js" else path.with_suffix(".js")
    companion = config.with_suffix(".css")
    config.write_text(serialize_tailwind_v3_config())
    companion.write_text(serialize_tailwind_v3_css(layers))
    print(f"wrote {config}", file=sys.stderr)
    print(f"wrote {companion}", file=sys.stderr)
