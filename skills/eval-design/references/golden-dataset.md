# Step 4: Generate golden dataset spec

Produce a golden dataset spec document (`4. golden-dataset-spec.md`) with sections 4A–4K.

**Mandatory-content rule.** Every section below is required unless a Step 1/2 verdict prunes it; pruned sections must say **"N/A — [reason]"** in place, never be silently dropped.

## 4A. Evaluation scope

- Behaviours/tasks to evaluate (prioritized)
- Eval levels (what "correct" means at each level of output richness)
- Scenario dimensions to stratify by

## 4B. Dataset composition

Determine the segment split based on the **goal of the AI system being evaluated.** The composition should reflect what matters most for the system's use case:

| System goal | Composition strategy | Reasoning |
|-------------|---------------------|-----------|
| **Safety-critical detection** (e.g., fights, weapons, medical emergencies) | Heavy negatives (60%+), moderate positives, moderate edge cases | False positives erode trust but false negatives are dangerous — need both strong recall AND precision |
| **High-volume classification** (e.g., ticket routing, content moderation) | Balanced positives across categories, moderate negatives, heavy edge cases (30%+) | The system sees many true positives daily — the hard part is distinguishing between similar categories |
| **Rare event detection** (e.g., fraud, anomalies, defects) | Very heavy negatives (70%+), small but sufficient positives, targeted edge cases | Mirrors production reality where 99% of inputs are normal — precision on the rare positives matters most |
| **Generation/creative tasks** (e.g., essay feedback, summarization, recommendations) | Diverse inputs covering the full difficulty range, fewer "negatives" (may not apply), heavy edge cases | No binary correct/wrong — evaluation is about quality gradients across input types |
| **Multi-step reasoning** (e.g., diagnosis, investigation, planning) | Moderate positives with varying complexity levels, edge cases that test reasoning boundaries | The system needs to handle simple AND complex cases — composition should stratify by difficulty |

**The agent should:**
1. Identify which system goal pattern applies (or blend if multiple apply)
2. Propose a specific segment split with proportions and justify it based on the system's failure consequences
3. Consider: what does the system see most in production? What failures are most costly? Where is the decision boundary hardest?

**Deviation rule:** The pattern proportions above are defaults, not laws — but any deviation must be **explicitly justified in the document** (e.g. "45% negatives instead of the 60%+ default because each positive behaviour × venue cell needs enough positives for per-cell CIs, which caps the negative share at this dataset size"). A split that silently departs from the chosen pattern is a spec defect.

**Sample size:** Size each cell to achieve the CI precision you need, not a fixed number. High-stakes cells (P0 safety, fairness comparisons) require n ≥ 100 for actionable CIs (±0.07 half-width on a proportion near 0.85). Standard cells need n ≥ 50 (±0.10). Exploratory cells tolerate n ≥ 30 for Phase 1 baselines only — flag as "underpowered" and plan to grow. See eval-plan 3H for the full sample-size-vs-CI-width lookup table. Never claim statistical significance from n=30 on a proportion near 0.5.

**Matrix:** scenario dimensions × behaviour types × segments → total count. The matrix shape itself depends on the system — a binary detector has fewer cells than a multi-class classifier. **If there are no scenario dimensions** (per Step 1), drop that axis: the matrix reduces to behaviour/category × segments (or difficulty band × segments). Do not add a placeholder scenario axis.

**Arithmetic check:** the matrix cells must sum to the grand total, and the per-segment column sums must match the stated segment proportions (within rounding). Verify before finishing (Step 8).

## 4C. Data sources

For each segment, recommend:
- Real production data (preferred for negatives and where available)
- Staged/simulated (for positives that are rare in production)
- Synthetic/AI-generated (only for edge cases that can't be safely staged; note domain gap risk)

Always flag: **synthetic data cannot be the primary benchmark.** The benchmark must reflect real production conditions.

## 4D. Edge cases

For each behaviour type, list:
- Scenarios that look like the target behaviour but aren't
- Why they're hard (visual/semantic signature overlap)
- What makes them different from true positives

Derive these from the behaviour definitions and venue templates in the codebase.

## 4E. Annotation schema

Design the minimum annotation that supports L1+L2 eval:
```json
{
  "item_id": "string",
  "scenario_type": "string",
  "segment": "positive | edge_case | negative",
  "events": [
    {
      "type": "string (from system's taxonomy)",
      "timestamp_start": "number (if temporal)",
      "timestamp_end": "number (if temporal)",
      "is_true_event": "boolean"
    }
  ]
}
```

Adapt fields to the domain (timestamps for video/audio, spans for text, regions for images).

**Annotator identity:** reference annotators by opaque `annotator_id` only. Do not put direct PII (names, emails) in the widely-accessible annotation records; keep the id→person mapping in a separate restricted store.

**Dataset versioning:** the dataset carries a version (content hash or tag) that changes whenever items are added, removed, or re-labeled. Eval runs record this version (see eval-plan 3H, run provenance).

## 4F. Matching logic

Define what counts as a "match" between system output and ground truth:
- Same event type
- Overlap within tolerance. **Justify the tolerance in user-utility terms** — "would a human find the relevant content by navigating to this point?" — even when aligning with an existing implementation's threshold. If an implementation threshold already exists in the codebase, state both the alignment and the user-utility rationale.

## 4G. Metrics

| Metric | What it answers | Reporting format |
|--------|-----------------|-----------------|
| Detection recall | Of real events, how many found? | point [lower, upper] 95% CI (Wilson) |
| Detection precision | Of system outputs, how many real? | point [lower, upper] 95% CI (Wilson) |
| Classification accuracy | Of detected events, how many correctly categorized? | point [lower, upper] 95% CI (Wilson) |
| False positive rate on negatives | How often does it hallucinate on quiet inputs? | point [lower, upper] 95% CI (Wilson) |
| Edge case discrimination | Can it distinguish true from borderline? | point [lower, upper] 95% CI (Wilson) |
| Consistency (non-deterministic models) | How stable are results across re-runs? | agreement_rate ± std (N runs per item, see eval-plan 3H) |

All reported per scenario dimension (or per real variation axis if no scenario dimension exists). When the fairness track applies (eval-plan 3G), additionally stratify by each demographic/condition axis and report disparity ratios with bootstrap CIs.

## 4H. Acceptance criteria for dataset items

- Minimum duration/length for sufficient context
- Representative of production conditions (camera angle, resolution, format, etc.)
- Unambiguous ground truth — with this default adjudication procedure (adapt thresholds only with justification):
  1. Edge-case and adversarial items are **double-labeled** by independent annotators.
  2. Compute inter-annotator agreement (Cohen's kappa for categorical labels).
  3. Kappa ≥ 0.6 → keep, record kappa on the item. Below 0.6 → a third senior annotator adjudicates; if still unresolved, exclude the item (ambiguous ground truth poisons the benchmark).
  4. A random 10% of single-labeled positives/negatives are also double-labeled as a drift check on annotation quality.
- Privacy/anonymization requirements met

## 4I. Phased rollout

| Phase | When | What |
|-------|------|------|
| Phase 0 | Now | Finalize spec. Optional synthetic for early development. |
| Phase 1 | Data access ready | Capture/collect real data |
| Phase 2 | Annotation | Label per schema. Double-label edge cases per 4H. |
| Phase 3 | Baseline | Run system, compute metrics, establish baseline — including the 5-run noise band (eval-plan 3H), which Phase 4's regression gates depend on. **Calibrate all LLM-as-judge evaluators here** (eval-plan 3B calibration process); complete any rubric stubs before calibration. No judge score enters a gate before its calibration passes. |
| Phase 4 | Ongoing | Re-run on every change. Gate deployments. |

## 4J. Adversarial & fairness dataset segment

> **Adaptivity rule:** Include this section ONLY when the Step 2 untrusted-input tier is `end-user` or `trusted-author`, OR "Judges people" = yes. Otherwise state "Adversarial/fairness segment: not applicable" and skip.

### Adversarial segment composition

**This table is the single source of truth for adversarial counts** — the eval plan (3G) references it and must not restate different numbers.

| Sub-segment | Target count | Applies at tier | Source | Notes |
|-------------|-------------|-----------------|--------|-------|
| Prompt injection / jailbreak | 20–30 items | `end-user` (replace with template/config injection, same count, at `trusted-author`) | Red-teaming workshops; adapt published attack taxonomies to this domain | Craft domain-specific attacks, not generic "ignore instructions" — e.g. malicious text in a filename, document field, or template field |
| Malformed / corrupted input | 20–30 items | All tiers | Perturbation of real items: truncate, corrupt headers, inject encoding errors, zero-length payloads | Automated generation acceptable |
| Out-of-distribution | 20–30 items | All tiers | Real items from adjacent but wrong domains (e.g. nature documentary for a classroom model) | Tests whether the system confidently hallucinates vs declines |
| Adversarial false-positive triggers | 30–50 items | All tiers | Staged look-alikes; curated from production false positives; adversarially selected edge cases | The hardest items — designed to maximise false positive rate |

**Total: 90–140 items when all four sub-segments apply** (sum of the ranges above; scale down proportionally when the tier prunes a sub-segment). Every sub-segment that applies gets an explicit count in the generated spec — a sub-segment mentioned only in sourcing prose, without a count, is a spec defect. Domain-specific extra sub-segments (e.g. occupancy-hallucination triggers for a headcount system) are encouraged; add them as counted rows.

**Sourcing guidance:**
- **Red-teaming** is the primary source for injection/jailbreak items. Run 2–3 hour workshops with team members instructed to break the system.
- **Perturbation of real items** is primary for malformed/OOD. Take real production items and systematically degrade them.
- **Synthetic generation** is acceptable for malformed inputs only (encoding corruption, truncation). It is NOT acceptable as the primary source for adversarial false-positive triggers — those must come from real or realistically-staged scenarios.
- Apply the same "synthetic is never the primary benchmark" caveat as 4C.

### Fairness annotation fields

When the fairness track applies, add these fields to the annotation schema (4E). The axes here must be exactly the axes listed in the eval plan's fairness track (3G) — same names, same levels:

```json
{
  "fairness_metadata": {
    "axis_labels": {
      "[axis_1]": "string (level within axis, e.g. 'Fitzpatrick IV')",
      "[axis_2]": "string | null",
      "[condition_axis]": "string (e.g. 'poor_lighting', 'ceiling_camera')"
    },
    "labeler_confidence": "string (certain | probable | uncertain)",
    "consent_reference": "string (IRB/consent-form ID)"
  }
}
```

**Axis selection (from Step 2):** Only include axes that are (a) present in the actual population, (b) plausibly correlated with model error given the input modality, and (c) can be labelled with reasonable confidence. Do not include axes that require speculation.

**Privacy and access control:**
- Fairness-axis labels are **PII-adjacent sensitive data**. Store in a separate access-controlled partition from the main annotation dataset.
- Access restricted to: eval pipeline service account (read-only), designated DS reviewers (read-only), data protection officer (audit).
- Never surface demographic labels in production dashboards, Langfuse traces, or any user-facing interface.
- Retention: follow the same data-protection schedule as the raw video/media. Delete when the item exits the golden dataset.
- Consent: fairness-axis annotation requires explicit consent or IRB approval. Reference the consent mechanism in each item's `consent_reference` field.

## 4K. Annotation process & tooling

The schema (4E) says what ground truth looks like; this section says **how it gets created, by whom, and in what tool**. A spec without this section leaves the most labor-intensive step undefined.

**Tooling table.** For each kind of ground truth the eval needs, name the tool:

- **First, check the codebase for an existing in-app annotation/review feature** (annotation routers, verification/review endpoints, label exports). If the product already has one, prefer it for output-shaped ground truth (event timelines, labels, verdicts) — annotators see the same player/timebase the system reports in, and per-annotator records support the 4H double-labeling. Name the actual routes/services found.
- **Spatial ground truth** (bounding boxes, regions, masks, keypoints — for deterministic CV components) almost always needs an **external annotation tool** (e.g. CVAT, Label Studio): in-app tools rarely support geometry. Specify the export format (COCO or equivalent) and where exports land (object storage + in-repo manifests).
- **Langfuse is not an annotation tool for creating ground truth.** Its annotation queues let humans *score system outputs* against score configs — no media scrubbing, no geometry. Assign it exactly two roles: LLM-judge calibration (eval-plan 3B) and review of flagged production traces. State this explicitly — it is a common misconception.

**Timebase / granularity rule.** Annotate at the level of the **full input in absolute coordinates** (whole video with absolute timestamps, whole document with global spans) — never per pipeline chunk/segment, because chunking is a config knob under evaluation. Component-level ground truth that must match the system's segmentation (e.g. an isolated per-chunk eval) is **derived mechanically** from the full-input GT using the pipeline's own segmentation code (clip at boundaries, flag boundary-straddling items for human verification). One source of truth; never annotate the same content twice in two timebases. *(Single-stage systems: state "N/A — no segmentation".)*

**AI-assisted pre-labeling guardrails.** If annotators can approve/correct the system's own outputs into ground truth (fast, and many in-app tools support it), the GT risks anchoring to the system under eval. Require: (1) a full-scrub rule — approving system outputs never replaces reviewing the full input for missed events; (2) edge-case, adversarial, and the 4H drift-check sample are annotated **blind** (system output hidden); (3) approved outputs' details (timestamps/spans) are re-verified to the 4H standard, not accepted as-is; (4) record `source: manual | ai_approved` per annotation and compare blind-vs-assisted recall in the quality report — the gap is measured pre-label bias.

**Configuration vs annotation.** Distinguish ground truth from *product configuration that eval results depend on* (e.g. ROI lines/zones, routing rules, thresholds drawn/set by app users). Configuration is not annotated — the spec must say **who freezes it for eval** (typically DS), that it is **versioned with the dataset**, and that changing it invalidates the GT that was created against it.

**Export → dataset conversion.** Name the owner of the conversion script (annotation-tool export → 4E schema → the harness's item format), the stable-ID rule for ground-truth events, and require the conversion to be **hash-stable** (re-running on unchanged annotations is byte-identical), since `dataset_version` is a content hash.

**Roles table.** Annotators (who, what training), senior adjudicator (4H disagreements + boundary verification), DS (taxonomy/spec ownership, slicing + conversion scripts, quality report, frozen configs), privacy officer (fairness partition audit, consent verification — when 4J applies).
