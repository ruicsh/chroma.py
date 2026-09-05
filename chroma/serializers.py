"""Serializers: JSON and Tailwind (v3 config + companion CSS, v4 stylesheet).

The Tailwind formats emit the two theme tiers (global ramps + semantic
intent) chained through CSS custom properties (semantic -> global), so
swapping the raw global math re-themes the whole stack. Component tokens are
not emitted here — they belong in the code layer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chroma import __version__
from chroma.color import parse_hex, rgb_to_hsl, rgb_to_oklch
from chroma.tokens import SEMANTIC_TO_GLOBAL, THEMES

LAYERS = ("global", "semantic")

# Usage hints emitted as comments so consumers can see where each token is
# intended to be used without consulting the docs.
SEMANTIC_USAGE_HINTS: dict[str, str] = {
    "bg-surface-root": "app canvas background",
    "bg-surface-default": "layout panels & content cards",
    "bg-surface-subtle": "form inputs, table cells, alt rows",
    "bg-surface-hover": "grid row hover states",
    "bg-surface-active": "selected items, active nav tabs",
    "bg-surface-overlay": "popovers, dropdowns, modals",
    "border-subtle": "grid-line cell dividers",
    "border-default": "component boundary lines",
    "border-strong": "focus rings & active input outlines",
    "text-disabled": "recessed inactive parameters",
    "text-muted": "metadata, labels, table headers",
    "text-secondary": "body text & descriptive data",
    "text-primary": "critical numbers & main titles",
    "text-on-accent": "label/glyph on accent surfaces",
    "bg-action-primary": "primary brand buttons",
    "bg-action-hover": "primary button hover",
    "bg-action-active": "primary button pressed",
}

ACCENT_USAGE_HINTS: dict[str, str] = {
    "accent": "brand accent (AAA-normalized)",
    "accent-hover": "accent hover",
    "accent-active": "accent pressed",
    "accent-on": "auto on-color for accent",
}

# Tailwind utility class each ``@theme`` color maps to, shown as a hint.
UTILITY_PREFIX: dict[str, str] = {
    "surface": "bg",
    "foreground": "text",
    "border": "border",
    "on": "text",
    "action": "bg",
}

# Brief comment above each v3 config color group.
GROUP_HINTS: dict[str, str] = {
    "surface": "surfaces - canvas, cards, hover/active rows",
    "foreground": "text - primary, secondary, muted, disabled",
    "border": "borders - subtle rules, boundaries, focus",
    "on": "on-color - label on accent surfaces",
    "action": "actions - brand execution buttons",
}


def _tailwind_color_map() -> dict[str, dict[str, str]]:
    """Nested Tailwind ``colors`` shape: group -> member -> CSS var.

    Only the four core semantic domains are exposed. Group members are
    utility-friendly (no ``bg-``/``text-``/``border-`` prefix), so e.g.
    ``surface.root`` -> ``bg-surface-root`` and ``foreground.primary`` ->
    ``text-foreground-primary`` (never ``text-text-primary``). Border colors
    are the one accepted double prefix (``border-border-subtle``), matching
    the shadcn convention.
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


def _meta(brand_hex: str, preserve_vibrancy: bool = False) -> dict:
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
        "preserve_vibrancy": preserve_vibrancy,
    }


def serialize_json(
    layers: dict[str, dict[str, dict[str, str]]],
    brand_hex: str,
    preserve_vibrancy: bool = False,
) -> str:
    """Serialize the three-tier token map as a JSON document."""
    payload = {
        "meta": _meta(brand_hex, preserve_vibrancy),
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
        if group in GROUP_HINTS:
            lines.append(f"{indent}// {GROUP_HINTS[group]}")
        rendered = ", ".join(f"{key}: '{value}'" for key, value in members.items())
        lines.append(f"{indent}{group}: {{ {rendered} }},")
    return "\n".join(lines)


def serialize_tailwind_v3_config() -> str:
    """Serialize a Tailwind v3 ``tailwind.config.js`` (colors -> CSS vars)."""
    return f"""/* Generated by chroma.py v{__version__} — semantic theme config. */
/* Color utilities resolve to runtime CSS custom properties defined in the
   companion .css file (:root for light, .dark for dark). Only the four core
   semantic domains are exposed; the tiers are chained via var() (semantic ->
   global). Component tokens live in the code layer. */
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
    lines: list[str],
    layers: dict[str, dict[str, dict[str, str]]],
    theme_name: str,
    preserve_vibrancy: bool = False,
) -> None:
    """Emit CSS variables for the two theme tiers, chaining semantic -> global.

    Only the global layer carries concrete hex values; semantic tokens
    resolve through ``var()`` so swapping the raw math re-themes the entire
    stack. Component tokens are not emitted here (code layer).
    """
    lines.append("  /* The 12-Step Mathematical Gray Ramp */")
    accent_hint = (
        "brand accent (vibrancy-preserved)"
        if preserve_vibrancy
        else ACCENT_USAGE_HINTS["accent"]
    )
    for name, value in layers[theme_name]["global"].items():
        if name == "accent":
            lines.append("")
            lines.append("  /* The 10% High-Velocity Accent Coordinates */")
        hint = ACCENT_USAGE_HINTS.get(name)
        if name == "accent":
            hint = accent_hint
        lines.append(f"  --{name}: {value};{f'  /* {hint} */' if hint else ''}")
    lines.append("")
    lines.append("  /* Semantic Structural Mapping Matrix */")
    for name, value in layers[theme_name]["semantic"].items():
        rendered = (
            f"var(--{SEMANTIC_TO_GLOBAL[name]})"
            if name in SEMANTIC_TO_GLOBAL
            else value
        )
        hint = SEMANTIC_USAGE_HINTS.get(name)
        lines.append(f"  --{name}: {rendered};{f'  /* {hint} */' if hint else ''}")


def serialize_tailwind_v3_css(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the ``:root`` / ``.dark`` CSS variable definitions (v3 companion)."""
    lines = [
        f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */",
        ":root {",
    ]
    _var_block(lines, layers, "light", preserve_vibrancy)
    lines.append("}")
    lines.append("")
    lines.append(".dark {")
    _var_block(lines, layers, "dark", preserve_vibrancy)
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _theme_inline_block() -> list[str]:
    """Render the Tailwind v4 ``@theme inline`` block over the four core domains."""
    lines = ["@theme inline {"]
    sections = (
        ("  /* Core Semantic Layout Layer */", ("surface",)),
        ("  /* Core Semantic Typography Layer */", ("foreground",)),
        ("  /* Core Semantic Boundary Layer */", ("border",)),
        ("  /* Core High-Impact Action Layer */", ("on", "action")),
    )
    color_map = _tailwind_color_map()
    for comment, groups in sections:
        lines.append(comment)
        for group in groups:
            for key, value in color_map[group].items():
                utility = f"{UTILITY_PREFIX[group]}-{group}-{key}"
                lines.append(f"  --color-{group}-{key}: {value};  /* {utility} */")
    lines.append("}")
    return lines


def serialize_tailwind_v4_css(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize a self-contained Tailwind v4 theme stylesheet (``@theme`` + vars)."""
    lines = [f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */"]
    lines += [
        "@import 'tailwindcss';",
        "",
        "@custom-variant dark (&:where(.dark, .dark *));",
        "",
        *_theme_inline_block(),
        "",
        ":root {",
    ]
    _var_block(lines, layers, "light", preserve_vibrancy)
    lines += ["}", "", ".dark {"]
    _var_block(lines, layers, "dark", preserve_vibrancy)
    lines += ["}", ""]
    return "\n".join(lines)


def emit_tailwind(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the tailwind format by output target.

    No ``-o`` (stdout) or a ``.css`` target emits a self-contained v4
    stylesheet. Any other target emits a v3 ``config.js`` plus its companion
    ``.css`` variable file.
    """
    if output is None:
        sys.stdout.write(serialize_tailwind_v4_css(layers, preserve_vibrancy))
        return
    path = Path(output)
    if path.suffix == ".css":
        path.write_text(serialize_tailwind_v4_css(layers, preserve_vibrancy))
        print(f"wrote {path}", file=sys.stderr)
        return
    config = path if path.suffix == ".js" else path.with_suffix(".js")
    companion = config.with_suffix(".css")
    config.write_text(serialize_tailwind_v3_config())
    companion.write_text(serialize_tailwind_v3_css(layers, preserve_vibrancy))
    print(f"wrote {config}", file=sys.stderr)
    print(f"wrote {companion}", file=sys.stderr)
