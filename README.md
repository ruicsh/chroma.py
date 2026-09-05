# Chroma — Deterministic Semantic Theme Generation

A command-line tool that weaves a complete, dual-theme (Light/Dark) semantic token configuration from a single structural brand hue coordinate, compiled in OKLCH for enterprise frontends.

Run it via `make run` (defaults to `6366f1`) or `make run 10b981`. Or directly with `python3 -m chroma 6366f1`. Or via the launcher: `./chroma.sh 6366f1`.

---

## The Brand Hue Coordinate Engine

In color science, **chroma** represents the relative purity, intensity, and saturation of a specific visual coordinate. `chroma` applies this principle to frontend architecture: instead of manually guessing numeric hex variants or introducing visual inconsistencies, it treats your single brand accent color as a spatial metric inside a cylindrical coordinate system, converts it into **OKLCH** (the perceptually uniform space standardized in [CSS Color 4](https://www.w3.org/TR/css-color-4/)), and mathematically compiles a complete matrix of semantic design tokens for **both Light and Dark themes** instantly.

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

## The Structural Token Architecture: Atmos Token Taxonomy

`chroma` rejects arbitrary design names. It compiles tokens across the **Atmos UI** [taxonomy tiers](https://atmos.style/blog/how-to-build-a-color-system-for-ui-design) so application code stays decoupled from branding changes. The raw math follows the [Radix UI 12-step protocol](https://www.radix-ui.com/colors): each step is evaluated from an explicit, monotonic interpolation curve in OKLCH, then bound to functional intent (semantic).

```
[ 1. GLOBAL TOKENS ]  ───►  [ 2. SEMANTIC TOKENS ]
   Raw Palette Options          Functional Meaning
   (e.g. step-3, accent)        (e.g. bg-surface-default)
```

### 1. Global Tokens (the raw math)

The literal palette output — the 12 neutral steps (`step-1` … `step-12`, chromatic grays at the locked brand hue), the brand accent (`accent`, `accent-hover`, `accent-active`, `accent-on`), the **brand shade scale** (`brand-1` … `brand-12`, a 12-step chromatic ramp at the brand hue/chroma), the four **status coordinates** (`success`, `warning`, `danger`, `info` and their per-family hover/active/on solids) and the four **status shade scales** (`success-1…12`, `warning-1…12`, `danger-1…12`, `info-1…12`, one 12-step ramp per canonical hue).

### 2. Semantic Tokens (functional intent → global)

| Atmos semantic token | Resolves to     | Functional intent                                    |
| :------------------- | :-------------- | :--------------------------------------------------- |
| `bg-surface-root`    | `step-1`        | App canvas background / window                       |
| `bg-surface-default` | `step-2`        | Primary layout panels and content cards              |
| `bg-surface-subtle`  | `step-3`        | Form inputs, table cells, inactive text areas        |
| `bg-surface-hover`   | `step-4`        | High-velocity grid row hover states                  |
| `bg-surface-active`  | `step-5`        | Selected items, active navigation tabs               |
| `bg-surface-overlay` | _(dedicated)_   | Floating layers: popovers, dropdowns, modals         |
| `border-subtle`      | `step-6`        | Low-contrast grid-line cell dividers                 |
| `border-default`     | `step-7`        | Structural component boundary lines                  |
| `border-strong`      | `step-8`        | Focus states and active input outline rings          |
| `text-disabled`      | `step-8`        | Recessed inactive parameters (matches input borders) |
| `text-muted`         | `step-10`       | Metadata, labels, table headers                      |
| `text-secondary`     | `step-11`       | Standard body text and descriptive data              |
| `text-primary`       | `step-12`       | Critical numeric data cells and main titles          |
| `text-on-accent`     | `accent-on`     | Label/glyph color rendered on accent surfaces        |
| `bg-action-primary`  | `accent`        | Primary brand buttons and execution triggers         |
| `bg-action-hover`    | `accent-hover`  | Hover states for primary interaction buttons         |
| `bg-action-active`   | `accent-active` | Pressed state for primary interaction buttons        |

The brand accent is **normalized**: its lightness is shifted (perceptually, hue/chroma preserved) until its on-color label clears strict WCAG AAA (≥7:1). Mid-bright brands keep their vivid color with a black label; very dark brands keep white. Hover/active vary **chroma** at the same lightness, so the AAA guarantee holds across interaction states. Actions reference the **brand accent**, not a neutral gray — neutral buttons blend into layout containers, while the brand coordinate acts as an unmistakable execution beacon.

With `--preserve-vibrancy`, the accent is instead **locked exactly** to the marketing spec: no lightness shift. Bright neon accents get an ultra-dark **chromatic gray** on-color (brand hue, restrained chroma, the lightest shade that still clears AAA) so the brand identity stays loud while text stays readable; dark accents keep white. The CLI reports the achieved `text-on-accent` ratio against every action state on stderr so you can verify the boundary. Mid-bright brands (where no on-color can clear AAA without shifting lightness) fall back to normalization with a stderr warning.

### 3. Shade Scales (brand + status — Step 2)

Following the article's [Step 2: Build your shade scales](https://atmos.style/blog/how-to-build-a-color-system-for-ui-design#step-2-build-your-shade-scales), chroma now builds a full 12-step shade scale for **every** colored family — not just neutrals. Each scale shares the neutral lightness ladder (monotonic OKLCH interpolation) but uses a family-specific chroma profile peaking mid-scale (vivid at step 6–7, muted at the ends) and scaled back ~10% in dark mode (Step 6: reduced saturation on dark).

- **Brand scale** `brand-1…12` — brand hue + brand chroma (floor 0.01 so near-gray brands still tint).
- **Status scales** `success-1…12` / `warning-1…12` / `danger-1…12` / `info-1…12` — canonical hues/chromas independent of the brand.

The article's 50–950 guide collapsed onto chroma's 1–12 Radix protocol (attributed below) now drives the preview ramps, the emitted `brand-*` / `{s}-*` CSS vars, and the Sass/Less/Stylus sections:

| step | intent (chromatic & neutral) |
| :--- | :--------------------------- |
| `1` | Near-white, subtle background tints — app canvas / surface root |
| `2` | Light backgrounds, panels / default surfaces |
| `3` | Subtle tints, inputs / form fields |
| `4` | Hover surfaces |
| `5` | Selected / active surfaces, main brand tone (500) |
| `6` | Low-contrast borders, dividers |
| `7` | Component boundaries |
| `8` | Disabled text, focus outlines |
| `9` | Mid ramp · placeholder / muted mid |
| `10` | Muted text, metadata / labels |
| `11` | Secondary / body text — strong emphasis |
| `12` | Primary / headings — near-black, high-contrast text · darkest surfaces |

Source: adapted from Atmos *50 Near white … 950 Darkest* guide.

### 4. Status Colors (success / warning / danger / info)

The four semantic status families use **fixed canonical hues** — independent of the brand coordinate — so success is always a recognizable green, warning amber, danger red, and info blue, no matter the brand. Under **B1** (article Step 4: semantic → scale step), each family's tints are now **derived from its 12-step scale** and bound to 5 semantic tokens:

| Status semantic token | Resolves to          | Functional intent                    |
| :-------------------- | :------------------- | :----------------------------------- |
| `bg-{s}-subtle`       | `{s}-2`              | Tinted alert/badge surfaces          |
| `bg-{s}-strong`       | `{s}`                | Solid status fills (badges, buttons) |
| `border-{s}`          | `{s}-6`              | Tinted status borders                |
| `text-{s}`            | `{s}-11`             | Status text on default surfaces      |
| `text-on-{s}`         | `{s}-on`             | Label/glyph on status surfaces       |

The solid's lightness is normalized so its on-color clears **WCAG AA (≥4.5:1)** against the solid and both interaction states (success/danger/info keep white labels on vivid dark solids; warning keeps a black label on amber) — this solid stays **AAA-solved, not scale-indexed** (the one intentional exception: no scale step at `brand-9`/`{s}-9` can both be vivid and clear AA in light mode without overshooting). The `subtle`/`border`/`text` scale steps flip lightness per theme — pale tints in light mode, dark tints in dark mode — while `text-{s}` (`{s}-11`) is verified ≥4.5:1 against every surface in both themes; any future brand that would short the bar falls back to a solved value with a CLI warning (B1 safety hatch).

---

## Output

### Tailwind output resolution

`-f tailwind` adapts to your Tailwind major version through the `-o` target; `-f tailwind-v3` forces the v3 config explicitly:

| Format / target                      | Result                                                                                                                                                         |
| :----------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-f tailwind` _(stdout / no `-o`)_   | Self-contained **Tailwind v4** stylesheet (`@theme inline` + `@custom-variant dark` + `:root`/`.dark` tokens)                                                  |
| `-f tailwind` + `theme.css`          | Self-contained **Tailwind v4** stylesheet                                                                                                                      |
| `-f tailwind` + `tailwind.config.js` | **Tailwind v3** `config.js` (`darkMode: 'class'`, colors → `var(--token)`) **plus** a companion `tailwind.config.css` defining the `:root` / `.dark` variables |
| `-f tailwind-v3`                     | **Tailwind v3** `config.js` (+ companion `.css` when given `-o`); stdout carries the `config.js` only                                                          |
| `-f tailwind` + any other name       | Treated as v3 config (`.js` + `.css` emitted)                                                                                                                  |

The global ramps are emitted as **hex** (maximum browser compatibility); the semantic tokens chain through CSS custom properties (`--bg-surface-root: var(--step-1)`), so the raw global values remain the single source of truth. The CSS file exports **only** the global ramps and the semantic domains — no grids, inputs, or button aliases — and the Tailwind `colors` object exposes exactly those domains with utility-friendly names. Each status family lands in the group that matches its role (`surface.success`, `foreground.success`, `border.success`, `on.success`):

| Token group  | Utility example                                                 |
| :----------- | :-------------------------------------------------------------- |
| `surface`    | `bg-surface-root`, `bg-surface-success-subtle`, `bg-surface-success-strong` |
| `foreground` | `text-foreground-primary` (never `text-text-primary`), `text-foreground-danger` |
| `border`     | `border-border-subtle` _(the one accepted double prefix)_, `border-border-warning` |
| `action`     | `bg-action-primary`                                             |
| `on`         | `text-on-accent`, `text-on-info`                                |

### CSS custom properties (`--format css`)

A raw, Tailwind-free stylesheet for universal web-component and plain-CSS setups. `:root` carries the light theme, `.dark` the dark theme; the global ramps are concrete hex while semantic tokens chain through `var()`. No `@import`, `@theme` or `@custom-variant` — just the variables:

```bash
python3 -m chroma 6366f1 --format css -o theme.css
```

### TypeScript module (`--format ts`)

A compile-time-safe module for analytical dashboards, chart theming and custom viewport components. `chromaTheme` is frozen with `as const` (immune to accidental mutation during active view rendering) and its shape is exposed as the exported `ChromaTheme` type:

```bash
python3 -m chroma 6366f1 --format ts -o theme.ts
```

### W3C DTCG document (`--format dtcg`)

A [W3C Design Tokens Community Group](https://tr.designtokens.org/format/) JSON document — every token is nested with explicit `$value`, `$type` and `$description` — ready for ingestion by external tooling such as [Style Dictionary](https://styledictionary.com/). Light and dark theme trees are grouped under top-level `light` / `dark` keys:

```bash
python3 -m chroma 6366f1 --format dtcg -o theme.dtcg.json
```

All three targets emit only the **semantic tokens** (plus, for `css`, the global ramps its `var()` chain depends on).

### Figma Variables (`--format figma`)

A pair of W3C DTCG JSON documents built for Figma's **native** Variables import — no plugin needed. Figma's "Import into Variables" creates one mode per dropped file, so `-o theme.json` writes `theme.light.json` and `theme.dark.json`; drop them together into the Variables view and they become a single collection with **Light** and **Dark** modes. Both files carry the same semantic token tree (so variables are created for every token) with each theme's resolved hex values, forcing designers to design within the architectural color tokens:

```bash
python3 -m chroma 6366f1 --format figma -o theme.json
```

Without `-o`, the light mode reaches stdout (the dark mode is noted on stderr). Every token leaf carries `$type`, `$value` and `$description`.

### Sass variables (`--format sass`)

A SCSS partial with a nested Sass map keyed by theme. `$chroma-theme` holds the global ramps + accent and the semantic tokens under `light` / `dark`, all in concrete hex — so any Sass toolchain can consume the theme in one `@use`:

```bash
python3 -m chroma 6366f1 --format sass -o theme.scss
```

### Less variables (`--format less`)

A Less map (Less ≥ 3.5) keyed by theme. `@chroma-theme` nests `@light` / `@dark` maps holding the global ramps + accent and the semantic tokens in concrete hex:

```bash
python3 -m chroma 6366f1 --format less -o theme.less
```

### Stylus variables (`--format stylus`)

A Stylus hash keyed by theme. `chroma-theme` holds `light` / `dark` object literals with the global ramps + accent and the semantic tokens in concrete hex (keys are quoted so the `-N` step suffixes parse unambiguously):

```bash
python3 -m chroma 6366f1 --format stylus -o theme.styl
```

All three preprocessor targets emit **both** tiers (global ramps + accent, then semantic tokens) resolved to concrete hex — preprocessor variables are compile-time and cannot chain through CSS `var()`, so each theme holds its final values.

### Sample outputs

Committed sample outputs for every format, generated from the `6366f1` brand. Regenerate them with `make samples`:

| Format          | Command                                                   | Sample                                                                                                        |
| :-------------- | :-------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------ |
| `tailwind` (v4) | `python3 -m chroma 6366f1`                                | [`samples/tailwind-v4.css`](samples/tailwind-v4.css)                                                          |
| `tailwind-v3`   | `python3 -m chroma 6366f1 -f tailwind-v3`                 | [`samples/tailwind-v3.js`](samples/tailwind-v3.js)                                                            |
| `css`           | `python3 -m chroma 6366f1 -f css`                         | [`samples/theme.css`](samples/theme.css)                                                                      |
| `ts`            | `python3 -m chroma 6366f1 -f ts`                          | [`samples/theme.ts`](samples/theme.ts)                                                                        |
| `dtcg`          | `python3 -m chroma 6366f1 -f dtcg`                        | [`samples/theme.dtcg.json`](samples/theme.dtcg.json)                                                          |
| `figma`         | `python3 -m chroma 6366f1 -f figma -o samples/figma.json` | [`samples/figma.light.json`](samples/figma.light.json) + [`samples/figma.dark.json`](samples/figma.dark.json) |
| `json`          | `python3 -m chroma 6366f1 -f json`                        | [`samples/tokens.json`](samples/tokens.json)                                                                  |
| `sass`          | `python3 -m chroma 6366f1 -f sass`                        | [`samples/theme.scss`](samples/theme.scss)                                                                    |
| `less`          | `python3 -m chroma 6366f1 -f less`                        | [`samples/theme.less`](samples/theme.less)                                                                    |
| `stylus`        | `python3 -m chroma 6366f1 -f stylus`                      | [`samples/theme.styl`](samples/theme.styl)                                                                    |

A sync test in the suite asserts every committed sample byte-matches fresh output, so the samples can never drift from the code.

### Default output

`python3 -m chroma 6366f1` emits the self-contained Tailwind v4 stylesheet below (status coordinates follow the same pattern as `--accent-*` in the global ramp and resolve through `--bg-{s}-subtle` / `--bg-{s}-strong` / `--text-{s}` / `--border-{s}` / `--text-on-{s}` in the semantic matrix):

```css
/* Generated by chroma.py v1.2.0 — semantic theme tokens. */
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@theme inline {
  /* Core Semantic Layout Layer */
  --color-surface-root: var(--bg-surface-root); /* bg-surface-root */
  --color-surface-default: var(--bg-surface-default); /* bg-surface-default */
  --color-surface-subtle: var(--bg-surface-subtle); /* bg-surface-subtle */
  --color-surface-hover: var(--bg-surface-hover); /* bg-surface-hover */
  --color-surface-active: var(--bg-surface-active); /* bg-surface-active */
  --color-surface-overlay: var(--bg-surface-overlay); /* bg-surface-overlay */
  /* Core Semantic Typography Layer */
  --color-foreground-primary: var(--text-primary); /* text-foreground-primary */
  --color-foreground-secondary: var(
    --text-secondary
  ); /* text-foreground-secondary */
  --color-foreground-muted: var(--text-muted); /* text-foreground-muted */
  --color-foreground-disabled: var(
    --text-disabled
  ); /* text-foreground-disabled */
  /* Core Semantic Boundary Layer */
  --color-border-subtle: var(--border-subtle); /* border-border-subtle */
  --color-border-default: var(--border-default); /* border-border-default */
  --color-border-strong: var(--border-strong); /* border-border-strong */
  /* Core High-Impact Action Layer */
  --color-on-accent: var(--text-on-accent); /* text-on-accent */
  --color-action-primary: var(--bg-action-primary); /* bg-action-primary */
  --color-action-hover: var(--bg-action-hover); /* bg-action-hover */
  --color-action-active: var(--bg-action-active); /* bg-action-active */
}

:root {
  /* The 12-Step Mathematical Gray Ramp */
  --step-1: #fbfcfe;
  --step-2: #f7f8fc;
  --step-3: #f4f5f9;
  --step-4: #f1f2f7;
  --step-5: #eff0f5;
  --step-6: #e9eaf0;
  --step-7: #dddee4;
  --step-8: #cacbd1;
  --step-9: #9c9ea4;
  --step-10: #717279;
  --step-11: #2d2e34;
  --step-12: #05050a;

  /* The 10% High-Velocity Accent Coordinates */
  --accent: #d7e8ff; /* brand accent (AAA-normalized) */
  --accent-hover: #d5e6ff; /* accent hover */
  --accent-active: #daebff; /* accent pressed */
  --accent-on: #000000; /* auto on-color for accent */

  /* Semantic Structural Mapping Matrix */
  --bg-surface-root: var(--step-1); /* app canvas background */
  --bg-surface-default: var(--step-2); /* layout panels & content cards */
  --bg-surface-subtle: var(--step-3); /* form inputs, table cells, alt rows */
  --bg-surface-hover: var(--step-4); /* grid row hover states */
  --bg-surface-active: var(--step-5); /* selected items, active nav tabs */
  --border-subtle: var(--step-6); /* grid-line cell dividers */
  --border-default: var(--step-7); /* component boundary lines */
  --border-strong: var(--step-8); /* focus rings & active input outlines */
  --text-disabled: var(--step-8); /* recessed inactive parameters */
  --text-muted: var(--step-10); /* metadata, labels, table headers */
  --text-secondary: var(--step-11); /* body text & descriptive data */
  --text-primary: var(--step-12); /* critical numbers & main titles */
  --text-on-accent: var(--accent-on); /* label/glyph on accent surfaces */
  --bg-action-primary: var(--accent); /* primary brand buttons */
  --bg-action-hover: var(--accent-hover); /* primary button hover */
  --bg-action-active: var(--accent-active); /* primary button pressed */
  --bg-surface-overlay: #ffffff; /* popovers, dropdowns, modals */
}

.dark {
  /* The 12-Step Mathematical Gray Ramp */
  --step-1: #0c0d12;
  --step-2: #111218;
  --step-3: #17181e;
  --step-4: #1c1e25;
  --step-5: #22242c;
  --step-6: #31333d;
  --step-7: #3f414c;
  --step-8: #545663;
  --step-9: #797b89;
  --step-10: #a0a3b3;
  --step-11: #cccfe1;
  --step-12: #eff2ff;

  /* The 10% High-Velocity Accent Coordinates */
  --accent: #d7e8ff; /* brand accent (AAA-normalized) */
  --accent-hover: #d5e6ff; /* accent hover */
  --accent-active: #daebff; /* accent pressed */
  --accent-on: #000000; /* auto on-color for accent */

  /* Semantic Structural Mapping Matrix */
  --bg-surface-root: var(--step-1); /* app canvas background */
  --bg-surface-default: var(--step-2); /* layout panels & content cards */
  --bg-surface-subtle: var(--step-3); /* form inputs, table cells, alt rows */
  --bg-surface-hover: var(--step-4); /* grid row hover states */
  --bg-surface-active: var(--step-5); /* selected items, active nav tabs */
  --border-subtle: var(--step-6); /* grid-line cell dividers */
  --border-default: var(--step-7); /* component boundary lines */
  --border-strong: var(--step-8); /* focus rings & active input outlines */
  --text-disabled: var(--step-8); /* recessed inactive parameters */
  --text-muted: var(--step-10); /* metadata, labels, table headers */
  --text-secondary: var(--step-11); /* body text & descriptive data */
  --text-primary: var(--step-12); /* critical numbers & main titles */
  --text-on-accent: var(--accent-on); /* label/glyph on accent surfaces */
  --bg-action-primary: var(--accent); /* primary brand buttons */
  --bg-action-hover: var(--accent-hover); /* primary button hover */
  --bg-action-active: var(--accent-active); /* primary button pressed */
  --bg-surface-overlay: #3b3d45; /* popovers, dropdowns, modals */
}
```

Global hex values live in one place; everything else is an alias.

Every token carries an inline **usage hint**: semantic and accent variables document where they should be used (`--bg-surface-root: var(--step-1);  /* app canvas background */`), and each `@theme` color shows the utility class it generates (`--color-surface-root: var(--bg-surface-root);  /* bg-surface-root */`).

### Comprehensive Integration Example

To output a pure, raw programmatic JSON matrix — with both tiers in hex and OKLCH plus brand metadata — to feed straight into an advanced charting library or web-component configuration pipeline:

```bash
python3 -m chroma 10b981 --format json --output branding-tokens.json
```

The `json` document has the shape `{ "meta": …, "global": {theme: {token: hex}}, "semantic": …, "oklch": {layer: {theme: {token: "L C H"}}} }`.

---

## Under the Hood: The Interpolation Curves

`chroma` does not use hardcoded or randomly-sampled arrays. It processes your input color using deterministic spatial calculations:

1. **Hue Locking:** Isolates the brand hue to ensure all calculated gray tokens contain identical light reflection frequencies.
2. **Chroma Restraint:** Bounds neutral-surface chroma (dark ≤ `0.026`, light ≤ `0.012`) so interface elements never look muddy, cheap, or oversaturated.
3. **Explicit Curve Evaluation:** Lightness and chroma are piecewise-linear functions of the normalized step position across the 12-step scale — the same reproducible function, every run.

---

## Guarantees & Verification

The system ships a test suite that enforces its own contract:

- Hex parsing (`#RRGGBB` / `RRGGBB` / `#RGB` / `RGB`) and OKLCH round-trip fidelity.
- Monotonic 12-step lightness, surface lightness bands, and neutral chroma caps.
- **Taxonomy integrity:** every semantic token resolves to its exact global source.
- **WCAG AAA:** `text-primary` vs every `bg-surface-*` ≥ 7:1, `text-on-accent` vs every `bg-action-*` state ≥ 7:1, and `text-secondary` ≥ 4.5:1 (AA).
- Determinism: identical input → identical output.
- **Multi-format output:** `css` (vanilla), `ts` (as-const module), `dtcg` (W3C), `figma` (native Figma Variables import), `sass`/`less`/`stylus` (native preprocessor maps) targets are covered by the suite, with committed samples kept byte-identical via a sync test.

The full quality gate — lint (`ruff`), formatting (`ruff format`), type checking (`pyright`) and tests (`unittest`) — runs via:

```bash
make check
```

---

## Installation

Requires Python >= 3.10.

```bash
git clone <repo-url> chroma.py
cd chroma.py
```

**Development setup (recommended)** — installs the editable package plus the
dev toolchain (ruff, pyright) and unlocks `make check`:

```bash
uv sync
```

**Tool-only install** — installs just the `chroma` console script:

```bash
pip install .
```

### Run

```bash
uv run chroma 6366f1   # dev setup
chroma 6366f1          # pip install
./chroma.sh 6366f1     # launcher (uses the venv from `uv sync`)
```

---

## Usage

```bash
make run              # uv run python -m chroma 6366f1 (default brand)
make run 10b981       # uv run python -m chroma 10b981
```

Or directly:

```bash
python3 -m chroma 6366f1 -o tailwind.config.js
```

Or via the launcher (uses the project venv):

```bash
./chroma.sh 6366f1 --format json
```

Lock a bright neon accent exactly as specified and solve the on-color label instead of shifting lightness:

```bash
python3 -m chroma 00ffff --preserve-vibrancy
```

### CLI reference

```bash
usage: chroma [-h] [-o OUTPUT] [-f {json,tailwind,tailwind-v3,css,ts,dtcg,figma,sass,less,stylus}] [--preserve-vibrancy] hex

Systematic UI CLI Engine: Compile a complete dual-theme semantic token system
from one brand color hex.

positional arguments:
  hex                   The primary brand hex code to extract hue coordinate
                        from (e.g. 6366f1)

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Output file path instead of writing to stdout
  -f, --format {json,tailwind,tailwind-v3,css,ts,dtcg,figma,sass,less,stylus}
                        The configuration file target standard (Default: tailwind)
  --preserve-vibrancy   Lock the brand accent exactly and solve the on-color
                        label for AAA instead of shifting accent lightness
                        (bright accents get an ultra-dark chromatic-gray label;
                        mid-bright brands fall back to normalization)
```

---

## Testing

```bash
make test
```

Or directly:

```bash
python3 -m unittest discover -v -s chroma/tests
```

All tests pass (73 test cases and counting).

---

## References

- [CSS Color 4 — W3C](https://www.w3.org/TR/css-color-4/) — the OKLCH / OKLab color space standard that underpins chroma's perceptual math.
- [Radix UI Colors](https://www.radix-ui.com/colors) — the 12-step scale protocol whose monotonic interpolation curves chroma implements.
- [Atmos UI — How to build a color system](https://atmos.style/blog/how-to-build-a-color-system-for-ui-design) — the token taxonomy tiers (global → semantic) chroma compiles against.
- [W3C Design Tokens Community Group](https://tr.designtokens.org/format/) — the DTCG JSON format emitted by `--format dtcg` / `figma`.
- [Style Dictionary](https://styledictionary.com/) — compatible ingestion tool for chroma's DTCG output.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
