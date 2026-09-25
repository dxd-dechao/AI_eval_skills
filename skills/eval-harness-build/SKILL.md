---
name: eval-harness-build
description: >-
  Generate a Python eval harness from an approved rubric and evaluator
  register: route-specific deterministic, human, and optional LLM evaluators,
  fail-closed decision gates, and a diagnostic-by-default notebook. Gate mode
  also requires a READY Eval Spec whose trial contract is k=1 with runs 1.
  Stops with an actionable blocker when the Eval Spec, Product expectations,
  or rubric approval are missing. Use when the user asks to build, scaffold,
  or implement an eval harness, eval runner, or golden-eval notebook.
---

# Eval harness builder

Turns approved evaluation design into a Python package under `eval_harness/` plus a diagnostic notebook. Invoke from the project root.

This skill does not need `eval-design` to be installed. It enforces the same stop contract from the files in the target repo. Missing approval is a blocker, not a prompt to invent a rubric.

Neutral execution plumbing (adapter, local writer, config shell, no evaluators) is produced only when the user explicitly asks for it despite incomplete approval. That exception never includes evaluators, judge prompts, metric thresholds, or release gates.

## Workflow

```
- [ ] Step 1: Read registers and stop if they are not ready
- [ ] Step 2: Discover the real application entrypoint
- [ ] Step 3: Generate modules → read references/modules.md
- [ ] Step 4: Generate the notebook → read references/notebook.md
- [ ] Step 5: Offline checks — must pass before finishing
- [ ] Step 6: README with what was and was not verified
```

## Step 1: Readiness

Look in `Knowledge/` (or the project's docs directory) for:

- `eval-spec.json` (`schema_version` `product-eval-contract/1`)
- `product-expectations.json` (`schema_version` `product-eval-contract/1`)
- `rubric-register.json`
- `evaluator-register.json` when the rubric claims approval

**Stop with a blocker file** `eval_harness/BLOCKED.md` and do not generate evaluators when any of these is true:

- expectations are missing, or `state` is `NEEDS_PRODUCT_DECISION`
- rubric register is missing, or `review.approval_state` is not an approved value supplied by the source packet
- a route is missing `criterion_id`, `criterion_version`, `evaluator_id`, `evaluator_version`, or mismatches the rubric version
- acceptance is claimed with a bare `approved: true` / `validated: true` and no evidence record

The blocker states which file and field is missing and which human action unblocks it. Exit the skill there.

If the user explicitly requests neutral plumbing anyway, generate only `config.py`, `pipeline_adapter.py`, `langfuse_writer.py`, and a README that repeats the blocker. No `evaluators/`, no judge prompt, no `gates.py` release logic, no thresholds.

When registers are ready, implement only the routes they contain. An unaccepted route is generated as diagnostic/shadow code and cannot feed a gate.

## Step 2: Application entrypoint

Find how production starts one unit of work. The adapter imports or calls that entrypoint. It does not reimplement the product. Record the file and symbol in the adapter docstring. Default the runner to one call (`limit=1`, `runs=1`).

## Step 3: Modules

Read [references/modules.md](references/modules.md) and generate the package it specifies, including the top-level `Summary` aggregates and the per-route acceptance-evidence minimums. Conventional modules for contract validation and routing live in the consuming project, not in this skill repository.

## Step 4: Notebook

Read [references/notebook.md](references/notebook.md). Default execution is diagnostic. A thin slice does not imply a release pass.

## Step 5: Offline checks

In a scratch environment, without network and without a live model:

- contract validation rejects missing approval, version mismatch, and missing acceptance evidence
- explicit gate mode exits nonzero with a blocked reason before quality evaluation
- an empty gate list does not pass
- shadow verdict flips and shadow parse failures do not change an accepted gate exit code
- marking a shadow route required blocks the decision instead of dropping it
- human reviews import with no LLM credential; pending reviews do not pass a required human criterion
- a hand-computed mix of Pass, Fail, Not applicable, and Unscorable keeps denominator and counts distinct
- overlapping development and held-out items are rejected
- with Langfuse bypassed, `langfuse` is never imported and local writer files round-trip
- deterministic metrics match a hand-computed example; confidence intervals appear only on aggregates
- the notebook JSON loads and every code cell passes `ast.parse`

Fix failures in the generated project. Live model calls and a live Langfuse project are out of scope; say so.

## Step 6: README

Document variables, the diagnostic default, the gate-mode preflight, and unverified live paths. State that fixture acceptance evidence is not real-model validation.

## Invariants

- Langfuse bypass is total: `use_langfuse=False` never imports or contacts Langfuse.
- Evaluators emit criterion results. Metrics and gates are separate code and read only accepted, scorable results unless the run is explicitly diagnostic.
- Confidence intervals attach only to aggregates, and only when a measurement need declares them.
- Process health (the runner finished) is separate from a Product verdict.
- Diagnostic success may exit 0 with `decision_eligible=false` and no release verdict.
- Gate mode that fails preflight exits nonzero. That is configuration refusal, not a judge-derived Product failure.
- k=1 evidence is one call through the real entrypoint. Best-of-N is never reported as k=1.
