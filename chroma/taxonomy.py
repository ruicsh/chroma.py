"""Declarative multi-tenant token taxonomy registry.

This module is the pure, side-effect-free naming layer for ``chroma``. It maps
the engine's *internal* calculated scale steps and functional concepts onto the
*target string specifications* of a chosen design framework (Atmos, Material 3,
Atlassian, Salesforce Lightning Design System 2, Adobe Spectrum Core).

The layer owns no color math and performs no I/O: it is a declarative dictionary
lookup whose keys are stable canonical concept ids and whose values are the
framework-specific token names. Two tiers are derived from it:

    1.  **Tier 1 (primitives)** — the 12-step ``neutral`` and ``brand`` ramps are
        renamed via the taxonomy's naming functions while keeping their raw
        calculated hex values.
    2.  **Tier 2 (semantics)** — every functional semantic token (surface,
        border, text, action, status) is renamed from the registry and aliases
        back to a Tier-1 primitive key.

Accent and status *coordinate* primitives are not scale steps and are therefore
kept under their canonical names in every taxonomy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

# ---------------------------------------------------------------------------
# Canonical concept model
# ---------------------------------------------------------------------------
# The engine's functional concepts. ``CANONICAL`` is the fixed emission order of
# the semantic layer (surfaces, borders, text, on-colors, actions, status, and
# the computed overlay surface). Concept ids are stable and taxonomy-agnostic;
# each taxonomy renames them at the boundary.

STATUS_FAMILIES: tuple[str, ...] = ("success", "warning", "danger", "info")

SURFACE_CONCEPTS = (
    "bg-surface-root",
    "bg-surface-default",
    "bg-surface-subtle",
    "bg-surface-hover",
    "bg-surface-active",
)
# The six surfaces the WCAG contrast guarantee is defined over: the five
# aliased surfaces plus the computed overlay. Single source of truth for
# ``verify_contrast`` and the CI proof (``assert_contrast.py``).
CONTRAST_SURFACES: tuple[str, ...] = (*SURFACE_CONCEPTS, "bg-surface-overlay")
BORDER_CONCEPTS = ("border-subtle", "border-default", "border-strong")
TEXT_CONCEPTS = (
    "text-foreground-disabled",
    "text-foreground-muted",
    "text-foreground-secondary",
    "text-foreground-primary",
    "text-on-accent",
)
ACTION_CONCEPTS = ("bg-action-primary", "bg-action-hover", "bg-action-active")

_STATUS_CONCEPT_KINDS = (
    "bg-{f}-subtle",
    "bg-{f}-strong",
    "border-{f}",
    "text-{f}",
    "text-on-{f}",
)


def _status_concepts() -> tuple[str, ...]:
    return tuple(
        kind.format(f=family)
        for family in STATUS_FAMILIES
        for kind in _STATUS_CONCEPT_KINDS
    )


STATUS_CONCEPTS: tuple[str, ...] = _status_concepts()

# Fixed emission order of the semantic layer.
CANONICAL_SEMANTIC: tuple[str, ...] = (
    SURFACE_CONCEPTS
    + BORDER_CONCEPTS
    + TEXT_CONCEPTS
    + ACTION_CONCEPTS
    + STATUS_CONCEPTS
    + ("bg-surface-overlay",)
)

# Fixed emission order of the global (primitive) layer, mirroring the merge
# order in ``chroma.tokens.build_layers``.
CANONICAL_GLOBAL: tuple[str, ...] = (
    tuple(f"step-{i}" for i in range(1, 13))
    + ("accent", "accent-hover", "accent-active", "accent-on")
    + tuple(f"brand-{i}" for i in range(1, 13))
    + tuple(
        f"{family}{suffix}"
        for family in STATUS_FAMILIES
        for suffix in ("", "-hover", "-active", "-on")
    )
    + tuple(f"{family}-{step}" for family in STATUS_FAMILIES for step in range(1, 13))
)

TAXONOMIES: tuple[str, ...] = ("atmos", "m3", "atlassian", "slds", "spectrum")

_ILLEGAL_CHARS = re.compile(r"[^a-zA-Z0-9_.\-\u0080-\uffff]")
_REPEATED_DELIM = re.compile(r"[.\-]{2,}")
_TRAILING_DELIM = re.compile(r"[.\-]+$")
_LEADING_DELIM = re.compile(r"^[.\-]+")


def sanitize_token(name: str) -> str:
    """Return ``name`` stripped of characters illegal in token identifiers.

    Guarantees no runs of repeated delimiters, no leading/trailing dots or
    dashes, and keeps only ``[a-z0-9_.-]`` (plus non-ASCII word characters).
    """
    cleaned = _ILLEGAL_CHARS.sub("", name)
    cleaned = _REPEATED_DELIM.sub(lambda m: m.group(0)[0], cleaned)
    cleaned = _TRAILING_DELIM.sub("", cleaned)
    cleaned = _LEADING_DELIM.sub("", cleaned)
    return cleaned


@dataclass(frozen=True)
class TaxonomySpec:
    """Declarative naming contract for one target framework."""

    name: str
    prefix: str
    delimiter: str
    neutral: Callable[[int], str]
    brand: Callable[[int], str]
    semantic: dict[str, str]

    def __post_init__(self) -> None:
        missing = [cid for cid in CANONICAL_SEMANTIC if cid not in self.semantic]
        if missing:
            raise ValueError(
                f"taxonomy {self.name!r} is missing semantic names for: {missing}"
            )

    def global_primitive(self, canonical_global: str) -> str:
        """Map a canonical *global* primitive key to this taxonomy's Tier-1 name.

        Neutral steps (``step-N``) and brand steps (``brand-N``) are the scale
        steps renamed by the taxonomy; accent / status coordinates pass through
        unchanged (they are not scale steps).
        """
        if canonical_global.startswith("step-"):
            return sanitize_token(self.neutral(int(canonical_global[5:])))
        if canonical_global.startswith("brand-"):
            return sanitize_token(self.brand(int(canonical_global[6:])))
        return canonical_global

    def semantic_name(self, concept: str) -> str:
        return sanitize_token(self.semantic[concept])


# ---------------------------------------------------------------------------
# Status family -> local framework labels
# ---------------------------------------------------------------------------

_LOCAL_FAMILIES: dict[str, tuple[str, ...]] = {
    "atmos": ("success", "warning", "danger", "info"),
    "m3": ("success", "warning", "error", "info"),
    "atlassian": ("success", "warning", "danger", "information"),
    "slds": ("success", "warning", "error", "info"),
    "spectrum": ("positive", "notice", "negative", "informative"),
}


def _expand_status(pattern: Callable[[str, str], str], taxonomy: str) -> dict[str, str]:
    """Build the 20 status concept -> framework token names for ``taxonomy``."""
    labels = _LOCAL_FAMILIES[taxonomy]
    out: dict[str, str] = {}
    for canonical, local in zip(STATUS_FAMILIES, labels):
        for kind in _STATUS_CONCEPT_KINDS:
            concept = kind.format(f=canonical)
            out[concept] = pattern(kind, local)
    return out


# ---------------------------------------------------------------------------
# Per-taxonomy semantic tables (canonical concept -> framework token name)
# ---------------------------------------------------------------------------


def _identity_semantic() -> dict[str, str]:
    return {cid: cid for cid in CANONICAL_SEMANTIC}


def _atmos_semantic() -> dict[str, str]:
    return _identity_semantic()


def _m3_semantic() -> dict[str, str]:
    base: dict[str, str] = {
        "bg-surface-root": "sys-color-surface-container-lowest",
        "bg-surface-default": "sys-color-surface-container-low",
        "bg-surface-subtle": "sys-color-surface-container",
        "bg-surface-hover": "sys-color-surface-container-high",
        "bg-surface-active": "sys-color-surface-container-highest",
        "bg-surface-overlay": "sys-color-surface-bright",
        "border-subtle": "sys-color-outline-variant",
        "border-default": "sys-color-outline",
        "border-strong": "sys-color-outline-strong",
        "text-foreground-disabled": "sys-color-on-surface-disabled",
        "text-foreground-muted": "sys-color-on-surface-muted",
        "text-foreground-secondary": "sys-color-on-surface-variant",
        "text-foreground-primary": "sys-color-on-surface",
        "text-on-accent": "sys-color-on-primary",
        "bg-action-primary": "sys-color-primary",
        "bg-action-hover": "sys-color-primary-container",
        "bg-action-active": "sys-color-primary-container-high",
    }

    def status(kind: str, local: str) -> str:
        if kind.endswith("-subtle"):
            return f"sys-color-{local}-container"
        if kind.endswith("-strong"):
            return f"sys-color-{local}"
        if kind.startswith("border-"):
            return f"sys-color-{local}-outline"
        if kind.startswith("text-on-"):
            return f"sys-color-on-{local}"
        return f"sys-color-on-{local}-container"

    base.update(_expand_status(status, "m3"))
    return base


def _atlassian_semantic() -> dict[str, str]:
    base: dict[str, str] = {
        "bg-surface-root": "background.sunken",
        "bg-surface-default": "background.elevation.surface",
        "bg-surface-subtle": "background.neutral.subtle",
        "bg-surface-hover": "background.neutral.subtle.hovered",
        "bg-surface-active": "background.neutral.subtle.pressed",
        "bg-surface-overlay": "background.elevation.overlay",
        "border-subtle": "border.subtle",
        "border-default": "border",
        "border-strong": "border.bold",
        "text-foreground-disabled": "text.disabled",
        "text-foreground-muted": "text.subtlest",
        "text-foreground-secondary": "text.subtle",
        "text-foreground-primary": "text.default",
        "text-on-accent": "text.inverse",
        "bg-action-primary": "background.selected.bold",
        "bg-action-hover": "background.selected.bold.hovered",
        "bg-action-active": "background.selected.bold.pressed",
    }

    def status(kind: str, local: str) -> str:
        if kind.endswith("-subtle"):
            return f"background.{local}.subtle"
        if kind.endswith("-strong"):
            return f"background.{local}.bold"
        if kind.startswith("border-"):
            return f"border.{local}"
        if kind.startswith("text-on-"):
            return f"text.on.{local}"
        return f"text.{local}"

    base.update(_expand_status(status, "atlassian"))
    return base


def _slds_semantic() -> dict[str, str]:
    base: dict[str, str] = {
        "bg-surface-root": "color-neutral-base-10",
        "bg-surface-default": "color-neutral-base-20",
        "bg-surface-subtle": "color-neutral-base-30",
        "bg-surface-hover": "color-neutral-base-40",
        "bg-surface-active": "color-neutral-base-50",
        "bg-surface-overlay": "color-neutral-base-60",
        "border-subtle": "color-border-1",
        "border-default": "color-border-2",
        "border-strong": "color-border-3",
        "text-foreground-disabled": "color-text-weakened",
        "text-foreground-muted": "color-neutral-base-70",
        "text-foreground-secondary": "color-neutral-base-80",
        "text-foreground-primary": "color-neutral-base-95",
        "text-on-accent": "color-brand-contrast",
        "bg-action-primary": "color-brand-base-50",
        "bg-action-hover": "color-brand-base-60",
        "bg-action-active": "color-brand-base-40",
    }

    def status(kind: str, local: str) -> str:
        if kind.endswith("-subtle"):
            return f"color-{local}-base-95"
        if kind.endswith("-strong"):
            return f"color-{local}-base-50"
        if kind.startswith("border-"):
            return f"color-{local}-base-70"
        if kind.startswith("text-on-"):
            return f"color-{local}-contrast"
        return f"color-{local}-base-40"

    base.update(_expand_status(status, "slds"))
    return base


def _spectrum_semantic() -> dict[str, str]:
    base: dict[str, str] = {
        "bg-surface-root": "core-color-background-layer-lowest",
        "bg-surface-default": "core-color-background-layer-low",
        "bg-surface-subtle": "core-color-background-layer-1",
        "bg-surface-hover": "core-color-background-layer-2",
        "bg-surface-active": "core-color-background-base-default",
        "bg-surface-overlay": "core-color-background-elevation",
        "border-subtle": "core-color-border-subtle",
        "border-default": "core-color-border",
        "border-strong": "core-color-border-strong",
        "text-foreground-disabled": "core-color-content-disabled",
        "text-foreground-muted": "core-color-content-tertiary",
        "text-foreground-secondary": "core-color-content-secondary",
        "text-foreground-primary": "core-color-content-primary",
        "text-on-accent": "core-color-content-accent",
        "bg-action-primary": "core-color-background-accent-high",
        "bg-action-hover": "core-color-background-accent-high-hover",
        "bg-action-active": "core-color-background-accent-high-down",
    }

    def status(kind: str, local: str) -> str:
        if kind.endswith("-subtle"):
            return f"core-color-background-{local}-subtle"
        if kind.endswith("-strong"):
            return f"core-color-background-{local}-default"
        if kind.startswith("border-"):
            return f"core-color-border-{local}"
        if kind.startswith("text-on-"):
            return f"core-color-content-on-{local}"
        return f"core-color-content-{local}"

    base.update(_expand_status(status, "spectrum"))
    return base


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def _atmos_neutral(step: int) -> str:
    return f"neutral-scale-{step}"


def _atmos_brand(step: int) -> str:
    return f"brand-scale-{step}"


def _m3_neutral(step: int) -> str:
    return f"md-ref-palette-neutral-{step}"


def _m3_brand(step: int) -> str:
    return f"md-ref-palette-primary-{step}"


def _atlassian_neutral(step: int) -> str:
    return f"palette.neutral.{step}0"


def _atlassian_brand(step: int) -> str:
    return f"palette.blue.{step}0"


def _slds_neutral(step: int) -> str:
    return f"primitive-color-neutral-{step}"


def _slds_brand(step: int) -> str:
    return f"primitive-color-brand-{step}"


def _spectrum_neutral(step: int) -> str:
    return f"gray-{step}00"


def _spectrum_brand(step: int) -> str:
    return f"blue-{step}00"


TAXONOMY_REGISTRY: dict[str, TaxonomySpec] = {
    "atmos": TaxonomySpec(
        name="atmos",
        prefix="atmos-",
        delimiter="-",
        neutral=_atmos_neutral,
        brand=_atmos_brand,
        semantic=_atmos_semantic(),
    ),
    "m3": TaxonomySpec(
        name="m3",
        prefix="md-",
        delimiter="-",
        neutral=_m3_neutral,
        brand=_m3_brand,
        semantic=_m3_semantic(),
    ),
    "atlassian": TaxonomySpec(
        name="atlassian",
        prefix="color.",
        delimiter=".",
        neutral=_atlassian_neutral,
        brand=_atlassian_brand,
        semantic=_atlassian_semantic(),
    ),
    "slds": TaxonomySpec(
        name="slds",
        prefix="slds-g-",
        delimiter="-",
        neutral=_slds_neutral,
        brand=_slds_brand,
        semantic=_slds_semantic(),
    ),
    "spectrum": TaxonomySpec(
        name="spectrum",
        prefix="spectrum-",
        delimiter="-",
        neutral=_spectrum_neutral,
        brand=_spectrum_brand,
        semantic=_spectrum_semantic(),
    ),
}


def get_taxonomy(name: str) -> TaxonomySpec:
    """Return the registry spec for ``name`` or raise a precise error."""
    try:
        return TAXONOMY_REGISTRY[name]
    except KeyError:
        choices = ", ".join(TAXONOMIES)
        raise KeyError(f"unknown taxonomy {name!r}; choose one of: {choices}") from None
