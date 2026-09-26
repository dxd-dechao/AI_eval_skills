# Forward checks

These scripts prepare temporary git repositories and later verify artifacts a skill run wrote there. They do not contain expected skill essays or a pre-built harness.

## Prepare

```sh
python3 tests/forward/prepare_cases.py --root /private/tmp/ai-eval-skills-forward-<run-id>
```

The target directory must be missing or empty. The command creates eight repos:

| Repo | Input state |
|------|-------------|
| `A-missing-expectations` | Application only. No Product packet. |
| `B-expectations-only` | Application plus expectations JSON and a ready `k=1` Eval Spec. No approved rubric. |
| `C-approved-criteria` | Approved rubric, three routes, disjoint development and held-out manifests, ready `k=1` Eval Spec. |
| `D-approved-unrouted` | Approved rubric and expectations. No `evaluator-register.json`. Ready Eval Spec, `k=1`. |
| `E-episode-unapproved` | Tool-using app, supplied expectations, ready Eval Spec (`pass^k`, k=3, judgment unit is a task episode). Rubric not approved. |
| `F-dialog-missing-unit` | Multi-message app, supplied expectations, Eval Spec whose judgment-unit answer is missing and whose holder is named. |
| `G-episode-approved` | Tool-using app with module memory, an app reset, and an external dependency schedule. Approved rubric. Ready Eval Spec (`pass^k`, k=3, judgment unit `episode`). |
| `H-session-approved` | Multi-message app with an app reset. Approved rubric: a required session criterion and a diagnostic turn criterion. Ready Eval Spec (`k=1`, judgment unit `session`). |

Each repo contains `PROMPT.md` (the same request for every case), `app/`, and `INPUT_MANIFEST.json`. Cases A–D use a document summarizer with an invocation counter. Case E uses a two-tool order helper. Case F uses a multi-message helper. Case G uses a tool-using order helper whose dependency schedule lives beside the module. Case H uses a multi-message helper. Case A also contains `PROMPT-PLUMBING.md` for a separate generator that asks only for neutral execution plumbing. Cases B, C, and D contain a ready `k=1` Eval Spec. Case C also contains the other `Knowledge/` registers. Case D contains expectations, the Eval Spec, and an approved rubric only. Cases G and H contain approved registers. Synthetic names are fixtures, not real approvals. Inputs do not name archetypes, criteria, routes, or expected verifier output.

## Invoke

Use a new run id. Run `prepare_cases.py` into `/private/tmp/ai-eval-skills-forward-<run-id>/`. Give each case a fresh generator. That generator receives only its case repo, `skills/eval-design`, `skills/eval-harness-build`, and that case's `PROMPT.md`. Do not provide this verifier, an answer key, or another case. Do not send a follow-up after a generator finishes, and do not reveal verifier output. After case A finishes, a new generator may read that same repo plus `PROMPT-PLUMBING.md` and add neutral plumbing only. If a probe fails, record it, fix the skill text, and regenerate that case from scratch under a new run id.

## Verify

```sh
python3 tests/forward/verify_cases.py --root /private/tmp/ai-eval-skills-forward-<run-id>
```

The verifier writes `<root>/report.json`. A missing artifact, an exception, or a skipped probe is a failure. Each probe is listed on its own. An exception fails only that probe; later probes still run. The verifier reads the documented `Summary` aggregates and acceptance-evidence fields, not private attributes.
