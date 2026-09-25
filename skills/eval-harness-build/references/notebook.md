# Diagnostic notebook

Generate `eval_harness/notebooks/mode1_diagnostic.ipynb` as JSON. Every code cell must pass `ast.parse`.

The notebook's default is diagnostic inspection of one item. It must not present a release pass.

## Cell sequence

1. **Title.** State that the run is diagnostic, that Langfuse is bypassed unless `USE_LANGFUSE` is set, and that one item is wiring evidence rather than validation or release readiness. List a cost warning when an LLM route exists. If every route is deterministic or human, say no model call is required.

2. **Configure.** One code cell holds every user variable: `MODE = "diagnostic"`, `LIMIT = 1`, `USE_LANGFUSE = False`, plus paths to the registers and dataset. Read `trial_contract` from the Eval Spec and assign `TRIAL_MODE` and `RUNS` from that file only. Write `RUNS` as the spec's integer `k` (a spec with `k` 1 produces the literal `RUNS = 1`). Do not edit the spec's mode or k in the notebook. Build `HarnessConfig` with `runs=RUNS`, call `validate()`, and print `mode`, `TRIAL_MODE`, `RUNS`, `decision_eligible` expectation (`false` in diagnostic), and whether Langfuse is bypassed.

3. **Readiness.** Load registers and print `state`, pending approvals, and each route's `acceptance_state` and `execution_scope`. A pending review is visible as pending.

4. **Run.** Call `run(config, limit=LIMIT)` once. The adapter must use the application entrypoint.

5. **Items.** Show raw output, invocation count, per-trial success (`trial_pass_count`, `trial_count`, each `trial_index`), `run_health_count`, the aggregated item `status`, and per-criterion `status` (`PASS`, `FAIL`, `UNSCORABLE`, `PENDING`, `ERROR`) plus applicability. Unscorable is the word “Unscorable” in the display heading. Do not collapse these into one score. Diagnostic finer-unit rows stay visible and are labeled diagnostic.

6. **Decision line.** Print `decision_eligible` and `release_verdict`. In the default diagnostic configuration both are `false` and `null`. The markdown says a successful cell here is not a release decision.

7. **Evidence path.** List writer files. Note that gate mode is a separate explicit opt-in and refuses incomplete approval before scoring.

No cell may set `MODE = "gate"` as the default. No cell may treat an empty gate table as a pass.
