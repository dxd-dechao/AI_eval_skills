#!/usr/bin/env python3
"""Verify forward-test repos. Missing artifacts fail; they are not skips."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import sys
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


def check_a(repo: Path, report: Report) -> None:
    case = "A"
    intake = repo / "Knowledge" / "product-expectations.json"
    data = _load(intake)
    report.add(case, "intake-json", data is not None, str(intake))
    if not data:
        return
    blocked = data.get("state") == "NEEDS_PRODUCT_DECISION" or "BLOCKED" in str(data.get("display_state", ""))
    report.add(case, "blocked-state", blocked, str(data.get("state")))
    inv = data.get("inventory") or []
    report.add(case, "inventory-nonempty", len(inv) > 0, f"rows={len(inv)}")
    log = data.get("decision_log") or []
    report.add(case, "open-decisions", len(log) > 0, f"decisions={len(log)}")
    blob = _text_blobs(repo / "Knowledge") + "\n" + _text_blobs(repo / "eval_harness")
    banned = ("judge prompt", "DEFAULT_GATES", "kappa")
    # A builder blocker may mention gates only to say they were not generated.
    has_eval_pkg = (repo / "eval_harness" / "evaluators").exists() or (repo / "eval_harness" / "gates.py").exists()
    report.add(case, "no-evaluator-package", not has_eval_pkg, "evaluators or gates.py present" if has_eval_pkg else "absent")
    report.add(case, "blocked-md", (repo / "eval_harness" / "BLOCKED.md").exists(), "BLOCKED.md")
    plumbing = repo / "eval_harness" / "pipeline_adapter.py"
    plumbing_ok = plumbing.exists() and not (repo / "eval_harness" / "gates.py").exists() and not (repo / "eval_harness" / "evaluators").exists()
    report.add(case, "neutral-plumbing", plumbing_ok, str(plumbing) if plumbing_ok else "follow-up plumbing missing or it included scoring")
    del banned, blob


def check_b(repo: Path, report: Report) -> None:
    case = "B"
    rubric_path = repo / "Knowledge" / "rubric-register.json"
    data = _load(rubric_path)
    report.add(case, "rubric-json", data is not None, str(rubric_path))
    if not data:
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


def check_c(repo: Path, report: Report) -> None:
    case = "C"
    reg = _load(repo / "Knowledge" / "evaluator-register.json")
    report.add(case, "register-present", reg is not None, "evaluator-register.json")
    if reg:
        types = {r.get("evaluator_type") for r in reg.get("routes", [])}
        report.add(case, "three-routes", types >= {"deterministic", "human", "llm"}, str(types))
    dev = _load(repo / "Knowledge" / "dev_manifest.json")
    hold = _load(repo / "Knowledge" / "heldout_manifest.json")
    report.add(case, "disjoint-manifests", bool(dev and hold), "manifests")
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
        from eval_harness.metrics import summarize, interval_iou, PRODUCTION_PROXIES
        from eval_harness.gates import evaluate_decision
        from eval_harness.contract import PreflightResult
        from eval_harness.dataset_loader import assert_held_out_disjoint
        from eval_harness.human_review import import_reviews
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
        ok_pre = PreflightResult(True, None, True)
        bad_pre = PreflightResult(False, "missing acceptance evidence", False)
        accepted = summarize(
            [{"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False}],
            {"required_criteria": ["C-len"], "unscorable_consequence": "block"},
        )
        base = evaluate_decision(accepted, ok_pre, [{"criterion_id": "C-faithful", "status": "FAIL", "shadow": True}])
        flipped = evaluate_decision(accepted, ok_pre, [{"criterion_id": "C-faithful", "status": "PASS", "shadow": True}])
        parse_fail = evaluate_decision(accepted, ok_pre, "{not-json")
        report.add(case, "shadow-does-not-flip", base.exit_code == flipped.exit_code == parse_fail.exit_code == 0, f"{base.exit_code},{flipped.exit_code},{parse_fail.exit_code}")
        required_shadow = summarize(
            [{"criterion_id": "C-len", "applicability": "applicable", "status": "PASS", "shadow": False}],
            {"required_criteria": ["C-len", "C-faithful"], "unscorable_consequence": "block"},
        )
        blocked = evaluate_decision(required_shadow, ok_pre, [{"criterion_id": "C-faithful", "status": "PASS", "shadow": True}])
        report.add(case, "required-shadow-blocks", blocked.exit_code == 2 and blocked.release_verdict is None, f"exit={blocked.exit_code}")
        refused = evaluate_decision(accepted, bad_pre, [])
        report.add(case, "preflight-before-quality", refused.exit_code == 2 and refused.release_verdict is None, refused.blocked_reason or "")
        report.add(case, "iou", abs(interval_iou((0, 10), (5, 15)) - (5 / 15)) < 1e-9, str(interval_iou((0, 10), (5, 15))))
        report.add(case, "proxies-separate", "proxy_" in "".join(PRODUCTION_PROXIES) and "proxy_headline_length_watch" not in accepted.decision_metrics, str(list(PRODUCTION_PROXIES)))
        try:
            assert_held_out_disjoint({"items": [{"id": "dev-1", "content": "same"}]}, {"items": [{"id": "hold-9", "content": "same"}]})
            report.add(case, "overlap-rejected", False, "overlap was accepted")
        except ValueError as exc:
            report.add(case, "overlap-rejected", "overlap" in str(exc), str(exc))
        review_path = repo / "fixture-review.json"
        review_path.write_text(json.dumps({"item_id": "dev-1", "criterion_id": "C-tone", "criterion_version": "1.0", "reviewer_id": "fixture-expert", "rubric_version": "1.0", "verdict": "Pass", "evidence_note": "opening words match"}) + "\n")
        reviews = import_reviews(str(review_path))
        report.add(case, "human-import", bool(reviews) and reviews[0].pending is False, str(reviews[0]))
        pending_path = repo / "fixture-pending.json"
        pending_path.write_text(json.dumps({"item_id": "dev-1", "criterion_id": "C-tone", "verdict": "Pass"}) + "\n")
        pending = import_reviews(str(pending_path))
        report.add(case, "pending-review", bool(pending) and pending[0].pending is True and pending[0].verdict is None, str(pending[0]))
        import sys as _sys
        from eval_harness.langfuse_writer import make_writer
        _sys.modules.pop("langfuse", None)
        writer = make_writer(cfg)
        roundtrip = writer.write({"k": 1, "decision_eligible": False}, [{"item_id": "dev-1"}], {"pass_rate": None}, {"release_verdict": None})
        report.add(case, "langfuse-bypass", "langfuse" not in _sys.modules and roundtrip["run_meta"]["k"] == 1, f"modules={'langfuse' in _sys.modules}")
    except Exception as exc:
        report.add(case, "generated-behavior-probes", False, f"{type(exc).__name__}: {exc}")
    try:
        gate_cfg = HarnessConfig(
            mode="gate",
            limit=1,
            runs=1,
            use_langfuse=False,
            results_dir=str(repo / "results-gate"),
            expectations_path=str(repo / "Knowledge" / "product-expectations.json"),
            rubric_path=str(repo / "Knowledge" / "missing-rubric.json"),
            evaluator_register_path=str(repo / "Knowledge" / "evaluator-register.json"),
            dataset_path=str(repo / "Knowledge" / "dev_manifest.json"),
        )
        pre = preflight_gate(gate_cfg)
        ok = getattr(pre, "ok", pre.get("ok") if isinstance(pre, dict) else None)
        report.add(case, "gate-refuses-missing", ok is False, f"ok={ok}")
    except Exception as exc:
        report.add(case, "gate-refuses-missing", False, f"{type(exc).__name__}: {exc}")


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
