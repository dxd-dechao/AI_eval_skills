# Step 4: Mode 1 notebook requirements

Generate `eval_harness/notebooks/mode1_golden_layer2.ipynb` programmatically
(compose the JSON with a script; don't hand-write .ipynb). Validate afterwards:
JSON loads, and every code cell passes `ast.parse`.

## Cell sequence

1. **Markdown — title + orientation.** What the notebook runs (one-line Mode 1
   flow), the Langfuse-bypass statement, prerequisites list (app running +
   how to start it locally, golden inputs prepared, credentials command,
   Python deps and where they already exist), and a 💸 **cost warning** with
   this project's per-item cost shape ("each item = one full pipeline run +
   one judge call — start with LIMIT = 1").

2. **Markdown — "⚙️ 1. CONFIGURE ME — the only cell you must edit".**

3. **Code — the CONFIGURE-ME cell.** The defining feature:
   - `sys.path` bootstrap that finds the repo root by walking up until
     `eval_harness/` exists (works regardless of where jupyter launched).
   - EVERY user variable as an UPPERCASE constant with an inline `# ←` comment
     saying what it is and what to put there. Grouped with section-comment
     rules: REQUIRED (no safe defaults) / app under eval / judge credentials /
     **Langfuse ON or BYPASSED** (the `USE_LANGFUSE` switch with its
     dependency + env-key requirements spelled out) / run identity &
     provenance / session slice controls (`LIMIT` — default 1, `VENUE_FILTER`).
   - Ends by constructing `HarnessConfig(...)`, calling `config.validate()`,
     and printing a one-line confirmation including whether Langfuse is ON or
     BYPASSED.
   - No other cell defines a user variable. If a variable can't live here,
     the markdown must say exactly where it lives instead (e.g. "env var X").

4. **Markdown + code — load & inspect the dataset.** Table of items (id,
   scenario, tier, case, gt count, input ref) BEFORE spending tokens; warn
   that `REPLACE_…` placeholders will fail at the pipeline step. `pandas`
   optional: `try: import pandas … except ImportError:` print fallback —
   never make pandas a hard dependency.

5. **Markdown + code — run Mode 1.** One call: `result = run_mode1(config,
   limit=LIMIT, venue_type=VENUE_FILTER)`. Note that per-item results stream
   to the sink, so a crash loses nothing already written.

6. **Markdown + code — per-item results.** Point-value table (counts by
   verdict, recall/precision, judge_flagged) + a visible ⚠️ block listing any
   pipeline errors and stating those items are excluded from aggregates.

7. **Markdown + code — aggregates.** Slice × metric table with point, 95% CI,
   and n. Heading states the stratification rule ("per venue and per tier —
   never one number").

8. **Markdown + code — ship gates.** Gate table (threshold, point, gating
   bound, ✅/❌) + overall verdict line. The markdown must pre-empt the
   small-sample surprise: "with a tiny LIMIT the CIs are wide, so gates will
   usually fail — that is the statistics working, not a bug."

9. **Markdown + code — where the evidence went.** List the run directory
   files with sizes and print gates.json; state what extra happened when
   Langfuse was ON (scores on trace ids + run-summary trace, which dashboard
   to open).

10. **Markdown — next steps.** Real dataset, N-run consistency via the CLI,
    flipping `USE_LANGFUSE=True`, and the provenance rule for valid
    baseline↔candidate comparisons.
