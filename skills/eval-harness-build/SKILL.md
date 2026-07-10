---
name: eval-harness-build
description: >-
  Generate a working eval-harness implementation (Python package + Mode 1
  golden-eval Jupyter notebook) from a project's eval design docs: a pipeline
  adapter that calls the real app, an LLM judge runner, deterministic metrics
  with confidence intervals, ship gates on lower CI bounds, and a results sink
  with a full Langfuse bypass. Use when the user asks to build, scaffold, or
  implement an eval harness, eval runner, eval pipeline code, or a golden-eval
  notebook — the implementation counterpart to the eval-design skill.
---

# Eval Harness Builder

Turns an eval **design** (the documents produced by the `eval-design` skill —
especially the eval plan and the eval-harness spec) into an eval
**implementation**: a Python package under `eval_harness/` plus an interactive
Mode 1 notebook. Invoke from the root of the project codebase.

## Workflow

Copy this checklist and track progress:

```
- [ ] Step 1: Locate & validate the eval design docs (fallback rules below)
- [ ] Step 2: Discover the pipeline contract from the codebase
- [ ] Step 3: Generate the module set → read references/modules.md
- [ ] Step 4: Generate the Mode 1 notebook → read references/notebook.md
- [ ] Step 5: Smoke-test the offline logic — must pass before finishing
- [ ] Step 6: README + honest handoff notes
```

---

## Step 1: Locate & validate the eval design docs

Search the repo (typically `docs/`) for:

- **Harness spec** (eval-design doc 6, `eval-harness.md` or similar): harness
  modes, automation groups, Langfuse configuration, gate semantics.
- **Eval plan** (doc 3, `eval-plan*.md`): Layer 2 metrics + targets, the
  LLM-as-judge definition (unified or per-dimension), rubrics, harm-severity
  tiers, statistical-rigor rules (CI methods, N-run consistency).
- **Golden dataset spec** (doc 4): item schema, priority tiers, positive /
  negative case definitions.
- **Langfuse setup** (doc 5): score-name registry (5D) — the generated code
  must emit exactly these names.

**Fallback rules — do not silently invent a design:**

- Docs exist → extract judge schema, rubrics, metric formulas, gate thresholds,
  and score names from them. Where the code needs a number the docs define,
  quote the doc value and cite the section in a comment.
- Docs partially exist → build from what exists; mark every gap in the README
  ("gates default to X — no eval plan found defining thresholds").
- No eval docs at all → tell the user and offer to run `eval-design` first
  (recommended), or proceed with the generic defaults in references/modules.md,
  clearly labelled as defaults to revisit.

## Step 2: Discover the pipeline contract from the codebase

The adapter must call the **real app** — never reimplement its logic. Answer
these from the code (do NOT ask the user):

1. **How is a job started?** (HTTP endpoint + request body / queue message /
   importable function). Prefer the same service endpoint production traffic
   uses.
2. **How is completion detected?** (status endpoint + terminal statuses /
   callback / synchronous return). Note timeouts appropriate to the workload.
3. **How are results fetched?** (endpoint + pagination + the exact field names
   of the output records — ids, types, timestamps, confidence).
4. **How does the harness authenticate?** (gateway/dev headers, bearer token,
   API key). Find the path that works when calling the service directly.
5. **How does the app call its LLM?** (client library, credentials pattern,
   structured-output mechanism). The judge runner should use the same client
   pattern with a **stronger model** than the one under eval.
6. **What input does the judge need?** (file URI + MIME for multimodal, or
   text). Multimodal judges MUST run in the harness — never as a
   Langfuse-managed evaluator.
7. **Local-run constraints** — modes that don't work locally (e.g. cloud task
   queues that never fire), rate limits on the start endpoint, and the
   cheapest mode for dev runs. Default the config to the mode that works
   locally.

Record the answers as a short "pipeline contract" note; the adapter code
comments should cite where each answer came from.

## Step 3: Generate the module set

Read [references/modules.md](references/modules.md) and generate, under
`eval_harness/` (or the project's convention for tooling folders):

```
eval_harness/
  __init__.py          exports HarnessConfig + run_mode1
  config.py            HarnessConfig — ALL user variables, env fallbacks, validate()
  dataset_loader.py    golden items: local JSONL default + optional Langfuse Dataset
  pipeline_adapter.py  the Step 2 contract, implemented (real app, no duplication)
  judge_runner.py      judge call + strict schema + structural validation + retry
  metrics.py           deterministic derivation + Wilson/bootstrap CIs + stratified aggregation
  gates.py             ship gates on lower CI bounds (upper bound for "must stay below" rates)
  langfuse_writer.py   LocalResultsWriter (default) + LangfuseScoreWriter; make_writer() switch
  run_layer2.py        run_mode1() + CLI with exit 0/1 and --runs N consistency
  sample_data/golden_sample.jsonl   schema template with REPLACE_ placeholders
  README.md            variables table, prerequisites, run commands, cost warning
```

Non-negotiable invariants (from the harness spec):

- **Langfuse bypass is total**: with `use_langfuse=False`, langfuse is never
  imported and never contacted; all evidence lands on disk.
- **Judge never computes a metric** — metrics derive deterministically from
  validated judge JSON.
- **CIs only at aggregate level**; per-item scores are point values.
- **Gates on the CI bound, never the point estimate**; CLI exit code is the
  enforcement mechanism.
- **Run provenance recorded** with every run (dataset version, template/prompt
  version, model + config).
- Score names match the project's Langfuse score registry exactly.

Add the results directory to `.gitignore`.

## Step 4: Generate the Mode 1 notebook

Read [references/notebook.md](references/notebook.md) and generate
`eval_harness/notebooks/mode1_golden_layer2.ipynb`. The defining feature is a
single prominent **⚙️ CONFIGURE ME** cell holding every user variable with
inline comments — a user should never hunt through other cells or files to run
the eval. Generate the .ipynb programmatically (build the JSON with a script)
and validate that every code cell parses with `ast.parse`.

## Step 5: Smoke-test the offline logic

Before reporting done, run (in an env with the package's deps — create a
scratch venv if needed) a script that exercises everything that works without
network:

- dataset loader on the shipped sample file;
- judge structural-constraint validation (accept a valid alignment set, reject
  a violating one);
- metric derivation on a hand-computed example — verify recall/precision with
  partial credit and the deterministic temporal IoU **by hand-checking the
  arithmetic** (compute intersection/union yourself before asserting);
- Wilson CI sanity bounds; aggregation produces the expected slice keys;
- gate evaluation passes/fails the constructed example correctly;
- local writer round-trip: all expected files exist and reload as valid JSON;
- CLI module imports.

Fix every failure. The pipeline adapter and Langfuse writer cannot be fully
verified offline — that's a handoff note, not a skipped step.

## Step 6: README + honest handoff

The README must contain: the **variables table** (variable → where to set it →
what it is), prerequisites (app running, data prepared, credentials), run
commands (notebook + CLI), and a **cost warning** sized to this project's
per-item cost. State plainly what was NOT verified (live adapter run, live
Langfuse write) and what the user must replace (sample-data placeholders).

---

## Relationship to eval-design

This skill implements what `eval-design` designs. If the design docs are
missing, prefer running `eval-design` first — the generated code will be
strictly better when rubrics, gates, and score names come from a reviewed
design rather than generic defaults. This skill builds **Mode 1 (golden
end-to-end eval)** fully; Modes 2–3 from the harness spec (component eval,
post-production judge audit) remain design-only unless the user asks.
