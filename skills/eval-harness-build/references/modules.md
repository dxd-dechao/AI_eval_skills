# Step 3: Module requirements & templates

Per-module requirements plus generalized code patterns. Adapt names, endpoints,
schemas, and rubrics to THIS project (Steps 1–2); keep the invariants from
SKILL.md verbatim. The patterns below are skeletons — fill every `[bracket]`
from the project's docs and code, and delete whatever the project doesn't have.

## config.py — the single home of user variables

- One `@dataclass HarnessConfig` holding EVERY user-defined variable: run
  identity/provenance, app base URL + auth identity, judge project/model,
  `use_langfuse` switch, results dir, CI parameters, gate thresholds.
- Env-var fallbacks via `field(default_factory=...)`; document each env var in
  the module docstring. Nothing outside config.py reads env vars.
- `DEFAULT_GATES: dict[str, float]` quoting the eval plan's thresholds, with a
  comment pointing at the doc section ("change there first, then here").
- `validate()` raises one error listing ALL problems (empty required fields,
  missing dataset file, langfuse enabled without keys).

## dataset_loader.py

- `GoldenItem` dataclass + `from_dict` that fails loudly listing missing
  required fields.
- Item schema mirrors the golden-dataset spec: `input` (references to
  already-ingested inputs + the judge's direct-access URI + per-item param
  overrides), `expected_output.events` (ground-truth annotations with stable
  `gt_event_id`s), `metadata` (scenario dimension, positive/negative case,
  priority tier). Document the schema in the module docstring with a worked
  JSON example.
- `load_local(path)` — JSONL (one item per line) and JSON-array tolerant.
- `load_langfuse(dataset_name)` — imports langfuse INSIDE the function so the
  bypass never needs the dependency; maps Dataset items through the same
  `from_dict`.

## pipeline_adapter.py — the Step 2 contract, no app logic duplicated

- Docstring states: which endpoints it calls, the auth mechanism, and the
  local-run constraint (e.g. "use mode X locally; queue Y never fires").
- `PipelineResult` carries: item_id, the app's job/trace id (this doubles as
  the observability trace id), terminal status, fetched output records, raw
  job record, wall seconds.
- `run_item(item)`: start → poll (interval + hard timeout from config; raise
  on `failed` with the app's recorded error) → fetch all results (respect
  pagination limits).
- Handle the start endpoint's rate limit if one exists (sleep + one retry).
- All failures raise a single `PipelineError` with the item id and response
  snippet — the runner catches per item and continues.

## judge_runner.py

- Pydantic models for the judge output exactly as the eval plan defines them
  (e.g. unified alignments: `gt_event_id | system_event_id | verdict | N
  quality scores | rationale`).
- The judge prompt embeds the eval plan's rubrics VERBATIM (verdict rules,
  per-dimension score anchors). Do not paraphrase rubrics — they are
  calibration artifacts.
- Structural constraints validated IN CODE after the call (bipartite coverage:
  every gt id and every system id appears exactly once; null rules per
  verdict). Re-run up to `judge_max_retries` on parse/constraint failure, then
  return a flagged result — parse-failure rate is a tracked proxy metric.
- Same LLM client pattern the app uses (Step 2, prompt 5), stronger model,
  temperature 0, structured output (`response_schema`). Lazy client property
  so metrics-only sessions never need credentials.
- Short-circuit: zero ground-truth events AND zero system events → empty valid
  alignment, no API call.

## metrics.py — deterministic derivation + statistical rigor

- Item-level: derive from judge verdicts + raw timestamps. Standard pattern
  for detection tasks: recall = (detected + 0.5·partial)/gt_count, precision =
  (detected + 0.5·partial)/system_count, classification accuracy = pairs with
  type score ≥ [doc threshold], deterministic temporal IoU computed from the
  aligned pair's timestamps (not from the judge's 1–5 score), FP-on-negative =
  any fabricated event on a negative item. Adapt to the project's metric
  definitions — the eval plan is the source of truth.
- `wilson_ci(successes, n)` for proportions (tolerate fractional successes
  from partial credit); `bootstrap_mean_ci(values, resamples, confidence,
  seed)` percentile method for means. Seeded RNG for reproducibility.
- `aggregate(...)` returns stratified slices — `venue:<scenario>` /
  `tier:<P0..>` keys (or the project's real stratification axis) plus an
  `overall` key labelled orientation-only. Never emit a lone aggregate.
- N-run consistency helper: per item, fraction of runs matching the modal
  detection set, averaged over items.

## gates.py

- `evaluate_gates(aggregates, gates) -> list[GateCheck]`; each check records
  slice, metric, threshold, point, the gating bound, pass/fail.
- Quality gates use the LOWER CI bound ≥ threshold; "must stay below" rates
  (FP rate) use the UPPER CI bound ≤ threshold, with a note field saying so.
- Tier gates follow the harm-severity table (costly-direction metric per
  tier); venue gates apply to every venue slice present. Missing support ⇒ no
  check emitted (never a fake pass).

## langfuse_writer.py — the bypass switch

- `LocalResultsWriter` (default): creates `results_dir/<run_name>/` and writes
  `run_meta.json` (provenance triple + timestamps), `items.jsonl` (streamed,
  flushed per item so crashes lose nothing), `aggregates.json`, `gates.json`.
- `LangfuseScoreWriter(LocalResultsWriter)`: EXTENDS the local writer (disk
  output always complete), imports langfuse inside the class, writes per-item
  scores against the app's job id as trace_id using the project's score
  registry names exactly, plus one run-summary synthetic trace carrying
  aggregates (CI in the score comment — never a CI on a per-item score).
- `make_writer(config)` — the single switch on `config.use_langfuse`.

## run_layer2.py — runner + CLI

- `run_mode1(config, limit, venue_type, positive_only, progress) ->
  Mode1Result`: load → filter → per item (pipeline → judge → derive → write;
  catch PipelineError into an errors dict and continue) → aggregate → gates →
  summary → finalize. Numbered comments mapping to the harness spec's Mode 1
  steps.
- `Mode1Result.passed` = all gates passed AND no item errors.
- CLI: `--dataset --run-name --limit --venue-type --use-langfuse --runs N`.
  `--runs N` executes N runs named `<base>_runKofN` and prints the consistency
  agreement rate. Exit 0 only when every run passed — CI blocks on this.

## sample_data + README

- `golden_sample.jsonl`: 2 items (one positive with ≥1 gt event, one negative
  with none), every project-specific value spelled `REPLACE_WITH_…`.
- README: module map, the variables table (variable → where → what), 
  prerequisites, CLI + notebook run commands, cost warning sized to this
  project, and the not-verified-offline caveats.
