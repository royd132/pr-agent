import unittest

from evoagent.models import Finding, ReviewReport, Severity
from evoagent.report import to_markdown


class ReportContractTests(unittest.TestCase):
    def test_new_report_fields_default_for_legacy_callers(self):
        finding = Finding(
            "R", Severity.HIGH, "Title", "Explanation", "a.py", 3,
            "danger()", "replace it", "add regression", 0.9,
        )
        payload = ReviewReport("org/repo", 7, "summary", "high", [finding]).to_dict()
        self.assertEqual({}, payload["change_map"])
        self.assertEqual({}, payload["verdict"])
        self.assertEqual("", payload["findings"][0]["trigger"])
        self.assertEqual("", payload["findings"][0]["impact"])
        self.assertEqual("unverified", payload["findings"][0]["verification"])

    def test_markdown_leads_with_verdict_then_change_map(self):
        markdown = to_markdown({
            "repository": "org/repo",
            "pull_request": 7,
            "risk": "high",
            "summary": "summary",
            "findings": [{
                "rule_id": "AUTH-EXPIRY",
                "severity": "high",
                "title": "Expiry is not checked",
                "path": "auth.py",
                "line": 8,
                "evidence": "return token.user",
                "explanation": "Expired tokens pass",
                "fix": "Validate exp before returning",
                "test": "Add an expired-token test",
                "trigger": "An expired token reaches this return",
                "impact": "A stale session remains authorized",
                "verification": "verified",
                "examiner_reason": "The changed line proves the path.",
            }],
            "change_map": {
                "intent": "tighten auth",
                "surfaces": ["auth"],
                "affected_files": ["auth.py"],
                "test_gaps": ["expiry"],
                "unknowns": ["deployment config"],
            },
            "verdict": {
                "decision": "warn",
                "reason": "test gap",
                "required_actions": ["add expiry test"],
                "verified_findings": 1,
                "rejected_findings": 1,
            },
        })
        self.assertLess(markdown.index("## Merge verdict"), markdown.index("## Change map"))
        self.assertLess(markdown.index("## Change map"), markdown.index("## Verified findings"))
        self.assertIn("**Trigger:** An expired token", markdown)
        self.assertIn("**Impact:** A stale session", markdown)
        self.assertIn("**Suggested verification:** Add an expired-token test", markdown)
        self.assertIn("deployment config", markdown)


if __name__ == "__main__":
    unittest.main()
