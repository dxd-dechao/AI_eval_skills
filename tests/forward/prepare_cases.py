#!/usr/bin/env python3
"""Create three temporary repos for product-first skill forward checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

APP = '''\
"""Tiny document summarizer used only as a forward-test fixture."""

from pathlib import Path

_COUNTER = Path(__file__).with_name("invocation_count")


def _bump() -> int:
    n = int(_COUNTER.read_text()) if _COUNTER.exists() else 0
    n += 1
    _COUNTER.write_text(str(n))
    return n


def summarize(document: str) -> dict:
    """Production entrypoint. One call increments the counter by one."""
    calls = _bump()
    text = document.strip()
    words = text.split()
    headline = " ".join(words[:8]) if words else ""
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            bullets.append(line[:80])
    return {
        "headline": headline,
        "bullet_count": len(bullets),
        "char_count": len(text),
        "mentions_total": "total" in text.lower(),
        "invocation_count": calls,
    }
'''

EXPECTATIONS = {
    "schema_version": "product-eval-contract/1",
    "artifact": "product-expectations",
    "state": "RUBRIC_REVIEW",
    "display_state": "Expectations supplied — rubric not approved",
    "inventory": [
        {
            "id": "mode-summary",
            "version": "observed-1",
            "mode": "summarize",
            "output": "headline, bullet_count, char_count, mentions_total",
            "source": "app/summarize.py:summarize",
        }
    ],
    "applicability_map": [
        {
            "id": "app-headline",
            "output": "headline",
            "candidate_behaviour": "Headline uses the document's opening words",
            "product_story": "Reader sees a faithful short title",
            "precondition": "Document is non-empty",
            "status": "in_scope",
        }
    ],
    "story_packet": [
        {
            "id": "story-brief",
            "source": "fixture expectations",
            "scenario": "One document in, one summary out",
            "judgment_unit": "The dict returned by summarize",
            "named_expert": "fixture-expert",
            "exclusions": ["Do not score writing style"],
            "open_decisions": [],
        }
    ],
    "decision_log": [
        {
            "id": "dec-style",
            "question": "Is writing style in scope?",
            "holder": "fixture-pm",
            "decision": "No. Style is excluded.",
            "status": "decided",
            "source": "fixture expectations",
        }
    ],
    "observed_facts": [],
}

RUBRIC_PENDING = {
    "schema_version": "product-eval-contract/1",
    "artifact": "rubric-register",
    "state": "RUBRIC_REVIEW",
    "criteria": [
        {
            "id": "C-len",
            "version": "candidate-0.1",
            "source_expectation_id": "story-brief",
            "applicable_unit": "summarize() result",
            "preconditions": "non-empty document",
            "judgment": "char_count equals the stripped document length",
            "pass_rule": "char_count matches",
            "fail_rule": "char_count differs",
            "unscorable_rule": "result missing char_count",
            "required_evidence": "raw summarize dict",
            "decision_consequence": {"proposal": "block ship", "status": "proposed"},
            "approval_state": "pending",
        }
    ],
    "review": {
        "product_domain_approver": None,
        "named_expert": None,
        "reviewed_examples": [],
        "boundary_cases": [],
        "development_dataset": {"id": None, "version": None},
        "disagreements": [],
        "resolution": None,
        "unresolved_questions": ["Confirm char_count is the unit Product wants"],
        "approval_state": "pending",
        "approved_version": None,
        "approved_date": None,
    },
}

APPROVED_RUBRIC = {
    "schema_version": "product-eval-contract/1",
    "artifact": "rubric-register",
    "state": "EVALUATOR_ROUTING",
    "criteria": [
        {
            "id": "C-len",
            "version": "1.0",
            "source_expectation_id": "story-brief",
            "applicable_unit": "summarize() result",
            "preconditions": "document stripped length is defined",
            "judgment": "char_count equals the stripped document length",
            "pass_rule": "char_count == len(document.strip())",
            "fail_rule": "char_count differs",
            "unscorable_rule": "char_count absent",
            "required_evidence": "raw summarize dict plus source document",
            "decision_consequence": {"proposal": "required for ship", "status": "approved"},
            "approval_state": "approved",
        },
        {
            "id": "C-tone",
            "version": "1.0",
            "source_expectation_id": "story-brief",
            "applicable_unit": "headline",
            "preconditions": "headline is present",
            "judgment": "A named reviewer accepts the headline as faithful to the opening",
            "pass_rule": "reviewer verdict Pass",
            "fail_rule": "reviewer verdict Fail",
            "unscorable_rule": "no attributable review",
            "required_evidence": "item-level review with reviewer_id",
            "decision_consequence": {"proposal": "required for ship", "status": "approved"},
            "approval_state": "approved",
        },
        {
            "id": "C-faithful",
            "version": "1.0",
            "source_expectation_id": "story-brief",
            "applicable_unit": "headline versus document",
            "preconditions": "both strings present",
            "judgment": "Headline does not introduce a claim absent from the document",
            "pass_rule": "no unsupported claim",
            "fail_rule": "headline adds a claim the document does not contain",
            "unscorable_rule": "either string missing",
            "required_evidence": "document text and headline",
            "decision_consequence": {"proposal": "required for ship", "status": "approved"},
            "approval_state": "approved",
        },
    ],
    "review": {
        "product_domain_approver": "fixture-pm",
        "named_expert": "fixture-expert",
        "reviewed_examples": ["dev-1"],
        "boundary_cases": ["empty document is unscorable"],
        "development_dataset": {"id": "dev-set", "version": "1"},
        "disagreements": [],
        "resolution": "fixture sign-off",
        "unresolved_questions": [],
        "approval_state": "approved",
        "approved_version": "1.0",
        "approved_date": "2026-09-25",
    },
}

ROUTES = {
    "schema_version": "product-eval-contract/1",
    "artifact": "evaluator-register",
    "state": "EVALUATOR_ROUTING",
    "routes": [
        {
            "criterion_id": "C-len",
            "criterion_version": "1.0",
            "evaluator_type": "deterministic",
            "evaluator_id": "det-len",
            "evaluator_version": "1.0",
            "measurement_rationale": "char_count is an integer comparison",
            "acceptance_state": "unaccepted",
            "decision_eligible": False,
            "execution_scope": "DIAGNOSTIC/SHADOW ONLY",
            "evidence": {"kind": "verification", "cases": [], "implementation_version": None},
            "provenance": {"rubric_source": "rubric-register.json"},
            "decision_consequence": {"rule": "required", "status": "approved"},
        },
        {
            "criterion_id": "C-tone",
            "criterion_version": "1.0",
            "evaluator_type": "human",
            "evaluator_id": "human-tone",
            "evaluator_version": "1.0",
            "measurement_rationale": "faithfulness of wording needs a named reviewer",
            "acceptance_state": "unaccepted",
            "decision_eligible": False,
            "execution_scope": "DIAGNOSTIC/SHADOW ONLY",
            "evidence": {"kind": "human_procedure", "reviewer_id": "fixture-expert"},
            "provenance": {"rubric_source": "rubric-register.json"},
            "decision_consequence": {"rule": "required", "status": "approved"},
        },
        {
            "criterion_id": "C-faithful",
            "criterion_version": "1.0",
            "evaluator_type": "llm",
            "evaluator_id": "llm-faithful",
            "evaluator_version": "1.0",
            "measurement_rationale": "unsupported-claim check is semantic and repeatable",
            "acceptance_state": "unaccepted",
            "decision_eligible": False,
            "execution_scope": "DIAGNOSTIC/SHADOW ONLY",
            "evidence": {"kind": "held_out", "dataset_id": "heldout-set", "dataset_version": "1"},
            "provenance": {"rubric_source": "rubric-register.json"},
            "decision_consequence": {"rule": "required", "status": "approved"},
        },
    ],
    "datasets": {
        "development": {"id": "dev-set", "version": "1", "manifest": "Knowledge/dev_manifest.json"},
        "held_out_validation": {
            "id": "heldout-set",
            "version": "1",
            "manifest": "Knowledge/heldout_manifest.json",
        },
    },
    "decision_policy": {"required_criteria": ["C-len", "C-tone", "C-faithful"], "unscorable_consequence": "block"},
}

DEV_MANIFEST = {"id": "dev-set", "version": "1", "items": [{"id": "dev-1", "content": "Alpha budget note"}]}
HELD_MANIFEST = {"id": "heldout-set", "version": "1", "items": [{"id": "hold-1", "content": "Beta launch note"}]}

PROMPTS = {
    "A": """Design evaluation for this document-summary application using the eval-design skill, then build a harness with the eval-harness-build skill.
There is no Product expectations packet. Follow the skills. Write outputs under Knowledge/ and eval_harness/ as the skills require.
Do not invent approvers, thresholds, or a judge.
""",
    "B": """Design evaluation using the eval-design skill, then build a harness with eval-harness-build.
Product expectations are in Knowledge/product-expectations.json. The rubric is not approved.
Draft candidate binary criteria and stop before evaluator implementation. The builder must stop too.
""",
    "C": """Design evaluation using eval-design, then implement the harness with eval-harness-build.
Knowledge/ already contains an approved rubric, evaluator routes, and disjoint development and held-out manifests. Do not alter those JSON files.
Route the mechanical criterion, the named-expert criterion, and the semantic criterion as the register states.
Generate the package described by the harness skill, defaulting to diagnostic k=1.
""",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=fixture@example.com", "-c", "user.name=fixture", "commit", "-m", "fixture app"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _base_app(repo: Path) -> None:
    _write(repo / "app" / "summarize.py", APP)
    _write(repo / "app" / "__init__.py", "")
    _write(
        repo / "README.md",
        "# Brief\n\nCallable entrypoint: `app.summarize.summarize(document: str) -> dict`.\n",
    )


def prepare(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        sys.exit(f"refusing nonempty target: {root}")
    root.mkdir(parents=True, exist_ok=True)
    specs = {
        "A-missing-expectations": ("A", False, False),
        "B-expectations-only": ("B", True, False),
        "C-approved-criteria": ("C", True, True),
    }
    for name, (key, expectations, approved) in specs.items():
        repo = root / name
        _base_app(repo)
        _write(repo / "PROMPT.md", PROMPTS[key])
        manifest = {
            "case": name,
            "prompt": "PROMPT.md",
            "entrypoint": "app.summarize.summarize",
            "expects_registers": approved,
        }
        if expectations:
            packet = dict(EXPECTATIONS)
            if not approved:
                packet["state"] = "RUBRIC_REVIEW"
            else:
                packet["state"] = "EVALUATOR_ROUTING"
                packet["display_state"] = "Rubric approved — evaluator acceptance separate"
            _write(repo / "Knowledge" / "product-expectations.json", json.dumps(packet, indent=2) + "\n")
            _write(
                repo / "Knowledge" / "product-expectations.md",
                "# Fixture expectations\n\nSee product-expectations.json. Style is out of scope.\n",
            )
        if not approved and expectations:
            _write(repo / "Knowledge" / "rubric-register.json", json.dumps(RUBRIC_PENDING, indent=2) + "\n")
        if approved:
            _write(repo / "Knowledge" / "rubric-register.json", json.dumps(APPROVED_RUBRIC, indent=2) + "\n")
            _write(repo / "Knowledge" / "evaluator-register.json", json.dumps(ROUTES, indent=2) + "\n")
            _write(repo / "Knowledge" / "dev_manifest.json", json.dumps(DEV_MANIFEST, indent=2) + "\n")
            _write(repo / "Knowledge" / "heldout_manifest.json", json.dumps(HELD_MANIFEST, indent=2) + "\n")
        _write(repo / "INPUT_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        _git_init(repo)
    print(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    prepare(Path(args.root))


if __name__ == "__main__":
    main()
