# AI Eval Skills

A Claude Code skill that reads any AI/LLM project's codebase and generates a complete eval + observability design — no questions asked.

## What it does

Point it at a repo root and it produces **six deliverables**, fully adapted to the system's actual architecture:

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | **Codebase Architecture Overview** | System purpose, service tiers, repo structure, subsystems, recent activity |
| 2 | **LLM In-Out Flow** | Per-model prompt/schema contracts, data-flow diagrams, inference config |
| 3 | **Eval Plan** | Two-layer eval: end-to-end shipping gate (Layer 2) + per-component diagnostics (Layer 1), with LLM-as-judge rubrics, safety/robustness/fairness tracks, and statistical rigor |
| 4 | **Golden Dataset Spec** | Goal-driven composition, annotation schema, matching logic, acceptance criteria, phased rollout |
| 5 | **Langfuse Setup Spec** | Trace structure, metadata, scores, dashboards, alerts, integration points |
| 6 | **Stakeholder HTML Overview** | Single-file visual summary styled to match the project's own frontend |

## Key design principles

- **Adaptive, not templated** — classifies each system on pipeline shape (single-stage vs multi-stage) and scenario dimensions, then expands or prunes sections accordingly
- **Never a single aggregate** — metrics are always stratified by the real variation axis
- **Cross-document consistency** — shared numbers, axes, and pipeline stages are verified across all six deliverables
- **Safety and fairness built in** — untrusted-input tier, demographic axes, and costly failure direction are identified from code and carry through to eval gates and dataset segments

## Best fit

Detection/classification-style LLM pipelines — systems where video, text, or documents flow through one or more AI models and produce structured outputs (incidents, classifications, scores, matches).

Examples: school safety analytics, content moderation, document processing, support ticket routing, medical triage.

## Usage

### As a Claude Code skill

Copy the `skills/eval-design/` directory into your Claude Code skills path, then invoke from the root of any AI project:

```
/eval-design
```

The skill runs autonomously — it explores the codebase, discovers the architecture, and writes all six documents without asking questions.

### Output location

Deliverables are written to a `Knowledge/` folder (or equivalent docs location) in the target project.

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
      html-overview.md          # Requirements for doc 6
sample docs/                    # Example output from SmartCampus run
  1. Codebase Architecture Overview.md
  2. LLM In-Out Flow.md
  3. eval-plan-full.md
  4. golden-dataset-spec.md
  5. langfuse-setup.md
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

## How it works (workflow)

1. **Understand the architecture** — explores entry points, routes, models, configs, git history
2. **Classify system shape** — pipeline complexity and scenario dimensions
3. **Identify eval-relevant properties** — output schema, async patterns, deterministic vs non-deterministic components, safety profile
4. **Generate deliverables** — each document follows detailed reference specs
5. **Self-verify** — audits completeness, cross-document consistency, and internal correctness before finishing
