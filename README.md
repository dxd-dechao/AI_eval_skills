# AI Eval Skills

Two skills that take an AI/LLM project from Product expectations through an approved rubric to a fail-closed eval harness. They stop when the next decision is not in evidence. They do not invent Product intent, approvers, or thresholds.

The sequence follows the Eval Playbook's Product-to-evaluation bridge (Stage 00 and Stage 03): Product supplies expectations → atomic binary rubric → Product/domain and named-expert approval → one evaluator per accepted criterion → evaluator verification → decision use.

## Skills

### 1. `eval-design` — Generate the eval design

Point it at a repo root. What it writes depends on readiness. Product/domain supplies expectations (the PM coordinates). Data science or the AI drafter writes atomic binary criteria. Product/domain and the named expert test, approve, and version the rubric. Each approved criterion gets its own evaluator route:

- **Deterministic** — fully specified and machine-observable
- **Named expert** — interpretive, evolving, rare, or needing named accountability
- **Optional LLM** — interpretive, stable, and repeated at scale (with a stated volume reason)

That evaluator is accepted separately, with its own evidence, before it can support a decision.

| State | What you get |
|-------|----------------|
| No usable Product expectations | Intake (`product-expectations.md` + JSON) marked **BLOCKED — Product decision required**, plus factual architecture notes. No rubric, judge, threshold, or gate. |
| Expectations supplied, rubric not approved | Candidate binary criteria and a review packet. Stops before evaluators. |
| Rubric approved | Per-criterion routes, dataset split, Langfuse registry, harness spec, HTML. Unaccepted evaluators stay diagnostic. |

Each state writes readable Markdown beside a JSON register the harness can validate: `product-expectations.json`, `rubric-register.json`, `evaluator-register.json`, plus separately versioned development and held-out manifests.

Factual architecture documents (when code is explored):

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | **Codebase Architecture Overview** | System purpose, service tiers, repo structure, subsystems, recent activity |
| 2 | **LLM In-Out Flow** | Per-model prompt/schema contracts, data-flow diagrams, inference config |
| 3 | **Eval Plan** | Two-layer eval: end-to-end shipping gate (Layer 2) + per-component diagnostics (Layer 1), with per-criterion routing, safety/robustness/fairness tracks, and statistical rigor |
| 4 | **Golden Dataset Spec** | Goal-driven composition, annotation schema, matching logic, acceptance criteria, phased rollout |
| 5 | **Langfuse Setup Spec** | Trace structure, metadata, scores, dashboards, alerts, integration points |
| 6 | **Eval Harness Spec** | Harness modes, automation groups, module architecture, Langfuse integration, gate semantics |
| — | **Stakeholder HTML Overview** | Single-file visual summary styled to match the project's own frontend |

### 2. `eval-harness-build` — Implement the eval harness

Reads the registers in the target repo (it does not need the design skill installed) and generates a harness only when approval evidence is present. Missing approval returns `eval_harness/BLOCKED.md`. An explicit request for neutral plumbing may add an adapter and local writer only — no evaluators, judge prompts, thresholds, or gates.

When the registers are ready it produces:

- **`eval_harness/` package** — adapter that calls the real app, contract preflight, route-specific evaluators, metrics that keep Pass/Fail, Not applicable, and Unscorable apart, fail-closed gates, and a local results writer with a total Langfuse bypass
- **Diagnostic notebook** — one configure cell; default `MODE=diagnostic`, `LIMIT=1`, `RUNS=1`; a thin slice is not a release pass
- **Offline checks** — approval and version refusal, shadow isolation, denominator counts, disjoint held-out data, metric arithmetic, local writer round-trip

Invariants: diagnostic success can exit 0 with `decision_eligible=false`; gate mode refuses bad config before scoring; empty checks do not pass; confidence intervals only on aggregates; Langfuse is never imported when bypassed.

## Key design principles

- **Product first** — Product/domain owns intended behaviour; missing decisions are recorded as `NEEDS_PRODUCT_DECISION` with a named holder, never filled in by the skill
- **Rubric before evaluator** — approving a rubric and accepting an evaluator are two separate checks; development examples are never reused as held-out validation
- **Fail closed** — diagnostic runs never produce a release verdict; gate mode refuses missing approval, versions, or evidence before scoring
- **Adaptive, not templated** — classifies each system on pipeline shape (single-stage vs multi-stage) and scenario dimensions, then expands or prunes sections accordingly
- **Never a single aggregate** — metrics are always stratified by the real variation axis
- **Cross-document consistency** — shared numbers, axes, and pipeline stages are verified across all six deliverables
- **Safety and fairness built in** — untrusted-input tier, demographic axes, and costly failure direction are identified from code and carry through to candidate criteria and dataset segments; any gate on them needs a Product-approved rule

## Best fit

Detection/classification-style LLM pipelines — systems where video, text, or documents flow through one or more AI models and produce structured outputs (incidents, classifications, scores, matches).

Examples: school safety analytics, content moderation, document processing, support ticket routing, medical triage.

## Usage

### As Claude Code skills

Copy the `skills/` directory into your Claude Code skills path, then invoke from the root of any AI project:

```
/eval-design          # intake, rubric review, or routing — whichever the evidence supports
/eval-harness-build   # harness from approved registers, or a blocker
```

Both skills read the codebase for facts. They ask, in a decision log, when Product intent, ownership, or approval is missing.

### Recommended workflow

1. Run `/eval-design` and finish the Product intake before any rubric is treated as approved
2. Product/domain and the named expert approve a rubric version
3. Run `/eval-harness-build` only after that approval is in the registers

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
      product-expectations.md   # Intake, rubric review, routing contract
  eval-harness-build/
    SKILL.md                    # Skill definition and workflow
    references/
      modules.md                # Module specs (contract preflight, routing, evaluators, metrics, gates, writer)
      notebook.md               # Notebook generation spec
tests/forward/                  # Forward checks: prepare temp repos, verify generated artifacts
  README.md
  prepare_cases.py              # Cases A–D (no expectations, unapproved, approved, unrouted)
  verify_cases.py
sample docs/                    # Example output from SmartCampus run
  0. product-expectations-and-rubric-review.md
  1. Codebase Architecture Overview.md
  2. LLM In-Out Flow.md
  3. eval-plan-full.md
  4. golden-dataset-spec.md
  5. langfuse-setup.md
  6. eval-harness.md
  architecture-eval-overview.html
```

## Sample run: SmartCampus

The `sample docs/` directory contains a complete end-to-end run against SmartCampus — a multi-venue school video analytics platform using Gemini for behaviour detection, D-FINE for person tracking, and InsightFace for face recognition. The run demonstrates:

- Multi-stage pipeline classification (chunk → Gemini → merge → combine → summarize → embed → search)
- Scenario dimension stratification by venue type
- Fairness track for face recognition of minors
- Full adversarial track (end-user untrusted input tier)
- 7-stage Layer 1 component eval with per-stage metrics
- Illustrative candidate criteria and routes for this product only — not a universal judge suite, and not evidence that SmartCampus approved those thresholds

## Checking the skills

Structural check (needs PyYAML in a scratch virtualenv):

```sh
python3 /path/to/skill-creator/scripts/quick_validate.py skills/eval-design
python3 /path/to/skill-creator/scripts/quick_validate.py skills/eval-harness-build
```

Forward checks live in `tests/forward/README.md`. They prepare temporary repos for four states (A no expectations, B unapproved rubric, C approved and routed, D approved but unrouted), then verify the generated artifacts and exercise the generated harness. Each probe is recorded separately; missing artifacts and errors count as failures. They do not run inside this checkout.

## How it works

### eval-design workflow

1. **Product intake** — expectations packet, or a blocker when decisions are missing
2. **Factual discovery** — architecture from code; thresholds stay observed facts
3. **Rubric review** — candidate binary criteria and a pending review record
4. **Routing** — after approval, one evaluator route per criterion, acceptance recorded separately
5. **Self-verify** — only the artifacts that state allows

### eval-harness-build workflow

1. **Read registers** — block when approval, version, or acceptance evidence is missing
2. **Discover the real entrypoint** — the adapter calls it
3. **Generate route-specific modules** — diagnostic by default; gate mode fail-closed
4. **Notebook** — limit 1, diagnostic, no release implication
5. **Offline checks** — preflight, denominators, shadow isolation, local writer
6. **README** — what ran and what did not
