# Forward checks

These scripts prepare temporary git repositories and later verify artifacts a skill run wrote there. They do not contain expected skill essays or a pre-built harness.

## Prepare

```sh
python3 tests/forward/prepare_cases.py --root /private/tmp/ai-eval-skills-forward-<run-id>
```

The target directory must be missing or empty. The command creates three repos:

| Repo | Input state |
|------|-------------|
| `A-missing-expectations` | Application only. No Product packet. |
| `B-expectations-only` | Application plus expectations JSON. No approved rubric. |
| `C-approved-criteria` | Approved rubric, three routes, disjoint development and held-out manifests. |

Each repo contains `PROMPT.md` (the user request), `app/` (a document summarizer with an invocation counter), and `INPUT_MANIFEST.json`. Case A also contains `PROMPT-PLUMBING.md` for a follow-up that asks only for neutral execution plumbing. Case C also contains `Knowledge/` registers. Synthetic names in case C are fixtures, not real approvals.

## Invoke

In a fresh agent context per scenario, provide only that repo, the relevant skill directory, and `PROMPT.md`. Do not provide this verifier or an answer key. Run `eval-design`, then `eval-harness-build`. For A, a follow-up may ask for neutral plumbing only.

## Verify

```sh
python3 tests/forward/verify_cases.py --root /private/tmp/ai-eval-skills-forward-<run-id>
```

The verifier writes `<root>/report.json`. A missing artifact, a skipped probe, or a scenario that did not run is a failure. The report lists every probe path and outcome.
