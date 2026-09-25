---
name: eval-design
description: >-
  Design evaluation for an AI/LLM system from a Stage 00 Eval Spec, Product
  expectations, and the codebase: a blocked intake when the spec or expectations
  are not ready, a candidate atomic binary rubric for expert review, or
  per-criterion evaluator routing after the rubric is approved. Tags observed
  outputs as classification, open-ended generative, rubric scoring,
  conversational, or agentic. Includes factual architecture notes, a golden
  dataset split, Langfuse evidence design, a harness spec, and a stakeholder
  HTML overview only for the sections the current state allows. Use when the
  user asks to design evals, an evaluation strategy, a golden dataset, an eval
  harness, LLM observability, or Langfuse instrumentation.
---

# Eval design from Product expectations and the codebase

Invoke from the project root. Read [references/eval-spec.md](references/eval-spec.md) first, then [references/product-expectations.md](references/product-expectations.md). Output completeness depends on workflow state. A useful intake or review packet is a successful finish. A missing Eval Spec answer or holder blocks rubric drafting. Do not invent the missing piece.

Product/domain supplies expectations; the PM coordinates that intake. Data science or the AI drafter writes atomic binary criteria. Product/domain and the named expert test, approve, and version the rubric. Each approved criterion then chooses its own evaluator. Evaluator acceptance is a separate record and is required before decision use.

## Workflow

Copy this checklist and stop at the first state that matches the evidence:

```
- [ ] Step 0: Eval Spec, then Product intake — read references/eval-spec.md and references/product-expectations.md
- [ ] Step 1: Factual discovery — read references/architecture-docs.md
- [ ] Step 2: Record observed eval-relevant facts (unknowns stay unknown)
- [ ] If state is NEEDS_PRODUCT_DECISION: write the intake and stop
- [ ] Step 3: Candidate rubric review — read references/eval-plan.md
- [ ] If state is RUBRIC_REVIEW: write the review packet and stop
- [ ] Step 4: Dataset split — read references/golden-dataset.md
- [ ] Step 5: Evidence registry — read references/langfuse-setup.md
- [ ] Step 6: Harness spec — read references/eval-harness.md
- [ ] Step 7: HTML overview — read references/html-overview.md
- [ ] Step 8: Self-verification for the sections this state allows
```

Do not ask the user to supply code facts you can read. Do ask, in the decision log, for Product intent, ownership, consequence, and boundaries you cannot read from code.

## Step 0: Eval Spec, then Product intake

Search the repo and the user message for `eval-spec.json` (and `eval-spec.md`). If a supplied spec is already `READY`, keep its 8 answers, holders, and `trial_contract` unchanged. If it is missing, or any required answer or holder is missing, write the Eval Spec from [references/eval-spec.md](references/eval-spec.md) with `state: NEEDS_PRODUCT_DECISION` and leave the missing answer null. Code may mark a factual candidate `proposed`. Do not mark it `decided`. Carry a supplied trial contract through unchanged (`k=1`, `pass^k`, or `pass@k`, and its k).

Then search for a versioned expectations packet (Markdown plus `product-expectations.json`). If none exists, or required decisions are unresolved, or the Eval Spec is not `READY`, produce the intake and set:

```json
"state": "NEEDS_PRODUCT_DECISION",
"display_state": "BLOCKED — Product decision required"
```

Include the versioned mode/output/source inventory, applicability map, story packet, and decision log from the contract. Add one `NEEDS_PRODUCT_DECISION` decision-log row for each missing Eval Spec answer or holder. Prefill observed system facts from source-pinned code. Mark unknown owner, intent, and consequence as `unknown`.

Do not generate an evaluator, candidate scoring rubric, judge prompt, threshold, or release gate from a not-ready Eval Spec or from absent expectations. Do not choose turn versus session when the judgment-unit answer is missing.

## Step 1: Factual discovery

Explore the codebase and record what the code does. Read [references/architecture-docs.md](references/architecture-docs.md). These documents describe observed behaviour and configuration. They are not intended behaviour, approved thresholds, or decision authority.

Discovery questions (answer from code; leave Product questions in the decision log):

1. What user-visible modes and outputs exist, and which source files implement them?
2. What is the tech stack and which tiers actually exist?
3. Which components are deterministic and which call a model?
4. How does data move from input to each output surface?
5. Are there async, batch, or post-processing steps?
6. Which configs change behaviour, and what are the code-derived thresholds?
7. What shipped recently (`git log`)?
8. What observability exists today?
9. Does untrusted content reach a model prompt (`none`, `trusted-author`, or `end-user`)?
10. Does the system make judgments about people, and is a wrong output safety-critical? Record the question; do not assign a Product harm policy.

### System shape

On each inventory output, record one or more observed archetypes in `archetypes`: `classification`, `open-ended generative`, `rubric scoring`, `conversational`, `agentic`. The tag is an observed fact about the output. It does not decide criteria, routes, or thresholds. Use the archetype only later, when a ready Eval Spec allows candidate criteria, and follow the matching section in [references/eval-plan.md](references/eval-plan.md).

Classify pipeline shape from code and record one line:

```
System shape: single-stage LLM call · no scenario dimensions (stratify by input difficulty)
System shape: multi-stage async pipeline · observed variation axis = venue_type
```

- **Multi-stage** keeps component diagnostics for stages that exist.
- **Single-stage** collapses diagnostics to the call plus real pre/post steps.
- **No scenario dimension** means you do not invent one. Stratify by variation that exists, or say the system is uniform.

## Step 2: Observed properties

| Property | How to find it | If absent |
|----------|----------------|-----------|
| Output surfaces | Modes, handlers, return types | Inventory row stays empty and the intake asks for it |
| Output archetype | Tool use, dialogue turns, class labels, free text, ordinal bands | Tag what the code emits; do not invent a criterion from the tag |
| Observed variation axis | Config, templates, routing | Do not invent a scenario dimension |
| Pipeline stages | Call graph | Collapse Layer 1 and say so |
| Deterministic components | Non-LLM models and pure functions | No deterministic route is proposed for them |
| Model calls | Client usage | No LLM route is proposed until a criterion needs one |
| Untrusted input tier | Prompt construction | Record the tier; adversarial checks wait for a Product criterion |
| People-judging / harm | Domain behaviour in code | Record the observation; consequence stays a Product decision |

## Steps 3–7, only when the state allows them

- **Eval Spec `READY` and expectations present, rubric unapproved** — write `rubric-review.md` and `rubric-register.json`. Each criterion has an ID and version, source expectation, applicable unit equal to the spec's judgment unit, preconditions, one independently failable judgment, pass rule, fail rule, unscorable rule, required evidence, and a proposed consequence whose status is `proposed`. Follow the archetype pattern for that output. Carry `trial_contract` from the Eval Spec; do not rewrite it. The review record lists the Product/domain approver, named expert, real examples, boundary cases, development dataset ID/version, disagreements, unresolved questions, and `approval_state: pending` until a source supplies approval. Then stop. Do not write judge prompts, numeric thresholds, or evaluators.
- **Rubric version approved** — read or write `evaluator-register.json`. Route every approved criterion independently: fully specified and machine-observable → `deterministic`; interpretive, evolving, rare, or requiring named accountability → `human` (named expert); interpretive, stable and repeated at scale → optional `llm`, only after fresh held-out human validation and evaluator acceptance. A rare criterion stays with the named expert even when its judgment is stable. Choosing `llm` requires a stated volume reason in `measurement_rationale`. Carry criterion ID/version, evaluator type/ID/version, measurement rationale, acceptance state, scoped evidence, provenance, and decision consequence. Missing approval evidence keeps `acceptance_state` unaccepted and `decision_eligible` false. A bare `approved: true` is not enough.
- **Dataset, Langfuse, harness, HTML** — produce these only after the rubric is approved, and only with the routes and acceptance states the register actually contains. Unaccepted evaluators are specified as `DIAGNOSTIC/SHADOW ONLY`.

Candidate verdicts are `Pass` / `Fail`. Serialize insufficient evidence as `UNSCORABLE`. Unknown applicability uses that route.

## Output files

| File | When |
|------|------|
| `eval-spec.md` + `eval-spec.json` | Always. First artifact. `READY` or `NEEDS_PRODUCT_DECISION` |
| `product-expectations.md` + `product-expectations.json` | Always when intake is missing or blocked; also when later states need the packet |
| `1. Codebase Architecture Overview.md`, `2. LLM In-Out Flow.md` | Whenever code was explored; factual only |
| `rubric-review.md` + `rubric-register.json` | Expectations exist and the rubric is not yet approved, and again as the approved record when a version is approved |
| `evaluator-register.json` | An approved rubric version is in hand |
| `3. eval-plan-full.md` | Approved rubric; decision gates only for accepted evaluators |
| `4. golden-dataset-spec.md` | Approved rubric; separate development and held-out IDs |
| `5. langfuse-setup.md` | Approved rubric; proxies named separately from decision scores |
| `6. eval-harness.md` | Approved rubric; diagnostic default; gate mode fail-closed |
| `architecture-eval-overview.html` | The same state as the documents above; blockers visible |

Header for every generated Markdown document:

```
# [Project] [document name]

Version: Draft 1.0 — [today's date]
State: [NEEDS_PRODUCT_DECISION | RUBRIC_REVIEW | EVALUATOR_ROUTING | DECISION_READY]
```

## Step 8: Self-verification

Check only the artifacts this state should contain. Fix failures before finishing. Do not create the later artifacts to satisfy a checklist row.

### 8A. State completeness

- [ ] The JSON `state` matches the Markdown display state.
- [ ] The Eval Spec lists all 8 decision ids. `READY` only when every answer and holder is supplied. Otherwise `NEEDS_PRODUCT_DECISION`, and the decision log has one row per missing answer or holder.
- [ ] `NEEDS_PRODUCT_DECISION` has inventory, applicability map, story packet, decision log, and observed facts. No scoring rubric, judge prompt, threshold, or release gate appears anywhere in the output. A missing judgment unit is not filled with turn or session.
- [ ] `RUBRIC_REVIEW` criteria are individually binary, source-linked, and `approval_state: pending` unless the user supplied an approval record. No evaluator implementation.
- [ ] `EVALUATOR_ROUTING` has one route per approved criterion, with versions. Unaccepted routes are `DIAGNOSTIC/SHADOW ONLY`.
- [ ] Development and held-out datasets, when present, have different IDs, versions, and manifests, and no shared items.
- [ ] Header convention and system-shape line appear on documents that were written.
- [ ] Pruned sections say **N/A — [reason]** in documents that exist.

### 8B. Cross-document consistency

- [ ] Shared IDs and versions match across Markdown and JSON.
- [ ] Code-derived thresholds are quoted as observed facts, not as approved gates.
- [ ] Score names used for decisions exist only for accepted evaluators. Production proxy names are distinct.
- [ ] Layer 1 stages match observed pipeline stages. The harness does not gate on a shadow score.

### 8C. Internal correctness

- [ ] Worked examples reconcile with their pass, fail, and unscorable rules.
- [ ] Confidence intervals appear only on aggregates, and only where a declared measurement need exists.
- [ ] One-item or k=1 examples are labeled wiring evidence.
- [ ] No universal kappa, correlation, or sample-size threshold was invented.

## Principles

1. Product intent comes from Product/domain. Code discovery records observations.
2. One criterion, one independently failable judgment, `Pass` or `Fail` when the case is scorable.
3. Not applicable leaves the denominator. Unscorable stays visible and follows the predeclared route.
4. The rubric is approved before any evaluator is built. The evaluator is accepted before it can decide.
5. Route each criterion on its own. A human route does not need a model-validation statistic.
6. Online proxies and offline decision evidence use different names.
7. The harness calls production code paths. Langfuse stores evidence and never enforces a gate.
8. Start with one production-like output. Repeat only for a declared measurement need.
9. Stratify by an observed axis when one exists. Do not invent a scenario dimension.
10. Empty, all-excluded, or missing-required evidence never yields a pass.
