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

_PREVIEW_SUFFIX = (Path(__file__).parent / "preview_suffix.html").read_text(
    encoding="utf-8"
)


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
