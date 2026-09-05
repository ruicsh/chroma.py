"""Serializers: JSON and Tailwind (v3 config + companion CSS, v4 stylesheet).

The Tailwind formats emit the two theme tiers (global ramps + semantic
intent) chained through CSS custom properties (semantic -> global), so
swapping the raw global math re-themes the whole stack.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chroma import __version__
from chroma.color import parse_hex, rgb_to_hex, rgb_to_hsl, rgb_to_oklch
from chroma.tokens import (
    BRAND_SCALE_NAMES,
    SEMANTIC_TO_GLOBAL,
    STATUS_COORD_NAMES,
    STATUS_FAMILIES,
    STATUS_SCALE_NAMES,
    THEMES,
)

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

for _family in STATUS_FAMILIES:
    SEMANTIC_USAGE_HINTS[f"bg-{_family}-subtle"] = (
        f"{_family} tinted surfaces (alerts, badges)"
    )
    SEMANTIC_USAGE_HINTS[f"bg-{_family}-strong"] = f"{_family} solid fills"
    SEMANTIC_USAGE_HINTS[f"border-{_family}"] = f"{_family} tinted borders"
    SEMANTIC_USAGE_HINTS[f"text-{_family}"] = f"{_family} text on default surfaces"
    SEMANTIC_USAGE_HINTS[f"text-on-{_family}"] = f"label/glyph on {_family} surfaces"

ACCENT_USAGE_HINTS: dict[str, str] = {
    "accent": "brand accent (AAA-normalized)",
    "accent-hover": "accent hover",
    "accent-active": "accent pressed",
    "accent-on": "auto on-color for accent",
}

_STATUS_HINTS: dict[str, str] = {
    "": "solid (AA on-color)",
    "-hover": "hover",
    "-active": "pressed",
    "-on": "auto on-color",
}

STATUS_USAGE_HINTS: dict[str, str] = {
    f"{family}{suffix}": f"{family} {meaning}"
    for family in STATUS_FAMILIES
    for suffix, meaning in _STATUS_HINTS.items()
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
    "surface": "surfaces - canvas, cards, hover/active rows, status tints",
    "foreground": "text - primary, secondary, muted, disabled, status",
    "border": "borders - subtle rules, boundaries, focus, status",
    "on": "on-color - labels on accent and status surfaces",
    "action": "actions - brand execution buttons",
}

# Emission order for the Layer 2 semantic tokens in the ts / dtcg formats,
# grouped by domain (surfaces, borders, foreground, actions). A fixed order
# keeps output deterministic and greppable across runs.
SEMANTIC_TOKEN_ORDER: tuple[str, ...] = (
    "bg-surface-root",
    "bg-surface-default",
    "bg-surface-subtle",
    "bg-surface-hover",
    "bg-surface-active",
    "bg-surface-overlay",
    "border-subtle",
    "border-default",
    "border-strong",
    "text-disabled",
    "text-muted",
    "text-secondary",
    "text-primary",
    "text-on-accent",
    "bg-action-primary",
    "bg-action-hover",
    "bg-action-active",
)

for _family in STATUS_FAMILIES:
    SEMANTIC_TOKEN_ORDER += (
        f"bg-{_family}-subtle",
        f"bg-{_family}-strong",
        f"border-{_family}",
        f"text-{_family}",
        f"text-on-{_family}",
    )

# Documented theme order (light first) for the ts / dtcg formats. The internal
# ``layers`` map itself is keyed dark-first to match the pipeline iteration.
_THEME_ORDER: tuple[str, ...] = ("light", "dark")


def _camel_case(token: str) -> str:
    """Map a kebab-case token name (``bg-surface-root``) to camelCase."""
    head, *tail = token.split("-")
    return head + "".join(part.capitalize() for part in tail)


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
            **_status_group("bg-", ("subtle", "strong")),
        },
        "foreground": {
            "primary": "var(--text-primary)",
            "secondary": "var(--text-secondary)",
            "muted": "var(--text-muted)",
            "disabled": "var(--text-disabled)",
            **_status_group("text-", ("",)),
        },
        "border": {
            "subtle": "var(--border-subtle)",
            "default": "var(--border-default)",
            "strong": "var(--border-strong)",
            **_status_group("border-", ("",)),
        },
        "on": {
            "accent": "var(--text-on-accent)",
            **_status_group("text-on-", ("",)),
        },
        "action": {
            "primary": "var(--bg-action-primary)",
            "hover": "var(--bg-action-hover)",
            "active": "var(--bg-action-active)",
        },
    }


def _status_group(prefix: str, suffixes: tuple[str, ...]) -> dict[str, str]:
    """Map the four status families into a Tailwind group.

    ``prefix`` is the semantic token prefix (``bg-``, ``text-``, ``border-``,
    ``text-on-``) and ``suffixes`` the per-family members, so e.g.
    ``surface.success`` -> ``var(--bg-success)`` and
    ``surface.success-subtle`` -> ``var(--bg-success-subtle)``.
    """
    group: dict[str, str] = {}
    for family in STATUS_FAMILIES:
        for suffix in suffixes:
            key = f"{family}-{suffix}" if suffix else family
            var = f"--{prefix}{family}-{suffix}" if suffix else f"--{prefix}{family}"
            group[key] = f"var({var})"
    return group


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
   global). */
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
    stack.
    """
    lines.append("  /* The 12-Step Mathematical Gray Ramp */")
    accent_hint = (
        "brand accent (vibrancy-preserved)"
        if preserve_vibrancy
        else ACCENT_USAGE_HINTS["accent"]
    )
    status_section_emitted = False
    brand_section_emitted = False
    status_scale_emitted = False
    for name, value in layers[theme_name]["global"].items():
        if name == "accent":
            lines.append("")
            lines.append("  /* The 10% High-Velocity Accent Coordinates */")
        if name == BRAND_SCALE_NAMES[0] and not brand_section_emitted:
            lines.append("")
            lines.append("  /* Brand Shade Scale — 12-step chromatic ramp */")
            brand_section_emitted = True
        if name in STATUS_FAMILIES and not status_section_emitted:
            lines.append("")
            lines.append("  /* The Four Semantic Status Coordinates */")
            status_section_emitted = True
        if name == STATUS_SCALE_NAMES[0] and not status_scale_emitted:
            lines.append("")
            lines.append("  /* Status Shade Scales — 12-step per family */")
            status_scale_emitted = True
        hint = ACCENT_USAGE_HINTS.get(name) or STATUS_USAGE_HINTS.get(name)
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


def serialize_css(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize raw, Tailwind-free CSS custom properties.

    Light values live in ``:root`` and dark values in a ``.dark`` class block,
    so the sheet drops into any web component or plain-CSS project. The global
    ramps carry the concrete hex math while semantic tokens chain through
    ``var()``.
    """
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


def serialize_tailwind_v3_css(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the ``:root`` / ``.dark`` CSS variable definitions (v3 companion).

    Identical to :func:`serialize_css` — the Tailwind v3 companion file is the
    same raw variable sheet.
    """
    return serialize_css(layers, preserve_vibrancy)


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


def _emit_v3_files(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str,
    preserve_vibrancy: bool = False,
) -> None:
    """Write the Tailwind v3 ``config.js`` and its companion ``.css`` sheet."""
    path = Path(output)
    config = path if path.suffix == ".js" else path.with_suffix(".js")
    companion = config.with_suffix(".css")
    config.write_text(serialize_tailwind_v3_config())
    companion.write_text(serialize_tailwind_v3_css(layers, preserve_vibrancy))
    print(f"wrote {config}", file=sys.stderr)
    print(f"wrote {companion}", file=sys.stderr)


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
    _emit_v3_files(layers, output, preserve_vibrancy)


def emit_tailwind_v3(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the tailwind-v3 format by output target.

    Emits a Tailwind v3 ``config.js`` (colors -> CSS vars) plus its companion
    ``.css`` variable file. With no ``-o``, only the config.js can reach stdout;
    the companion is noted on stderr.
    """
    if output is None:
        sys.stdout.write(serialize_tailwind_v3_config())
        print(
            "companion variable sheet not shown on stdout; pass -o <path> to "
            "write both tailwind.config.js and tailwind.config.css",
            file=sys.stderr,
        )
        return
    _emit_v3_files(layers, output, preserve_vibrancy)


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------


def serialize_ts(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the semantic palette as an immutable TypeScript module.

    Emits ``chromaTheme`` as a deeply immutable object (``as const``) plus a
    derived ``ChromaTheme`` type, so analytical dashboards and chart/component
    styling get compile-time-safe access to flat hex tokens.
    """
    blocks = []
    for theme_name in _THEME_ORDER:
        semantic = layers[theme_name]["semantic"]
        body = "\n".join(
            f"    {_camel_case(name)}: '{semantic[name]}',"
            for name in SEMANTIC_TOKEN_ORDER
        )
        blocks.append(f"  {theme_name}: {{\n{body}\n  }},")
    lines = [
        f"/* Generated by chroma.py v{__version__} — semantic theme tokens. */",
        "/* Flat semantic palette. */",
        "export const chromaTheme = {",
        *blocks,
        "} as const;",
        "",
        "export type ChromaTheme = typeof chromaTheme;",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# W3C Design Tokens Community Group (DTCG)
# ---------------------------------------------------------------------------


def _dtcg_tree(semantic: dict[str, str]) -> dict[str, object]:
    """Nest semantic tokens into a DTCG tree keyed by their dashed path.

    Each ``bg-surface-root`` token becomes ``bg -> surface -> root`` with a
    ``$value`` / ``$type`` / ``$description`` leaf, ready for W3C DTCG tooling
    (e.g. Style Dictionary).
    """
    tree: dict[str, object] = {}
    for name in SEMANTIC_TOKEN_ORDER:
        parts = name.split("-")
        node: dict[str, object] = tree
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[parts[-1]] = {
            "$value": semantic[name],
            "$type": "color",
            "$description": SEMANTIC_USAGE_HINTS[name],
        }
    return tree


def serialize_dtcg(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the semantic palette as a W3C DTCG JSON document.

    Light and dark theme trees are grouped under top-level ``light`` / ``dark``
    keys; every token leaf carries ``$value``, ``$type`` and ``$description``.
    """
    payload = {
        theme_name: _dtcg_tree(layers[theme_name]["semantic"])
        for theme_name in _THEME_ORDER
    }
    return json.dumps(payload, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Figma Variables (native DTCG import)
# ---------------------------------------------------------------------------

# Per-mode file naming: a ``theme.json`` target becomes ``theme.light.json``
# and ``theme.dark.json``. Figma's native import creates one mode per dropped
# file, so the theme name carried by the file name maps directly to a mode.


def serialize_figma_mode(
    layers: dict[str, dict[str, dict[str, str]]],
    theme_name: str,
    preserve_vibrancy: bool = False,
) -> str:
    """Serialize one theme as a single-mode Figma-native DTCG document.

    Figma's native "Import into Variables" consumes DTCG JSON where one file
    is one mode: a new mode is created for each dropped file and variables are
    created only for tokens present (with the same ``$type``) in every file.
    Each mode therefore carries the full semantic tree (``bg.surface.root``,
    ``text.on.accent``, ...) with that theme's resolved hex values.
    """
    return json.dumps(_dtcg_tree(layers[theme_name]["semantic"]), indent=2) + "\n"


def serialize_figma(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the light-mode document (the single file stdout carries)."""
    return serialize_figma_mode(layers, "light", preserve_vibrancy)


def _figma_target(output: str, theme_name: str) -> Path:
    """Derive the per-mode file path for a theme from an ``-o`` target.

    A ``theme.json`` (or extension-less ``theme``) target produces
    ``theme.light.json`` and ``theme.dark.json``.
    """
    stem = Path(output)
    if stem.suffix == ".json":
        stem = stem.with_suffix("")
    return stem.with_name(f"{stem.name}.{theme_name}.json")


def emit_figma(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the figma format by output target.

    Without ``-o`` the light-mode document reaches stdout and the dark mode is
    noted on stderr. With ``-o`` both per-mode files are written so designers
    can drop them together into the Figma Variables panel as one collection
    with two modes.
    """
    if output is None:
        sys.stdout.write(serialize_figma(layers, preserve_vibrancy))
        print(
            "dark mode not shown on stdout; pass -o <stem>.json to write "
            "<stem>.light.json and <stem>.dark.json for the Figma Variables panel",
            file=sys.stderr,
        )
        return
    for theme_name in _THEME_ORDER:
        path = _figma_target(output, theme_name)
        path.write_text(serialize_figma_mode(layers, theme_name, preserve_vibrancy))
        print(f"wrote {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CSS preprocessors (Sass, Less, Stylus)
# ---------------------------------------------------------------------------

# Section headings shared with the css output, kept in each preprocessor's own
# comment syntax so the map stays greppable and deterministic.
_RAMP_COMMENT = "The 12-Step Mathematical Gray Ramp"
_ACCENT_COMMENT = "The 10% High-Velocity Accent Coordinates"
_BRAND_COMMENT = "Brand Shade Scale — 12-step chromatic ramp"
_STATUS_COMMENT = "The Four Semantic Status Coordinates"
_STATUS_SCALE_COMMENT = "Status Shade Scales — 12-step per family"
_SEMANTIC_COMMENT = "Semantic Structural Mapping Matrix"

# Root name of the emitted theme map in each preprocessor's native syntax.
_MAP_ROOT = "chroma-theme"


def _token_sections(
    layers: dict[str, dict[str, dict[str, str]]],
) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
    """Ordered (theme, [(heading, tokens)]) sections for map serialization.

    Within a theme the global ramp, then the accent, then the semantic tokens
    each carry their own heading, mirroring the css ``_var_block`` structure.
    """
    sections: list[tuple[str, list[tuple[str, dict[str, str]]]]] = []
    for theme_name in _THEME_ORDER:
        global_tokens = layers[theme_name]["global"]
        ramp = {
            name: value
            for name, value in global_tokens.items()
            if name.startswith("step-")
        }
        accent = {
            name: value
            for name, value in global_tokens.items()
            if name.startswith("accent")
        }
        brand = {
            name: value
            for name, value in global_tokens.items()
            if name in BRAND_SCALE_NAMES
        }
        status_coords = {
            name: value
            for name, value in global_tokens.items()
            if name in STATUS_COORD_NAMES
        }
        status_scales = {
            name: value
            for name, value in global_tokens.items()
            if name in STATUS_SCALE_NAMES
        }
        semantic = layers[theme_name]["semantic"]
        sections.append(
            (
                theme_name,
                [
                    (_RAMP_COMMENT, ramp),
                    (_ACCENT_COMMENT, accent),
                    (_BRAND_COMMENT, brand),
                    (_STATUS_COMMENT, status_coords),
                    (_STATUS_SCALE_COMMENT, status_scales),
                    (_SEMANTIC_COMMENT, semantic),
                ],
            )
        )
    return sections


def serialize_sass(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the theme as a nested Sass map (``$chroma-theme``).

    Light and dark themes are keys of a top-level map; each holds the global
    ramps + accent and the semantic tokens, all resolved to concrete hex.
    """
    lines = [f"// Generated by chroma.py v{__version__} — semantic theme tokens."]
    lines.append(f"${_MAP_ROOT}: (")
    for theme_name, theme_sections in _token_sections(layers):
        lines.append(f"  {theme_name}: (")
        for heading, tokens in theme_sections:
            lines.append(f"    // {heading}")
            lines.extend(f"    {name}: {value}," for name, value in tokens.items())
        lines.append("  ),")
    lines.append(");")
    lines.append("")
    return "\n".join(lines)


def serialize_less(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the theme as a nested Less map (``@chroma-theme``, Less >= 3.5).

    Light and dark themes are ``@key`` entries of a top-level map; each holds
    the global ramps + accent and the semantic tokens, all in concrete hex.
    """
    lines = [f"// Generated by chroma.py v{__version__} — semantic theme tokens."]
    lines.append(f"@{_MAP_ROOT}: {{")
    for theme_name, theme_sections in _token_sections(layers):
        lines.append(f"  @{theme_name}: {{")
        for heading, tokens in theme_sections:
            lines.append(f"    // {heading}")
            lines.extend(f"    @{name}: {value};" for name, value in tokens.items())
        lines.append("  };")
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def serialize_stylus(
    layers: dict[str, dict[str, dict[str, str]]], preserve_vibrancy: bool = False
) -> str:
    """Serialize the theme as a Stylus hash (``chroma-theme``).

    Light and dark themes are keys of a top-level hash; each holds the global
    ramps + accent and the semantic tokens, all in concrete hex. Keys are
    quoted so the ``-N`` step suffixes parse unambiguously.
    """
    lines = [f"// Generated by chroma.py v{__version__} — semantic theme tokens."]
    lines.append(f"{_MAP_ROOT} = {{")
    for theme_name, theme_sections in _token_sections(layers):
        lines.append(f"  {theme_name}: {{")
        for heading, tokens in theme_sections:
            lines.append(f"    // {heading}")
            lines.extend(f"    '{name}': {value}," for name, value in tokens.items())
        lines.append("  },")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Preview HTML
# ---------------------------------------------------------------------------

_PREVIEW_SUFFIX = '\n:root {\n  color-scheme: light;\n}\n.dark {\n  color-scheme: dark;\n}\n\n* { box-sizing: border-box; }\n\nbody {\n  margin: 0;\n  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;\n  background: var(--bg-surface-root);\n  color: var(--text-primary);\n  -webkit-font-smoothing: antialiased;\n  transition: background 0.2s ease, color 0.2s ease;\n}\n\n.page {\n  max-width: 1080px;\n  margin: 0 auto;\n  padding: 32px 24px 80px;\n}\n\n/* ---- header ---- */\n.banner {\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  gap: 16px;\n  padding-bottom: 20px;\n  border-bottom: 1px solid var(--border-default);\n  margin-bottom: 28px;\n}\n.banner h1 { margin: 0; font-size: 22px; letter-spacing: -0.02em; }\n.banner p { margin: 4px 0 0; color: var(--text-muted); font-size: 13px; }\n.badge {\n  display: inline-flex;\n  align-items: center;\n  gap: 8px;\n  padding: 8px 14px;\n  border: 1px solid var(--border-default);\n  border-radius: 10px;\n  background: var(--bg-surface-default);\n  font-size: 13px;\n  font-variant-numeric: tabular-nums;\n  white-space: nowrap;\n}\n.swatch-dot {\n  width: 18px; height: 18px;\n  border-radius: 6px;\n  background: var(--accent);\n  border: 1px solid var(--border-default);\n}\n.toggle {\n  cursor: pointer;\n  border: 1px solid var(--border-default);\n  background: var(--bg-surface-subtle);\n  color: var(--text-secondary);\n  border-radius: 10px;\n  padding: 9px 16px;\n  font-size: 13px;\n  font-weight: 600;\n}\n.toggle:hover { background: var(--bg-surface-hover); }\n\n/* ---- sections ---- */\nsection { margin-top: 40px; }\nh2 {\n  font-size: 15px;\n  font-weight: 700;\n  letter-spacing: 0.03em;\n  text-transform: uppercase;\n  color: var(--text-muted);\n  margin: 0 0 4px;\n}\n.section-note { font-size: 13px; color: var(--text-muted); margin: 0 0 16px; }\n\n/* ---- neutral ramp ---- */\n.ramp {\n  display: grid;\n  grid-template-columns: repeat(12, 1fr);\n  gap: 8px;\n}\n.ramp-cell {\n  border: 1px solid var(--border-default);\n  border-radius: 12px;\n  overflow: hidden;\n  background: var(--bg-surface-default);\n}\n.ramp-cell .fill { height: 64px; }\n.ramp-cell .meta { padding: 8px 10px; font-size: 11px; }\n.ramp-cell .meta b { display: block; font-size: 12px; }\n.ramp-cell .meta span { color: var(--text-muted); font-variant-numeric: tabular-nums; word-break: break-all; }\n.usage { color: var(--text-muted); display: block; margin-top: 2px; font-size: 10px; }\n.usage code { background: var(--bg-surface-subtle); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 0 4px; }\n\n/* ---- token cards ---- */\n.grid {\n  display: grid;\n  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));\n  gap: 12px;\n}\n.card {\n  border: 1px solid var(--border-default);\n  border-radius: 12px;\n  padding: 14px;\n  background: var(--bg-surface-default);\n}\n.card .swatch {\n  height: 44px;\n  border-radius: 8px;\n  border: 1px solid var(--border-subtle);\n  margin-bottom: 10px;\n}\n.card b { display: block; font-size: 13px; }\n.card code { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; }\n\n/* ---- semantic matrix ---- */\n.matrix {\n  display: grid;\n  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));\n  gap: 10px;\n}\n.matrix .row {\n  display: flex;\n  align-items: center;\n  gap: 12px;\n  border: 1px solid var(--border-default);\n  border-radius: 10px;\n  padding: 10px 12px;\n  background: var(--bg-surface-default);\n}\n.matrix .row .chip {\n  width: 40px; height: 40px;\n  border-radius: 8px;\n  border: 1px solid var(--border-subtle);\n  flex-shrink: 0;\n}\n.matrix .row .labels { min-width: 0; }\n.matrix .row .labels b { display: block; font-size: 12.5px; }\n.matrix .row .labels span { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; word-break: break-all; }\n.matrix .row .arrow { margin-left: auto; color: var(--text-muted); font-size: 11px; font-variant-numeric: tabular-nums; text-align: right; }\n\n/* ---- status ---- */\n.status-group { margin-bottom: 16px; }\n.status-group h3 {\n  font-size: 13px; font-weight: 600; margin: 0 0 8px;\n  display: flex; align-items: center; gap: 8px;\n}\n.status-dot { width: 10px; height: 10px; border-radius: 50%; }\n.status-row { display: flex; gap: 10px; flex-wrap: wrap; }\n.status-item {\n  flex: 1 1 150px;\n  min-width: 140px;\n  border: 1px solid var(--border-default);\n  border-radius: 10px;\n  padding: 12px;\n  background: var(--bg-surface-default);\n}\n.status-item .swatch { height: 34px; border-radius: 7px; border: 1px solid var(--border-subtle); margin-bottom: 8px; }\n.status-item b { font-size: 12px; display: block; }\n.status-item span { font-size: 10.5px; color: var(--text-muted); }\n\n/* ---- sample UI ---- */\n.sample-grid {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));\n  gap: 16px;\n}\n.panel {\n  border: 1px solid var(--border-default);\n  border-radius: 14px;\n  padding: 20px;\n  background: var(--bg-surface-default);\n}\n.panel h3 { margin: 0 0 4px; font-size: 15px; }\n.panel .sub { margin: 0 0 16px; color: var(--text-muted); font-size: 12.5px; }\n.btn {\n  border: none;\n  border-radius: 9px;\n  padding: 10px 18px;\n  font-size: 13.5px;\n  font-weight: 600;\n  cursor: pointer;\n}\n.btn-primary { background: var(--bg-action-primary); color: var(--text-on-accent); }\n.btn-primary:hover { background: var(--bg-action-hover); }\n.btn-primary:active { background: var(--bg-action-active); }\n.btn-ghost { background: transparent; color: var(--text-secondary); border: 1px solid var(--border-default); }\n.btn-ghost:hover { background: var(--bg-surface-hover); }\n.input {\n  width: 100%;\n  padding: 10px 12px;\n  border-radius: 9px;\n  border: 1px solid var(--border-default);\n  background: var(--bg-surface-subtle);\n  color: var(--text-primary);\n  font-size: 13.5px;\n}\n.input:focus { outline: 2px solid var(--border-strong); outline-offset: 1px; }\n.tag {\n  display: inline-flex; align-items: center;\n  gap: 6px; border-radius: 999px;\n  padding: 4px 12px; font-size: 12px; font-weight: 600;\n}\n.alert {\n  border-radius: 10px; padding: 12px 14px; font-size: 13px; margin-top: 12px;\n  border: 1px solid var(--border-danger);\n  background: var(--bg-danger-subtle);\n  color: var(--text-danger);\n}\n.alert-ok {\n  border-color: var(--border-success);\n  background: var(--bg-success-subtle);\n  color: var(--text-success);\n}\n</style>\n</head>\n<body>\n<div class="page">\n\n  <header class="banner">\n    <div>\n      <h1>chroma — Default Color System</h1>\n      <p>Compiled from a single brand hue in OKLCH · Light / Dark dual theme</p>\n    </div>\n    <div style="display:flex; gap:10px; align-items:center;">\n      <span class="badge"><span class="swatch-dot"></span> brand #6366f1</span>\n      <button class="toggle" id="toggle">Switch to Dark</button>\n    </div>\n  </header>\n\n  <!-- brand shade scale -->\n  <section>\n    <h2>Brand Shade Scale</h2>\n    <p class="section-note">12-step chromatic ramp at the brand hue — 1 near-white tint, 12 near-black shade. Hover a cell for the step legend (adapted from the article\'s 50–950 guide).</p>\n    <div class="ramp" id="brand-ramp"></div>\n  </section>\n\n  <!-- 12-step neutral ramp -->\n  <section>\n    <h2>The 12-Step Neutral Ramp</h2>\n    <p class="section-note">Chromatic grays — every step is tinted with the locked brand hue. Hover a cell for its semantic use.</p>\n    <div class="ramp" id="ramp"></div>\n  </section>\n\n    <!-- accent -->\n  <section>\n    <h2>Brand Accent</h2>\n    <p class="section-note">Lightness-normalized to clear WCAG AAA with its on-color.</p>\n    <div class="grid">\n      <div class="card"><div class="swatch" style="background: var(--accent);"></div><b>accent</b><code>var(--accent)</code></div>\n      <div class="card"><div class="swatch" style="background: var(--accent-hover);"></div><b>accent-hover</b><code>var(--accent-hover)</code></div>\n      <div class="card"><div class="swatch" style="background: var(--accent-active);"></div><b>accent-active</b><code>var(--accent-active)</code></div>\n      <div class="card"><div class="swatch" style="background: var(--accent-on);"></div><b>accent-on</b><code>var(--accent-on)</code></div>\n    </div>\n  </section>\n\n  <!-- semantic surface / border / text -->\n  <section>\n    <h2>Semantic Mapping Matrix</h2>\n    <p class="section-note">Functional intent → global token. Neutral steps power surfaces, borders and text.</p>\n    <div class="matrix" id="matrix"></div>\n  </section>\n\n  <!-- status families -->\n  <section>\n    <h2>Status Families</h2>\n    <p class="section-note">Four fixed canonical hues, independent of the brand coordinate.</p>\n    <div id="statuses"></div>\n  </section>\n\n  <!-- status shade scales -->\n  <section>\n    <h2>Status Shade Scales</h2>\n    <p class="section-note">One 12-step ramp per canonical hue; steps share the neutral lightness ladder but peak chroma mid-scale. Dark theme scales back ~10% (article Step 6).</p>\n    <div id="status-scales"></div>\n  </section>\n\n    <!-- sample UI -->\n  <section>\n    <h2>Sample Composition</h2>\n    <p class="section-note">The tokens wired into a real-looking surface.</p>\n    <div class="sample-grid">\n      <div class="panel">\n        <h3>Invoice #1042</h3>\n        <p class="sub">Overview of the workspace</p>\n        <label class="sub" style="display:block; margin-bottom:6px;">Project name</label>\n        <input class="input" type="text" value="Atmos Storefront" style="margin-bottom:14px;">\n        <div style="display:flex; gap:8px;">\n          <button class="btn btn-primary">Save changes</button>\n          <button class="btn btn-ghost">Cancel</button>\n        </div>\n      </div>\n      <div class="panel">\n        <h3>Notifications</h3>\n        <p class="sub">Recent activity on your account</p>\n        <span class="tag" style="background: var(--bg-success-strong); color: var(--text-on-success);">Deployed</span>\n        <span class="tag" style="background: var(--bg-warning-subtle); color: var(--text-warning);">Pending review</span>\n        <span class="tag" style="background: var(--bg-danger-strong); color: var(--text-on-danger);">Failed</span>\n        <span class="tag" style="background: var(--bg-info-subtle); color: var(--text-info);">New comment</span>\n        <div class="alert alert-ok">\n          <b>Build succeeded</b> — 3 deployments shipped to production.\n        </div>\n        <div class="alert">\n          <b>API rate limit</b> — 429 responses detected in the last 5 minutes.\n        </div>\n      </div>\n    </div>\n  </section>\n\n</div>\n\n<script>\nconst html = document.documentElement;\nconst toggle = document.getElementById(\'toggle\');\ntoggle.addEventListener(\'click\', () => {\n  html.classList.toggle(\'dark\');\n  toggle.textContent = html.classList.contains(\'dark\') ? \'Switch to Light\' : \'Switch to Dark\';\n});\n\nconst legend = {\n  1: "Near-white, subtle background tints — app canvas / surface root",\n  2: "Light backgrounds, panels / default surfaces",\n  3: "Subtle tints, inputs / form fields",\n  4: "Hover surfaces",\n  5: "Selected / active surfaces, main brand tone (500)",\n  6: "Low-contrast borders, dividers",\n  7: "Component boundaries",\n  8: "Disabled text, focus outlines",\n  9: "Mid ramp · placeholder / muted mid",\n  10: "Muted text, metadata / labels",\n  11: "Secondary / body text — strong emphasis",\n  12: "Primary / headings — near-black, high-contrast text · darkest surfaces",\n};\n\nconst rampEl = document.getElementById(\'ramp\');\nconst ramp = [\n  [\'step-1\', \'app canvas\', \'bg-surface-root\'],\n  [\'step-2\', \'panels / cards\', \'bg-surface-default\'],\n  [\'step-3\', \'inputs / rows\', \'bg-surface-subtle\'],\n  [\'step-4\', \'row hover\', \'bg-surface-hover\'],\n  [\'step-5\', \'selected / active\', \'bg-surface-active\'],\n  [\'step-6\', \'grid-line dividers\', \'border-subtle\'],\n  [\'step-7\', \'component bounds\', \'border-default\'],\n  [\'step-8\', \'focus / disabled\', \'border-strong · text-disabled\'],\n  [\'step-9\', \'pure ramp step\', \'—\'],\n  [\'step-10\', \'metadata / labels\', \'text-muted\'],\n  [\'step-11\', \'body text\', \'text-secondary\'],\n  [\'step-12\', \'headings\', \'text-primary\'],\n];\nrampEl.innerHTML = ramp.map(([name, use, token]) => {\n  const stepNum = parseInt(name.split(\'-\')[1]||\'0\',10);\n  const leg = legend[stepNum]||use;\n  return `\n  <div class="ramp-cell" title="${leg}">\n    <div class="fill" style="background: var(--${name});"></div>\n    <div class="meta"><b>${name}</b><span title="resolve the live value">var(--${name})</span><span class="usage">${use}</span><span class="usage"><code>${token}</code></span></div>\n  </div>`;\n}).join(\'\');\n\nconst matrixEl = document.getElementById(\'matrix\');\nconst matrix = [\n  [\'bg-surface-root\', \'var(--step-1)\', \'root canvas\'],\n  [\'bg-surface-default\', \'var(--step-2)\', \'layout panels & cards\'],\n  [\'bg-surface-subtle\', \'var(--step-3)\', \'inputs, table cells\'],\n  [\'bg-surface-hover\', \'var(--step-4)\', \'row hover\'],\n  [\'bg-surface-active\', \'var(--step-5)\', \'selected / active\'],\n  [\'border-subtle\', \'var(--step-6)\', \'grid-line dividers\'],\n  [\'border-default\', \'var(--step-7)\', \'component boundaries\'],\n  [\'border-strong\', \'var(--step-8)\', \'focus rings\'],\n  [\'text-disabled\', \'var(--step-8)\', \'recessed text\'],\n  [\'text-muted\', \'var(--step-10)\', \'metadata / labels\'],\n  [\'text-secondary\', \'var(--step-11)\', \'body text\'],\n  [\'text-primary\', \'var(--step-12)\', \'headings\'],\n  [\'bg-action-primary\', \'var(--accent)\', \'primary buttons\'],\n  [\'bg-action-hover\', \'var(--accent-hover)\', \'button hover\'],\n  [\'bg-action-active\', \'var(--accent-active)\', \'button pressed\'],\n  [\'text-on-accent\', \'var(--accent-on)\', \'labels on accent\'],\n];\nmatrixEl.innerHTML = matrix.map(([token, ref, use]) => `\n  <div class="row">\n    <div class="chip" style="background: var(--${token});"></div>\n    <div class="labels"><b>${token}</b><span>${use}</span></div>\n    <div class="arrow">→ ${ref}</div>\n  </div>`).join(\'\');\n\nconst statuses = [\'success\', \'warning\', \'danger\', \'info\'];\nconst statusEl = document.getElementById(\'statuses\');\nstatusEl.innerHTML = statuses.map(family => `\n  <div class="status-group">\n    <h3><span class="status-dot" style="background: var(--${family});"></span>${family}</h3>\n    <div class="status-row">\n      <div class="status-item"><div class="swatch" style="background: var(--${family});"></div><b>${family}</b><span>solid · on ${family}</span></div>\n      <div class="status-item"><div class="swatch" style="background: var(--${family}-2);"></div><b>${family}-2</b><span>tinted surface</span></div>\n      <div class="status-item"><div class="swatch" style="background: var(--${family}-6);"></div><b>${family}-6</b><span>tinted border</span></div>\n      <div class="status-item"><div class="swatch" style="background: var(--${family}-11);"></div><b>${family}-11</b><span>readable text</span></div>\n    </div>\n  </div>`).join(\'\');\n\nconst brandRampEl = document.getElementById(\'brand-ramp\');\nif (brandRampEl) {\n  brandRampEl.innerHTML = Array.from({length: 12}, (_, i) => {\n    const n = i+1;\n    return `<div class="ramp-cell" title="${legend[n]}"><div class="fill" style="background: var(--brand-${n});"></div><div class="meta"><b>brand-${n}</b><span>var(--brand-${n})</span><span class="usage">${legend[n].split(" — ")[0]}</span></div></div>`;\n  }).join(\'\');\n}\n\nconst statusScalesEl = document.getElementById(\'status-scales\');\nif (statusScalesEl) {\n  statusScalesEl.innerHTML = statuses.map(family => `\n    <div class="status-group">\n      <h3><span class="status-dot" style="background: var(--${family});"></span>${family} scale</h3>\n      <div class="ramp">\n        ${Array.from({length: 12}, (_, i) => {\n          const n = i+1;\n          return `<div class="ramp-cell" title="${legend[n]}"><div class="fill" style="background: var(--${family}-${n});"></div><div class="meta"><b>${family}-${n}</b><span>var(--${family}-${n})</span><span class="usage">${legend[n].split(" — ")[0]}</span></div></div>`;\n        }).join(\'\')}\n      </div>\n    </div>`).join(\'\');\n}\n\n</script>\n</body>\n</html>'


def serialize_preview(
    layers: dict[str, dict[str, dict[str, str]]],
    brand_hex: str,
    preserve_vibrancy: bool = False,
) -> str:
    """Serialize a self-contained HTML preview for the theme.

    The page embeds the CSS custom properties for both themes and renders
    the neutral ramp, brand/status scales, semantic matrix and sample UI
    so the compiled tokens can be visually verified in a browser. The
    preview is theme-aware via a light/dark toggle and uses only the
    generated tokens (no external assets).
    """
    # Canonical brand hex for display (e.g., "#6366f1").
    brand_hex_canonical = rgb_to_hex(parse_hex(brand_hex))
    normalized = brand_hex_canonical.lower()
    is_default = normalized == "#6366f1"
    title_part = "Default" if is_default else brand_hex_canonical
    prefix = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>chroma — {title_part} Color System Preview</title>\n"
        "<style>\n"
    )
    suffix = _PREVIEW_SUFFIX
    if not is_default:
        suffix = suffix.replace(
            "brand #6366f1", f"brand {brand_hex_canonical}"
        ).replace(
            "chroma \u2014 Default Color System",
            f"chroma \u2014 {brand_hex_canonical} Color System",
        )
    css_block = serialize_css(layers, preserve_vibrancy).strip()
    return prefix + css_block + suffix


def emit_preview(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    brand_hex: str,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the preview format by output target."""
    _emit_text(serialize_preview(layers, brand_hex, preserve_vibrancy), output)


# ---------------------------------------------------------------------------
# Emission (stdout or file) shared by the token targets
# ---------------------------------------------------------------------------


def _emit_text(text: str, output: str | None) -> None:
    """Write ``text`` to stdout or, given ``output``, to that file."""
    if output is None:
        sys.stdout.write(text)
        return
    path = Path(output)
    path.write_text(text)
    print(f"wrote {path}", file=sys.stderr)


def emit_json(
    layers: dict[str, dict[str, dict[str, str]]],
    brand_hex: str,
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the json format by output target."""
    _emit_text(serialize_json(layers, brand_hex, preserve_vibrancy), output)


def emit_css(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the css format by output target."""
    _emit_text(serialize_css(layers, preserve_vibrancy), output)


def emit_ts(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the ts format by output target."""
    _emit_text(serialize_ts(layers, preserve_vibrancy), output)


def emit_dtcg(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the dtcg format by output target."""
    _emit_text(serialize_dtcg(layers, preserve_vibrancy), output)


def emit_sass(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the sass format by output target."""
    _emit_text(serialize_sass(layers, preserve_vibrancy), output)


def emit_less(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the less format by output target."""
    _emit_text(serialize_less(layers, preserve_vibrancy), output)


def emit_stylus(
    layers: dict[str, dict[str, dict[str, str]]],
    output: str | None,
    preserve_vibrancy: bool = False,
) -> None:
    """Resolve the stylus format by output target."""
    _emit_text(serialize_stylus(layers, preserve_vibrancy), output)
