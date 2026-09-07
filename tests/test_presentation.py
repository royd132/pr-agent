import unittest
from pathlib import Path

import diffprism
from diffprism.__main__ import main
from evoagent.github import GitHubClient
from evoagent.presentation import (
    BENCHMARK_ARM_LABELS,
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    REVIEW_PACK_LABELS,
    ROLE_LABELS,
    public_benchmark_summary,
    synthetic_benchmark_status,
)

ROOT = Path(__file__).resolve().parents[1]


class PresentationTests(unittest.TestCase):
    def test_public_brand_and_entrypoint(self):
        self.assertEqual("DiffPrism", PRODUCT_NAME)
        self.assertEqual("Split the diff. Verify the risk.", PRODUCT_TAGLINE)
        self.assertEqual("0.1.0", diffprism.__version__)
        self.assertTrue(callable(main))

    def test_public_labels_cover_the_review_flow(self):
        self.assertEqual("Prism Lead", ROLE_LABELS["prism-lead"])
        self.assertEqual("Scope Mapper", ROLE_LABELS["scope-mapper"])
        self.assertEqual("Failure Hunter", ROLE_LABELS["failure-hunter"])
        self.assertEqual("Evidence Examiner", ROLE_LABELS["evidence-examiner"])
        self.assertEqual("Security Boundaries", REVIEW_PACK_LABELS["security-review"])
        self.assertEqual("Full DiffPrism", BENCHMARK_ARM_LABELS["full-agentic"])

    def test_github_requests_use_the_public_product_name(self):
        headers = GitHubClient("token")._headers()
        self.assertEqual("DiffPrism/0.1.0", headers["User-Agent"])

    def test_synthetic_benchmark_status_reports_provenance_and_limits(self):
        status = synthetic_benchmark_status(ROOT / "evaluation_data" / "pr_diff_100.jsonl")
        self.assertEqual("Synthetic Fault Benchmark v1", status["name"])
        self.assertEqual(100, status["cases"])
        self.assertEqual(40, status["positive_cases"])
        self.assertEqual(60, status["clean_cases"])
        self.assertEqual(10, status["repositories"])
        self.assertEqual({"validation": 80, "holdout": 20}, status["splits"])
        self.assertFalse(status["production_ready"])
        self.assertEqual("no-train-split-and-not-public-pr-data", status["limitation"])

    def test_public_benchmark_summary_uses_public_arm_names(self):
        summary = public_benchmark_summary({
            "id": "run-1", "decision": "rejected", "created_at": "2026-09-07",
            "metrics": {"arm": "full-agentic", "f1": 0.7,
                        "p95_review_latency_ms": 120,
                        "cost_per_verified_finding_usd": 0.03},
        })
        self.assertEqual("Full DiffPrism", summary["arm_display_name"])
        self.assertEqual(120, summary["metrics"]["p95_review_latency_ms"])


if __name__ == "__main__":
    unittest.main()
