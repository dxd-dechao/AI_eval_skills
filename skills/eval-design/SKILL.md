---
name: eval-design
description: >-
  Produce a complete eval and observability design for an AI/LLM system by
  exploring its codebase: a two-layer eval plan (end-to-end + component,
  LLM-as-judge, safety/robustness/fairness tracks, statistical rigor), a golden
  dataset spec, a Langfuse observability setup, an eval harness spec (runner,
  automation/routing, CI gates, post-production judge audits), and a
  stakeholder-facing HTML architecture overview. Use when the user asks to
  design evals, an evaluation strategy or benchmark, a golden dataset, an eval
  harness or eval automation, LLM observability or tracing, or Langfuse
  instrumentation for a project.
---

# Eval & Observability Design from Codebase

Invoke from the root of a project codebase. The deliverables are six markdown documents plus a visual HTML summary page (see Output files below).

## Workflow

Copy this checklist and track progress:

```
- [ ] Step 1: Understand the architecture — record the system-shape verdict,
      write docs 1 + 2 → read references/architecture-docs.md
- [ ] Step 2: Identify eval-relevant properties
- [ ] Step 3: Eval plan → read references/eval-plan.md
- [ ] Step 4: Golden dataset spec → read references/golden-dataset.md
- [ ] Step 5: Langfuse setup → read references/langfuse-setup.md
- [ ] Step 6: Eval harness spec → read references/eval-harness.md
- [ ] Step 7: Architecture & roadmap HTML → read references/html-overview.md
- [ ] Step 8: Self-verification — fix every failure before finishing
```

Steps 1, 2, and 8 are defined in this file. Read each reference file when you reach its step — they carry the full section-by-section requirements.

---

## Step 1: Understand the architecture

Explore the codebase and answer these questions. Do NOT ask the user — find the answers in the code.

### Discovery prompts

1. **What does this system do?** (Read README, package.json, main entry points, route handlers)
2. **What is the tech stack?** (Languages, frameworks, cloud services, databases, APIs)
3. **What are the tiers?** (Frontend, BFF/gateway, backend, workers, external services)
4. **What AI/ML models are used?** For each model:
   - Is it an LLM (non-deterministic) or a traditional model (deterministic)?
   - What are its inputs and outputs?
   - Is it called via API, sidecar service, or embedded?
5. **What is the data pipeline?** (How does data flow from user input → model → output → user?)
6. **Are there async/batch processing steps?** (Queues, chunking, parallel workers, aggregation)
7. **What are the venues/scenarios/domains?** (Are there different configurations, templates, or modes that produce different behaviour for different contexts?)
8. **What post-processing exists?** (Merging, triage, synthesis, formatting between raw model output and user-facing results)
9. **What's been shipped recently?** (Check git log for last 2 weeks — what features, fixes, or changes landed?)
10. **What observability exists already?** (Logging, tracing, monitoring — what's instrumented today?)
11. **Does untrusted content reach an LLM prompt?** Classify the surface into one of three tiers — the tier scopes the adversarial track in Step 3:
    - **none** — all prompt content is authored by the dev team;
    - **trusted-author** — content written by admins/config authors (templates, behaviour descriptions, venue context) is interpolated into prompts, but end users cannot inject text;
    - **end-user** — free text, filenames, document content, OCR output, or anything else from end users reaches a prompt.
12. **Does the system make judgments about people?** (Detection, classification, scoring, matching, or ranking of identifiable individuals or groups. Includes face recognition, behaviour attribution, performance scoring, hiring filters, etc.)
13. **Is the system safety-critical?** (Can a wrong output cause physical harm, legal liability, reputational damage to individuals, or denial of opportunity? Define the costliest failure direction: false positive vs false negative.)
14. **What demographic or condition axes matter?** (For people-judging systems: skin tone, age band, gender presentation, lighting/camera conditions, language/dialect, attire/uniform variation, disability status — whichever axes are both present in the population AND could correlate with model error rates.)

### Output

Step 1 produces two standalone documents from the exploration — read [references/architecture-docs.md](references/architecture-docs.md) for their full section-by-section requirements:

- **`1. Codebase Architecture Overview.md`** — what the system is, service-tier diagram, repo structure, key subsystems, infrastructure, recent activity.
- **`2. LLM In-Out Flow.md`** — the exact I/O contract of every model: code locations, data-flow diagram, per-model inputs (prompt construction, inference config) and outputs (schemas), storage layout, pipeline modes and transformation thresholds.

Additionally, write a concise architecture summary (≤1 page, condensed from doc 1) to open the eval plan. Identify:
- The **primary AI task** (e.g., "detect fighting in video", "mark student essays", "classify support tickets")
- The **pipeline stages** from input to output
- The **scenario dimensions** (venue types, user types, document types — whatever axis creates different system behaviour)
- The **deterministic vs non-deterministic components**
- The **safety/fairness profile** (from prompts 11–14): untrusted-input tier? judges-people? safety-critical? which demographic/condition axes?

### Adaptivity gate — decide the system's shape

This skill defaults to a rich multi-stage, multi-scenario pipeline (like a video-analytics platform), but **not every system has that shape**. Before proceeding, classify the system on two axes and carry the decision through every downstream step. Do NOT ask the user — infer from the code.

**Axis 1 — Pipeline shape.** Is there a genuine multi-stage pipeline (chunking, parallel workers, aggregation/merging, multi-call orchestration), or is this effectively a single-stage call (one model invocation, minimal pre/post-processing)?
- **Multi-stage** → keep Layer 1 component eval, boundary/merge failure modes, per-stage tracing, orchestration eval.
- **Single-stage** → collapse Layer 1 to just the model call plus any pre/post step that actually exists. Drop chunking/merge/boundary sections entirely. Say so explicitly ("This system is single-stage; component eval reduces to the model call and output validation").

**Axis 2 — Scenario dimensions.** Is there a real axis that changes system behaviour (venue templates, document types, user tiers, routing modes), or does the system behave uniformly for all inputs?
- **Has scenario dimensions** → stratify every metric by that axis (never a single aggregate); build the scenario × behaviour matrix; add per-scenario dashboards.
- **No scenario dimensions** → do NOT invent one. Report metrics stratified by whatever variation DOES exist (input difficulty, category, length band) or as a single well-characterised distribution if truly uniform. Replace "per scenario dimension" language with the real stratification axis, and state that the system has no scenario dimension.

**Record the verdict** at the top of the architecture summary as an explicit line, e.g.:

```
System shape: single-stage LLM call · no scenario dimensions (stratify by input difficulty)
System shape: multi-stage async pipeline (chunk→gemini→merge→combine) · scenario dimensions = venue_type
```

Every subsequent step (3–6) reads this verdict and simplifies or expands accordingly. When a section says "for each scenario dimension" or "for each pipeline stage", interpret it through this verdict — if the dimension/stage doesn't exist, omit that structure rather than fabricating it, and state the omission explicitly ("N/A — single-stage system").

---

## Step 2: Identify eval-relevant properties

From the architecture, determine the following. Each property may resolve to **"not present"** — that is a valid, expected outcome for simpler systems, and it prunes the corresponding eval structure (per the Step 1 adaptivity gate). When a property prunes a section, the generated document must still say so explicitly — never silently omit.

| Property | How to find it | Impact on eval design |
|----------|---------------|----------------------|
| Output schema complexity | Read the model output types/schemas | Determines annotation schema and what levels to evaluate |
| Scenario dimensions | Read config/templates/routing logic | If present: stratification (never a single number). If absent: stratify by real input variation instead |
| Pipeline stages | Trace data flow through handlers/workers | If multi-stage: Layer 1 component eval scope. If single-stage: Layer 1 collapses to the model call |
| Async/chunking | Look for queue producers/consumers, chunk logic | If present: boundary-related failure modes. If absent: omit boundary/merge sections |
| Deterministic components | Identify non-LLM models (detection, matching, classification) | These get standard ML metrics + proxy monitoring |
| Non-deterministic components | Identify LLM calls | These get template-versioned eval + isolated testing |
| Post-processing | Find aggregation/merge/synthesis logic after model calls | If present: incident-drop failure mode monitoring. If absent: omit |
| User feedback mechanisms | Check frontend for flag/report/rate features | Determines human score flow (omit if no frontend) |
| Untrusted input tier | Discovery prompt 11 | **end-user** → full adversarial track (prompt injection + jailbreak + all other categories). **trusted-author** → reduced track: template-injection, malformed, OOD, and false-positive-trigger categories only. **none** → omit the track |
| Judges people | Discovery prompt 12 | If yes: fairness track applies — all L2 metrics also stratified by demographic/condition axes. If no: omit fairness stratification |
| Safety-critical | Discovery prompt 13 | If yes: define the costly failure direction; gate on that direction's metric, not aggregate. If no: symmetric error weighting acceptable |
| Demographic/condition axes | Discovery prompt 14 | Lists the axes to stratify by in fairness track. Empty = fairness track not applicable. These same axes must appear in the dataset spec's fairness annotation fields and the Langfuse disparity scores — keep the three documents in lockstep |

---

## Steps 3–7: Generate the deliverables

Read each reference file at its step and follow it fully:

- **Step 3 — Eval plan** → [references/eval-plan.md](references/eval-plan.md): layer overview, Layer 2 end-to-end metrics + LLM-as-judge suite, Layer 1 per-stage component eval, error-analysis flow, cadence, ownership, safety/robustness/fairness tracks, statistical rigor.
- **Step 4 — Golden dataset spec** → [references/golden-dataset.md](references/golden-dataset.md): scope, composition (goal-driven segment split), sources, edge cases, annotation schema, matching logic, metrics, acceptance criteria, phased rollout, adversarial & fairness segment, annotation process & tooling.
- **Step 5 — Langfuse setup** → [references/langfuse-setup.md](references/langfuse-setup.md): concept mapping, trace structure, metadata, scores, dashboards, alerts, integration points, misconceptions, phases, full worked trace example.
- **Step 6 — Eval harness spec** → [references/eval-harness.md](references/eval-harness.md): the executable counterpart to docs 3–5 — three harness modes (golden Layer 2, Layer 1 component with automation groups + trigger routing, post-production judge audit), Langfuse dataset/run configuration, judge execution, gates & CI, automation boundary, repo layout.
- **Step 7 — HTML overview** → [references/html-overview.md](references/html-overview.md): derive the visual theme from the project's frontend, then build a single self-contained HTML summary page.

## Output files

The skill produces these files in a `Knowledge/` folder (or equivalent docs location):

| File | Produced in | Content |
|------|-------------|---------|
| `1. Codebase Architecture Overview.md` | Step 1 | System purpose, tier diagram, repo structure, subsystems, infra, recent activity |
| `2. LLM In-Out Flow.md` | Step 1 | Per-model I/O contracts, prompt construction, schemas, storage layout, pipeline modes |
| `3. eval-plan-full.md` | Step 3 | Layer 1 + Layer 2 eval plan with error analysis flow |
| `4. golden-dataset-spec.md` | Step 4 | Dataset composition, annotation schema + process/tooling, metrics, rollout |
| `5. langfuse-setup.md` | Step 5 | Trace structure, metadata, scores, dashboards, alerts, integration |
| `6. eval-harness.md` | Step 6 | Harness modes, Layer 1 automation groups + routing, Langfuse run config, gates & CI, automation boundary |
| `architecture-eval-overview.html` | Step 7 | Visual summary page for review and stakeholder communication |

**Document header convention:** every generated markdown document opens with a title (`#`) followed by a version/date line in this exact form:

```
# [Project] [document name]

Version: Draft 1.0 — [today's date, e.g. Jul 2, 2026]
```

Use the same header on the HTML page (title + version/date visible near the top). This makes every deliverable versionable and dateable for later comparison.

---

## Step 8: Self-verification

Before finishing, audit all seven deliverables against this checklist. Fix every failure — do not report the task complete with open failures.

### 8A. Completeness

- [ ] Every mandatory section, table, and table row required by the reference files is present in each document, or explicitly marked **"N/A — [reason]"**. Silent omission is a failure.
- [ ] Every LLM-as-judge evaluator has a rubric per the rules in references/eval-plan.md (at least the gate-critical judges fully worked with an example at each score level; the rest at minimum stubbed and flagged).
- [ ] The header convention appears on all seven deliverables with today's date.
- [ ] Every adaptivity decision (system shape, track applicability, pruned sections) is stated in the document where the pruned content would have appeared.
- [ ] The harness doc (6) contains all three modes (or an explicit "N/A — [reason]" for a pruned mode) and the automation-boundary section (6I) with all three tiers populated.

### 8B. Cross-document consistency

- [ ] Any number that appears in more than one deliverable — dataset sizes, adversarial counts, metric targets and gates, fairness floors, phase timelines — is identical everywhere. Define each shared number in one document and reference it from the others.
- [ ] The fairness axes listed in the eval plan (3G), the dataset spec's fairness annotation fields (4J), and the Langfuse disparity scores (5D) match exactly — same axes, same levels.
- [ ] Composition-matrix totals in the dataset spec equal the stated segment proportions and grand total.
- [ ] The pipeline stages in doc 2's data-flow diagram match one-for-one the Layer 1 stages (3C) and the Langfuse spans (5B); thresholds/config values quoted in doc 2 match those referenced by the eval plan and dataset spec; the prompt placeholders in doc 2 agree with the adversarial track (3G) on what is author-controlled vs end-user-controlled.
- [ ] Every Layer 1 stage (3C) appears in exactly one harness automation group (6D), and the harness regression-router table matches the 3D error-analysis branches one-for-one.
- [ ] Every score name the harness writes (6C/6E/6G) exists in the Langfuse score registry (5D), including Mode 3 proxy scores; `eval_*`/`ground_truth_*` names appear only in ground-truth modes; one canonical name per dimension — no synonyms across docs 3, 5, 6.
- [ ] The eval-plan cadence table (3E) and the harness triggers (6D routing, 6E schedule/escalation) agree, and the 5G alert table contains the proxy-drift alert that 6E escalates from.

### 8C. Internal correctness

- [ ] Worked examples are arithmetically and logically self-consistent: counts, timestamps, gap/merge decisions, token totals, and score values must all reconcile with each other.
- [ ] No confidence interval is attached to a single-item or per-trace score. CIs belong to aggregate metrics over an eval set (see eval-plan 3H); per-trace Langfuse scores are point values.
- [ ] No "statistically significant" claim is made from a cell below the sample-size table's power for that effect size; underpowered cells are flagged as such.

---

## Principles (embedded in all outputs)

1. **Never report a single aggregate number without stratification.** Stratify by scenario dimension when one exists; otherwise stratify by the real variation axis (difficulty, category, length). Only report a single distribution when the system is genuinely uniform — and say so.
2. **Online monitoring uses proxies. Offline eval uses ground truth.** They complement each other.
3. **In a multi-model pipeline, accuracy is bounded by the weakest upstream model.** Report per-stage.
4. **Template/prompt changes are the most frequent deployments.** Every change passes through the eval gate.
5. **Backward error analysis:** Start at the output, trace back through stages to find root cause.
6. **DS defines what to measure and what good looks like. Engineers build the machinery.**
7. **Synthetic data is for stress testing, not for primary benchmarks.** Ground the benchmark in real conditions.
8. **Trace ID is the glue.** It must link model traces, app results, and human feedback.
9. **Eval levels match output complexity.** Rich outputs need tiered evaluation — not everything is benchmarked at the same depth.
10. **Design for the error analysis, not just the metric.** The metric tells you IF something is wrong. The trace structure tells you WHERE and WHY.
11. **Stratify by who the system affects, and gate on the most harmful error direction.** When the system judges people, report metrics per demographic/condition axis. When errors are asymmetric in harm, the ship gate is on the costly direction — not aggregate F1.
12. **No point estimates without intervals.** Every aggregate metric carries a 95% CI. Ship/no-ship decisions use the confidence bound, not the point estimate.
13. **No regressions declared inside the noise band.** Non-deterministic models have run-to-run variance. Establish the noise band empirically (3H); only trigger error analysis when the drop exceeds it.
14. **Every eval run is reproducible.** Record dataset version, prompt/template version, and model version + config with every run; comparisons are valid only between runs that differ in exactly one of these.
15. **The harness runs the eval; Langfuse stores the evidence.** The harness calls the same production code paths, executes any multimodal judge, computes aggregates, and enforces gates via exit codes that CI blocks on. Langfuse is the record and comparison UI — it never executes a video/audio judge and never enforces a gate.
16. **Automate execution, routing, and alerting — never labeling, calibration, or judgment.** Ground-truth creation, judge calibration against humans, adversarial crafting, root-cause diagnosis, and ship sign-off are permanently human; without ground truth, judge scores are proxy signals and must not borrow ground-truth metric names.
