# 🎨 chroma.py

> **Deterministic Semantic Theme Generation for Enterprise Frontends.**  
> Weave a complete, dual-theme (Light/Dark) semantic token configuration from a single structural hue coordinate.

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](https://opensource.org/licenses/MIT)
[![Style: Systematic UI](https://img.shields.io/badge/Style-Systematic%20UI-blue.svg)](https://tailwindcss.com)
[![Accessibility: WCAG AAA](https://img.shields.io/badge/Accessibility-WCAG%20AAA-blueviolet.svg)](https://www.w3.org/WAI/WCAG21/quickref/)

---

## 🏛️ The Craftsmanship Narrative

In color science, **chroma** represents the relative purity, intensity, and saturation of a specific visual coordinate.

`chroma.py` applies this exact principle to frontend architecture. Instead of manually guessing numeric hex variants or introducing visual inconsistencies, `chroma.py` treats your single brand accent color as a spatial coordinate. It converts that coordinate into **OKLCH** — the perceptually uniform cylindrical color space (per [Björn Ottosson](https://bottosson.github.io/posts/oklab/), standardized in [CSS Color 4](https://www.w3.org/TR/css-color-4/)) — and mathematically compiles a complete, comprehensive matrix of semantic design tokens for **both Light and Dark themes** instantly.

Every generated background, text color, and border layer is programmatically calibrated to maintain **strict WCAG AAA contrast ratios (≥7:1)** while utilizing **Chromatic Grays** — injecting a micro-dose of your brand's chroma directly into the neutral background layers to anchor the entire layout canvas.

---

## 📐 The Brand Hue Coordinate Engine

`chroma.py` does not treat colors as static aesthetic choices. It treats your primary input hex as a spatial metric inside a cylindrical color coordinate system.

```
                  ┌─── [Brand Hue Coordinate] ───┐
                  ▼                              ▼
     [ Dark Theme Pipeline ]        [ Light Theme Pipeline ]
     • Deep neutral canvas          • High-contrast reading surfaces
     • Chromatic Gray saturation    • Crisp layout breathing room
     • Restrained eye-strain core   • Maximum daylight legibility
```

When you feed a single hex code into the compiler, the calculation pipeline executes the following deterministic transformations:

1. **Hue Angle Extraction ($H$):** The input color is converted through OKLab into OKLCH to extract its exact angular position ($0^\circ$ to $360^\circ$). This angle is locked as an unchangeable anchor coordinate, and every generated gray shares it — so all "chromatic grays" reflect the brand's exact light frequency.
2. **Perceptual Lightness Curves ($L$):** Each of the 12 scale steps is evaluated from an **explicit, monotonic interpolation curve** in OKLCH lightness — never from a sampled array. The dark theme clamps background surfaces to a deep, eye-strain-reducing band (perceptual $L \lesssim 0.32$); the light theme flips the curve, keeping surfaces bright and near-white ($L \gtrsim 0.93$) for maximum legibility.
3. **Chromatic Gray Blending ($C$):** Rather than outputting sterile, dead grays, the compiler injects a restrained dose of the brand chroma (dark ≈ `0.010–0.026`, light ≈ `0.004–0.012`) directly into the neutral definitions. This harmonizes the interface, making different canvas sections feel visually bound to the primary brand accent.

---

## 🧭 The Structural Token Architecture

`chroma.py` rejects arbitrary design names. Its token scale is bound to **functional intent** by following the [Radix UI 12-step protocol](https://www.radix-ui.com/colors) — backgrounds, interactive components, borders, solids, and text each occupy a fixed band of the scale — while outputting production-grade **Semantic Hierarchy** names designed to support hyper-dense workspaces, data grids, and high-frequency real-time viewports.

### Radix 12-Step → Semantic Alias Mapping

| Radix step band | Functional intent | Semantic token |
| :-------------- | :---------------- | :-------------- |
| 1               | App background    | `surface-root`  |
| 2               | Subtle background | `surface-subtle` |
| 3               | UI element bg (normal) | `surface-default` |
| 4               | UI element bg (hover)  | `surface-elevated` |
| 5               | UI element bg (active) | `surface-active` |
| 6               | Subtle border     | `border-subtle` |
| 7               | UI element border/focus | `border-default` |
| 8               | Solid / strong surface | `border-strong` |
| 10–12           | Low/high/highest contrast text | `text-muted` / `text-secondary` / `text-primary` |

### Brand Accent (Intent)

- `intent-primary` — the brand hue, **normalized**: its lightness is shifted (perceptually, hue/chroma preserved) until the on-color label clears strict WCAG AAA (≥7:1). Mid-bright brands keep their vivid color with a black label; very dark brands keep white.
- `intent-primary-hover` / `intent-primary-active` — vary **chroma** (perceived vibrancy) at the same lightness, so the AAA guarantee holds across interaction states.
- `intent-on-primary` — the auto-picked black/white label.
- `intent-focus-ring` — a visible focus indicator at the locked hue.

---

## 🛠️ Installation & Quickstart

Clone the file directly into your local workspace setup or automation pipeline:

```bash
# Clone or download the single-file utility (stdlib only — no dependencies)
curl -O https://raw.githubusercontent.com/yourusername/chroma/main/chroma.py

# Make the compiler executable
chmod +x chroma.py

# Generate a Tailwind v3 config + companion theme CSS for an institutional Violet accent
./chroma.py 6366f1 -o tailwind.config.js
```

---

## 💻 CLI Usage & API Reference

```bash
usage: chroma.py [-h] [-o OUTPUT] [-f {json,tailwind}] hex

Systematic UI CLI Engine: Compile a complete dual-theme semantic token system
from one brand color hex.

positional arguments:
  hex                   The primary brand hex code to extract hue coordinate
                        from (e.g. 6366f1)

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Output file path instead of writing to stdout
  -f, --format {json,tailwind}
                        The configuration file target standard (Default: tailwind)
```

### Tailwind output resolution

`-f tailwind` adapts to your Tailwind major version through the `-o` target:

| Output target        | Result |
| :------------------- | :------ |
| *(stdout / no `-o`)* | Self-contained **Tailwind v4** stylesheet (`@theme inline` + `@custom-variant dark` + `:root`/`.dark` tokens) |
| `theme.css`          | Self-contained **Tailwind v4** stylesheet |
| `tailwind.config.js` | **Tailwind v3** `config.js` (`darkMode: 'class'`, colors → `var(--token)`) **plus** a companion `tailwind.config.css` defining the `:root` / `.dark` variables |
| any other name       | Treated as v3 config (`.js` + `.css` emitted) |

### Comprehensive Integration Example

To output a pure, raw programmatic JSON matrix — with both hex and OKLCH views plus brand metadata — to feed straight into an advanced charting library or web-component configuration pipeline:

```bash
./chroma.py 10b981 --format json --output branding-tokens.json
```

The `tailwind` format uses **hex** values for maximum browser compatibility; the `json` format also exposes a parallel `oklch` view (`L C H`) for consumers who want the perceptual space directly.

---

## 🎨 Under the Hood: The Interpolation Curves

`chroma.py` does not use hardcoded or randomly-sampled arrays. It processes your input color using deterministic spatial calculations:

1. **Hue Locking:** Isolates the brand hue to ensure all calculated gray tokens contain identical light reflection frequencies.
2. **Chroma Restraint:** Bounds neutral-surface chroma (dark ≤ `0.026`, light ≤ `0.012`) so interface elements never look muddy, cheap, or oversaturated.
3. **Explicit Curve Evaluation:** Lightness and chroma are piecewise-linear functions of the normalized step position across the 12-step scale — the same reproducible function, every run.

---

## ✅ Guarantees & Verification

The system is shipped with a pytest suite that enforces its own contract:

- Hex parsing (`#RRGGBB` / `RRGGBB` / `#RGB` / `RGB`) and OKLCH round-trip fidelity.
- Monotonic 12-step lightness, surface lightness bands, and neutral chroma caps.
- **WCAG AAA:** `text-primary` vs every `surface-*` ≥ 7:1, `intent-on-primary` vs every `intent-*` state ≥ 7:1, and `text-secondary` ≥ 4.5:1 (AA).
- Determinism: identical input → identical output.

```bash
python3 -m pytest -q
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.