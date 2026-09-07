"""Stable public labels over the legacy runtime's machine identifiers."""

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
    "reliability-review": "Reliability Paths",
    "llm-review": "Context Reasoning",
}

BENCHMARK_ARM_LABELS = {
    "single-model": "Solo Review",
    "single-llm": "Solo Review",
    "multi-llm-no-critic": "Prism without Examiner",
    "full-agentic": "Full DiffPrism",
}
