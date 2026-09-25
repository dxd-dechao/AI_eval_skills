#!/usr/bin/env python3
"""Verify forward-test repos. Missing artifacts fail; they are not skips."""

from __future__ import annotations

import argparse
import ast
import copy
import importlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path


def _load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


class Report:
    def __init__(self) -> None:
        self.probes: list[dict] = []

    def add(self, case: str, name: str, ok: bool, detail: str) -> None:
        self.probes.append({"case": case, "probe": name, "ok": bool(ok), "detail": detail})

    def dump(self, path: Path) -> int:
        failed = [p for p in self.probes if not p["ok"]]
        payload = {"passed": not failed, "probes": self.probes, "failed": len(failed)}
        path.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps({"passed": payload["passed"], "failed": payload["failed"], "report": str(path)}))
        return 0 if payload["passed"] else 1


def _text_blobs(repo: Path) -> str:
    parts = []
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix in {".md", ".py", ".json", ".ipynb"} and "invocation_count" not in p.name:
            try:
                parts.append(p.read_text())
            except UnicodeDecodeError:
                continue
    return "\n".join(parts)


def _scan_case_a(repo: Path) -> list[str]:
    """Fail when generated files contain a rubric, judge, threshold, gate, or invented approval."""
    problems: list[str] = []
    judge_prompt = re.compile(r"(?i)you are (an? )?(expert )?(llm )?judge")
    threshold = re.compile(r"(?i)(threshold\s*[:=]\s*0\.\d+|>=\s*0\.\d+|κ\s*[≥>=]\s*0\.\d|kappa\s*[≥>=]\s*0\.\d)")
    for root_name in ("Knowledge", "eval_harness"):
        root = repo / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(repo))
            lowered = path.name.lower()
            if lowered == "gates.py" or "judge_prompt" in lowered or lowered.startswith("judge"):
                problems.append(f"artifact {rel}")
            if path.suffix not in {".py", ".json", ".md", ".ipynb", ".yaml", ".yml"}:
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            if judge_prompt.search(text):
                problems.append(f"judge prompt in {rel}")
            if path.suffix == ".py" and threshold.search(text):
                problems.append(f"numeric threshold in {rel}")
            if path.suffix == ".py" and re.search(r"def (preflight_gate|evaluate_decision)\b", text):
                problems.append(f"gate implementation in {rel}")
            if path.suffix != ".json":
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            criteria = data.get("criteria")
            if isinstance(criteria, list) and criteria and any(isinstance(row, dict) and "pass_rule" in row for row in criteria):
                problems.append(f"rubric criteria in {rel}")
            review = data.get("review") if isinstance(data.get("review"), dict) else {}
            if review.get("approval_state") == "approved" or data.get("approval_state") == "approved":
                problems.append(f"invented approval in {rel}")
            approver = review.get("product_domain_approver")
            if approver:
                problems.append(f"invented approver in {rel}")
            if data.get("approved") is True or data.get("validated") is True:
                problems.append(f"bare approval flag in {rel}")
    return problems


def check_a(repo: Path, report: Report) -> None:
    case = "A"
    intake = repo / "Knowledge" / "product-expectations.json"
    data = _load(intake)
    report.add(case, "intake-json", data is not None, str(intake))
    if not data:
        report.add(case, "blocked-state", False, "missing intake")
        report.add(case, "inventory-nonempty", False, "missing intake")
        report.add(case, "open-decisions", False, "missing intake")
    else:
        blocked = data.get("state") == "NEEDS_PRODUCT_DECISION" or "BLOCKED" in str(data.get("display_state", ""))
        report.add(case, "blocked-state", blocked, str(data.get("state")))
        inv = data.get("inventory") or []
        report.add(case, "inventory-nonempty", len(inv) > 0, f"rows={len(inv)}")
        log = data.get("decision_log") or []
        report.add(case, "open-decisions", len(log) > 0, f"decisions={len(log)}")
    problems = _scan_case_a(repo)
    report.add(case, "no-scoring-artifacts", not problems, "; ".join(problems) if problems else "no rubric, judge, threshold, gate, or approval")
    has_eval_pkg = (repo / "eval_harness" / "evaluators").exists() or (repo / "eval_harness" / "gates.py").exists()
    report.add(case, "no-evaluator-package", not has_eval_pkg, "evaluators or gates.py present" if has_eval_pkg else "absent")
    report.add(case, "blocked-md", (repo / "eval_harness" / "BLOCKED.md").exists(), "BLOCKED.md")
    plumbing = repo / "eval_harness" / "pipeline_adapter.py"
    plumbing_ok = plumbing.exists() and not (repo / "eval_harness" / "gates.py").exists() and not (repo / "eval_harness" / "evaluators").exists()
    report.add(case, "neutral-plumbing", plumbing_ok, str(plumbing) if plumbing_ok else "follow-up plumbing missing or it included scoring")


def check_b(repo: Path, report: Report) -> None:
    case = "B"
    rubric_path = repo / "Knowledge" / "rubric-register.json"
    data = _load(rubric_path)
    report.add(case, "rubric-json", data is not None, str(rubric_path))
    if not data:
        report.add(case, "has-criteria", False, "missing rubric")
        report.add(case, "approval-pending", False, "missing rubric")
        report.add(case, "binary-rules", False, "missing rubric")
        report.add(case, "builder-stopped", False, "missing rubric")
        return
    criteria = data.get("criteria") or []
    report.add(case, "has-criteria", len(criteria) > 0, f"n={len(criteria)}")
    pending = all((c.get("approval_state") == "pending") for c in criteria) if criteria else False
    review_pending = (data.get("review") or {}).get("approval_state") == "pending"
    report.add(case, "approval-pending", pending and review_pending, "approval fields")
    binary = all("pass_rule" in c and "fail_rule" in c and "unscorable_rule" in c for c in criteria)
    report.add(case, "binary-rules", binary, "pass/fail/unscorable")
    has_eval = (repo / "eval_harness" / "evaluators").exists()
    report.add(case, "builder-stopped", (repo / "eval_harness" / "BLOCKED.md").exists() and not has_eval, "BLOCKED.md without evaluators")


def _import_harness(repo: Path):
    sys.path.insert(0, str(repo))
    for name in list(sys.modules):
        if name == "eval_harness" or name.startswith("eval_harness."):
            del sys.modules[name]
    return importlib.import_module("eval_harness")


def _manifest_items(manifest: dict | None) -> list:
    if not manifest:
        return []
    if isinstance(manifest, list):
        return [row for row in manifest if isinstance(row, dict)]
    return [row for row in (manifest.get("items") or []) if isinstance(row, dict)]


def _manifests_disjoint(dev: dict | None, hold: dict | None) -> tuple[bool, str]:
    dev_items = _manifest_items(dev)
    hold_items = _manifest_items(hold)
    if not dev_items or not hold_items:
        return False, "a manifest has no items"
    dev_ids = {str(row.get("id")) for row in dev_items}
    hold_ids = {str(row.get("id")) for row in hold_items}
    dev_content = {str(row.get("content", "")).strip().lower() for row in dev_items}
    hold_content = {str(row.get("content", "")).strip().lower() for row in hold_items}
    shared_ids = dev_ids & hold_ids
    shared_content = dev_content & hold_content
    if shared_ids or shared_content:
        return False, f"shared ids={shared_ids} content={shared_content}"
    return True, f"ids {sorted(dev_ids)} vs {sorted(hold_ids)}"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _accept_route(route: dict, evidence: dict) -> None:
    route["acceptance_state"] = "accepted"
    route["decision_eligible"] = True
    route["execution_scope"] = "accepted"
    route["evidence"] = evidence


def _base_registers(repo: Path) -> tuple[dict, dict, dict]:
    return (
        _load(repo / "Knowledge" / "product-expectations.json"),
        _load(repo / "Knowledge" / "rubric-register.json"),
        _load(repo / "Knowledge" / "evaluator-register.json"),
    )


def _stage(repo: Path, root: Path, expectations: dict, rubric: dict, register: dict, dataset: dict) -> Path:
    staged = root / "staged"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "results", "results-gate")
    shutil.copytree(repo, staged, ignore=ignore)
    knowledge = staged / "Knowledge"
    datasets = register.setdefault("datasets", {})
    development = datasets.setdefault("development", {})
    held_out = datasets.setdefault("held_out_validation", {})
    development["manifest"] = str((knowledge / "dev_manifest.json").resolve())
    held_out["manifest"] = str((knowledge / "heldout_manifest.json").resolve())
    _write_json(knowledge / "product-expectations.json", expectations)
    _write_json(knowledge / "rubric-register.json", rubric)
    _write_json(knowledge / "evaluator-register.json", register)
    _write_json(knowledge / "dev_manifest.json", dataset)
    counter = staged / "app" / "invocation_count"
    if counter.exists():
        counter.unlink()
    return staged


def _config(staged: Path, **overrides):
    from eval_harness.config import HarnessConfig
    import dataclasses

    values = {
        "mode": "gate",
        "limit": 1,
        "runs": 1,
        "use_langfuse": False,
        "results_dir": str(staged / "probe-results"),
        "expectations_path": str(staged / "Knowledge" / "product-expectations.json"),
        "rubric_path": str(staged / "Knowledge" / "rubric-register.json"),
        "evaluator_register_path": str(staged / "Knowledge" / "evaluator-register.json"),
        "dataset_path": str(staged / "Knowledge" / "dev_manifest.json"),
        "development_manifest_path": str(staged / "Knowledge" / "dev_manifest.json"),
        "held_out_manifest_path": str(staged / "Knowledge" / "heldout_manifest.json"),
        "project_root": str(staged),
    }
    values.update(overrides)
    names = {field.name for field in dataclasses.fields(HarnessConfig)}
    return HarnessConfig(**{key: value for key, value in values.items() if key in names})


def _cli_gate(staged: Path) -> subprocess.CompletedProcess[str]:
    help_run = subprocess.run(
        [sys.executable, "-m", "eval_harness.run_eval", "--help"],
        cwd=staged,
        capture_output=True,
        text=True,
    )
    help_text = (help_run.stdout or "") + (help_run.stderr or "")
    cmd = [sys.executable, "-m", "eval_harness.run_eval", "--mode", "gate", "--limit", "1"]
    if "--results-dir" in help_text:
        cmd.extend(["--results-dir", str(staged / "probe-results")])
    if "--runs" in help_text:
        cmd.extend(["--runs", "1"])
    env = os.environ.copy()
    env["EVAL_MODE"] = "gate"
    env["EVAL_USE_LANGFUSE"] = "0"
    env["EVAL_RESULTS_DIR"] = str(staged / "probe-results")
    return subprocess.run(cmd, cwd=staged, capture_output=True, text=True, env=env)


def _payload(result) -> dict:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if hasattr(result, "as_dict"):
        return result.as_dict()
    data = getattr(result, "__dict__", {})
    return dict(data) if isinstance(data, dict) else {}


def _refused(staged: Path) -> tuple[bool, str]:
    from eval_harness.contract import preflight_gate
    from eval_harness.run_eval import run

    cfg = _config(staged)
    pre = preflight_gate(cfg)
    ok = pre.ok if hasattr(pre, "ok") else pre.get("ok")
    reason = pre.blocked_reason if hasattr(pre, "blocked_reason") else pre.get("blocked_reason")
    result = run(cfg, limit=1)
    payload = _payload(result)
    quality = payload.get("quality_evaluated")
    invoked = payload.get("invocation_count")
    raw = payload.get("raw_output")
    before_quality = quality is False or (quality is None and invoked in (0, None) and not raw)
    cli = _cli_gate(staged)
    detail = f"preflight_ok={ok} reason={reason} run_exit={payload.get('exit_code')} quality={quality} calls={invoked} cli_exit={cli.returncode}"
    refused = ok is False and bool(reason) and payload.get("exit_code") not in (0, None) and before_quality and cli.returncode != 0
    return refused, detail


def _len_evidence() -> dict:
    return {
        "kind": "verification",
        "cases": [
            {"role": "known-good", "name": "known-good", "expect": "PASS"},
            {"role": "known-bad", "name": "known-bad", "expect": "FAIL"},
            {"role": "edge", "name": "edge", "expect": "UNSCORABLE"},
        ],
        "implementation_version": "app.summarize.summarize",
    }


def _accepted_len(expectations: dict, rubric: dict, register: dict) -> tuple[dict, dict, dict]:
    expectations = copy.deepcopy(expectations)
    rubric = copy.deepcopy(rubric)
    register = copy.deepcopy(register)
    for route in register.get("routes") or []:
        if route.get("criterion_id") == "C-len":
            _accept_route(route, _len_evidence())
    register["decision_policy"] = {"required_criteria": ["C-len"], "unscorable_consequence": "block"}
    return expectations, rubric, register


def check_c(repo: Path, report: Report) -> None:
    case = "C"
    reg = _load(repo / "Knowledge" / "evaluator-register.json")
    report.add(case, "register-present", reg is not None, "evaluator-register.json")
    if reg:
        types = {r.get("evaluator_type") for r in reg.get("routes", [])}
        report.add(case, "three-routes", types >= {"deterministic", "human", "llm"}, str(types))
    dev = _load(repo / "Knowledge" / "dev_manifest.json")
    hold = _load(repo / "Knowledge" / "heldout_manifest.json")
    disjoint, disjoint_detail = _manifests_disjoint(dev, hold)
    report.add(case, "disjoint-manifests", disjoint, disjoint_detail)
    nb = next(iter((repo / "eval_harness").glob("notebooks/*.ipynb")), None) if (repo / "eval_harness").exists() else None
    report.add(case, "notebook", nb is not None, str(nb))
    if nb:
        notebook = json.loads(nb.read_text())
        parsed = True
        err = ""
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                src = "".join(cell.get("source", []))
                try:
                    ast.parse(src)
                except SyntaxError as exc:
                    parsed = False
                    err = str(exc)
        blob = nb.read_text()
        compact = "".join(blob.split())
        report.add(case, "notebook-ast", parsed, err or "parsed")
        report.add(case, "notebook-defaults", "diagnostic" in blob and "LIMIT=1" in compact and "RUNS=1" in compact, "diagnostic limit/runs")
    try:
        _import_harness(repo)
        from eval_harness.config import HarnessConfig
        from eval_harness.contract import preflight_gate
        from eval_harness.run_eval import run
    except Exception as exc:
        report.add(case, "import-harness", False, traceback.format_exc().splitlines()[-1] if False else f"{type(exc).__name__}: {exc}")
        return
    report.add(case, "import-harness", True, "imported")
    cfg = HarnessConfig(
        mode="diagnostic",
        limit=1,
        runs=1,
        use_langfuse=False,
        results_dir=str(repo / "results"),
        expectations_path=str(repo / "Knowledge" / "product-expectations.json"),
        rubric_path=str(repo / "Knowledge" / "rubric-register.json"),
        evaluator_register_path=str(repo / "Knowledge" / "evaluator-register.json"),
        dataset_path=str(repo / "Knowledge" / "dev_manifest.json"),
    )
    counter = repo / "app" / "invocation_count"
    if counter.exists():
        counter.unlink()
    try:
        result = run(cfg, limit=1)
        payload = result if isinstance(result, dict) else getattr(result, "__dict__", {})
        if hasattr(result, "to_dict"):
            payload = result.to_dict()
        report.add(case, "k1-run", True, "run returned")
        count = int(counter.read_text()) if counter.exists() else payload.get("invocation_count")
        report.add(case, "entrypoint-once", count == 1, f"invocation_count={count}")
        eligible = payload.get("decision_eligible", getattr(result, "decision_eligible", None))
        verdict = payload.get("release_verdict", getattr(result, "release_verdict", "missing"))
        report.add(case, "diagnostic-not-release", eligible is False and verdict in (None, "null"), f"eligible={eligible} verdict={verdict}")
    except Exception as exc:
        report.add(case, "k1-run", False, f"{type(exc).__name__}: {exc}")
        report.add(case, "entrypoint-once", False, "run failed")
        report.add(case, "diagnostic-not-release", False, "run failed")
    try:
        import eval_harness.metrics as metrics

        summarize = metrics.summarize
        overlap_fn = getattr(metrics, "interval_iou", None) or getattr(metrics, "temporal_overlap", None)
        proxies = getattr(metrics, "PRODUCTION_PROXIES", None)
        if proxies is None:
            proxies = getattr(metrics, "PROXY_SCORE_NAMES", ())
        from eval_harness.gates import evaluate_decision
        from eval_harness.dataset_loader import assert_held_out_disjoint
        from eval_harness.human_review import import_reviews
        from eval_harness.run_eval import run as run_gate
        rows = [
            {"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False},
            {"criterion_id": "C-tone", "applicability": "applicable", "status": "FAIL", "shadow": False},
            {"criterion_id": "C-faithful", "applicability": "not_applicable", "status": "PASS", "shadow": False},
            {"criterion_id": "C-extra", "applicability": "unknown", "status": "PASS", "shadow": False},
        ]
        summary = summarize(rows, {"required_criteria": ["C-len"], "unscorable_consequence": "block"})
        report.add(
            case,
            "denominator",
            summary.denominator == 2 and summary.pass_count == 1 and summary.fail_count == 1 and summary.not_applicable_count == 1 and summary.unscorable_count == 1 and abs((summary.pass_rate or 0) - 0.5) < 1e-9,
            f"den={summary.denominator} pass={summary.pass_count} fail={summary.fail_count} na={summary.not_applicable_count} uns={summary.unscorable_count} rate={summary.pass_rate}",
        )
        empty = summarize([], {"required_criteria": ["C-len"], "unscorable_consequence": "block"})
        report.add(case, "empty-not-pass", empty.pass_rate is None and empty.denominator == 0, f"rate={empty.pass_rate}")
        expectations, rubric, register = _base_registers(repo)
        dataset = _load(repo / "Knowledge" / "dev_manifest.json") or {"id": "dev-set", "version": "1", "items": [{"id": "dev-1", "content": "Alpha budget note"}]}
        with tempfile.TemporaryDirectory(prefix="ai-eval-skills-probes-") as tmp:
            root = Path(tmp)
            ready_exp, ready_rubric, ready_reg = _accepted_len(expectations, rubric, register)
            ready = _stage(repo, root / "ready", ready_exp, ready_rubric, ready_reg, dataset)
            ready_pre = preflight_gate(_config(ready))
            report.add(case, "accepted-preflight", ready_pre.ok is True, getattr(ready_pre, "blocked_reason", None))
            passed = run_gate(_config(ready), limit=1)
            passed_payload = _payload(passed)
            evidence_kept = "implementation_version" in json.dumps(passed_payload)
            meta_path = ready / "probe-results" / "run_meta.json"
            if meta_path.exists():
                evidence_kept = evidence_kept or "implementation_version" in meta_path.read_text()
            report.add(
                case,
                "accepted-gate-pass",
                passed_payload.get("exit_code") == 0 and passed_payload.get("release_verdict") == "pass" and evidence_kept,
                f"exit={passed_payload.get('exit_code')} verdict={passed_payload.get('release_verdict')} evidence={evidence_kept}",
            )
            fail_exp, fail_rubric, fail_reg = _accepted_len(expectations, rubric, register)
            for route in fail_reg.get("routes") or []:
                if route.get("criterion_id") == "C-tone":
                    _accept_route(
                        route,
                        {
                            "kind": "human_procedure",
                            "reviewer_id": "fixture-expert",
                            "procedure": "compare headline to opening",
                            "rubric_version": "1.0",
                            "item_reviews": [
                                {
                                    "item_id": "dev-1",
                                    "reviewer_id": "fixture-expert",
                                    "verdict": "Pass",
                                    "evidence_note": "procedure check",
                                }
                            ],
                        },
                    )
            fail_reg["decision_policy"] = {"required_criteria": ["C-tone"], "unscorable_consequence": "block"}
            fail_stage = _stage(repo, root / "fail", fail_exp, fail_rubric, fail_reg, dataset)
            review_path = root / "fail-review.json"
            review_path.write_text(json.dumps({"item_id": "dev-1", "criterion_id": "C-tone", "criterion_version": "1.0", "reviewer_id": "fixture-expert", "rubric_version": "1.0", "verdict": "Fail", "evidence_note": "headline adds a claim"}) + "\n")
            fail_cfg = _config(fail_stage, reviews_path=str(review_path))
            failed = run_gate(fail_cfg, limit=1)
            failed_payload = _payload(failed)
            report.add(
                case,
                "accepted-gate-fail",
                failed_payload.get("exit_code") == 1 and failed_payload.get("release_verdict") == "fail",
                f"exit={failed_payload.get('exit_code')} verdict={failed_payload.get('release_verdict')}",
            )
            faults = {
                "gate-missing-approval": lambda exp, rub, reg: rub["review"].update({"approval_state": "pending", "product_domain_approver": None, "approved_version": None, "approved_date": None}),
                "gate-missing-version": lambda exp, rub, reg: [row.update({"criterion_version": ""}) for row in reg.get("routes") or [] if row.get("criterion_id") == "C-len"],
                "gate-version-mismatch": lambda exp, rub, reg: [row.update({"criterion_version": "9.9"}) for row in reg.get("routes") or [] if row.get("criterion_id") == "C-len"],
                "gate-missing-acceptance": lambda exp, rub, reg: [row.update({"acceptance_state": "accepted", "evidence": {"approved": True}}) for row in reg.get("routes") or [] if row.get("criterion_id") == "C-len"],
            }
            fault_tokens = {
                "gate-missing-approval": "approval",
                "gate-missing-version": "missing version",
                "gate-version-mismatch": "version mismatch",
                "gate-missing-acceptance": "acceptance",
            }
            for name, mutate in faults.items():
                exp, rub, reg = _accepted_len(expectations, rubric, register)
                mutate(exp, rub, reg)
                staged = _stage(repo, root / name, exp, rub, reg, dataset)
                try:
                    ok_refuse, detail = _refused(staged)
                except Exception as exc:
                    ok_refuse, detail = False, f"{type(exc).__name__}: {exc}"
                token = fault_tokens[name]
                report.add(case, name, ok_refuse and token in detail.lower(), detail)
            unscorable = summarize(
                [{"criterion_id": "C-len", "applicability": "applicable", "status": "UNSCORABLE", "shadow": False}],
                {"required_criteria": ["C-len"], "unscorable_consequence": "block"},
            )
            pending_summary = summarize(
                [{"criterion_id": "C-tone", "applicability": "applicable", "status": "PENDING", "shadow": False}],
                {"required_criteria": ["C-tone"], "unscorable_consequence": "block"},
            )
            blocked_unscorable = evaluate_decision(unscorable, ready_pre, [])
            blocked_pending = evaluate_decision(pending_summary, ready_pre, [])
            report.add(case, "all-unscorable-not-pass", blocked_unscorable.exit_code != 0 and blocked_unscorable.release_verdict != "pass", f"exit={blocked_unscorable.exit_code}")
            report.add(case, "pending-required-not-pass", blocked_pending.exit_code != 0 and blocked_pending.release_verdict != "pass", f"exit={blocked_pending.exit_code}")
            accepted = summarize(
                [{"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False}],
                {"required_criteria": ["C-len"], "unscorable_consequence": "block"},
            )
            base = evaluate_decision(accepted, ready_pre, [{"criterion_id": "C-faithful", "status": "FAIL", "shadow": True}])
            flipped = evaluate_decision(accepted, ready_pre, [{"criterion_id": "C-faithful", "status": "PASS", "shadow": True}])
            parse_fail = evaluate_decision(accepted, ready_pre, "{not-json")
            report.add(case, "shadow-does-not-flip", base.exit_code == flipped.exit_code == parse_fail.exit_code == 0, f"{base.exit_code},{flipped.exit_code},{parse_fail.exit_code}")
            required_shadow = summarize(
                [{"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False}],
                {"required_criteria": ["C-len", "C-faithful"], "unscorable_consequence": "block"},
            )
            blocked = evaluate_decision(required_shadow, ready_pre, [{"criterion_id": "C-faithful", "status": "PASS", "shadow": True}])
            report.add(case, "required-shadow-blocks", blocked.exit_code == 2 and blocked.release_verdict is None, f"exit={blocked.exit_code}")
            review_path = root / "human-pass.json"
            review_path.write_text(json.dumps({"item_id": "dev-1", "criterion_id": "C-tone", "criterion_version": "1.0", "reviewer_id": "fixture-expert", "rubric_version": "1.0", "verdict": "Pass", "evidence_note": "opening words match"}) + "\n")
            reviews = import_reviews(str(review_path))
            report.add(case, "human-import", bool(reviews) and reviews[0].pending is False, str(reviews[0]))
            pending_path = root / "human-pending.json"
            pending_path.write_text(json.dumps({"item_id": "dev-1", "criterion_id": "C-tone", "verdict": "Pass"}) + "\n")
            pending = import_reviews(str(pending_path))
            report.add(case, "pending-review", bool(pending) and pending[0].pending is True, str(pending[0]))
            writer_cfg = _config(ready, mode="diagnostic", use_langfuse=False, results_dir=str(root / "bypass-results"))

            class _BlockLangfuse:
                def find_spec(self, fullname, path, target=None):
                    if fullname == "langfuse" or fullname.startswith("langfuse."):
                        raise RuntimeError("langfuse import blocked")
                    return None

            class _BlockSocket(socket.socket):
                def connect(self, address):
                    raise OSError("network blocked during langfuse bypass")

            sys.modules.pop("langfuse", None)
            sys.meta_path.insert(0, _BlockLangfuse())
            original_socket = socket.socket
            socket.socket = _BlockSocket
            try:
                from eval_harness.langfuse_writer import make_writer
                writer = make_writer(writer_cfg)
                writer.write({"k": 1, "decision_eligible": False}, [{"item_id": "dev-1"}], {"pass_rate": None}, {"release_verdict": None})
                reread = json.loads((root / "bypass-results" / "run_meta.json").read_text())
                report.add(case, "langfuse-bypass", "langfuse" not in sys.modules and reread.get("k") == 1, "local round-trip under import and network traps")
            finally:
                socket.socket = original_socket
                sys.meta_path.pop(0)
        if overlap_fn is None:
            report.add(case, "iou", False, "no overlap or IoU function on eval_harness.metrics")
        else:
            overlap_value = overlap_fn((0, 10), (5, 15))
            expected = (5 / 15) if overlap_fn.__name__ == "interval_iou" else 5
            report.add(case, "iou", overlap_value is not None and abs(overlap_value - expected) < 1e-9, f"{overlap_fn.__name__}={overlap_value}")
        proxy_blob = " ".join(str(item) for item in proxies)
        decision_metrics = getattr(accepted, "decision_metrics", {}) or {}
        report.add(case, "proxies-separate", "proxy_" in proxy_blob and not any(str(name).startswith("proxy_") for name in decision_metrics), proxy_blob)
        try:
            assert_held_out_disjoint({"items": [{"id": "dev-1", "content": "same"}]}, {"items": [{"id": "hold-9", "content": "same"}]})
            report.add(case, "overlap-rejected", False, "overlap was accepted")
        except ValueError as exc:
            report.add(case, "overlap-rejected", "overlap" in str(exc), str(exc))
    except Exception as exc:
        report.add(case, "generated-behavior-probes", False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    report = Report()
    mapping = {
        "A-missing-expectations": check_a,
        "B-expectations-only": check_b,
        "C-approved-criteria": check_c,
    }
    for name, fn in mapping.items():
        repo = root / name
        if not repo.exists():
            report.add(name, "repo-exists", False, "missing scenario; not a pass")
            continue
        fn(repo, report)
    sys.exit(report.dump(root / "report.json"))


if __name__ == "__main__":
    main()
