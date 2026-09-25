# Forward checks

These scripts prepare temporary git repositories and later verify artifacts a skill run wrote there. They do not contain expected skill essays or a pre-built harness.

## Prepare

```sh
python3 tests/forward/prepare_cases.py --root /private/tmp/ai-eval-skills-forward-<run-id>
```

The target directory must be missing or empty. The command creates four repos:

| Repo | Input state |
|------|-------------|
| `A-missing-expectations` | Application only. No Product packet. |
| `B-expectations-only` | Application plus expectations JSON. No approved rubric. |
| `C-approved-criteria` | Approved rubric, three routes, disjoint development and held-out manifests. |
| `D-approved-unrouted` | Approved rubric and expectations. No `evaluator-register.json`. |

Each repo contains `PROMPT.md` (the user request), `app/` (a document summarizer with an invocation counter), and `INPUT_MANIFEST.json`. Case A also contains `PROMPT-PLUMBING.md` for a separate generator that asks only for neutral execution plumbing. Case C also contains `Knowledge/` registers. Case D contains expectations and an approved rubric only. Synthetic names are fixtures, not real approvals.

## Invoke

Use a new run id. Run `prepare_cases.py` into `/private/tmp/ai-eval-skills-forward-<run-id>/`. Give each case a fresh generator. That generator receives only its case repo, `skills/eval-design`, `skills/eval-harness-build`, and that case's `PROMPT.md`. Do not provide this verifier, an answer key, or another case. Do not send a follow-up after a generator finishes, and do not reveal verifier output. After case A finishes, a new generator may read that same repo plus `PROMPT-PLUMBING.md` and add neutral plumbing only. If a probe fails, record it, fix the skill text, and regenerate that case from scratch under a new run id. Then run this verifier read-only on the Planner case C at `/private/tmp/ai-eval-skills-forward-qa2-planner` and record the result.

## Verify

```sh
python3 tests/forward/verify_cases.py --root /private/tmp/ai-eval-skills-forward-<run-id>
```

The verifier writes `<root>/report.json`. A missing artifact, an exception, or a skipped probe is a failure. Each probe is listed on its own. An exception fails only that probe; later probes still run. The verifier reads the documented `Summary` aggregates and acceptance-evidence fields, not private attributes.
