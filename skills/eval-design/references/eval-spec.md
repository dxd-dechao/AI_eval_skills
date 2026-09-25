# Stage 00 Eval Spec

Read this before [product-expectations.md](product-expectations.md). One Eval Spec per end-to-end feature and launch decision. Product/domain agrees it before rubric drafting. Write `eval-spec.md` beside `eval-spec.json`. Schema version: `product-eval-contract/1`.

Owner roles, used as `holder_role` (a person's name appears only when a supplied source names them):

| Role | Scope |
|------|--------|
| Product/domain | Owns intended behaviour. The PM coordinates intake. |
| DS | Operationalises the spec. |
| Engineering | Identifies observable evidence. |
| Governance | Policy/governance retains approval and minimum-obligation rights. |
| Named expert | Reference role. Resolves semantic boundaries. Not a substitute holder for Product/domain. |

`signed` is `{holder, date, version}`. Fill it only when one supplied source gives all three. Otherwise each field is null. Writing a signature because the skill drafted the spec is a failure.

## Readiness

`state` is `READY` only when all 8 decisions below have a non-empty `answer`, a `holder` other than `unknown`, and `status: decided`. Otherwise:

```json
"state": "NEEDS_PRODUCT_DECISION",
"display_state": "BLOCKED — Product decision required"
```

If a required answer or holder is missing, the Eval Spec is not ready. Code discovery may prefill a factual item (for example a candidate judgment unit observed in code) as `status: proposed` with a source path. Proposed is not decided. Do not invent an answer, a named holder, a threshold, or a turn-versus-session choice.

A not-ready spec blocks rubric drafting. Also write the Product intake. Add one `NEEDS_PRODUCT_DECISION` row to `product-expectations.json` `decision_log` per missing answer or holder. The row's `holder` is the named holder when the source names one, otherwise `unknown`. The question names the missing decision.

## Eight required decisions

Record every row. Do not drop a row because the answer is unknown.

| id | Question | holder_role |
|----|----------|-------------|
| `end-to-end-feature` | What complete user-facing behavior will this Eval Spec evaluate for one launch decision? | Product/domain owner |
| `judgment-unit` | What is one artifact being judged (output, passage, rubric dimension, turn, session, or task episode), and what makes it pass? | Product/domain; the named expert resolves semantic boundaries |
| `outcome-verdict` | What outcome decides pass, and which architecture-derived checks materially help locate failure? | Product/domain + named expert |
| `measurement-decision` | What decision does each measurement drive: ship gate, alarm, or research insight? | Product/domain; policy/governance authorizes consequential use |
| `trial-contract` | Is one attempt the promise, or are several attempts part of the experience, and which of `k=1`, `pass^k`, or `pass@k` is recorded, with what k? | Product/domain |
| `governance-profile` | Which governance profile applies, what minimum evidence and protection obligations does it impose, and who may approve launch, controlled evidence accrual, a waiver, or an external claim? | Policy/governance |
| `protection-requirement` | For each material risk, what must be prevented before it takes effect, and what may be detected or reviewed later? | Product/domain defines harm; policy/governance sets the minimum |
| `harm-asymmetry` | For each criterion or risk, which error is worse, a miss or a false alarm? | Product/domain; policy/governance constrains consequential risks |

Rules that travel with the answers:

1. One spec covers one end-to-end feature and one launch decision.
2. The judgment unit fixes the outcome verdict, the labelled row, and every rate denominator. It does not select the grader type. Each later rubric criterion uses this unit.
3. The outcome verdict is mandatory. Diagnostic decomposition is optional: it helps locate failure and never replaces the outcome.
4. Ship gates and alarms need an explicit decision rule. Research insight needs no pass threshold.
5. Trial contract is `k=1`, `pass^k`, or `pass@k`, with the selected k. Record per-trial success and k. Never compare or trend results across different k. Copy the same mode and k into top-level `trial_contract`. Do not change a supplied contract.
6. The governance profile sets minimum obligations, not sample size, evaluator type, or action channel.
7. Protection requirements state consequence and timing, not mechanism.
8. Harm asymmetry records which error is worse. It does not choose operating points.

## JSON

```json
{
  "schema_version": "product-eval-contract/1",
  "artifact": "eval-spec",
  "state": "NEEDS_PRODUCT_DECISION",
  "display_state": "BLOCKED — Product decision required",
  "feature_id": "",
  "decisions": [
    {
      "id": "end-to-end-feature",
      "question": "What complete user-facing behavior will this Eval Spec evaluate for one launch decision?",
      "answer": null,
      "holder": "unknown",
      "holder_role": "Product/domain owner",
      "status": "NEEDS_PRODUCT_DECISION",
      "source": ""
    }
  ],
  "trial_contract": {"mode": null, "k": null},
  "signed": {"holder": null, "date": null, "version": null}
}
```

`decisions` always has the 8 ids in the table order. `trial_contract.mode` is `k=1`, `pass^k`, or `pass@k` when that decision is `decided`; otherwise null. `trial_contract.k` is the selected integer. A ready example sets `state` to `READY`, `display_state` to `Eval Spec ready`, and fills `signed` only from a supplied source.

## Copyable template

```
| id | question | answer | holder | holder_role | status | source |
|----|----------|--------|--------|-------------|--------|--------|
| end-to-end-feature | What complete user-facing behavior will this Eval Spec evaluate for one launch decision? |  |  | Product/domain owner | NEEDS_PRODUCT_DECISION |  |
| judgment-unit | What is one artifact being judged, and what makes it pass? |  |  | Product/domain; the named expert resolves semantic boundaries | NEEDS_PRODUCT_DECISION |  |
| outcome-verdict | What outcome decides pass, and which checks only help locate failure? |  |  | Product/domain + named expert | NEEDS_PRODUCT_DECISION |  |
| measurement-decision | Ship gate, alarm, or research insight? |  |  | Product/domain; policy/governance authorizes consequential use | NEEDS_PRODUCT_DECISION |  |
| trial-contract | k=1, pass^k, or pass@k, and which k? |  |  | Product/domain | NEEDS_PRODUCT_DECISION |  |
| governance-profile | Which profile, which minimum obligations, and who may approve? |  |  | Policy/governance | NEEDS_PRODUCT_DECISION |  |
| protection-requirement | What must be prevented before it takes effect, and what may be detected later? |  |  | Product/domain defines harm; policy/governance sets the minimum | NEEDS_PRODUCT_DECISION |  |
| harm-asymmetry | Which error is worse, a miss or a false alarm? |  |  | Product/domain; policy/governance constrains consequential risks | NEEDS_PRODUCT_DECISION |  |
```
