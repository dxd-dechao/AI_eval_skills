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

Required fields: `mode` (`"diagnostic"` default, or `"gate"`), `limit` (default 1), `runs` (default 1), `use_langfuse` (default False), `results_dir`, `expectations_path`, `rubric_path`, `evaluator_register_path`, `dataset_path`, `decision_policy` (criterion IDs the Product policy requires, copied from the register).

`validate()` collects every structural problem and raises one error. It does not judge output quality.

## contract.py

`load_registers(config) -> dict` reads the three JSON artifacts and checks `schema_version == "product-eval-contract/1"`.

`preflight_gate(config) -> PreflightResult` runs only for decision use. It returns `ok=False` and a `blocked_reason` **before any quality evaluation** when:

- expectations state is `NEEDS_PRODUCT_DECISION` or the file is missing
- rubric `review.approval_state` is not approved, or approver/date/version is missing
- a required criterion is absent, or its evaluator version does not match the register
- acceptance evidence is missing or is only a bare boolean
- development and held-out manifests share an item id or normalized content
- the decision policy names a criterion whose route is unaccepted

`PreflightResult` fields: `ok: bool`, `blocked_reason: str | None`, `decision_eligible: bool`.

An empty check list is `ok=False` with reason `no gate checks configured`. It is never a pass.

## routing.py

`route_for(criterion_id, register) -> Route` returns the register row. `execution_scope` is `DIAGNOSTIC/SHADOW ONLY` unless `acceptance_state` is `accepted` and the evidence record is present. Shadow rows set `decision_eligible=False`.

## pipeline_adapter.py

`run_item(item) -> PipelineResult` calls the application's real entrypoint once per item. `PipelineResult` includes `item_id`, `raw_output`, `invocation_count` for that call, and provenance (code path or version). Do not duplicate product logic.

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

`import_reviews(path) -> list[Review]` reads a local JSON/JSONL file. Required fields: `item_id`, `criterion_id`, `criterion_version`, `reviewer_id`, `rubric_version`, `verdict` (`Pass` or `Fail`), `evidence_note`. No network and no LLM credential. Pending or unsigned rows stay pending.

## metrics.py

`summarize(results, policy) -> Summary` counts only scorable applicable units in the denominator. Not applicable is excluded. Unscorable, pending, and error counts are separate fields and stay visible.

`pass_rate = pass_count / denominator` only when `denominator > 0`. If the denominator is 0, or every required result is unscorable, pending, or missing, `pass_rate` is null and `blocked_reason` explains why. That is not a pass.

Confidence intervals are computed only inside `summarize` for a declared aggregate measurement. Never attach an interval to one item. Stratify by an axis the dataset actually has; do not invent one.

Deterministic arithmetic (counts, overlap, IoU) is a pure function with a docstring example. Temporal overlap exists only when the criterion's evidence has intervals.

Production proxy names are a separate dict and are omitted from decision metrics and baselines.

## gates.py

`evaluate_decision(summary, preflight, shadow_results) -> DecisionReport`.

- If `preflight.ok` is false: `exit_code=2`, `release_verdict=null`, `blocked_reason` copied from preflight. Do not look at quality scores.
- Shadow results are stored under `shadow` and ignored by the exit code. Changing a shadow verdict or injecting a shadow parse error must not change `exit_code` when the accepted policy still passes.
- If policy requires a shadow or unaccepted criterion: `exit_code=2`, blocked, not silently omitted.
- Accepted policy with a real pass under the Product aggregation rule: `exit_code=0`, `release_verdict="pass"`.
- Accepted policy with a real fail: `exit_code=1`, `release_verdict="fail"`.
- Respect the register's unscorable consequence (block versus report). Do not treat unscorable as pass.

`DecisionReport` fields: `exit_code`, `decision_eligible`, `release_verdict`, `blocked_reason`, `denominator`, `pass_count`, `fail_count`, `not_applicable_count`, `unscorable_count`, `pending_count`, `shadow`.

## dataset_loader.py

Load local JSONL or a JSON array. `assert_held_out_disjoint(development_manifest, held_out_manifest)` raises if any id or normalized content string appears in both. Held-out evidence that overlaps is rejected and cannot be acceptance evidence.

## langfuse_writer.py

`LocalResultsWriter` writes `run_meta.json`, `items.jsonl`, `summary.json`, and `decision.json`. `run_meta.json` includes criterion versions, evaluator versions, acceptance state, provenance, `decision_eligible`, and `k`.

`make_writer(config)` returns the local writer when `use_langfuse` is false and must not import `langfuse` anywhere on that path. A Langfuse writer subclass imports `langfuse` only inside its own methods. Local files are still written.

## run_eval.py

`run(config, limit=None) -> RunResult` uses `config.limit` when `limit` is omitted. Default limit is 1. For each selected item call `run_item` once (k=1). Do not retry and then keep the best score as the k=1 record.

Diagnostic mode (`config.mode != "gate"`): still record every criterion result, set `decision_eligible=false`, `release_verdict=null`, and return `exit_code=0` when the process itself succeeded (the app was called and results were written). Item-level product failures do not become a release fail in diagnostic mode.

Gate mode: call `preflight_gate` first. On failure return immediately with `exit_code=2` and do not need to have judged quality. On success, evaluate only accepted routes and set the exit code from `evaluate_decision`.

CLI: `python -m eval_harness.run_eval --mode diagnostic|gate`. Exit with `RunResult.exit_code`.

`RunResult` is JSON-serializable and includes `raw_output`, per-criterion results, provenance, `invocation_count`, `decision_eligible`, and `release_verdict`.

## README

List each variable, the diagnostic default, the gate preflight, and the statement that one item is wiring evidence. Say live model and live Langfuse calls were not verified unless they actually ran.
