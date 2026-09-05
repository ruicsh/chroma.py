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

## The Structural Token Architecture: Atmos Three-Tier Taxonomy

`chroma` rejects arbitrary design names. It compiles tokens across **three abstraction tiers** — the industry-standard [Atmos UI](https://atmos.style/blog/how-to-build-a-color-system-for-ui-design) taxonomy — so application code stays decoupled from branding changes. The raw math follows the [Radix UI 12-step protocol](https://www.radix-ui.com/colors): each step is evaluated from an explicit, monotonic interpolation curve in OKLCH, then bound to functional intent (semantic), then pinned to explicit UI placements (component).

```
[ 1. GLOBAL TOKENS ]  ───►  [ 2. SEMANTIC TOKENS ]  ───►  [ 3. COMPONENT TOKENS ]
   Raw Palette Options          Functional Meaning             Explicit UI Placements
   (e.g. step-3, accent)        (e.g. bg-surface-default)      (e.g. bg-grid-row-hover)
```

### 1. Global Tokens (the raw math)

The literal palette output — the 12 neutral steps (`step-1` … `step-12`, chromatic grays at the locked brand hue) plus the brand accent (`accent`, `accent-hover`, `accent-active`, `accent-on`, `accent-focus`). Component templates never consume these directly.

### 2. Semantic Tokens (functional intent → global)

| Atmos semantic token | Resolves to      | Functional intent                                   |
| :------------------- | :--------------- | :-------------------------------------------------- |
| `bg-surface-root`    | `step-1`         | App canvas background / window                      |
| `bg-surface-default` | `step-2`         | Primary layout panels and content cards             |
| `bg-surface-subtle`  | `step-3`         | Form inputs, table cells, inactive text areas       |
| `bg-surface-hover`   | `step-4`         | High-velocity grid row hover states                 |
| `bg-surface-active`  | `step-5`         | Selected items, active navigation tabs              |
| `bg-surface-overlay` | *(dedicated)*    | Floating layers: popovers, dropdowns, modals        |
| `border-subtle`      | `step-6`         | Low-contrast grid-line cell dividers                |
| `border-default`     | `step-7`         | Structural component boundary lines                 |
| `border-strong`      | `step-8`         | Focus states and active input outline rings         |
| `text-disabled`      | `step-8`         | Recessed inactive parameters (matches input borders)|
| `text-muted`         | `step-10`        | Metadata, labels, table headers                     |
| `text-secondary`     | `step-11`        | Standard body text and descriptive data             |
| `text-primary`       | `step-12`        | Critical numeric data cells and main titles         |
| `text-on-accent`     | `accent-on`      | Label/glyph color rendered on accent surfaces       |
| `bg-action-primary`  | `accent`         | Primary brand buttons and execution triggers        |
| `bg-action-hover`    | `accent-hover`   | Hover states for primary interaction buttons        |
| `bg-action-active`   | `accent-active`  | Pressed state for primary interaction buttons       |

The brand accent is **normalized**: its lightness is shifted (perceptually, hue/chroma preserved) until its on-color label clears strict WCAG AAA (≥7:1). Mid-bright brands keep their vivid color with a black label; very dark brands keep white. Hover/active vary **chroma** at the same lightness, so the AAA guarantee holds across interaction states. Actions reference the **brand accent**, not a neutral gray — neutral buttons blend into layout containers, while the brand coordinate acts as an unmistakable execution beacon.

### 3. Component Tokens (explicit UI placements → semantic)

| Component token           | Resolves to        |
| :------------------------ | :----------------- |
| `bg-grid-header`          | `bg-surface-subtle` |
| `bg-grid-row-hover`       | `bg-surface-hover`  |
| `bg-grid-row-selected`    | `bg-surface-active` |
| `border-grid-cell`        | `border-subtle`     |
| `text-grid-value`         | `text-primary`      |
| `bg-input-field`          | `bg-surface-subtle` |
| `border-input-default`    | `border-default`    |
| `border-input-focus`      | `border-strong`     |
| `text-input-placeholder`  | `text-disabled`     |
| `bg-btn-primary-default`  | `bg-action-primary` |
| `bg-btn-primary-hover`    | `bg-action-hover`   |
| `text-btn-primary-glyph`  | `text-on-accent`    |

Changing a single component token never affects the rest of the ecosystem; changing the raw global math re-themes the entire stack.

---

## Usage

```bash
make run              # python3 -m chroma 6366f1 (default brand)
make run 10b981       # python3 -m chroma 10b981
```

Or directly:

```bash
python3 -m chroma 6366f1 -o tailwind.config.js
```

Or via the launcher (uses the project venv):

```bash
./chroma.sh 6366f1 --format json
```

### CLI reference

```bash
usage: chroma [-h] [-o OUTPUT] [-f {json,tailwind}] hex

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

| Output target        | Result                                                                                                                                                         |
| :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _(stdout / no `-o`)_ | Self-contained **Tailwind v4** stylesheet (`@theme inline` + `@custom-variant dark` + `:root`/`.dark` tokens)                                                  |
| `theme.css`          | Self-contained **Tailwind v4** stylesheet                                                                                                                      |
| `tailwind.config.js` | **Tailwind v3** `config.js` (`darkMode: 'class'`, colors → `var(--token)`) **plus** a companion `tailwind.config.css` defining the `:root` / `.dark` variables |
| any other name       | Treated as v3 config (`.js` + `.css` emitted)                                                                                                                  |

The `tailwind` format uses **hex** values for maximum browser compatibility. The three tiers are chained through CSS custom properties (`--bg-grid-header: var(--bg-surface-subtle)` → `--bg-surface-subtle: var(--step-3)`), so the raw global values remain the single source of truth. The Tailwind `colors` object exposes **semantic + component** tokens only (global is never consumed directly by components), using utility-friendly names:

| Token group | Utility example                |
| :---------- | :----------------------------- |
| `surface`   | `bg-surface-root`              |
| `foreground`| `text-foreground-primary` (never `text-text-primary`) |
| `border`    | `border-border-subtle` *(the one accepted double prefix)* |
| `action`    | `bg-action-primary`            |
| `on`        | `text-on-accent`               |
| `grid`      | `bg-grid-header` / `border-grid-cell` / `text-grid-value` |
| `input`     | `bg-input-field` / `border-input-focus` / `text-input-placeholder` |
| `btn`       | `bg-btn-primary-default` / `text-btn-primary-glyph` |

### Comprehensive Integration Example

To output a pure, raw programmatic JSON matrix — with all three tiers in hex and OKLCH plus brand metadata — to feed straight into an advanced charting library or web-component configuration pipeline:

```bash
python3 -m chroma 10b981 --format json --output branding-tokens.json
```

The `json` document has the shape `{ "meta": …, "global": {theme: {token: hex}}, "semantic": …, "component": …, "oklch": {layer: {theme: {token: "L C H"}}} }`.

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
- **Taxonomy integrity:** every semantic token resolves to its exact global source and every component token to its exact semantic source.
- **WCAG AAA:** `text-primary` vs every `bg-surface-*` ≥ 7:1, `text-on-accent` vs every `bg-action-*` state ≥ 7:1, and `text-secondary` ≥ 4.5:1 (AA).
- Determinism: identical input → identical output.

The full quality gate — lint (`ruff`), formatting (`ruff format`), type checking (`pyright`) and tests (`unittest`) — runs via:

```bash
make check
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

All tests pass (43 test cases and counting).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
