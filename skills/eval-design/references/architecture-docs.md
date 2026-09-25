# Step 1 deliverables: architecture overview & LLM in-out flow documents

Step 1's codebase exploration produces two standalone documents. Downstream design may cite them. Keep them factual: observed behaviour and configuration only.

Code-derived thresholds, prompts, and schemas are implementation facts. They are not Product intent, approved quality bars, or decision authority. When a number comes from code, label it `observed` and cite the file. Do not copy it into a release gate unless `product-expectations.md` shows that Product approved that consequence.

These documents are allowed in every workflow state, including `NEEDS_PRODUCT_DECISION`. They do not contain a scoring rubric, judge prompt, or ship gate.

Both documents follow the header convention from SKILL.md (title + `Version: Draft 1.0 — [date]` line).

---

## Document 1: `1. Codebase Architecture Overview.md`

Audience: someone new to the repo who needs the full picture in one read. Everything here is discovered from the code (README, configs, routers, deploy files, git log) — never invented.

Required sections:

### What is [project]?
One paragraph naming the system and its purpose, then a bullet list of the primary user-facing capabilities/outputs (each bolded with a short explanation).

### High-level architecture
- An ASCII diagram of the service tiers and their connections: client → gateway/BFF → backend → backing services (DBs, queues, model services). Show ports, paths, and service names from the actual deploy config.
- Callouts (blockquote) for the load-bearing constraints (e.g. "frontend talks only to the BFF").
- A **Design philosophy** bullet list extracted from the repo's own docs/config (serverless, CSR-only, async patterns, managed services — whatever actually holds).

### Repository structure
- An annotated directory tree (top 2 levels, with one-line comments per entry).
- A table: layer → tech stack → package manager/tooling.

### Key subsystems
Numbered subsections for each subsystem that matters to the AI pipeline, discovered from the code:
1. The core domain abstraction (templates, rulesets, routing config — whatever configures model behaviour).
2. The processing pipeline (stages, async mechanism, modes).
3. An inventory table of backend modules/routers with one-line purposes (link the file paths).
4. Model-serving components (sidecars, external APIs) and how they deploy.
5. Cloud/infrastructure resources table (project, region, DBs, buckets, queues — actual values from config).

### Recent activity
From `git log` (per Step 1 discovery prompt 9): recent commits table + a short note on what the recent work means for eval design (new features that need coverage, refactors that invalidate baselines).

**Adaptivity:** for a single-service or backend-only project, collapse the tier diagram to what exists and drop the frontend/BFF rows — say so rather than padding.

---

## Document 2: `2. LLM In-Out Flow.md`

Audience: the data scientist designing evals — this is the precise I/O contract of every model in the system. Everything must come from reading the actual code (request builders, schemas, prompt templates), with exact field names and types.

Required sections:

### Core code locations
Table: file path → purpose, covering the pipeline orchestrator, prompt construction, output schemas, embedding/indexing services, and any model sidecars.

### Data flow diagram
ASCII diagram tracing one job from user input through every pipeline stage to storage, marking where each model is called and what crosses each boundary (IN/OUT annotations on the model boxes). Show parallel/independent pipelines separately and label them as such.

### Per-model In/Out
One subsection per model (LLM calls, embedding models, deterministic models/sidecars). For each:
- **Input:** exact request construction — content parts, prompts, and the full inference config (temperature, seed, resolution, schema binding, thinking level — whatever the code sets).
- **Prompt construction:** every placeholder/template field the prompt builder interpolates, with one line on what fills it. This is the ground truth for the eval plan's template-versioning and injection-surface analysis.
- **Output:** the exact structured output schema (paste the model/class definition), including shared sub-models and per-scenario variants.
- **Token/usage extraction** where applicable.

### Hosting distinction
If the system mixes managed-API models and self-hosted models: table comparing who runs each model, where, cost model, and why. Omit if all models are one kind — say so.

### What gets stored where
Tables per storage system (DB collections, object-store paths, vector indexes): key fields, ID formats, and which pipeline stage writes them. This is what the Langfuse setup's trace_id-glue section builds on.

### Summary table
One row per model/component: INPUT → OUTPUT, compressed to a single line each.

### Pipeline relationships and modes
- How the pipelines relate (chained vs independent), where results surface to users, and any merge points. If pipelines are independent, state it explicitly — it means separate eval tracks.
- Pipeline modes table and the key transformations applied between model output and stored results (timestamp offsetting, stitching/dedup rules with their exact thresholds, ID formats). These thresholds feed the eval plan's post-processing failure modes verbatim — quote the real values from code.

**Adaptivity:** a single-model system produces the same document with one Per-model section and no pipeline-relationship section (state "single model, no parallel pipelines"). Do not fabricate stages.

---

## Consistency obligations (checked in Step 8)

- The pipeline stages in doc 2's data-flow diagram must match, one-for-one, the Layer 1 stages in the eval plan (3C) and the spans in the Langfuse trace structure (5B).
- Thresholds and config values quoted in doc 2 (chunk duration, merge gaps, similarity cutoffs) must match the values the eval plan and dataset spec reference — one source of truth: the code.
- The prompt placeholders listed in doc 2 define the injection surface the eval plan's adversarial track (3G) analyses; the two must agree on what is author-controlled vs end-user-controlled.
