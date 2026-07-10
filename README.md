# AI Eval Skills

Claude Code skills that take an AI/LLM project from eval **design** to eval **implementation** — no questions asked.

## Skills

### 1. `eval-design` — Generate the eval design

Point it at a repo root and it produces **six deliverables**, fully adapted to the system's actual architecture:

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | **Codebase Architecture Overview** | System purpose, service tiers, repo structure, subsystems, recent activity |
| 2 | **LLM In-Out Flow** | Per-model prompt/schema contracts, data-flow diagrams, inference config |
| 3 | **Eval Plan** | Two-layer eval: end-to-end shipping gate (Layer 2) + per-component diagnostics (Layer 1), with LLM-as-judge rubrics, safety/robustness/fairness tracks, and statistical rigor |
| 4 | **Golden Dataset Spec** | Goal-driven composition, annotation schema, matching logic, acceptance criteria, phased rollout |
| 5 | **Langfuse Setup Spec** | Trace structure, metadata, scores, dashboards, alerts, integration points |
| 6 | **Eval Harness Spec** | Harness modes, automation groups, module architecture, Langfuse integration, gate semantics |
| — | **Stakeholder HTML Overview** | Single-file visual summary styled to match the project's own frontend |

### 2. `eval-harness-build` — Implement the eval harness

Takes the design documents produced by `eval-design` and generates a **working Python eval harness** — real code, not scaffolding. Produces:

- **`eval_harness/` package** — pipeline adapter (calls the real app), LLM judge runner with structured output, deterministic metrics with confidence intervals, ship gates on CI lower bounds, and a results sink with full Langfuse bypass
- **Mode 1 notebook** — interactive golden-eval Jupyter notebook with a single "Configure Me" cell holding every user variable
- **Smoke tests** — offline verification of dataset loading, judge validation, metric arithmetic, gate logic, and local writer round-trip

The harness enforces key invariants: judges never compute metrics, CIs only at aggregate level, gates on CI bounds (not point estimates), and Langfuse is never imported when bypassed.

## Key design principles

- **Adaptive, not templated** — classifies each system on pipeline shape (single-stage vs multi-stage) and scenario dimensions, then expands or prunes sections accordingly
- **Never a single aggregate** — metrics are always stratified by the real variation axis
- **Cross-document consistency** — shared numbers, axes, and pipeline stages are verified across all six deliverables
- **Safety and fairness built in** — untrusted-input tier, demographic axes, and costly failure direction are identified from code and carry through to eval gates and dataset segments

## Best fit

Detection/classification-style LLM pipelines — systems where video, text, or documents flow through one or more AI models and produce structured outputs (incidents, classifications, scores, matches).

Examples: school safety analytics, content moderation, document processing, support ticket routing, medical triage.

## Usage

### As Claude Code skills

Copy the `skills/` directory into your Claude Code skills path, then invoke from the root of any AI project:

```
/eval-design          # generates the 6 design documents
/eval-harness-build   # implements the harness from those documents
```

Both skills run autonomously — they explore the codebase, discover the architecture, and produce deliverables without asking questions.

### Recommended workflow

1. Run `/eval-design` first to generate the eval plan, golden dataset spec, and harness spec
2. Review and iterate on the design documents
3. Run `/eval-harness-build` to generate the working implementation

### Output location

- Design deliverables → `Knowledge/` folder (or equivalent docs location)
- Harness implementation → `eval_harness/` package in the target project

## Project structure

```
skills/
  eval-design/
    SKILL.md                    # Skill definition and workflow
    references/
      architecture-docs.md      # Requirements for docs 1 & 2
      eval-plan.md              # Requirements for doc 3
      golden-dataset.md         # Requirements for doc 4
      langfuse-setup.md         # Requirements for doc 5
      eval-harness.md           # Requirements for doc 6
      html-overview.md          # Requirements for HTML overview
  eval-harness-build/
    SKILL.md                    # Skill definition and workflow
    references/
      modules.md                # Module specs (adapter, judge, metrics, gates, writer)
      notebook.md               # Notebook generation spec
sample docs/                    # Example output from SmartCampus run
  1. Codebase Architecture Overview.md
  2. LLM In-Out Flow.md
  3. eval-plan-full.md
  4. golden-dataset-spec.md
  5. langfuse-setup.md
  6. eval-harness.md
  architecture-eval-overview.html
```

## Sample run: SmartCampus

The `sample docs/` directory contains a complete end-to-end run against [SmartCampus](https://github.com/user/smartcampus) — a multi-venue school video analytics platform using Gemini for behaviour detection, D-FINE for person tracking, and InsightFace for face recognition. The run demonstrates:

- Multi-stage pipeline classification (chunk → Gemini → merge → combine → summarize → embed → search)
- Scenario dimension stratification by venue type
- Fairness track for face recognition of minors
- Full adversarial track (end-user untrusted input tier)
- 7-stage Layer 1 component eval with per-stage metrics
- LLM-as-judge rubrics with worked examples
- Eval harness spec with Mode 1–3 automation groups

## How it works

### eval-design workflow

1. **Understand the architecture** — explores entry points, routes, models, configs, git history
2. **Classify system shape** — pipeline complexity and scenario dimensions
3. **Identify eval-relevant properties** — output schema, async patterns, deterministic vs non-deterministic components, safety profile
4. **Generate deliverables** — each document follows detailed reference specs
5. **Self-verify** — audits completeness, cross-document consistency, and internal correctness before finishing

### eval-harness-build workflow

1. **Locate & validate eval design docs** — finds harness spec, eval plan, golden dataset spec, and Langfuse setup
2. **Discover pipeline contract** — identifies how to start jobs, detect completion, fetch results, and authenticate
3. **Generate module set** — produces the `eval_harness/` package with all components
4. **Generate Mode 1 notebook** — creates the interactive golden-eval Jupyter notebook
5. **Smoke-test offline logic** — verifies dataset loading, judge validation, metric math, gates, and local writer
6. **README + honest handoff** — documents what works, what remains unverified, and what to replace
