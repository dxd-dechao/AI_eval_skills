# Step 7: HTML overview

Produce `architecture-eval-overview.html` only for the sections the current state allows. The page must show Product state, rubric approval state, evaluator acceptance state, blockers, and a one-line route summary without hiding a critical blocker behind a disclosure. Omit evaluator and gate sections when the state is `NEEDS_PRODUCT_DECISION` or `RUBRIC_REVIEW`, and show the blocker in the first screen.

Single self-contained file. Offline styling only (no remote fonts, no CDN). Keep print CSS readable: status text is visible without hover.

## 7.0 Derive the visual theme from the project's frontend

Before styling anything, **inspect the project for an existing frontend UI and adopt its visual language** so the deliverable looks like it belongs to the product — not a generic template. This is a required discovery step.

**Where to look (in priority order):**
1. Design tokens / theme config — Tailwind config (`tailwind.config.*`), CSS custom properties / `:root { --... }`, `theme.ts`, design-system or `@commons/ui` theme files.
2. Global stylesheets — `globals.css`, `app.css`, `index.css` (primary/background/foreground/accent colors).
3. Component library conventions — shadcn/ui tokens, MUI/Chakra theme, brand colors.
4. Fonts — the font families the app actually loads (e.g. from `next/font`, `@font-face`, or the `font-family` stack).
5. Any brand assets — logo colors, favicon, existing project docs/HTML.

**Extract and reuse:**
- **Primary / accent color(s)** — use as the section headers, tier labels, and accent borders.
- **Background / surface colors** — use for page background and cards (respect light/dark preference the app uses).
- **Foreground / text colors** — for body and headings, preserving contrast.
- **Font families** — headings and body should match the app's fonts where they're web-safe or self-hostable offline; otherwise pick the nearest system-font fallback and note it.
- **Border radius / spacing feel** — match the app's rounded-vs-sharp, dense-vs-airy character.

**Output of this step:** a short "theme palette" note at the top of the HTML source (in a comment) listing the extracted tokens and their source file, so the styling is traceable. Example:

```
<!-- Theme derived from apps/web: primary #0f766e, bg #F0FDF4, fonts DM Sans + Instrument Serif (tailwind.config.ts, globals.css) -->
```

**Fallback:** if the project has **no frontend UI** (backend-only service, library, CLI), keep the default palette described in the sections below (green frontend / yellow gateway / blue backend / gold managed services; warm peach trace block). In that case the "Frontend" tier row is omitted from the Service Tiers diagram. **When a frontend theme exists, it OVERRIDES the specific default colors named below** — treat those named colors (green/yellow/blue/gold, warm peach `#FFF8F0`, rust/orange accents) as *roles* to be filled by the project's own palette, not literal values. Keep the roles distinct (each tier and each stage-type still visually separable) even when recolored.

## Content sections

1. **System architecture** — two visual diagrams:

   **Service Tiers diagram:** A table-like layout with rows for each tier. Each row has:
   - A colored tier label on the left (rounded pill shape, pastel background): Frontend (green), Gateway/BFF (yellow), Backend (blue), Managed Services (purple/gold)
   - Service boxes on the right with: bold service name, key details (port, platform, role) in smaller text
   - Multiple services per tier displayed side-by-side in their own bordered boxes
   - Clean grid alignment, generous whitespace, no connecting arrows between tiers

   **Data Flow diagram:** A horizontal pipeline showing the primary data path:
   - Rounded-rectangle boxes for each stage, connected by simple `→` arrows
   - Each box has: bold stage name on top, brief description below
   - Color-code boxes by type: deterministic stages in one color family, LLM stages in another
   - Show parallel/branching paths below the main flow for secondary processing (e.g. embedding, face indexing)
   - Use subtle background color (e.g. light cyan border for deterministic, light yellow for LLM-driven)

2. **AI pipeline detail** — zoom into the model pipeline:
   - Each model/stage with inputs and outputs
   - Deterministic vs non-deterministic labels
   - Where templates/prompts configure behaviour

3. **Eval strategy overview** — the two-layer model:
   - Layer 2: End-to-end (shipping gate)
   - Layer 1: Component diagnostics
   - How they connect (error analysis flow)
   - Harness & automation strip (from doc 6): the three harness modes and what runs automatically per PR / scheduled / pre-ship, with the "harness enforces gates, Langfuse stores evidence, CI blocks" division of labor

4. **Golden dataset plan** — visual of:
   - Segment split (use the proportions chosen in Step 4B for this system's goal — not a fixed 20/20/60). If the adversarial/fairness track applies, include the adversarial segment as an additional slice in the visual, with the counts from the dataset spec's 4J table (the single source of truth for those numbers).
   - Scenario × behaviour matrix (omit the scenario axis if the system has none — show behaviour/category × segments instead)
   - Data sources per segment (including adversarial sourcing from 4J when applicable)
   - Phased rollout timeline

5. **Observability roadmap** — Langfuse setup:
   - Trace structure using the compact tree format from 5B, styled per "Visual style for trace structure" below
   - Dashboard overview (4 dashboards, their audiences)
   - Alert categories
   - Implementation phases with timeline

6. **Metrics at a glance** — table showing:
   - What's measured
   - Per which dimension
   - Target thresholds (identical to the numbers in the eval plan — do not restate different values)
   - Current status (TBD / baseline / monitored)

## Design requirements

- Single self-contained HTML file (inline CSS, inline JS if needed)
- **Use the theme palette derived in Step 7.0** (project frontend colors/fonts) throughout; the color names in the sections below are roles, filled by that palette when a frontend exists
- Reflect the system shape from Step 1: omit tiers/stages/scenario visuals that don't exist (e.g. no Frontend tier for a backend-only service, no scenario matrix for a uniform system, collapsed pipeline for a single-stage system)
- Clean, professional look — suitable for presenting to stakeholders
- Use diagrams (CSS/SVG-based — no external dependencies)
- Responsive (readable on laptop screen)
- Color-coded sections for architecture vs eval vs observability
- Use cards, tables, and flow diagrams — not walls of text
- Audience: data scientist reviewing before discussion with engineers and PMs
- Include a "status" column showing what exists vs what's planned vs what's blocked
- Header: same title + version/date convention as the markdown deliverables, visible near the top

## Visual style for architecture diagrams

> The specific colors named below (green/yellow/blue/gold, pastels) are **roles**. When a frontend theme was derived in Step 7.0, map these roles onto the project's palette (e.g. primary → backend tier, accent → LLM stages) while keeping each role visually distinct. Use the literal defaults only for backend-only projects with no frontend.

The architecture section should use a **tiered table layout** (not a vertical flowchart with arrows between tiers):

- **Service Tiers:** Each tier is a row in a grid. Left column = colored tier label (pill/badge shape with pastel fill: green for frontend, yellow for gateway, blue for backend, gold for managed services). Right column = one or more service boxes (white background, light border, containing bold service name + 2-3 lines of metadata).
- **Data Flow:** Horizontal left-to-right pipeline. Each stage is a rounded-rect box with 2 lines of text (name + detail). Boxes connected by `→` text or thin arrows. Color-coding: pastel cyan/green border for deterministic steps, pastel yellow/gold border for LLM steps. Parallel post-processing shown as a second row below with its own flow.
- **No stacked vertical arrows.** The tier diagram communicates hierarchy via row position; the flow diagram communicates sequence via horizontal position.

## Visual style for trace structure

> The warm-peach/rust palette below is the **backend-only default**. When a frontend theme exists (Step 7.0), recolor this block using the project's accent and surface colors — keep the thick left accent border + subtle surface fill + monospace tree, but in the product's own hues.

The Langfuse trace structure should be rendered as:
- A block with a thick left border (4px, warm accent color like dark orange/rust)
- Light warm background (e.g. `#FFF8F0` or light peach)
- Monospace font for the tree structure
- "Span:" labels in dark bold text
- "Generation:" labels and LLM call names in a warm accent color (rust/orange)
- Metadata annotations (tokens, cost) in muted gray
- No outer border on the other 3 sides — just the left accent border

## Technical constraints

- No external CDN links (must work offline / in gov network)
- All styles inline or in a `<style>` block
- Use modern CSS (grid, flexbox) for layout
- Accessible (sufficient contrast, semantic HTML)
- Print-friendly (no critical info hidden behind JS interactions)
