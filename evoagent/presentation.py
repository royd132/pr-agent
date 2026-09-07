"""Stable public labels and adapters over internal runtime data."""

from collections import Counter
import hashlib
import os

from .evaluation_harness import dataset_fingerprint, load_jsonl

PRODUCT_NAME = "DiffPrism"
PRODUCT_VERSION = "0.1.0"
PRODUCT_TAGLINE = "Split the diff. Verify the risk."
GITHUB_USER_AGENT = "%s/%s" % (PRODUCT_NAME, PRODUCT_VERSION)

ROLE_LABELS = {
    "prism-lead": "Prism Lead",
    "scope-mapper": "Scope Mapper",
    "failure-hunter": "Failure Hunter",
    "evidence-examiner": "Evidence Examiner",
}

REVIEW_PACK_LABELS = {
    "security-review": "Security Boundaries",
    "correctness-review": "Behavioral Correctness",
    "reliability-review": "Failure Recovery",
    "database-review": "Data Integrity",
    "api-compatibility": "Contract Compatibility",
    "performance-review": "Performance Risk",
    "test-quality": "Test Coverage",
    "observability-review": "Runtime Signals",
    "code-quality": "Maintainability",
    "llm-review": "Context Reasoning",
}

BENCHMARK_ARM_LABELS = {
    "single-model": "Solo Review",
    "single-llm": "Solo Review",
    "multi-llm-no-critic": "Prism without Examiner",
    "full-agentic": "Full DiffPrism",
}

DEFAULT_SYNTHETIC_BENCHMARK = os.path.abspath(os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "evaluation_data", "pr_diff_100.jsonl",
))


def synthetic_benchmark_status(path=DEFAULT_SYNTHETIC_BENCHMARK):
    path = os.fspath(path)
    cases = load_jsonl(path)
    findings = [finding for case in cases for finding in case.get("expected_findings", [])]
    splits = Counter(str(case.get("split") or "unknown") for case in cases)
    repositories = {str(case.get("repository") or "") for case in cases}
    sources = {
        str((case.get("source") or {}).get("kind") or "unknown") for case in cases
    }
    production_ready = "train" in splits and sources == {"public-github-pr"}
    with open(path, "rb") as handle:
        file_sha256 = hashlib.sha256(handle.read()).hexdigest()
    return {
        "name": "Synthetic Fault Benchmark v1",
        "cases": len(cases),
        "positive_cases": sum(bool(case.get("expected_findings")) for case in cases),
        "clean_cases": sum(not case.get("expected_findings") for case in cases),
        "findings": len(findings),
        "repositories": len(repositories),
        "splits": dict(sorted(splits.items())),
        "source_kinds": sorted(sources),
        "rule_ids": sorted({str(item.get("rule_id") or "") for item in findings}),
        "severities": dict(sorted(Counter(
            str(item.get("severity") or "unknown") for item in findings
        ).items())),
        "file_sha256": file_sha256,
        "dataset_sha256": dataset_fingerprint(cases),
        "production_ready": production_ready,
        "limitation": "" if production_ready else "no-train-split-and-not-public-pr-data",
    }


def public_benchmark_summary(run):
    metrics = dict(run.get("metrics") or {})
    arm = str(metrics.get("arm") or run.get("arm") or "full-agentic")
    visible_metrics = {
        key: metrics[key] for key in (
            "precision", "recall", "f1", "high_risk_recall", "clean_accuracy",
            "p95_review_latency_ms", "cost_per_verified_finding_usd",
            "average_latency_ms_per_pr", "average_cost_usd_per_pr",
        ) if key in metrics
    }
    return {
        "id": run.get("id") or run.get("run_id"),
        "decision": run.get("decision", "unknown"),
        "created_at": run.get("created_at", ""),
        "arm": arm,
        "arm_display_name": BENCHMARK_ARM_LABELS.get(arm, arm),
        "metrics": visible_metrics,
    }


def present_review_pack(skill):
    """Add stable product-facing metadata without changing a skill's identity."""
    value = dict(skill)
    name = str(value.get("name") or "")
    value["display_name"] = REVIEW_PACK_LABELS.get(name, name or "Unknown pack")
    value["status_label"] = "Sandboxed" if value.get("sandboxed") else "Active"
    value["scope"] = str(value.get("description") or "No scope description available")
    return value
