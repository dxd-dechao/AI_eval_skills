# Product expectations, rubric review, and evaluator routing

Canonical contract for `eval-design` and for any harness that consumes its registers. Read this before drafting criteria, judge prompts, thresholds, or release gates.

Schema version for every JSON register: `product-eval-contract/1`.

Write readable Markdown beside a JSON register with the same facts. The harness validates fields from JSON. Prose is for reviewers. Generated text is never an approval.

Use `Knowledge/` by default, or the consuming project's established documentation directory.

Stable IDs are strings chosen once and kept. No database, approval service, or signature system is required. A person's name appears only when the supplied source names them. Unknown owner, intent, or consequence stays `unknown`.

## States

| State | Meaning | Design outputs that are in scope | Stop before |
|-------|---------|----------------------------------|-------------|
| `NEEDS_PRODUCT_DECISION` | Usable Product expectations are absent | `product-expectations.md` + `product-expectations.json`, plus factual architecture docs | Candidate scoring rubric, evaluator, judge prompt, threshold, release gate |
| `RUBRIC_REVIEW` | Expectations exist; rubric is not approved | `rubric-review.md` + `rubric-register.json` | Evaluator implementation and judge prompts |
| `EVALUATOR_ROUTING` | Rubric version is approved; evaluator acceptance is separate | `evaluator-register.json` and the design docs that record routes | Treating an unaccepted evaluator as decision-eligible |
| `DECISION_READY` | Each criterion required by the declared decision policy has an accepted evaluator and a Product-approved consequence | Decision-facing plan, dataset split, harness spec | Using development labels as held-out acceptance evidence |

Display `NEEDS_PRODUCT_DECISION` as **BLOCKED — Product decision required**.

Stopping with a useful intake or review packet is successful skill behavior. Do not fill later documents to look complete.

## A. Product expectations

`product-expectations.json`:

```json
{
  "schema_version": "product-eval-contract/1",
  "artifact": "product-expectations",
  "state": "NEEDS_PRODUCT_DECISION",
  "display_state": "BLOCKED — Product decision required",
  "inventory": [
    {"id": "mode-1", "version": "observed-1", "mode": "", "output": "", "source": "path:line"}
  ],
  "applicability_map": [
    {
      "id": "app-1",
      "output": "",
      "candidate_behaviour": "",
      "product_story": "",
      "precondition": "",
      "status": "unknown"
    }
  ],
  "story_packet": [
    {
      "id": "story-1",
      "source": "",
      "scenario": "",
      "judgment_unit": "",
      "named_expert": "unknown",
      "exclusions": [],
      "open_decisions": []
    }
  ],
  "decision_log": [
    {
      "id": "dec-1",
      "question": "",
      "holder": "unknown",
      "decision": null,
      "status": "NEEDS_PRODUCT_DECISION",
      "source": ""
    }
  ],
  "observed_facts": [
    {"id": "fact-1", "statement": "", "source": "path:line", "kind": "observed"}
  ]
}
```

Inventory rows are versioned and pinned to code or a supplied Product source. Applicability status is `unknown` until Product decides it. Fill `observed_facts` from source-pinned code. Ask targeted questions in `decision_log`. Do not invent people or Product decisions.

Copyable Markdown tables use the same columns: Mode / Output / Source; Output / Candidate behaviour / Story / Precondition / Status; Source / Scenario / Unit / Expert / Exclusions / Open decisions; Question / Holder / Decision / Status / Source.

## B. Rubric review

`rubric-register.json` when expectations exist and approval is still open:

```json
{
  "schema_version": "product-eval-contract/1",
  "artifact": "rubric-register",
  "state": "RUBRIC_REVIEW",
  "criteria": [
    {
      "id": "C-1",
      "version": "candidate-0.1",
      "source_expectation_id": "story-1",
      "applicable_unit": "",
      "preconditions": "",
      "judgment": "one independently failable statement",
      "pass_rule": "",
      "fail_rule": "",
      "unscorable_rule": "",
      "required_evidence": "",
      "decision_consequence": {"proposal": "", "status": "proposed"},
      "approval_state": "pending"
    }
  ],
  "review": {
    "product_domain_approver": null,
    "named_expert": null,
    "reviewed_examples": [],
    "boundary_cases": [],
    "development_dataset": {"id": null, "version": null},
    "disagreements": [],
    "resolution": null,
    "unresolved_questions": [],
    "approval_state": "pending",
    "approved_version": null,
    "approved_date": null
  }
}
```

Candidate verdicts are `Pass` or `Fail`. Applicability and evidence sufficiency stay separate:

- **Not applicable** — outside this case; excluded from that criterion's denominator.
- **Unscorable** — serialize as `UNSCORABLE`, display “Unscorable”. Required evidence is missing or unreliable. Unknown applicability uses this route. It is never an automatic Not applicable.
- **Pass / Fail** — only after applicability and evidence sufficiency are established.

An ordinal product measure may remain only when that product's approved contract says the measure is ordinal. It does not replace the binary decision criterion. Do not invent a 1–5 semantic judge or partial-credit success metric.

`approval_state: pending` with null approver fields is the honest candidate record. Writing “approved” because the skill drafted the text is a failure.

## C. Evaluator register

After a rubric version is approved, route **each** criterion on its own. Record the route in `evaluator-register.json`:

| Condition | Route | Acceptance evidence |
|-----------|-------|---------------------|
| Mechanically computable from known fields | `deterministic` | Known-good, known-bad, and shortcut/edge cases tied to the implementation version |
| Interpretation, evolving boundaries, or named accountability | `human` | Named reviewer or resolvable reviewer ID, accepted procedure/rubric version, attributable item-level review. Pending stays pending |
| Stable, repeatable semantic judgment suitable for automation | `llm` | Fresh held-out expert labels, agreement/error and stability checks fit to that label regime, run-health checks, inspectable rationales, and a scoped acceptance decision |

```json
{
  "schema_version": "product-eval-contract/1",
  "artifact": "evaluator-register",
  "state": "EVALUATOR_ROUTING",
  "routes": [
    {
      "criterion_id": "C-1",
      "criterion_version": "1.0",
      "evaluator_type": "deterministic",
      "evaluator_id": "det-c1",
      "evaluator_version": "0.1",
      "measurement_rationale": "",
      "acceptance_state": "unaccepted",
      "decision_eligible": false,
      "execution_scope": "DIAGNOSTIC/SHADOW ONLY",
      "evidence": {
        "kind": "verification",
        "cases": [],
        "implementation_version": null
      },
      "provenance": {"rubric_source": "rubric-register.json", "notes": ""},
      "decision_consequence": {"rule": "", "status": "approved"}
    }
  ],
  "datasets": {
    "development": {"id": "", "version": "", "manifest": ""},
    "held_out_validation": {"id": "", "version": "", "manifest": ""}
  }
}
```

Reject a missing or mismatched criterion/evaluator version. A bare `approved: true` or `validated: true` without the record above is not acceptance. Do not force a human route through model-validation statistics. Do not invent a universal kappa, correlation, or sample-size threshold. Changing the rubric, prompt, model, or evaluator outside the accepted scope requires renewed verification or validation.

Development examples and held-out validation labels have separate IDs, versions, and membership manifests. Overlapping item IDs or content cannot count as held-out evidence. If validation examples inform a revision, move them to development and require a fresh held-out set.

## D. Diagnostic versus decision

An unaccepted evaluator may run only as `DIAGNOSTIC/SHADOW ONLY`. That run must not establish a decision baseline, clear an artifact, block CI through its scores, alter release eligibility, or support a consequential decision.

A successful diagnostic run may exit 0. It still records `decision_eligible: false` and no release verdict. Process health is separate from a Product-quality verdict.

Explicit gate mode preflights approval, accepted evaluator versions and evidence, the Product consequence/aggregation rule, and required coverage. Invalid gate configuration exits nonzero with a blocked reason **before** quality evaluation. That refusal is not a Product failure from a judge.

Mixed runs keep shadow scores and errors off accepted gate inputs. If the declared decision policy requires an unaccepted criterion, the decision is blocked. Do not drop it silently. Flipping an optional shadow result must not flip the gate exit code or an accepted baseline.

## E. Decision evidence

When an evaluator is accepted, carry criterion version, evaluator type and version, acceptance status and evidence, provenance, and consequence through config, per-item records, aggregates, and gate reports. Link each record back to the register IDs.

`Pass` / `Fail` apply only to scorable applicable units. Not applicable leaves the denominator. Unscorable, pending, and error counts stay visible with the predeclared consequence. An empty set, an all-excluded set, or missing required evidence is never an automatic pass.

Aggregate only with the Product-approved rule. Deterministic assertions and attributable human judgments do not wait for a model judge. Keep the Product outcome (Layer 2) distinct from component diagnostics (Layer 1).

Start with one production-like output (`k=1`, limit 1) through the real application entrypoint. One item is wiring and inspection evidence. Broaden or repeat only for a declared measurement need. Preserve the retry contract. A best-of-N selection is not k=1 evidence.

## State transitions

1. No usable expectations → write the intake, state `NEEDS_PRODUCT_DECISION`, stop.
2. Expectations supplied, review record not approved → write the candidate rubric and review packet, state `RUBRIC_REVIEW`, stop.
3. Approved rubric version recorded → route each criterion, state `EVALUATOR_ROUTING`. Unaccepted routes stay diagnostic.
4. Scoped acceptance evidence recorded for every criterion the decision policy requires → `DECISION_READY` for that policy only.

Factual architecture documents may be written in every state. They record observed behaviour and configuration. They are not Product intent, approved thresholds, or decision authority.
