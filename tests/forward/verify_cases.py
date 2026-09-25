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


def _run_probe(report: Report, case: str, name: str, fn):
    """Record one probe. An exception fails only this probe."""
    try:
        ok, detail = fn()
    except Exception:
        tail = "\n".join(traceback.format_exc().strip().splitlines()[-6:])
        report.add(case, name, False, tail)
        return None
    report.add(case, name, bool(ok), "" if detail is None else str(detail))
    return ok


def _summary_attr(summary, name: str):
    if not hasattr(summary, name):
        raise AttributeError(f"Summary.{name} is not on the documented top-level aggregate")
    return getattr(summary, name)


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
    no_calls = invoked in (0, None, "", []) or invoked == ()
    before_quality = quality is False or (quality is None and no_calls and not raw)
    cli = _cli_gate(staged)
    detail = f"preflight_ok={ok} reason={reason} run_exit={payload.get('exit_code')} quality={quality} calls={invoked} cli_exit={cli.returncode}"
    refused = ok is False and bool(reason) and payload.get("exit_code") not in (0, None) and before_quality and cli.returncode != 0
    return refused, detail


def _len_evidence() -> dict:
    return {
        "kind": "verification",
        "cases": [
            {"role": "known-good", "name": "known-good",         "expected": "PASS"},
            {"role": "known-bad", "name": "known-bad", "expected": "FAIL"},
            {"role": "edge", "name": "edge", "expected": "UNSCORABLE"},
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
    types = {r.get("evaluator_type") for r in (reg or {}).get("routes", [])} if reg else set()
    report.add(case, "three-routes", bool(reg) and types >= {"deterministic", "human", "llm"}, str(types))
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
    else:
        report.add(case, "notebook-ast", False, "notebook missing")
        report.add(case, "notebook-defaults", False, "notebook missing")
    try:
        _import_harness(repo)
        from eval_harness.config import HarnessConfig
        from eval_harness.contract import preflight_gate
        from eval_harness.run_eval import run
    except Exception:
        report.add(case, "import-harness", False, "\n".join(traceback.format_exc().strip().splitlines()[-6:]))
        report.add(case, "k1-run", False, "harness import failed")
        report.add(case, "entrypoint-once", False, "harness import failed")
        report.add(case, "diagnostic-not-release", False, "harness import failed")
    else:
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
        except Exception:
            tail = "\n".join(traceback.format_exc().strip().splitlines()[-6:])
            report.add(case, "k1-run", False, tail)
            report.add(case, "entrypoint-once", False, "run failed")
            report.add(case, "diagnostic-not-release", False, "run failed")
    _check_c_metrics(repo, report, case)


def _check_c_metrics(repo: Path, report: Report, case: str) -> None:
    """Each probe is isolated. Documented Summary fields only; no private attributes."""
    box: dict = {}

    def _load_metrics():
        import eval_harness.metrics as metrics
        from eval_harness.gates import evaluate_decision
        from eval_harness.dataset_loader import assert_held_out_disjoint
        from eval_harness.human_review import import_reviews
        from eval_harness.run_eval import run as run_gate
        from eval_harness.contract import preflight_gate

        box.update(
            metrics=metrics,
            summarize=metrics.summarize,
            evaluate_decision=evaluate_decision,
            assert_held_out_disjoint=assert_held_out_disjoint,
            import_reviews=import_reviews,
            run_gate=run_gate,
            preflight_gate=preflight_gate,
        )
        return True, "metrics imported"

    if _run_probe(report, case, "metrics-import", _load_metrics) is not True:
        pass

    policy_len = {"required_criteria": ["C-len"], "unscorable_consequence": "block"}
    rows = [
        {"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False},
        {"criterion_id": "C-tone", "applicability": "applicable", "status": "FAIL", "shadow": False},
        {"criterion_id": "C-faithful", "applicability": "not_applicable", "status": "PASS", "shadow": False},
        {"criterion_id": "C-extra", "applicability": "unknown", "status": "PASS", "shadow": False},
    ]

    def _denominator():
        summary = box["summarize"](rows, policy_len)
        box["summary"] = summary
        den = _summary_attr(summary, "denominator")
        passed = _summary_attr(summary, "pass_count")
        failed = _summary_attr(summary, "fail_count")
        na = _summary_attr(summary, "not_applicable_count")
        uns = _summary_attr(summary, "unscorable_count")
        pending = _summary_attr(summary, "pending_count")
        errors = _summary_attr(summary, "error_count")
        rate = _summary_attr(summary, "pass_rate")
        blocked = _summary_attr(summary, "blocked_reason")
        shadows = list(_summary_attr(summary, "required_shadow_ids") or [])
        ok = (
            den == 2
            and passed == 1
            and failed == 1
            and na == 1
            and uns == 1
            and pending == 0
            and errors == 0
            and blocked in (None, "")
            and shadows == []
            and abs((rate or 0) - 0.5) < 1e-9
        )
        return ok, f"den={den} pass={passed} fail={failed} na={na} uns={uns} pending={pending} err={errors} rate={rate} blocked={blocked} shadow={shadows}"

    def _empty():
        empty = box["summarize"]([], policy_len)
        rate = _summary_attr(empty, "pass_rate")
        den = _summary_attr(empty, "denominator")
        blocked = _summary_attr(empty, "blocked_reason")
        return rate is None and den == 0 and bool(blocked), f"rate={rate} blocked={blocked}"

    _run_probe(report, case, "denominator", _denominator)
    _run_probe(report, case, "empty-not-pass", _empty)

    def _stage_ready():
        expectations, rubric, register = _base_registers(repo)
        dataset = _load(repo / "Knowledge" / "dev_manifest.json") or {
            "id": "dev-set",
            "version": "1",
            "items": [{"id": "dev-1", "content": "Alpha budget note"}],
        }
        box["expectations"] = expectations
        box["rubric"] = rubric
        box["register"] = register
        box["dataset"] = dataset
        box["tmp"] = tempfile.TemporaryDirectory(prefix="ai-eval-skills-probes-")
        box["root"] = Path(box["tmp"].name)
        ready_exp, ready_rubric, ready_reg = _accepted_len(expectations, rubric, register)
        ready = _stage(repo, box["root"] / "ready", ready_exp, ready_rubric, ready_reg, dataset)
        box["ready"] = ready
        ready_pre = box["preflight_gate"](_config(ready))
        box["ready_pre"] = ready_pre
        ok = ready_pre.ok is True
        return ok, getattr(ready_pre, "blocked_reason", None)

    def _gate_pass():
        passed = box["run_gate"](_config(box["ready"]), limit=1)
        payload = _payload(passed)
        evidence_kept = "implementation_version" in json.dumps(payload)
        meta_path = box["ready"] / "probe-results" / "run_meta.json"
        if meta_path.exists():
            evidence_kept = evidence_kept or "implementation_version" in meta_path.read_text()
        ok = payload.get("exit_code") == 0 and payload.get("release_verdict") == "pass" and evidence_kept
        return ok, f"exit={payload.get('exit_code')} verdict={payload.get('release_verdict')} evidence={evidence_kept}"

    def _gate_fail():
        expectations, rubric, register = box["expectations"], box["rubric"], box["register"]
        fail_exp, fail_rubric, fail_reg = _accepted_len(expectations, rubric, register)
        for route in fail_reg.get("routes") or []:
            if route.get("criterion_id") == "C-tone":
                _accept_route(
                    route,
                    {
                        "kind": "human_procedure",
                        "reviewer_id": "fixture-expert",
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
        fail_stage = _stage(repo, box["root"] / "fail", fail_exp, fail_rubric, fail_reg, box["dataset"])
        review_path = box["root"] / "fail-review.json"
        review_path.write_text(
            json.dumps(
                {
                    "item_id": "dev-1",
                    "criterion_id": "C-tone",
                    "criterion_version": "1.0",
                    "reviewer_id": "fixture-expert",
                    "rubric_version": "1.0",
                    "verdict": "Fail",
                    "evidence_note": "headline adds a claim",
                }
            )
            + "\n"
        )
        failed = box["run_gate"](_config(fail_stage, reviews_path=str(review_path)), limit=1)
        payload = _payload(failed)
        ok = payload.get("exit_code") == 1 and payload.get("release_verdict") == "fail"
        return ok, f"exit={payload.get('exit_code')} verdict={payload.get('release_verdict')}"

    def _fault(name, mutate, token):
        def _probe():
            exp, rub, reg = _accepted_len(box["expectations"], box["rubric"], box["register"])
            mutate(exp, rub, reg)
            staged = _stage(repo, box["root"] / name, exp, rub, reg, box["dataset"])
            ok_refuse, detail = _refused(staged)
            return ok_refuse and token in detail.lower(), detail
        return _probe

    faults = {
        "gate-missing-approval": (
            lambda exp, rub, reg: rub["review"].update(
                {"approval_state": "pending", "product_domain_approver": None, "approved_version": None, "approved_date": None}
            ),
            "approval",
        ),
        "gate-missing-version": (
            lambda exp, rub, reg: [row.update({"criterion_version": ""}) for row in reg.get("routes") or [] if row.get("criterion_id") == "C-len"],
            "version",
        ),
        "gate-version-mismatch": (
            lambda exp, rub, reg: [row.update({"criterion_version": "9.9"}) for row in reg.get("routes") or [] if row.get("criterion_id") == "C-len"],
            "version",
        ),
        "gate-missing-acceptance": (
            lambda exp, rub, reg: [
                row.update({"acceptance_state": "accepted", "evidence": {"approved": True}})
                for row in reg.get("routes") or []
                if row.get("criterion_id") == "C-len"
            ],
            "acceptance",
        ),
    }

    def _unscorable():
        summary = box["summarize"](
            [{"criterion_id": "C-len", "applicability": "applicable", "status": "UNSCORABLE", "shadow": False}],
            policy_len,
        )
        blocked = box["evaluate_decision"](summary, box["ready_pre"], [])
        ok = blocked.exit_code != 0 and blocked.release_verdict != "pass"
        return ok, f"exit={blocked.exit_code} verdict={blocked.release_verdict} blocked={_summary_attr(summary, 'blocked_reason')}"

    def _pending():
        summary = box["summarize"](
            [{"criterion_id": "C-tone", "applicability": "applicable", "status": "PENDING", "shadow": False}],
            {"required_criteria": ["C-tone"], "unscorable_consequence": "block"},
        )
        blocked = box["evaluate_decision"](summary, box["ready_pre"], [])
        ok = blocked.exit_code != 0 and blocked.release_verdict != "pass"
        return ok, f"exit={blocked.exit_code} verdict={blocked.release_verdict}"

    def _shadow_flip():
        accepted = box["summarize"](
            [{"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False}],
            policy_len,
        )
        base = box["evaluate_decision"](accepted, box["ready_pre"], [{"criterion_id": "C-faithful", "status": "FAIL", "shadow": True}])
        flipped = box["evaluate_decision"](accepted, box["ready_pre"], [{"criterion_id": "C-faithful", "status": "PASS", "shadow": True}])
        parse_fail = box["evaluate_decision"](accepted, box["ready_pre"], "{not-json")
        ok = base.exit_code == flipped.exit_code == parse_fail.exit_code == 0
        return ok, f"{base.exit_code},{flipped.exit_code},{parse_fail.exit_code}"

    def _required_shadow():
        summary = box["summarize"](
            [{"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False}],
            {"required_criteria": ["C-len", "C-faithful"], "unscorable_consequence": "block"},
        )
        ids = list(_summary_attr(summary, "required_shadow_ids") or [])
        blocked = box["evaluate_decision"](summary, box["ready_pre"], [{"criterion_id": "C-faithful", "status": "PASS", "shadow": True}])
        ok = "C-faithful" in ids and blocked.exit_code == 2 and blocked.release_verdict is None
        return ok, f"ids={ids} exit={blocked.exit_code} verdict={blocked.release_verdict}"

    def _human_import():
        review_path = box["root"] / "human-pass.json"
        review_path.write_text(
            json.dumps(
                {
                    "item_id": "dev-1",
                    "criterion_id": "C-tone",
                    "criterion_version": "1.0",
                    "reviewer_id": "fixture-expert",
                    "rubric_version": "1.0",
                    "verdict": "Pass",
                    "evidence_note": "opening words match",
                }
            )
            + "\n"
        )
        reviews = box["import_reviews"](str(review_path))
        return bool(reviews) and reviews[0].pending is False, str(reviews[0])

    def _pending_review():
        pending_path = box["root"] / "human-pending.json"
        pending_path.write_text(json.dumps({"item_id": "dev-1", "criterion_id": "C-tone", "verdict": "Pass"}) + "\n")
        pending = box["import_reviews"](str(pending_path))
        return bool(pending) and pending[0].pending is True, str(pending[0])

    def _langfuse():
        writer_cfg = _config(box["ready"], mode="diagnostic", use_langfuse=False, results_dir=str(box["root"] / "bypass-results"))

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
            reread = json.loads((box["root"] / "bypass-results" / "run_meta.json").read_text())
            ok = "langfuse" not in sys.modules and reread.get("k") == 1
            return ok, "local round-trip under import and network traps"
        finally:
            socket.socket = original_socket
            sys.meta_path.pop(0)

    def _iou():
        metrics = box["metrics"]
        fn = None
        for name in dir(metrics):
            if "iou" in name.lower() or "overlap" in name.lower():
                cand = getattr(metrics, name)
                if callable(cand):
                    fn = cand
                    break
        if fn is None:
            return True, "no interval evidence on this register; overlap function not required"
        value = fn((0, 10), (5, 15))
        expected = (5 / 15) if "iou" in fn.__name__.lower() else 5
        return value is not None and abs(value - expected) < 1e-9, f"{fn.__name__}={value}"

    def _proxies():
        metrics = box["metrics"]
        found = getattr(metrics, "PRODUCTION_PROXIES", None)
        if not isinstance(found, dict):
            return False, "metrics.PRODUCTION_PROXIES is missing"
        summary = box.get("summary")
        leaked = []
        if summary is not None:
            for field in (
                "denominator",
                "pass_count",
                "fail_count",
                "not_applicable_count",
                "unscorable_count",
                "pending_count",
                "error_count",
                "pass_rate",
                "blocked_reason",
                "required_shadow_ids",
            ):
                if field.startswith("proxy_"):
                    leaked.append(field)
        return not leaked, found

    def _overlap():
        try:
            box["assert_held_out_disjoint"](
                {"items": [{"id": "dev-1", "content": "same"}]},
                {"items": [{"id": "hold-9", "content": "same"}]},
            )
        except ValueError as exc:
            return True, str(exc)
        return False, "overlap was accepted"

    try:
        _run_probe(report, case, "accepted-preflight", _stage_ready)
        _run_probe(report, case, "accepted-gate-pass", _gate_pass)
        _run_probe(report, case, "accepted-gate-fail", _gate_fail)
        for name, (mutate, token) in faults.items():
            _run_probe(report, case, name, _fault(name, mutate, token))
        _run_probe(report, case, "all-unscorable-not-pass", _unscorable)
        _run_probe(report, case, "pending-required-not-pass", _pending)
        _run_probe(report, case, "shadow-does-not-flip", _shadow_flip)
        _run_probe(report, case, "required-shadow-blocks", _required_shadow)
        _run_probe(report, case, "human-import", _human_import)
        _run_probe(report, case, "pending-review", _pending_review)
        _run_probe(report, case, "langfuse-bypass", _langfuse)
        _run_probe(report, case, "iou", _iou)
        _run_probe(report, case, "proxies-separate", _proxies)
        _run_probe(report, case, "overlap-rejected", _overlap)
    finally:
        tmp = box.get("tmp")
        if tmp is not None:
            tmp.cleanup()


def check_d(repo: Path, report: Report) -> None:
    case = "D"
    reg = _load(repo / "Knowledge" / "evaluator-register.json")
    report.add(case, "register-present", reg is not None, "evaluator-register.json")
    routes = (reg or {}).get("routes") or []
    by_id = {row.get("criterion_id"): row for row in routes if isinstance(row, dict)}

    def _route(cid):
        row = by_id.get(cid) or {}
        return row

    rare = _route("C-hold")
    scale = _route("C-claim")
    report.add(case, "rare-human", rare.get("evaluator_type") == "human", str(rare.get("evaluator_type")))
    rationale = str(scale.get("measurement_rationale") or "")
    volume = any(token in rationale.lower() for token in ("thousand", "per day", "daily", "volume", "at scale", "scale"))
    report.add(
        case,
        "scale-llm-volume",
        scale.get("evaluator_type") == "llm" and rationale.strip() != "" and volume,
        rationale,
    )
    accepted = [
        row.get("criterion_id")
        for row in routes
        if row.get("acceptance_state") == "accepted" or row.get("decision_eligible") is True
    ]
    report.add(case, "none-accepted", not accepted, str(accepted))
    blob = json.dumps(reg or {})
    banned = []
    for token in ("Hard", "Soft", "launch_policy", "launch-policy", "launch policy"):
        if token in blob:
            banned.append(token)
    report.add(case, "no-hard-soft-launch", not banned, ",".join(banned) if banned else "absent")
    harness = (repo / "eval_harness" / "run_eval.py").exists()
    report.add(case, "harness-present", harness, "eval_harness/run_eval.py")



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
        "D-approved-unrouted": check_d,
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
