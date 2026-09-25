#!/usr/bin/env python3
"""Create temporary repos for product-first skill forward checks."""

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

D_EXPECTATIONS = {
    "schema_version": "product-eval-contract/1",
    "artifact": "product-expectations",
    "state": "EVALUATOR_ROUTING",
    "display_state": "Rubric approved — evaluator acceptance separate",
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
            "id": "app-hold",
            "output": "headline",
            "candidate_behaviour": "Headline for a legal-hold notice keeps the hold's scope",
            "product_story": "A legal-hold notice is a rare document type",
            "precondition": "Document type is legal-hold notice",
            "status": "in_scope",
        },
        {
            "id": "app-claim",
            "output": "headline",
            "candidate_behaviour": "Headline does not add a claim the document does not contain",
            "product_story": "Every summary is checked",
            "precondition": "Any non-empty document",
            "status": "in_scope",
        },
    ],
    "story_packet": [
        {
            "id": "story-hold",
            "source": "fixture expectations",
            "scenario": "Legal-hold notices only. This document type is rare: a handful of items per quarter. Experts already mark this judgment consistently.",
            "judgment_unit": "The headline of a legal-hold notice",
            "named_expert": "fixture-expert",
            "exclusions": ["Do not score writing style"],
            "open_decisions": [],
        },
        {
            "id": "story-claim",
            "source": "fixture expectations",
            "scenario": "Every summary. Volume is thousands of summaries per day. Experts already mark this judgment consistently.",
            "judgment_unit": "The headline versus the source document",
            "named_expert": "fixture-expert",
            "exclusions": ["Do not score writing style"],
            "open_decisions": [],
        },
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
    "observed_facts": [
        {
            "id": "fact-hold-volume",
            "statement": "Legal-hold notices occur a handful of times per quarter.",
            "source": "fixture expectations",
            "kind": "observed",
        },
        {
            "id": "fact-summary-volume",
            "statement": "Summaries occur at thousands per day.",
            "source": "fixture expectations",
            "kind": "observed",
        },
        {
            "id": "fact-expert-agreement",
            "statement": "Experts already mark both judgments consistently.",
            "source": "fixture expectations",
            "kind": "observed",
        },
    ],
}

D_RUBRIC = {
    "schema_version": "product-eval-contract/1",
    "artifact": "rubric-register",
    "state": "EVALUATOR_ROUTING",
    "criteria": [
        {
            "id": "C-hold",
            "version": "1.0",
            "source_expectation_id": "story-hold",
            "applicable_unit": "headline of a legal-hold notice",
            "preconditions": "document type is legal-hold notice",
            "judgment": "The headline preserves the scope of the legal hold",
            "pass_rule": "hold scope is preserved",
            "fail_rule": "headline drops or widens the hold scope",
            "unscorable_rule": "document is not a legal-hold notice, or headline is missing",
            "required_evidence": "legal-hold notice text and headline",
            "decision_consequence": {"proposal": "required for ship", "status": "approved"},
            "approval_state": "approved",
        },
        {
            "id": "C-claim",
            "version": "1.0",
            "source_expectation_id": "story-claim",
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
        "reviewed_examples": ["dev-1", "dev-2"],
        "boundary_cases": ["non-hold documents are unscorable for C-hold"],
        "development_dataset": {"id": "dev-set", "version": "1"},
        "disagreements": [],
        "resolution": "Experts already mark both judgments consistently.",
        "unresolved_questions": [],
        "approval_state": "approved",
        "approved_version": "1.0",
        "approved_date": "2026-09-25",
    },
}

def _decision(decision_id, question, answer, holder, holder_role, status="decided"):
    return {
        "id": decision_id,
        "question": question,
        "answer": answer,
        "holder": holder,
        "holder_role": holder_role,
        "status": status,
        "source": "fixture eval spec",
    }


def _ready_spec(feature, judgment, mode="k=1", k=1):
    """Complete READY Eval Spec. Trial contract is the only part that varies."""
    decisions = [
        _decision(
            "end-to-end-feature",
            "What complete user-facing behavior will this Eval Spec evaluate for one launch decision?",
            feature,
            "fixture-pm",
            "Product/domain owner",
        ),
        _decision(
            "judgment-unit",
            "What is one artifact being judged (output, passage, rubric dimension, turn, session, or task episode), and what makes it pass?",
            judgment,
            "fixture-pm",
            "Product/domain; the named expert resolves semantic boundaries",
        ),
        _decision(
            "outcome-verdict",
            "What outcome decides pass, and which architecture-derived checks materially help locate failure?",
            "The user-facing outcome in the judgment unit passes or fails. Extra checks only locate failure.",
            "fixture-pm",
            "Product/domain + named expert",
        ),
        _decision(
            "measurement-decision",
            "What decision does each measurement drive: ship gate, alarm, or research insight?",
            "Ship gate for the outcome verdict. No research-only metric.",
            "fixture-pm",
            "Product/domain; policy/governance authorizes consequential use",
        ),
        _decision(
            "trial-contract",
            "Is one attempt the promise, or are several attempts part of the experience, and which of k=1, pass^k, or pass@k is recorded, with what k?",
            f"{mode} with k={k}. Record per-trial success. Do not compare across k.",
            "fixture-pm",
            "Product/domain",
        ),
        _decision(
            "governance-profile",
            "Which governance profile applies, what minimum evidence and protection obligations does it impose, and who may approve launch, controlled evidence accrual, a waiver, or an external claim?",
            "Internal tool profile. fixture-gov may approve launch. Obligations are evidence minimums only.",
            "fixture-gov",
            "Policy/governance",
        ),
        _decision(
            "protection-requirement",
            "For each material risk, what must be prevented before it takes effect, and what may be detected or reviewed later?",
            "A wrong user-facing outcome must be caught before release. Later review is allowed for diagnostic detail.",
            "fixture-pm",
            "Product/domain defines harm; policy/governance sets the minimum",
        ),
        _decision(
            "harm-asymmetry",
            "For each criterion or risk, which error is worse, a miss or a false alarm?",
            "A miss of a wrong user-facing outcome is worse than a false alarm. Operating points are not set here.",
            "fixture-pm",
            "Product/domain; policy/governance constrains consequential risks",
        ),
    ]
    return {
        "schema_version": "product-eval-contract/1",
        "artifact": "eval-spec",
        "state": "READY",
        "display_state": "Eval Spec ready",
        "feature_id": "fixture-feature",
        "decisions": decisions,
        "trial_contract": {"mode": mode, "k": k},
        "signed": {"holder": "fixture-pm", "date": "2026-09-25", "version": "1"},
    }


def _spec_missing_unit():
    """READY-shaped spec with the judgment-unit answer absent and its holder named."""
    spec = _ready_spec("A person exchanges a series of messages and receives replies.", None)
    spec["state"] = "NEEDS_PRODUCT_DECISION"
    spec["display_state"] = "BLOCKED — Product decision required"
    spec["trial_contract"] = {"mode": None, "k": None}
    spec["signed"] = {"holder": None, "date": None, "version": None}
    for row in spec["decisions"]:
        if row["id"] == "judgment-unit":
            row["answer"] = None
            row["holder"] = "fixture-owner"
            row["status"] = "NEEDS_PRODUCT_DECISION"
        if row["id"] == "trial-contract":
            row["answer"] = None
            row["status"] = "NEEDS_PRODUCT_DECISION"
            row["holder"] = "unknown"
    return spec


AGENT_APP = '''\
"""Small tool-using fixture. Two tools, then a final state."""

from pathlib import Path

_COUNTER = Path(__file__).with_name("invocation_count")
ALLOWED = {"acme", "northwind"}


def _bump() -> int:
    n = int(_COUNTER.read_text()) if _COUNTER.exists() else 0
    n += 1
    _COUNTER.write_text(str(n))
    return n


def lookup_vendor(name: str) -> dict:
    return {"vendor": name, "approved": name.lower() in ALLOWED}


def place_order(vendor: str, sku: str, qty: int) -> dict:
    return {"order_id": f"{vendor}-{sku}", "vendor": vendor, "sku": sku, "qty": qty}


def run_task(request: str) -> dict:
    """Production entrypoint. One call increments the counter by one."""
    calls = _bump()
    text = request.strip()
    vendor = "acme" if "acme" in text.lower() else "other"
    looked = lookup_vendor(vendor)
    trajectory = [{"tool": "lookup_vendor", "args": {"name": vendor}, "result": looked}]
    order = None
    if looked["approved"]:
        order = place_order(vendor, "sku-1", 1)
        trajectory.append({"tool": "place_order", "args": {"vendor": vendor, "sku": "sku-1", "qty": 1}, "result": order})
    return {
        "final_state": {"order": order, "vendor_approved": looked["approved"]},
        "trajectory": trajectory,
        "invocation_count": calls,
    }
'''

CHAT_APP = '''\
"""Small multi-message fixture."""

from pathlib import Path

_COUNTER = Path(__file__).with_name("invocation_count")


def _bump() -> int:
    n = int(_COUNTER.read_text()) if _COUNTER.exists() else 0
    n += 1
    _COUNTER.write_text(str(n))
    return n


def continue_dialog(history: list, message: str) -> dict:
    """Production entrypoint. One call increments the counter by one."""
    calls = _bump()
    prior = list(history or [])
    reply = message.strip()[:80]
    prior.append({"speaker": "person", "text": message})
    prior.append({"speaker": "assistant", "text": reply})
    return {"history": prior, "reply": reply, "invocation_count": calls}
'''

E_EXPECTATIONS = {
    "schema_version": "product-eval-contract/1",
    "artifact": "product-expectations",
    "state": "RUBRIC_REVIEW",
    "display_state": "Expectations supplied — rubric not approved",
    "inventory": [
        {
            "id": "mode-task",
            "version": "observed-1",
            "mode": "run_task",
            "output": "final_state and trajectory",
            "source": "app/worker.py:run_task",
        }
    ],
    "applicability_map": [
        {
            "id": "app-task",
            "output": "final_state and trajectory",
            "candidate_behaviour": "The caller can see the resulting state and the tools that ran",
            "product_story": "A person asks for a vendor order and receives the result",
            "precondition": "Request text is non-empty",
            "status": "in_scope",
        }
    ],
    "story_packet": [
        {
            "id": "story-task",
            "source": "fixture expectations",
            "scenario": "One request is handled through the available tools",
            "judgment_unit": "One task episode",
            "named_expert": "fixture-expert",
            "exclusions": [],
            "open_decisions": [],
        }
    ],
    "decision_log": [
        {
            "id": "dec-feature",
            "question": "Which user-facing behavior is in this launch?",
            "holder": "fixture-pm",
            "decision": "Vendor order requests handled by run_task.",
            "status": "decided",
            "source": "fixture expectations",
        }
    ],
    "observed_facts": [],
}

F_EXPECTATIONS = {
    "schema_version": "product-eval-contract/1",
    "artifact": "product-expectations",
    "state": "RUBRIC_REVIEW",
    "display_state": "Expectations supplied — rubric not approved",
    "inventory": [
        {
            "id": "mode-dialog",
            "version": "observed-1",
            "mode": "continue_dialog",
            "output": "history and reply",
            "source": "app/dialog.py:continue_dialog",
        }
    ],
    "applicability_map": [
        {
            "id": "app-dialog",
            "output": "history and reply",
            "candidate_behaviour": "The person receives a reply that stays on the message they sent",
            "product_story": "A person sends several messages and receives replies",
            "precondition": "Message text is non-empty",
            "status": "in_scope",
        }
    ],
    "story_packet": [
        {
            "id": "story-dialog",
            "source": "fixture expectations",
            "scenario": "Several messages in one exchange",
            "judgment_unit": "",
            "named_expert": "fixture-expert",
            "exclusions": [],
            "open_decisions": ["What one artifact is judged"],
        }
    ],
    "decision_log": [],
    "observed_facts": [],
}

PROMPTS = {
    "A": "Design an eval for this app and build the harness.\n",
    "B": "Design an eval for this app and build the harness.\n",
    "C": "Design an eval for this app and build the harness.\n",
    "D": "Design an eval for this app and build the harness.\n",
    "E": "Design an eval for this app and build the harness.\n",
    "F": "Design an eval for this app and build the harness.\n",
}
PLUMBING_PROMPT = "Please add neutral execution plumbing so we can call the app and save local results.\n"


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


def _write_spec(repo: Path, spec: dict) -> None:
    _write(repo / "Knowledge" / "eval-spec.json", json.dumps(spec, indent=2) + "\n")
    _write(
        repo / "Knowledge" / "eval-spec.md",
        "# Fixture Eval Spec\n\nSee eval-spec.json. Do not change a supplied trial contract.\n",
    )


def prepare(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        sys.exit(f"refusing nonempty target: {root}")
    root.mkdir(parents=True, exist_ok=True)
    k1 = _ready_spec(
        "Summarize one document into the returned dict.",
        "The dict returned by summarize",
    )
    specs = {
        "A-missing-expectations": ("A", False, False),
        "B-expectations-only": ("B", True, False),
        "C-approved-criteria": ("C", True, True),
        "D-approved-unrouted": ("D", True, True),
    }
    for name, (key, expectations, approved) in specs.items():
        repo = root / name
        _base_app(repo)
        _write(repo / "PROMPT.md", PROMPTS[key])
        if key == "A":
            _write(repo / "PROMPT-PLUMBING.md", PLUMBING_PROMPT)
        manifest = {
            "case": name,
            "prompt": "PROMPT.md",
            "entrypoint": "app.summarize.summarize",
            "expects_registers": approved and key != "D",
        }
        if key == "D":
            _write(repo / "Knowledge" / "product-expectations.json", json.dumps(D_EXPECTATIONS, indent=2) + "\n")
            _write(
                repo / "Knowledge" / "product-expectations.md",
                "# Fixture expectations\n\nSee product-expectations.json. Style is out of scope.\n",
            )
            _write(repo / "Knowledge" / "rubric-register.json", json.dumps(D_RUBRIC, indent=2) + "\n")
        elif expectations:
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
        if key != "D" and not approved and expectations:
            _write(repo / "Knowledge" / "rubric-register.json", json.dumps(RUBRIC_PENDING, indent=2) + "\n")
        if key != "D" and approved:
            _write(repo / "Knowledge" / "rubric-register.json", json.dumps(APPROVED_RUBRIC, indent=2) + "\n")
            _write(repo / "Knowledge" / "evaluator-register.json", json.dumps(ROUTES, indent=2) + "\n")
            _write(repo / "Knowledge" / "dev_manifest.json", json.dumps(DEV_MANIFEST, indent=2) + "\n")
            _write(repo / "Knowledge" / "heldout_manifest.json", json.dumps(HELD_MANIFEST, indent=2) + "\n")
        if expectations:
            _write_spec(repo, k1)
        _write(repo / "INPUT_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        _git_init(repo)

    episode = _ready_spec(
        "A person asks for a vendor order and receives the result.",
        "One task episode",
        mode="pass^k",
        k=3,
    )
    e_repo = root / "E-episode-unapproved"
    _write(e_repo / "app" / "worker.py", AGENT_APP)
    _write(e_repo / "app" / "__init__.py", "")
    _write(
        e_repo / "README.md",
        "# Order helper\n\nCallable entrypoint: `app.worker.run_task(request: str) -> dict`.\n",
    )
    _write(e_repo / "PROMPT.md", PROMPTS["E"])
    _write(e_repo / "Knowledge" / "product-expectations.json", json.dumps(E_EXPECTATIONS, indent=2) + "\n")
    _write(
        e_repo / "Knowledge" / "product-expectations.md",
        "# Fixture expectations\n\nSee product-expectations.json.\n",
    )
    _write_spec(e_repo, episode)
    _write(
        e_repo / "INPUT_MANIFEST.json",
        json.dumps({"case": "E-episode-unapproved", "prompt": "PROMPT.md", "entrypoint": "app.worker.run_task"}, indent=2) + "\n",
    )
    _git_init(e_repo)

    f_repo = root / "F-dialog-missing-unit"
    _write(f_repo / "app" / "dialog.py", CHAT_APP)
    _write(f_repo / "app" / "__init__.py", "")
    _write(
        f_repo / "README.md",
        "# Dialog helper\n\nCallable entrypoint: `app.dialog.continue_dialog(history: list, message: str) -> dict`.\n",
    )
    _write(f_repo / "PROMPT.md", PROMPTS["F"])
    _write(f_repo / "Knowledge" / "product-expectations.json", json.dumps(F_EXPECTATIONS, indent=2) + "\n")
    _write(
        f_repo / "Knowledge" / "product-expectations.md",
        "# Fixture expectations\n\nSee product-expectations.json.\n",
    )
    _write_spec(f_repo, _spec_missing_unit())
    _write(
        f_repo / "INPUT_MANIFEST.json",
        json.dumps({"case": "F-dialog-missing-unit", "prompt": "PROMPT.md", "entrypoint": "app.dialog.continue_dialog"}, indent=2) + "\n",
    )
    _git_init(f_repo)
    print(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    prepare(Path(args.root))


if __name__ == "__main__":
    main()
