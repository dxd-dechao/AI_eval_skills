# Generated module contract

Generate these modules under `eval_harness/` in the consuming project. Names below are the public interface. Fill project-specific fields from the registers and the application code. Do not add a default judge suite, a 1–5 scale, partial credit, or a numeric gate threshold the register does not contain.

```
eval_harness/
  __init__.py
  config.py
  contract.py
  dataset_loader.py
  pipeline_adapter.py
  routing.py
  evaluators/deterministic.py
  evaluators/human.py
  evaluators/llm.py          # only if a route has evaluator_type llm; lazy client
  metrics.py
  gates.py
  human_review.py
  langfuse_writer.py
  run_eval.py
  sample_data/               # placeholders only; never a fake approval
  README.md
```

## config.py

`HarnessConfig` is a dataclass and the only place that reads environment variables.

Required fields: `mode` (`"diagnostic"` default, or `"gate"`), `limit` (default 1), `runs` (default 1), `use_langfuse` (default False), `results_dir`, `eval_spec_path` (path to `eval-spec.json`; null when absent), `expectations_path`, `rubric_path`, `evaluator_register_path`, `dataset_path`, `decision_policy` (criterion IDs the Product policy requires, copied from the register), `reviews_path` (optional path to a local review file; null when absent).

`eval_spec_path` defaults to null. Callers pass the spec path explicitly. Do not invent a spec.

`validate()` collects every structural problem and raises one error. It does not judge output quality.

## contract.py

`load_registers(config) -> dict` reads the three JSON artifacts and checks `schema_version == "product-eval-contract/1"`.

`load_eval_spec(config) -> dict | None` reads `config.eval_spec_path` when it is set. A missing path or missing file returns None. It does not score quality.

`preflight_gate(config) -> PreflightResult` runs only for decision use. It checks the Eval Spec **before any other gate check and before any quality evaluation**:

- If the spec is missing, `state` is not `READY`, or any of the 8 decisions lacks an answer or a holder: return `ok=False` and `blocked_reason` exactly `eval spec not ready: <missing items>` (name the missing file, the state, or the decision ids). Do not continue to later checks.
- If `trial_contract.mode` is not exactly `k=1`, `pass^k`, or `pass@k`, or `trial_contract.k` is not a positive integer, or (`mode` is `k=1` and `k` is not `1`): return `ok=False` and `blocked_reason` exactly `invalid trial contract: <mode> k=<k>` (use `missing` for an absent mode or k). Do not continue.
- If `config.runs != trial_contract.k`: return `ok=False` and `blocked_reason` exactly `runs mismatch: config.runs=<n> spec k=<k>`. Do not continue.
- Isolation, before scoring. Product state is memory, cache, history, or files a later call can read such that the same arguments can yield a different product result. A provenance counter that criteria do not score is not product state. A pure function of its arguments records `isolation: not_required`. When the app is stateful, resolve the application's own reset or new-instance callable discovered from code (do not reimplement it). If that callable is missing, record `isolation: unverified` and return `ok=False` with `blocked_reason` exactly `trial isolation unverified`. Do not continue.
- Judgment unit, before scoring. Canonical units are `output`, `session`, and `episode`, read from top-level `judgment_unit` when that field is one of those tokens. A required criterion's `applicable_unit` must equal that token. Otherwise return `ok=False` and `blocked_reason` exactly `unit mismatch: <criterion> <unit> != <spec unit>`. Do not continue. When `judgment_unit` is absent, skip this check (prose Stage 00 answers are not tokens). A criterion whose `applicable_unit` is a finer grain than the spec unit (for example `turn` under `session`) is diagnostic decomposition only: it is never required, never a gate input, and never aggregated into the session or episode outcome.

The skill never chooses `k`, the mode, or a threshold. They come from the Eval Spec only.

Only when those checks pass, also return `ok=False` and a `blocked_reason` **before any quality evaluation** when:

- expectations state is `NEEDS_PRODUCT_DECISION` or the file is missing
- rubric `review.approval_state` is not approved, or approver/date/version is missing. `blocked_reason` contains `approval`
- a required criterion is absent, or its evaluator version does not match the register
- acceptance evidence is missing, is only a bare boolean (`approved: true` or `validated: true`), or lacks the minimum fields for its route kind (see below)
- development and held-out manifests share an item id or normalized content
- the decision policy names a criterion whose route is unaccepted

Minimum acceptance evidence, checked by `preflight_gate` whenever a route is `acceptance_state: accepted` or is required for a decision. Reject the route when these fields are absent. Do not treat a boolean flag as a substitute. Do not require a universal numeric threshold.

- **Deterministic verification** (`evidence.kind` = `verification`): `cases` includes one object with `role` `known-good`, one with `role` `known-bad`, and one with `role` `edge` or `shortcut`. Each of those objects has a non-empty `expected` outcome. `implementation_version` is a non-empty string.
- **Human procedure** (`evidence.kind` = `human_procedure`): a non-empty `reviewer_id`, or a `reviewer` object with a non-empty `id`. A non-empty `rubric_version` or `procedure_version`. `item_reviews` is a non-empty list; each object has non-empty `item_id`, `reviewer_id`, and `verdict`.
- **LLM held-out** (`evidence.kind` = `held_out`): non-empty `dataset_id`, `dataset_version`, and `labels_ref`. `agreement`, `stability`, and `run_health` are each a non-empty object or non-empty string describing the check for that label regime (presence only; no cutoff). `acceptance_decision` is an object with a non-empty `scope`.

`PreflightResult` fields: `ok: bool`, `blocked_reason: str | None`, `decision_eligible: bool`.

An empty check list is `ok=False` with reason `no gate checks configured`. It is never a pass.

## routing.py

`route_for(criterion_id, register) -> Route` returns the register row. `execution_scope` is `DIAGNOSTIC/SHADOW ONLY` unless `acceptance_state` is `accepted` and the evidence record is present. Shadow rows set `decision_eligible=False`.

## pipeline_adapter.py

`run_item(item) -> PipelineResult` calls the application's real entrypoint for one trial. The runner, not the adapter, loops trials. Before each trial, call the application's reset or new-instance path when product state exists. `PipelineResult` includes `item_id`, `trial_index`, `raw_output`, `invocation_count` for that call, and provenance (code path or version). Do not duplicate product logic.

Drive the entrypoint from the dataset item's `unit`, which matches the spec's `judgment_unit`:

- `output`: one call; return that output.
- `session`: one fresh state; replay `turns` in order; return the ordered turn outputs. History may accumulate inside that trial and must not survive `reset`.
- `episode`: one fresh state; return `{trajectory, final_state}` from what the app actually exposes. If a trajectory criterion needs a trajectory and the app does not expose one, that criterion is `UNSCORABLE` with reason `trajectory not observable`. Do not infer a trajectory.

Adapter exceptions, timeouts, and dependency outages (`ConnectionError`, `TimeoutError`, or an exception whose class name or message documents an infrastructure or dependency outage) are not product failures. Record that trial as `RUN_HEALTH`. Do not convert it to `FAIL`.

## evaluators

Deterministic: pure function of `raw_output` and the criterion's pass/fail/unscorable rules. Verification cases live next to the implementation version. No model import.

Human: `apply_review(item_id, criterion_id, review_record)`. A missing or pending review yields status `PENDING`, never Pass. No model import.

LLM: optional. Import the model client inside the function that calls it. If no client is configured, return status `UNSCORABLE` or a shadow error, and do not crash a diagnostic run that does not need the route. Prompt text comes from the approved criterion, not from a generic rubric. Unaccepted LLM routes are shadow.

Each evaluator returns:

```json
{
  "criterion_id": "",
  "criterion_version": "",
  "evaluator_id": "",
  "evaluator_version": "",
  "applicability": "applicable | not_applicable | unknown",
  "status": "PASS | FAIL | UNSCORABLE | PENDING | ERROR",
  "decision_eligible": false,
  "shadow": true,
  "evidence_ref": ""
}
```

Unknown applicability serializes as `UNSCORABLE` and must not be stored as not applicable.

## human_review.py

`import_reviews(path) -> list[Review]` reads a local JSON/JSONL file. A JSON array is many reviews. A JSON object with `item_id` is one review. A JSON object with a `reviews` array uses that array. JSONL is one object per line. Required fields: `item_id`, `criterion_id`, `criterion_version`, `reviewer_id`, `rubric_version`, `verdict` (`Pass` or `Fail`), `evidence_note`. No network and no LLM credential. `Review.pending` is true when any required field is missing or `verdict` is not `Pass` or `Fail`. Pending rows stay pending. Gate mode loads `config.reviews_path` through `import_reviews` and passes each row to `apply_review`. A `Fail` on a required accepted human criterion is a quality failure.

## metrics.py

`aggregate_trials(trial_statuses, mode, k) -> dict` with `status` and `reason`. `trial_statuses` has one entry per executed trial: `PASS`, `FAIL`, `UNSCORABLE`, `PENDING`, `ERROR`, or `RUN_HEALTH`. `RUN_HEALTH` is not a valid judgment. `k` and `mode` come from the spec being applied. Do not drop or reorder trials. Do not keep a best-of-N result.

Truth table, first match wins. A valid trial is any status other than `RUN_HEALTH`. `RUN_HEALTH` is never `FAIL`.

| Condition | Item status |
|---|---|
| `k=1` and the single trial is `RUN_HEALTH` | `UNSCORABLE`, reason `incomplete trials` |
| `k=1` | The single trial's status. |
| `pass^k`, any valid trial is `FAIL` | `FAIL` |
| `pass^k`, valid trials fewer than `k` | `UNSCORABLE`, reason `incomplete trials` |
| `pass^k`, any valid trial is `UNSCORABLE`, `PENDING`, or `ERROR` | `UNSCORABLE` |
| `pass^k` | `PASS` (every valid trial passed and there are `k` of them) |
| `pass@k`, any valid trial is `PASS` | `PASS` |
| `pass@k`, valid trials fewer than `k` | `UNSCORABLE`, reason `incomplete trials` |
| `pass@k`, any valid trial is `UNSCORABLE`, `PENDING`, or `ERROR` | `UNSCORABLE` |
| `pass@k` | `FAIL` |

`reaggregate_item(trial_rows, trial_contract) -> dict` applies `aggregate_trials` to stored trial rows. It does not call the application. Use it when the same trials are read under another mode with the same `k`.

`compare_runs(left_meta, right_meta)` raises `ValueError` with message `cannot compare across trial contracts` when `trial_mode` or `k` differs. It has no default `k` and no threshold.

`summarize(results, policy) -> Summary`. `Summary` is an object whose decision fields are attributes (`summary.denominator`, `summary.pass_rate`, `summary.required_shadow_ids`), not a dict. `results` are judgment rows, not trial rows. A row with `criterion_id` and `status` is counted as given. Do not require `row_kind` or `grain`. Skip only rows whose `row_kind` is `trial` or `diagnostic`. `Summary` always exposes these top-level decision aggregates, computed under the Product-approved aggregation rule:

`denominator`, `pass_count`, `fail_count`, `not_applicable_count`, `unscorable_count`, `pending_count`, `error_count`, `pass_rate`, `blocked_reason`, `required_shadow_ids`.

Also set `trial_mode`, `k`, `trial_pass_count`, `trial_count`, and `run_health_count` when `policy` carries them (from the spec and the trial rows). Otherwise leave `trial_mode` and `k` null and the three counts at 0. Those fields do not change `denominator`. `denominator` counts items, not trials. `run_health_count` counts `RUN_HEALTH` trials and is not added to `fail_count`. Diagnostic finer-unit rows (for example turn-level under a session spec) are omitted from `results` passed to `summarize` and from gate inputs.

An optional `criteria` map may repeat that same field set per criterion id. Top-level fields are the decision aggregate. Callers read the top-level fields; they do not have to read `criteria`.

Count every non-shadow row passed in `results`. Do not drop a row because its criterion is absent from `required_criteria`. `required_criteria` affects only `blocked_reason` and `required_shadow_ids`. Count only scorable applicable units (`PASS` or `FAIL` with applicability `applicable`) in `denominator`. Not applicable is excluded. Unknown applicability counts as unscorable, not as not applicable. Unscorable, pending, and error counts stay visible in their own fields.

`pass_rate = pass_count / denominator` only when `denominator > 0` and it is not true that every required criterion is unscorable, pending, error, or missing. Otherwise `pass_rate` is null and `blocked_reason` explains why. That is not a pass.

`required_shadow_ids` lists every id in `policy["required_criteria"]` that has no result with `shadow` false. A missing required criterion and a required criterion whose results are all `shadow: true` both belong in that list. Preserve policy order.

Default when the register marks criteria only as `required` (`decision_consequence.rule` or `decision_policy.required_criteria`, with no rate and no threshold): each required criterion needs at least one scorable applicable unit and no `FAIL`. An unscorable, pending, error, or missing required criterion sets `blocked_reason` and blocks. A `FAIL` on a required criterion stays a quality failure (`fail_count`), not a configuration block. Any other rule (rates, thresholds) must come from Product and is never invented by the skill. `evaluate_decision` applies this default from the `Summary` fields above; it does not take a separate policy argument.

Confidence intervals are computed only inside `summarize` for a declared aggregate measurement. Never attach an interval to one item. Stratify by an axis the dataset actually has; do not invent one.

Deterministic arithmetic (counts, overlap, IoU) is a pure function with a docstring example. Temporal overlap exists only when the criterion's evidence has intervals.

Expose production proxy names as `PRODUCTION_PROXIES`, a dict on `metrics.py`. It may be empty. Omit those names from decision metrics and baselines.

## gates.py

`evaluate_decision(summary, preflight, shadow_results) -> DecisionReport`.

- If `preflight.ok` is false: `exit_code=2`, `release_verdict=null`, `blocked_reason` copied from preflight. Do not look at quality scores.
- Shadow results are stored under `shadow` and ignored by the exit code. Changing a shadow verdict or injecting a shadow parse error must not change `exit_code` when the accepted policy still passes.
- If `summary.required_shadow_ids` is non-empty, or policy requires a shadow or unaccepted criterion: `exit_code=2`, `release_verdict=null`, blocked, not silently omitted.
- If `summary.blocked_reason` is set because a required criterion is unscorable, pending, error, or missing: `exit_code=2`, `release_verdict=null`. A required `FAIL` is `exit_code=1`, `release_verdict="fail"`.
- Accepted policy with a real pass under the Product aggregation rule: `exit_code=0`, `release_verdict="pass"`.
- Accepted policy with a real fail: `exit_code=1`, `release_verdict="fail"`.
- Respect the register's unscorable consequence (block versus report). Do not treat unscorable as pass.

`DecisionReport` fields: `exit_code`, `decision_eligible`, `release_verdict`, `blocked_reason`, `denominator`, `pass_count`, `fail_count`, `not_applicable_count`, `unscorable_count`, `pending_count`, `shadow`.

## dataset_loader.py

Load local JSONL or a JSON array. Each item declares `unit` (`output`, `session`, or `episode`) matching the spec `judgment_unit` when that token is present. Session items include ordered `turns`. Episode items are one task episode.

`assert_held_out_disjoint(development_manifest, held_out_manifest)` raises if any item id, normalized content string, `session_id`, or `episode_id` appears in both. Compare `session_id` and `episode_id` when those fields are present. Held-out evidence that overlaps is rejected and cannot be acceptance evidence.

## langfuse_writer.py

`LocalResultsWriter` writes `run_meta.json`, `items.jsonl`, `summary.json`, and `decision.json`. `run_meta.json` includes criterion versions, evaluator versions, acceptance state, the accepted evidence object (including `implementation_version` when that route is deterministic), provenance, `decision_eligible`, `k`, `trial_mode`, `trial_contract`, `isolation` (`not_required`, `verified`, or `unverified`), `trial_pass_count`, `trial_count`, `run_health_count`, and version stamps: `suite_version`, `dataset_version` (from the dataset manifest), `evaluator_version` (from the register rows), `harness_version` (the package `__version__`), and `trial_policy_version` (the spec mode and k, formatted `mode:k`). Do not invent a threshold version.

`items.jsonl` has one JSON object per line: every trial row (`row_kind` `trial`, `item_id`, `trial_index`, trial `status`, `raw_output`) and one aggregated item row (`row_kind` `item`, `item_id`, `status`, `reason`). Finer-unit diagnostic rows use `row_kind` `diagnostic` and are not item rows.

`trial_contract` is copied from the Eval Spec (`{"mode": "k=1" | "pass^k" | "pass@k", "k": <int>}`) when the spec file loads. When no spec is loaded, write `trial_contract: null`. Diagnostic mode always records this field and still runs. Gate mode never reaches the writer when preflight refused the spec.

`make_writer(config)` returns the local writer when `use_langfuse` is false and must not import `langfuse` anywhere on that path. A Langfuse writer subclass imports `langfuse` only inside its own methods. Local files are still written.

## run_eval.py

`run(config, limit=None) -> RunResult` uses `config.limit` when `limit` is omitted. Default limit is 1. Read `k` and `mode` from the Eval Spec. For each selected item, run `k` independent trials. Each trial calls `run_item` once after a fresh reset when the app has product state. No state, cache, or history may carry between trials. Never keep a best-of-N result as a `k=1` or `pass^k` record. A completed trial's status is `FAIL` if any required applicable criterion is `FAIL`; otherwise `UNSCORABLE`, `PENDING`, or `ERROR` if any required criterion has that status; otherwise `PASS`. Then set the item status with `aggregate_trials`. Feed item rows to `summarize`. `RUN_HEALTH` trials increment `run_health_count` and are not `FAIL`.

Diagnostic mode (`config.mode != "gate"`): still record every criterion result, set `decision_eligible=false`, `release_verdict=null`, and return `exit_code=0` when the process itself succeeded (the app was called and results were written). Item-level product failures do not become a release fail in diagnostic mode. Record `trial_contract` in `run_meta.json` and still call the entrypoint `k` times per selected item.

Gate mode: call `preflight_gate` first. On failure return immediately with `exit_code=2`, `quality_evaluated=false`, and do not call the application entrypoint. On success, evaluate only accepted routes whose unit equals the spec judgment unit, and set the exit code from `evaluate_decision`.

CLI: `python -m eval_harness.run_eval --mode diagnostic|gate`. Exit with `RunResult.exit_code`.

`RunResult` is JSON-serializable and includes `raw_output`, per-criterion results, provenance, `invocation_count`, `decision_eligible`, and `release_verdict`.

## README

List each variable, the diagnostic default, the gate preflight, and the statement that one item is wiring evidence. Say live model and live Langfuse calls were not verified unless they actually ran.
