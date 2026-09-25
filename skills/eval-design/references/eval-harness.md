# Step 6: Eval harness spec

Write this document only from an approved rubric and `evaluator-register.json`. Inputs are the registers, not a generic judge suite.

The generated runner defaults to diagnostic execution (`decision_eligible=false`, no release verdict). Explicit gate mode preflights the Eval Spec (`READY`, and trial contract `k=1` with `runs == 1`), approval, accepted evaluator versions, Product consequence, and coverage, and exits nonzero with a blocked reason before quality scoring when any of those are missing. Zero checks are a blocked configuration, not a pass.

Shadow scores stay off the gate. A required unaccepted criterion blocks the decision. k=1 through the real entrypoint is the first run.

Preserve the three modes below. Mode 1 is decision evidence only for accepted evaluators. Mode 2 is diagnostic. Mode 3 remains a production proxy and must not use decision-metric names.

Produce `6. eval-harness.md` with sections 6A–6K. This is the **executable counterpart** to docs 3–5: docs 3–5 define *what* to measure, *what data* to measure against, and *where* evidence lives; this document defines *what actually runs the measurement*, how runs are triggered automatically, and where the automation boundary sits.

**Audience note:** engineers who will build the harness plus the DS who will operate it. Write it so the repo layout, CLI, and CI wiring can be implemented directly.

**Mandatory-content rule.** Every section below is required unless a Step 1/2 verdict prunes it; pruned sections must say **"N/A — [reason]"**, never be silently dropped.

**Adaptivity:**
- **Single-stage system** (per Step 1) → Mode 2 collapses to the one model call plus whatever pre/post steps genuinely exist; the automation-group table shrinks accordingly. Say so explicitly.
- **System not yet in production** → Mode 3 is still specified, but marked "post-launch requirement — no traffic to audit yet".
- **No CI pipeline exists** → describe the target CI integration and mark it as an implementation requirement, not current state.

## 6A. Mental model

Open with the three-line mental model and the responsibility table, in the project's own vocabulary:

```
Langfuse      = experiment notebook / dashboard / evidence store
Eval harness  = machine that actually runs the experiment or audit
Actual app    = production system being evaluated
```

| Component | Responsibility | How it uses Langfuse |
|---|---|---|
| Actual app | Runs production/staging traffic | Logs traces, spans, metadata, costs, latency |
| Eval harness | Runs controlled evals, component diagnostics, production audits | Loads dataset items, creates experiment runs, links traces, writes scores |
| Langfuse UI | Lets humans inspect and compare | Traces, scores, dashboards, run comparisons |

State the **no-duplication principle** with a bad/good pattern: the harness must call the same pipeline code (or the same service endpoint) production uses — never a simplified reimplementation of app logic. Explain *why* the harness is nonetheless a separate codebase: different concerns (controlled replay, baseline-vs-candidate comparison, judge execution, metric computation, CIs, fairness slices, CI gates, reproducibility).

## 6B. Three harness modes

| Mode | Input | Ground truth? | Primary purpose | Typical output |
|---|---|---:|---|---|
| **1. Layer 2 golden eval** | Approved items (doc 4); local files by default | Yes, for accepted criteria | Diagnostic by default; release gate only after preflight | Criterion results, provenance; release verdict only in an explicit passing gate mode |
| **2. Layer 1 component eval** | Per-stage datasets/fixtures (6D) | Yes (per stage) | Diagnostics — which stage is the bottleneck; per-component gates | Stage metrics vs eval-plan 3C targets |
| **3. Post-production judge audit** | Sampled production traces / completed cases | No | Quality monitoring, drift detection, triage | Judge-derived **proxy** scores, alerts, review queues |

Make the ground-truth distinction explicit: Modes 1–2 are controlled evals against labels; Mode 3's judge is a **proxy evaluator** whose scores are monitoring signals, never gate metrics (naming rules in 6G).

## 6C. Mode 1 — Layer 2 golden eval (release gate)

Spell out the run loop as numbered pseudocode, populated with this project's names:

```
For each item in [golden dataset vX]:
  1. Load input, config, and expected annotations
  2. Run the real Layer 2 pipeline (same code path as production)
  3. Capture the trace in Langfuse (environment=eval_run)
  4. Run the judge(s) in the harness (6G)
  5. Derive item-level metrics deterministically from judge output + matching logic
  6. Write scores to the linked trace / dataset run
After all items:
  7. Aggregate by [scenario dimension], tier, positive/negative, fairness slice
  8. Compute CIs (eval-plan 3H)
  9. Check ship gates on lower CI bounds
  10. Write run-level summary scores to Langfuse
  11. Exit 0 (pass) / 1 (fail) — CI consumes the exit code
```

Cover the N-run consistency requirement (eval-plan 3H): N named runs, agreement rate computed across them.

## 6D. Mode 2 — Layer 1 component eval (diagnostics)

Layer 1 automation is **not one mechanism**. Classify every Layer 1 stage from eval-plan 3C into one of these automation groups (a group with no stages is omitted with "N/A"); every 3C stage must land in exactly one group:

| Group | Which stages qualify | Mechanism | Cost | Where the dataset lives |
|---|---|---|---|---|
| **A — Deterministic fixtures** | Orchestration stages (chunking, merge, dedup, routing) whose correct output is derivable from synthetic inputs | Fixture files + assertions, parameterized like unit tests | Seconds, free | In-repo (`evals/fixtures/...`) |
| **B — LLM component evals** | LLM stages with their own golden component dataset | Real model calls through the same code path the pipeline uses; deterministic scoring against labels where possible | Minutes, real token cost | Langfuse Datasets (versioned) |
| **C — Classic ML metrics** | Deterministic models (detection, matching, embedding) | Annotated media → standard metrics (mAP, FAR/FRR, precision/recall) — no LLM anywhere | Minutes, possible GPU cost | Object storage media + in-repo manifest |
| **D — Pinned-upstream evals** | Stages whose input quality is bounded by an upstream stage (retrieval over generated captions, RAG over generated chunks) | Run against a **frozen snapshot** of upstream output so a regression isolates to this layer | Minutes, cheap | Langfuse Dataset for queries/labels + versioned snapshot artifact |

Then specify the **trigger routing** — the part that makes Layer 1 hands-off:

1. **Change-based routing (CI, per PR).** A stage map (`stage_map.yaml` or equivalent) from changed paths to stages, as a table populated with this repo's real paths. Group A always runs (it is free); other stages run only when routed.
2. **Regression-based routing (from Layer 2).** Encode the eval-plan 3D error-analysis tree as a routing table: failing Layer 2 metric → auto-enqueued Layer 1 diagnostic run, results written to Langfuse under a linked run name — so human error analysis starts with component data already gathered. The table's branches must match 3D one-for-one.
3. **Schedule.** State what the periodic (e.g. monthly) regression includes.

## 6E. Mode 3 — Post-production judge audit (proxy monitoring)

*(If the system has no production traffic yet, keep the section and mark it "post-launch requirement".)*

Spell out the audit loop (load sampled trace/case → run judge with the production rubric, no ground truth → derive proxy signals → write scores to the production trace → aggregate trends → alert/queue).

**Proxy naming rule (mandatory):** without ground truth the judge is a proxy evaluator. Proxy scores get their own names (e.g. `judge_pass_fail`, `judge_missing_event_suspected`, `judge_false_positive_suspected`, `judge_confidence`); `eval_*` / `ground_truth_*` names are **reserved** for Mode 1/2 runs with labels and must never be emitted here. The proxy names must appear in the Langfuse doc's score design (5D).

**Sampling policy (mandatory — judging production traffic with a strong model is expensive):** a table covering at least:
- strata judged at 100% (always include user-flagged traces — never sample away complaints — plus any suspicious tags from 5C);
- the stratified random sample rate for the remainder (state a starting value);
- a per-scenario floor (minimum judged traces per period);
- a budget cap rule that downsamples only the random stratum, never the tagged strata.

**Escalation:** a proxy drift signal never gates anything by itself — it triggers a **targeted Mode 1 run** for the affected scenario (this row must also appear in eval-plan 3E and the alert in 5G).

## 6F. Langfuse configuration

- **Environment separation:** `production | staging | eval_run` via the environment field already defined in 5C.
- **Datasets table:** which datasets live in Langfuse (golden set, LLM component sets, query/label sets) vs in-repo fixtures (Group A) vs object-storage manifests (Group C), with **versioned names** (`golden-v1`, `stage-N-…-v1`). Gates compare runs on the same dataset version.
- **Dataset item schema** for the golden set: `input` (pointer to source + config), `expected_output` (annotations per doc 4), `metadata` (scenario dimension, positive/negative, priority tier, fairness axes).
- **Experiment runs:** controlled evals run as Langfuse Dataset Runs — the harness runs the real pipeline inside the dataset-item context so each trace links to both the item and the named run. Give a run-naming convention embedding date, template/prompt version, model, and run index (for N-run consistency), plus a diagnostic-run naming pattern for 6D's regression router.

## 6G. Judge execution

- **Where the judge runs:** in the harness whenever the judge input includes a non-text modality (video, audio, images) or ground-truth files — Langfuse-managed evaluators operate on trace text and cannot execute those. Text-only judges *may* run as managed evaluators; state the choice per judge. Langfuse stores judge scores; for multimodal judges it never executes them.
- **Deterministic derivation:** judge output is strict JSON (validated); all judge-derived metrics are computed by harness code from that JSON — the judge never computes a metric itself. This holds for every LLM route; each approved criterion has its own route and version, and an unaccepted route stays diagnostic.
- **Canonical naming registry:** 5D is the score registry of record; this section restates only the rules — `eval_*`/`ground_truth_*` require labels; proxy names for Mode 3; one canonical name per dimension (no synonyms drifting between docs); judge rationale attached as the Langfuse score **comment**, not a separate score.

## 6H. Aggregates, gates, and CI

Per-trace scores are point values (5D). The harness computes run-level and slice-level aggregates with CIs (eval-plan 3H) and enforces the ship gates (lower CI bound ≥ target, per scenario and tier). Close with the division of labor:

```
Harness  = computes metrics and enforces gates (exit 0 = pass, exit 1 = fail)
Langfuse = stores and visualizes the gate evidence (Dashboard 3)
CI       = blocks merge/release when the harness exits non-zero
```

Langfuse never enforces a gate; Mode 3 aggregates are never gates.

## 6I. Automation boundary

**Mandatory section — this is the contract for what the harness removes and what it cannot.** Three tiers, each populated with this system's specifics:

- **Fully automated (no human in the loop):** Group A fixture evals per PR; change-based routing; Mode 1 runs end-to-end (replay, judge calls, metric derivation, CIs, gate exit codes); regression-based diagnostic routing; Mode 3 sampled audits and drift alerts; all score writes and dashboard population.
- **Automated execution, human-triggered decision:** re-baselining / noise-band re-establishment after model updates; pinned-snapshot rebuilds (Group D); dataset version promotion; judge or judge-model changes (mechanical re-calibration run, human-reviewed decision).
- **Never automatable (human-only, permanently):** ground-truth creation and labeling (all datasets, all groups, fairness-axis annotation); judge calibration against human raters (and re-calibration on judge change); adversarial case crafting; in-app human verification/flagging; root-cause diagnosis (the harness delivers pre-gathered component data; naming the cause and choosing the fix is human); ship/no-ship sign-off (gates inform the release decision, they do not replace it); dataset composition decisions (the harness may auto-surface candidates from flagged traces or judge-suspected misses — a human decides what enters and labels it).

The framing sentence to preserve: **the harness automates execution, routing, and alerting — never labeling, calibration, or judgment.**

## 6J. Repository layout and interaction modes

Suggest a concrete layout (adapt names to the repo's conventions):

```
evals/
  run_layer2.py            # Mode 1 CLI
  run_layer1.py            # Mode 2 CLI (--stage ...)
  run_postprod_judge.py    # Mode 3 CLI
  stage_map.yaml           # 6D routing tables
  dataset_loader.py        # Langfuse dataset items (Modes 1/2)
  trace_loader.py          # sampled production traces (Mode 3)
  pipeline_adapter.py      # calls the real app pipeline / per-stage code paths
  judge_runner.py          # judge calls (6G)
  metrics.py               # metric + CI computation
  langfuse_writer.py       # runs, trace links, score writes
  gates.py                 # pass/fail + regression router hook
  fixtures/                # Group A fixtures, Group C manifests
```

Cover the four interaction modes with concrete example invocations: **CLI** (per-run flags: dataset, run name, candidate config; Mode 3 flags: environment, time window), **CI/CD gate** (what runs on PR vs release candidate, exit-code contract), **notebook/analyst** (a callable that runs small slices with filters), **scheduled jobs** (nightly Mode 3, periodic Mode 1 regression).

## 6K. Key takeaways

Close with ≤8 bullets restating: same-code-path principle; the three modes; per-group Layer 1 automation with routing; judge-in-harness and the proxy naming rule; harness-enforces/Langfuse-displays/CI-blocks; the automation boundary one-liner.

---

## Consistency obligations (checked in Step 8)

- Every Layer 1 stage in eval-plan 3C appears in **exactly one** 6D automation group, and the change-based stage map covers every stage.
- The regression-router table branches match the eval-plan 3D error-analysis tree one-for-one.
- Every score name written by the harness exists in the Langfuse doc's 5D registry (including Mode 3 proxy scores); no synonym drift (one canonical name per dimension across docs 3, 5, 6).
- Dataset names/versions in 6F match the golden-dataset spec (doc 4); gate thresholds referenced in 6H match eval-plan 3B/3G/3H — reference, don't restate different values.
- The eval-plan 3E cadence rows for per-PR CI runs, the scheduled Mode 3 audit, and the proxy-drift escalation match what 6D/6E define; the 5G alert table contains the drift alert 6E escalates from.
- Judge model, scale, and calibration are referenced from eval-plan 3B — not redefined here.

---

## Implementing the spec

This document is design-only. To generate the working implementation (the
`eval_harness/` Python package + Mode 1 notebook, with the Langfuse bypass),
invoke the **`eval-harness-build`** skill — it consumes this doc plus the eval
plan and emits the code.
