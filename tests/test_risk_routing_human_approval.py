import unittest

from evoagent.diff_parser import parse_unified_diff
from evoagent.gates import FindingGate
from evoagent.models import Finding, Severity
from evoagent.patching import VerifiedPatchFixer
from evoagent.risk_profile import build_risk_profile
from evoagent.runtime import AgentTool


class FakeFixModel:
    provider = "fake"
    model = "fix-model"

    def complete_json(self, role, system, user, ledger=None, max_tokens=None):
        if ledger:
            ledger.record_model(role, self.provider, self.model, {
                "prompt_tokens": 10, "completion_tokens": 10,
            }, 1)
        return {
            "patch": (
                "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
                "-dangerous()\n+safe()\n"
            ),
            "behavioral_claims": ["Replace the verified dangerous call."],
            "related_tests": ["test_safe_call"],
        }


class FakeVerifier:
    test_command = "pytest -q"

    def verify_contents(self, files):
        return {"passed": True, "files": sorted(files)}

    def verify_archive(self, archive, overlay):
        return {"passed": True, "overlay": sorted(overlay)}

    def compare(self, before, after):
        return {"passed": True, "before": before, "after": after}


class FakeGitHub:
    def __init__(self):
        self.head_sha = "abc123"
        self.commits = []
        self.drafts = []

    def get_pull_request(self, repository, pull_request):
        return {
            "head": {
                "ref": "feature", "sha": self.head_sha,
                "repo": {"full_name": repository},
            },
            "base": {"ref": "main"},
        }

    def get_file(self, repository, path, ref):
        return {"decoded_content": "dangerous()\n"}

    def download_archive(self, repository, sha):
        return b"archive"

    def create_atomic_commit(self, repository, branch, source_sha, files, message):
        self.commits.append({
            "repository": repository, "branch": branch, "source_sha": source_sha,
            "files": dict(files), "message": message,
        })
        return {"sha": "commit123"}

    def create_draft_pull_request(self, repository, title, branch, base, body):
        self.drafts.append({
            "repository": repository, "title": title, "branch": branch,
            "base": base, "body": body,
        })
        return {"number": 99, "html_url": "https://example.invalid/pr/99"}


class RiskRoutingAndApprovalTests(unittest.TestCase):
    def test_risk_profile_routes_security_without_unnecessary_reliability(self):
        diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+eval(user_input)\n"
        parsed = parse_unified_diff(diff)
        profile = build_risk_profile(diff, parsed)
        self.assertTrue(profile.requires_security_review)
        self.assertFalse(profile.requires_reliability_review)
        self.assertTrue(profile.auditor_recommended)
        self.assertEqual("high", profile.risk_level)
        self.assertIn("dynamic-execution", profile.risk_domains)

    def test_quality_signal_routes_reliability_alongside_security(self):
        diff = (
            "--- a/app.py\n+++ b/app.py\n@@ -1 +1,2 @@\n-old\n"
            "+eval(user_input)\n+# TODO finish validation\n"
        )
        profile = build_risk_profile(diff, parse_unified_diff(diff))
        self.assertEqual(["boundary-inspector", "behavior-inspector"], profile.worker_roles)
        self.assertIn("quality-regression", profile.risk_domains)

    def test_tool_catalog_exposes_side_effect_and_retry_contract(self):
        tool = AgentTool(
            "publish", "Publish a verified artifact.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            lambda: True, side_effect=True, retryable=False, timeout_seconds=30,
        )
        entry = tool.catalog_entry()
        self.assertTrue(entry["side_effect"])
        self.assertFalse(entry["retryable"])
        self.assertEqual(30, entry["timeout_seconds"])

    def test_high_risk_declared_contract_requires_precondition_and_impact(self):
        diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+eval(user_input)\n"
        parsed = parse_unified_diff(diff)
        finding = Finding(
            "SEC-EVAL", Severity.HIGH, "Dynamic execution", "Input reaches eval.",
            "app.py", 1, "eval(user_input)", "Use a parser.", "Add a malicious-input test.",
            0.9, call_chain=[{"path": "app.py", "line": 1, "symbol": "eval"}],
            source="boundary-inspector", category="dynamic-execution",
            precondition="Attacker controls user_input", impact="",
        )
        result = FindingGate().apply([finding], parsed)
        self.assertEqual([], result.accepted)
        self.assertEqual(1, result.checks["severity"]["rejected"])

        finding.impact = "Arbitrary code executes in the service process"
        result = FindingGate().apply([finding], parsed)
        self.assertEqual(1, len(result.accepted))
        self.assertEqual("strong", result.accepted[0].evidence_strength)

    def test_verified_fix_is_read_only_until_explicit_approval(self):
        github = FakeGitHub()
        fixer = VerifiedPatchFixer(FakeFixModel(), FakeVerifier())
        report = {"findings": [{
            "path": "app.py", "rule_id": "SEC-DANGEROUS", "gate": {"passed": True},
        }]}
        proposal = fixer.prepare_fix(github, "org/repo", 7, report)
        self.assertEqual("awaiting-approval", proposal["status"])
        self.assertTrue(proposal["approval_required"])
        self.assertEqual([], github.commits)
        self.assertEqual([], github.drafts)

        published = fixer.publish_fix(github, "org/repo", 7, proposal)
        self.assertEqual("verified-draft", published["status"])
        self.assertFalse(published["approval_required"])
        self.assertTrue(published["approved"])
        self.assertEqual(1, len(github.commits))
        self.assertEqual(1, len(github.drafts))

    def test_fix_approval_rejects_stale_pr_head(self):
        github = FakeGitHub()
        fixer = VerifiedPatchFixer(FakeFixModel(), FakeVerifier())
        proposal = fixer.prepare_fix(github, "org/repo", 7, {
            "findings": [{"path": "app.py", "gate": {"passed": True}}],
        })
        github.head_sha = "new-head"
        with self.assertRaisesRegex(ValueError, "head changed"):
            fixer.publish_fix(github, "org/repo", 7, proposal)
        self.assertEqual([], github.commits)


if __name__ == "__main__":
    unittest.main()
