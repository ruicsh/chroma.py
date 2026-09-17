#!/usr/bin/env python3
"""Cross-compiled taxonomy contrast proof for chroma.py.

This is a CI gate, not a spot check. It proves, in order:

1.  **Value invariance.** Every taxonomy is a pure *rename* of the canonical
    Atmos token set: for every brand, both themes, and every canonical
    semantic/global concept, the emitted hex is byte-identical to Atmos.
    WCAG contrast is a function of the emitted hex alone, so a rename cannot
    change any contrast ratio. A guarantee proven once therefore holds for
    every taxonomy -- this is what "cross-compiled targets preserve contrast"
    means, made executable.

2.  **Neutral-scale AAA theorem.** Sweeping the brand hue across the full
    0..359 degree circle, ``text-foreground-primary`` (step 12) and
    ``text-foreground-secondary`` (step 11) clear strict WCAG AAA (>= 7:1)
    against every surface (steps 1..5 plus the computed overlay) in both the
    light and dark frames. The neutral chroma is bounded small and the
    lightness ladder is fixed, so this is a theorem over all hues rather than
    a sampled corpus.

3.  **Accent + status corpus guarantees.** Over a representative brand corpus
    and every taxonomy, the accent on-color label clears AAA (>= 7:1) against
    every action state, and the status text / on-color labels clear WCAG AA
    (>= 4.5) against their surfaces. Status is AA by design (see
    ``chroma.tokens._STATUS_TARGET``); the accent guarantee is corpus-verified
    because a +10% chroma shift on an arbitrary out-of-gamut coordinate can
    move the hover sRGB luminance below the target.

4.  **Preserve-vibrancy path.** The ``--preserve-vibrancy`` accent keeps its
    AAA on-color guarantee for bright, dark, and mid-bright brands.

``text-foreground-muted`` is intentionally exempt: it is a low-emphasis
metadata tone that does not carry the AAA guarantee.

Exit status is 0 when every proof holds, 1 otherwise.
"""

from __future__ import annotations

import sys

from chroma import TAXONOMIES, build_layers, get_taxonomy, verify_contrast
from chroma.color import contrast_ratio, oklch_to_rgb
from chroma.tokens import (
    CANONICAL_SEMANTIC_TO_GLOBAL,
    DARK,
    LIGHT,
    STATUS_FAMILIES,
    neutral_steps,
)

AAA = 7.0
AA = 4.5

# Representative brands spanning the luminance/chroma gamut: vivid brights, a
# violet/pink pair, warm hues, near-black, black, near-white, and white. These
# are real 8-bit hex inputs, so the corpus exercises sRGB quantization.
BRAND_CORPUS: tuple[str, ...] = (
    "6366f1",  # indigo (project default)
    "10b981",  # emerald
    "06b6d4",  # cyan
    "0ea5e9",  # sky
    "8b5cf6",  # violet
    "f472b6",  # pink
    "ef4444",  # red
    "f59e0b",  # amber
    "111827",  # near-black
    "000000",  # black
    "f8fafc",  # near-white
    "ffffff",  # white
)

# The six guaranteed background surfaces (canonical concept ids).
SURFACE_CONCEPTS: tuple[str, ...] = (
    "bg-surface-root",
    "bg-surface-default",
    "bg-surface-subtle",
    "bg-surface-hover",
    "bg-surface-active",
    "bg-surface-overlay",
)

_ACTION_STATES = ("bg-action-primary", "bg-action-hover", "bg-action-active")
_SURFACE_STEPS = (1, 2, 3, 4, 5)  # steps behind the five non-overlay surfaces
_MAX_DETAIL = 20


class Report:
    """Accumulates violations while keeping the printed detail bounded."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.total = 0

    def expect(self, ok: bool, context: str) -> None:
        if not ok:
            self._record(context)

    def require(self, ratio: float, floor: float, context: str) -> None:
        if ratio < floor:
            self._record(f"{context}: {ratio:.4f}:1 < {floor:.1f}:1")

    def _record(self, detail: str) -> None:
        self.total += 1
        if len(self.failures) < _MAX_DETAIL:
            self.failures.append(detail)


def check_value_invariance(report: Report) -> None:
    """Prove each taxonomy is a value-preserving rename of the Atmos set."""
    reference = "atmos"
    ref_spec = get_taxonomy(reference)
    for brand in BRAND_CORPUS:
        ref_layers = build_layers(brand, taxonomy=reference)
        ref_report = verify_contrast(ref_layers, reference)
        for taxonomy in TAXONOMIES:
            if taxonomy == reference:
                continue
            spec = get_taxonomy(taxonomy)
            layers = build_layers(brand, taxonomy=taxonomy)
            ratios = verify_contrast(layers, taxonomy)
            for theme in ("light", "dark"):
                ref_semantic = ref_layers[theme]["semantic"]
                ref_global = ref_layers[theme]["global"]
                semantic = layers[theme]["semantic"]
                global_tokens = layers[theme]["global"]
                for concept, source in CANONICAL_SEMANTIC_TO_GLOBAL.items():
                    report.expect(
                        semantic[spec.semantic_name(concept)]
                        == ref_semantic[ref_spec.semantic_name(concept)],
                        f"semantic value drift: {brand}/{taxonomy}/{theme}/{concept}",
                    )
                    report.expect(
                        global_tokens[spec.global_primitive(source)]
                        == ref_global[ref_spec.global_primitive(source)],
                        f"global value drift: {brand}/{taxonomy}/{theme}/{source}",
                    )
                overlay = "bg-surface-overlay"
                report.expect(
                    semantic[spec.semantic_name(overlay)]
                    == ref_semantic[ref_spec.semantic_name(overlay)],
                    f"semantic value drift: {brand}/{taxonomy}/{theme}/{overlay}",
                )
                ref_values = sorted(
                    round(value, 9) for value in ref_report[theme].values()
                )
                values = sorted(round(value, 9) for value in ratios[theme].values())
                report.expect(
                    values == ref_values,
                    f"contrast drift: {brand}/{taxonomy}/{theme}",
                )


def check_neutral_scale_aaa(report: Report) -> tuple[float, float]:
    """Sweep every hue; prove primary/secondary text clear AAA on surfaces."""
    worst_primary = float("inf")
    worst_secondary = float("inf")
    for hue in range(360):
        brand_hue = float(hue)
        for theme in (DARK, LIGHT):
            steps = neutral_steps(theme, brand_hue)
            primary = oklch_to_rgb(steps["step-12"])
            secondary = oklch_to_rgb(steps["step-11"])
            overlay = oklch_to_rgb(
                (theme.overlay_lightness, theme.overlay_chroma, brand_hue)
            )
            surfaces = [oklch_to_rgb(steps[f"step-{step}"]) for step in _SURFACE_STEPS]
            surfaces.append(overlay)
            for surface in surfaces:
                primary_ratio = contrast_ratio(primary, surface)
                worst_primary = min(worst_primary, primary_ratio)
                report.require(
                    primary_ratio,
                    AAA,
                    f"hue={hue} {theme.name} text-foreground-primary/surface",
                )
                secondary_ratio = contrast_ratio(secondary, surface)
                worst_secondary = min(worst_secondary, secondary_ratio)
                report.require(
                    secondary_ratio,
                    AAA,
                    f"hue={hue} {theme.name} text-foreground-secondary/surface",
                )
    return worst_primary, worst_secondary


def check_corpus_guarantees(report: Report) -> None:
    """Prove accent AAA and status AA over the corpus and every taxonomy."""
    for brand in BRAND_CORPUS:
        for taxonomy in TAXONOMIES:
            spec = get_taxonomy(taxonomy)
            ratios = verify_contrast(build_layers(brand, taxonomy=taxonomy), taxonomy)
            for theme in ("light", "dark"):
                pairings = ratios[theme]
                on_accent = spec.semantic_name("text-on-accent")
                for state in _ACTION_STATES:
                    label = f"{on_accent}/{spec.semantic_name(state)}"
                    report.require(
                        pairings[label], AAA, f"{brand}/{taxonomy}/{theme}/{label}"
                    )
                for concept in ("text-foreground-primary", "text-foreground-secondary"):
                    text = spec.semantic_name(concept)
                    for surface in SURFACE_CONCEPTS:
                        label = f"{text}/{spec.semantic_name(surface)}"
                        report.require(
                            pairings[label], AAA, f"{brand}/{taxonomy}/{theme}/{label}"
                        )
                for family in STATUS_FAMILIES:
                    text = spec.semantic_name(f"text-{family}")
                    for surface in SURFACE_CONCEPTS:
                        label = f"{text}/{spec.semantic_name(surface)}"
                        report.require(
                            pairings[label], AA, f"{brand}/{taxonomy}/{theme}/{label}"
                        )
                    on_color = spec.semantic_name(f"text-on-{family}")
                    for state in (family, f"{family}-hover", f"{family}-active"):
                        label = f"{on_color}/{spec.global_primitive(state)}"
                        report.require(
                            pairings[label], AA, f"{brand}/{taxonomy}/{theme}/{label}"
                        )


def check_preserve_vibrancy(report: Report) -> None:
    """Prove the vibrancy-preserving accent keeps AAA across action states."""
    for brand in ("00ffff", "111827", "6366f1"):
        ratios = verify_contrast(build_layers(brand, preserve_vibrancy=True))
        for theme in ("light", "dark"):
            for state in _ACTION_STATES:
                label = f"text-on-accent/{state}"
                report.require(
                    ratios[theme][label],
                    AAA,
                    f"preserve-vibrancy {brand}/{theme}/{label}",
                )


def main() -> int:
    report = Report()
    print("chroma contrast proof — cross-compiled taxonomy AAA/AA guarantees")
    print("-" * 64)

    check_value_invariance(report)
    invariance = "ok" if report.total == 0 else "FAIL"
    print(f"[1/4] cross-taxonomy value invariance ......... {invariance}")

    before = report.total
    worst_primary, worst_secondary = check_neutral_scale_aaa(report)
    neutral = "ok" if report.total == before else "FAIL"
    print(f"[2/4] neutral-scale AAA over 360 hues ......... {neutral}")
    print(f"      min primary/surface   {worst_primary:6.3f}:1  (floor {AAA:.1f})")
    print(f"      min secondary/surface {worst_secondary:6.3f}:1  (floor {AAA:.1f})")

    before = report.total
    check_corpus_guarantees(report)
    corpus = "ok" if report.total == before else "FAIL"
    print(f"[3/4] accent AAA + status AA over corpus ...... {corpus}")

    before = report.total
    check_preserve_vibrancy(report)
    vibrancy = "ok" if report.total == before else "FAIL"
    print(f"[4/4] preserve-vibrancy accent AAA ............ {vibrancy}")

    print("-" * 64)
    if report.total:
        print(f"FAILED: {report.total} violation(s); first {len(report.failures)}:")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print("PASS: every cross-compiled taxonomy preserves its WCAG guarantees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
