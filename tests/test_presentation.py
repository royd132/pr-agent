import unittest

import diffprism
from diffprism.__main__ import main
from evoagent.github import GitHubClient
from evoagent.presentation import (
    BENCHMARK_ARM_LABELS,
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    REVIEW_PACK_LABELS,
    ROLE_LABELS,
)


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


if __name__ == "__main__":
    unittest.main()
