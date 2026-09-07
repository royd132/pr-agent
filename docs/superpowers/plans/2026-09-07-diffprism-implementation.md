# DiffPrism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repackage EvoAgent as DiffPrism with a stage-oriented four-agent review protocol, structured evidence reports, a usable review workspace, and an honest reproducible benchmark built from the supplied 100-case synthetic dataset.

**Architecture:** Keep the existing Python HTTP service, runtime, queue, stores, GitHub integration, and static frontend. Add compatibility layers for the new brand, extend the report contract with defaulted fields, replace role identifiers inside the existing orchestration topology, and expose presentation-ready benchmark metadata without changing stored schemas or the `/v1/*` route family.

**Tech Stack:** Python 3.11 standard library, unittest, HTML5, dependency-free browser JavaScript, CSS, SQLite/PostgreSQL, Redis Streams, OpenTelemetry.

**Spec:** `docs/superpowers/specs/2026-09-06-diffprism-redesign.md`

## Global Constraints

- Preserve SQLite/PostgreSQL stores, Redis/in-process queues, GitHub authentication, runtime, memory, checkpoint storage, RBAC, automatic-fix flow, and all existing `/v1/*` routes.
- Keep the `evoagent` Python package and `python -m evoagent` working; add DiffPrism as the preferred public entry point.
- Prefer `DIFFPRISM_*` environment variables and fall back to matching `EVOAGENT_*` variables.
- Keep the frontend dependency-free and escape all untrusted report content.
- Label the supplied dataset `Synthetic Fault Benchmark v1`; never describe it as real public PR data.
- Do not add or choose a license without explicit ownership and licensing confirmation.
- Do not commit secrets, databases, caches, generated run outputs, or credentials.

---

## File Structure

**Create**

- `pyproject.toml`: install metadata and `diffprism` console command.
- `diffprism/__init__.py`: public package version and compatibility description.
- `diffprism/__main__.py`: invoke the existing HTTP server.
- `evoagent/presentation.py`: brand constants, role labels, Review Pack labels, benchmark arm labels, and presentation-only adapters.
- `evaluation_data/pr_diff_100.jsonl`: byte-for-byte copy of the supplied synthetic dataset.
- `tests/test_presentation.py`: presentation mappings and benchmark summary tests.
- `tests/test_report.py`: new report-contract and Markdown-rendering tests.
- `tests/test_web_ui.py`: static UI structure, safe-renderer, and branding checks.
- `docs/architecture.md`: maintained architecture overview.
- `docs/agent-protocol.md`: role inputs, outputs, and decision states.
- `docs/evaluation.md`: dataset facts, metrics, commands, and claim limits.
- `examples/sample-review.json`: deterministic structured report example.
- `examples/sample-report.md`: Markdown rendering of the same example.
- `CHANGELOG.md`: DiffPrism 0.1.0 changes.
- `SECURITY.md`: supported reporting and deployment boundaries.

**Modify**

- `evoagent/__init__.py`: legacy package description and aligned version.
- `evoagent/api.py`: public brand output and `/api/benchmark` presentation endpoint.
- `evoagent/agentic_core.py`: new role protocol, role IDs, prompts, evidence decisions, change map, and verdict summary.
- `evoagent/config.py`: new environment prefix with legacy fallback.
- `evoagent/github.py`: DiffPrism User-Agent and generated branch/PR copy.
- `evoagent/models.py`: defaulted report and finding fields.
- `evoagent/modes.py`: DiffPrism role taxonomy.
- `evoagent/report.py`: evidence-first Markdown report.
- `evoagent/service.py`: merge agent summary fields into `ReviewReport`.
- `evoagent/evaluation_v2.py`: derived benchmark metrics and public metadata.
- `.env.example`: preferred DiffPrism variables plus compatibility note.
- `docker-compose.yml`: public service/container labels and preferred variables.
- `README.md`: complete DiffPrism product narrative and reproducible demo.
- `web/index.html`: new navigation and structured workspace markup.
- `web/app.js`: safe structured report, Review Pack, and Benchmark Lab renderers.
- `web/app.css`: graphite/prism design system and responsive workspace.
- `web/login.css`: aligned login branding.
- `tests/agentic_fake.py`: deterministic responses for new roles and output fields.
- `tests/test_config.py`: prefix precedence and fallback.
- `tests/test_service.py`: end-to-end DiffPrism role/report contract.
- `tests/test_lead_worker_collaboration.py`: new protocol and role behavior.
- `tests/test_evaluation_harness.py`: supplied dataset fingerprint and public metrics.
- Other tests containing exact legacy public names or role IDs: update only the affected assertions.

---

### Task 1: Package and brand compatibility foundation

**Files:**

- Create: `pyproject.toml`
- Create: `diffprism/__init__.py`
- Create: `diffprism/__main__.py`
- Create: `evoagent/presentation.py`
- Modify: `evoagent/__init__.py`
- Modify: `evoagent/api.py:572-580`
- Modify: `evoagent/github.py:28-30`
- Test: `tests/test_presentation.py`

**Interfaces:**

- Produces: `PRODUCT_NAME`, `PRODUCT_VERSION`, `PRODUCT_TAGLINE`, `ROLE_LABELS`, `REVIEW_PACK_LABELS`, and `BENCHMARK_ARM_LABELS` constants in `evoagent.presentation`.
- Produces: `diffprism.__version__ == "0.1.0"` and `diffprism.__main__.main() -> None`.
- Consumes: existing `evoagent.api.run() -> None`.

- [ ] **Step 1: Write failing package and presentation tests**

```python
import pathlib
import unittest

import diffprism
from diffprism.__main__ import main
from evoagent.presentation import (
    BENCHMARK_ARM_LABELS,
    PRODUCT_NAME,
    REVIEW_PACK_LABELS,
    ROLE_LABELS,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PresentationTests(unittest.TestCase):
    def test_public_brand_and_entrypoint(self):
        self.assertEqual("DiffPrism", PRODUCT_NAME)
        self.assertEqual("0.1.0", diffprism.__version__)
        self.assertTrue(callable(main))

    def test_public_labels_are_complete(self):
        self.assertEqual("Prism Lead", ROLE_LABELS["prism-lead"])
        self.assertEqual("Scope Mapper", ROLE_LABELS["scope-mapper"])
        self.assertEqual("Failure Hunter", ROLE_LABELS["failure-hunter"])
        self.assertEqual("Evidence Examiner", ROLE_LABELS["evidence-examiner"])
        self.assertEqual("Security Boundaries", REVIEW_PACK_LABELS["security-review"])
        self.assertEqual("Full DiffPrism", BENCHMARK_ARM_LABELS["full-agentic"])
```

- [ ] **Step 2: Run the new test and confirm import failure**

Run: `python -m unittest tests.test_presentation -v`

Expected: FAIL because `diffprism` and `evoagent.presentation` do not exist.

- [ ] **Step 3: Add the minimal package and constants**

```python
# diffprism/__main__.py
from evoagent.api import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
```

```python
# evoagent/presentation.py
PRODUCT_NAME = "DiffPrism"
PRODUCT_VERSION = "0.1.0"
PRODUCT_TAGLINE = "Split the diff. Verify the risk."

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
```

Add `pyproject.toml` with project name `diffprism`, version `0.1.0`, Python floor `>=3.11`, dependencies `psycopg[binary]>=3.1,<4`, `redis>=5,<7`, `PyJWT[crypto]>=2.8,<3`, `opentelemetry-sdk>=1.24,<2`, `opentelemetry-exporter-otlp-proto-http>=1.24,<2`, and `PyYAML>=5.4,<7`, package discovery for both packages, and console script `diffprism = "diffprism.__main__:main"`. Import `PRODUCT_NAME` in `evoagent.api` and `evoagent.github` for terminal output and both GitHub User-Agent headers.

- [ ] **Step 4: Run focused package tests**

Run: `python -m unittest tests.test_presentation -v`

Expected: PASS.

- [ ] **Step 5: Verify both module entry points resolve without starting a server**

Run: `python -c "from diffprism.__main__ import main as a; from evoagent.api import run as b; assert a.__module__ == 'diffprism.__main__' and callable(b)"`

Expected: exit code 0.

- [ ] **Step 6: Commit the packaging foundation**

```text
git add pyproject.toml diffprism evoagent/presentation.py evoagent/__init__.py evoagent/api.py evoagent/github.py tests/test_presentation.py
git commit -m "feat: establish DiffPrism product identity"
```

---

### Task 2: Environment-prefix compatibility

**Files:**

- Modify: `evoagent/config.py:1-66,231-329`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Test: `tests/test_config.py`

**Interfaces:**

- Produces: `_setting(name: str, default: str = "") -> str`, resolving `DIFFPRISM_<name>` first and `EVOAGENT_<name>` second.
- Consumes: all existing `Settings.from_env()` conversions and validation.

- [ ] **Step 1: Add failing precedence and fallback tests**

```python
from evoagent.config import Settings


def test_diffprism_environment_takes_precedence(self):
    values = {
        "DIFFPRISM_PORT": "9001",
        "EVOAGENT_PORT": "9002",
        "DIFFPRISM_LLM_PROVIDER": "local",
    }
    with patch.dict(os.environ, values, clear=True):
        self.assertEqual(9001, Settings.from_env().port)


def test_legacy_environment_remains_supported(self):
    with patch.dict(os.environ, {"EVOAGENT_PORT": "9003"}, clear=True):
        self.assertEqual(9003, Settings.from_env().port)


def test_empty_preferred_value_falls_back_to_legacy(self):
    values = {"DIFFPRISM_PORT": "", "EVOAGENT_PORT": "9004"}
    with patch.dict(os.environ, values, clear=True):
        self.assertEqual(9004, Settings.from_env().port)
```

- [ ] **Step 2: Run the three tests and confirm the new prefix is ignored**

Run: `python -m unittest tests.test_config.DotenvTests.test_diffprism_environment_takes_precedence tests.test_config.DotenvTests.test_legacy_environment_remains_supported tests.test_config.DotenvTests.test_empty_preferred_value_falls_back_to_legacy -v`

Expected: first test FAIL with port `9002`; second test PASS; third test PASS before implementation because the legacy parser already reads `EVOAGENT_PORT`.

- [ ] **Step 3: Implement one prefix resolver and reuse existing parsers**

```python
def _setting(name: str, default: str = "") -> str:
    preferred = "DIFFPRISM_%s" % name
    legacy = "EVOAGENT_%s" % name
    preferred_value = os.getenv(preferred)
    if preferred_value not in (None, ""):
        return preferred_value
    return os.getenv(legacy, default)
```

Update `_bool`, `_int`, `_non_negative_int`, and every direct environment read in `Settings.from_env()` to pass suffixes through `_setting`. Rewrite `.env.example` with `DIFFPRISM_*` keys and one compatibility note. In each Compose service, declare the preferred `DIFFPRISM_*` key with an empty shell default and retain its matching `EVOAGENT_*` key with the current default; `_setting` then gives a non-empty preferred value precedence while preserving existing Compose deployments.

- [ ] **Step 4: Run configuration tests**

Run: `python -m unittest tests.test_config tests.test_advanced.AdvancedTests.test_deepseek_and_free_openrouter_provider_presets -v`

Expected: PASS.

- [ ] **Step 5: Commit environment compatibility**

```text
git add evoagent/config.py .env.example docker-compose.yml tests/test_config.py tests/test_advanced.py
git commit -m "feat: prefer DiffPrism environment settings"
```

---

### Task 3: Evidence-first report contract

**Files:**

- Modify: `evoagent/models.py:38-91`
- Modify: `evoagent/report.py`
- Create: `tests/test_report.py`
- Test: `tests/test_service.py`

**Interfaces:**

- Produces: `Finding.trigger`, `Finding.impact`, `Finding.verification`, and `Finding.examiner_reason` with backward-compatible defaults.
- Produces: `ReviewReport.change_map` and `ReviewReport.verdict` with default factories.
- Produces: `to_markdown(report: Dict[str, Any]) -> str` with verdict, change map, verified findings, required actions, review trail, and unknowns.

- [ ] **Step 1: Write failing model and Markdown tests**

```python
from evoagent.models import Finding, ReviewReport, Severity
from evoagent.report import to_markdown


def test_report_defaults_preserve_old_callers(self):
    finding = Finding("R", Severity.HIGH, "Title", "Explanation", "a.py", 3,
                      "danger()", "replace it", "add regression", 0.9)
    report = ReviewReport("org/repo", 7, "summary", "high", [finding])
    payload = report.to_dict()
    self.assertEqual({}, payload["change_map"])
    self.assertEqual({}, payload["verdict"])
    self.assertEqual("", payload["findings"][0]["trigger"])


def test_markdown_leads_with_verdict_and_change_map(self):
    markdown = to_markdown({
        "repository": "org/repo", "pull_request": 7, "risk": "high",
        "summary": "summary", "findings": [{
            "rule_id": "AUTH-EXPIRY", "severity": "high",
            "title": "Expiry is not checked", "path": "auth.py", "line": 8,
            "evidence": "return token.user", "explanation": "Expired tokens pass",
            "fix": "Validate exp before returning", "test": "Add an expired-token test",
            "trigger": "An expired token reaches this return",
            "impact": "A stale session remains authorized",
        }],
        "change_map": {"intent": "tighten auth", "surfaces": ["auth"],
                       "affected_files": ["auth.py"], "test_gaps": ["expiry"],
                       "unknowns": ["deployment config"]},
        "verdict": {"decision": "warn", "reason": "test gap",
                    "required_actions": ["add expiry test"],
                    "verified_findings": 0, "rejected_findings": 1},
    })
    self.assertLess(markdown.index("## Merge verdict"), markdown.index("## Change map"))
    self.assertIn("Suggested verification", markdown)
    self.assertIn("deployment config", markdown)
```

- [ ] **Step 2: Run the new report tests and confirm missing fields/sections**

Run: `python -m unittest tests.test_report -v`

Expected: FAIL on missing dataclass fields and Markdown headings.

- [ ] **Step 3: Add defaulted fields and rewrite Markdown ordering**

```python
@dataclass
class Finding:
    # existing required fields stay in the same order
    confidence: float = 0.8
    evidence_refs: List[Dict[str, Any]] = field(default_factory=list)
    call_chain: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "unknown"
    gate: Dict[str, Any] = field(default_factory=dict)
    cwe: Optional[str] = None
    trigger: str = ""
    impact: str = ""
    verification: str = "verified"
    examiner_reason: str = ""
```

Append `change_map: Dict[str, Any] = field(default_factory=dict)` and `verdict: Dict[str, Any] = field(default_factory=dict)` to `ReviewReport`, include them in `to_dict`, and rebuild `to_markdown` in the specified order. Render absent legacy fields as `Not established` and label tests `Suggested verification` unless execution evidence explicitly says a check ran.

- [ ] **Step 4: Run report and service regression tests**

Run: `python -m unittest tests.test_report tests.test_service -v`

Expected: PASS.

- [ ] **Step 5: Commit the report contract**

```text
git add evoagent/models.py evoagent/report.py tests/test_report.py tests/test_service.py
git commit -m "feat: add evidence-first review reports"
```

---

### Task 4: Replace the agent protocol without replacing the runtime

**Files:**

- Modify: `evoagent/agentic_core.py:1-93,264-315,483-738,818-1065,1100-1245`
- Modify: `evoagent/modes.py:49-67`
- Modify: `evoagent/config.py:311-315`
- Modify: `evoagent/service.py` report construction path
- Modify: `tests/agentic_fake.py`
- Modify: `tests/test_lead_worker_collaboration.py`
- Modify: `tests/test_service.py`
- Modify: tests containing exact old role IDs

**Interfaces:**

- Produces role IDs `prism-lead`, `scope-mapper`, `failure-hunter`, `evidence-examiner`.
- Produces checkpoint protocol `prism-review-v1`.
- Produces collaboration keys `change_map`, `examiner_decisions`, and `verdict` while retaining existing aggregate counts needed by evaluation code.
- Consumes the existing `BoundedRole`, `RepositoryToolSuite`, `ExecutionLedger`, `FindingGate`, Skill provider, and checkpoint persistence interfaces unchanged.

- [ ] **Step 1: Change fake-client expectations first**

Update the deterministic fake so delegation returns both new workers, Scope Mapper returns a `change_map` plus findings, Failure Hunter returns trigger/impact fields, and Evidence Examiner returns string decisions:

```python
{"assignment_id": "scope-1", "worker": "scope-mapper",
 "objective": "Map changed contracts and tests", "files": ["a.py"],
 "skills": [], "risk_domains": ["contract"],
 "required_evidence": ["changed line"]}
```

```python
{"finding_index": 0, "decision": "verified",
 "reason": "The changed line and concrete trigger support the claim.",
 "confidence_adjustment": 0.0, "supporting_evidence_ids": []}
```

- [ ] **Step 2: Update role collaboration tests and confirm failure**

Assert:

```python
self.assertEqual(
    ["prism-lead", "scope-mapper", "failure-hunter", "evidence-examiner"],
    summary["collaboration"]["roles"],
)
self.assertEqual("prism-review-v1", checkpoint["state"]["protocol"])
self.assertIn("change_map", summary["collaboration"])
self.assertIn("verdict", summary["collaboration"])
```

Run: `python -m unittest tests.test_lead_worker_collaboration tests.test_service -v`

Expected: FAIL with old role IDs and protocol.

- [ ] **Step 3: Replace prompts, IDs, permissions, and normalization**

Rename prompt constants to `PRISM_LEAD_PROMPT`, `SCOPE_MAPPER_PROMPT`, `FAILURE_HUNTER_PROMPT`, and `EVIDENCE_EXAMINER_PROMPT`. Keep lead tool access bounded; grant Scope Mapper repository/search/test-location tools; grant Failure Hunter and Evidence Examiner the current factual/scanner/check tools. Normalize examiner decisions to the closed set `verified`, `weak`, `rejected`, `duplicate` and publish only `verified` candidates.

Update the default enabled-agent value to:

```python
("prism-lead", "scope-mapper", "failure-hunter", "evidence-examiner")
```

Change session creation to `protocol: "prism-review-v1"`. Map old completed report data only at render time; discard incompatible unfinished checkpoints through the existing protocol mismatch path.

- [ ] **Step 4: Build change map and verdict from bounded outputs**

Add private normalizers with stable shapes:

```python
def _normalize_change_map(value, changed_files):
    value = value if isinstance(value, dict) else {}
    return {
        "intent": str(value.get("intent") or "Not established")[:1000],
        "surfaces": [str(x)[:100] for x in value.get("surfaces", [])][:20],
        "affected_files": [x for x in value.get("affected_files", []) if x in changed_files][:100],
        "test_gaps": [str(x)[:500] for x in value.get("test_gaps", [])][:20],
        "unknowns": [str(x)[:500] for x in value.get("unknowns", [])][:20],
    }
```

```python
def _build_verdict(risk_level, accepted, rejected, final_decision):
    decision = "block" if any(item.severity in {Severity.CRITICAL, Severity.HIGH} for item in accepted) else (
        "warn" if accepted else "pass"
    )
    return {
        "decision": decision,
        "reason": str(final_decision.get("resolution_summary") or "")[:2000],
        "required_actions": [item.fix for item in accepted][:20],
        "verified_findings": len(accepted),
        "rejected_findings": len(rejected),
        "risk_level": risk_level,
    }
```

Store both values in the agent summary and pass them into `ReviewReport` from the existing service report-construction path.

- [ ] **Step 5: Run focused agent, service, memory, and evaluation tests**

Run: `python -m unittest tests.test_lead_worker_collaboration tests.test_service tests.test_runtime_memory_context tests.test_agentic_evaluation -v`

Expected: PASS.

- [ ] **Step 6: Commit the new protocol**

```text
git add evoagent/agentic_core.py evoagent/modes.py evoagent/config.py evoagent/service.py tests/agentic_fake.py tests/test_lead_worker_collaboration.py tests/test_service.py tests/test_runtime_memory_context.py tests/test_agentic_evaluation.py
git commit -m "feat: introduce the DiffPrism review protocol"
```

---

### Task 5: Integrate and expose the synthetic benchmark honestly

**Files:**

- Create: `evaluation_data/pr_diff_100.jsonl`
- Modify: `evoagent/presentation.py`
- Modify: `evoagent/evaluation_v2.py:520-810`
- Modify: `evoagent/api.py:210-229`
- Modify: `tests/test_evaluation_harness.py`
- Modify: `tests/test_presentation.py`

**Interfaces:**

- Produces: `synthetic_benchmark_status(path: str) -> Dict[str, Any]`.
- Produces: `public_benchmark_summary(report: Dict[str, Any]) -> Dict[str, Any]`.
- Produces: `GET /api/benchmark` with dataset facts, public arm labels, recent run summaries, and production-readiness boundary.
- Extends evaluation metrics with `p95_review_latency_ms` and `cost_per_verified_finding_usd`.

- [ ] **Step 1: Copy the supplied dataset byte-for-byte and verify its digest**

Run:

```powershell
New-Item -ItemType Directory -Force evaluation_data | Out-Null
Copy-Item -LiteralPath 'C:\Users\HPC\Downloads\pr_diff_100.jsonl' -Destination 'evaluation_data\pr_diff_100.jsonl'
(Get-FileHash -Algorithm SHA256 'evaluation_data\pr_diff_100.jsonl').Hash
```

Expected digest: `65F301C0C75125676D5DA482FFA00828399B7041D4DB378BC52E48BAAB36B1B6`.

- [ ] **Step 2: Add failing dataset and metric tests**

```python
def test_committed_synthetic_benchmark_has_expected_identity(self):
    path = os.path.join(os.path.dirname(__file__), "..", "evaluation_data", "pr_diff_100.jsonl")
    cases = load_jsonl(path)
    self.assertEqual(100, len(cases))
    self.assertEqual(40, sum(bool(case["expected_findings"]) for case in cases))
    self.assertEqual({"validation", "holdout"}, {case["split"] for case in cases})
    self.assertEqual({"offline-fixture"}, {case["source"]["kind"] for case in cases})
```

```python
def test_public_benchmark_status_does_not_claim_real_pr_readiness(self):
    status = synthetic_benchmark_status("evaluation_data/pr_diff_100.jsonl")
    self.assertEqual("Synthetic Fault Benchmark v1", status["name"])
    self.assertFalse(status["production_ready"])
    self.assertEqual("no-train-split-and-not-public-pr-data", status["limitation"])
```

Run: `python -m unittest tests.test_evaluation_harness tests.test_presentation -v`

Expected: FAIL because the status adapter and derived metrics are absent.

- [ ] **Step 3: Implement benchmark status and public summaries**

Use `load_jsonl` and `dataset_fingerprint`; count cases, positive/clean rows, split repositories, severities, and rules. Return the exact limitation string tested above. Add arm `display_name` values without renaming internal arm keys.

Track per-case latency values in evaluation totals. Compute p95 from sorted case latencies using nearest-rank indexing. Compute cost per verified finding as total cost divided by accepted comments, returning `0.0` when no finding is accepted.

- [ ] **Step 4: Expose the presentation endpoint**

Add `GET /api/benchmark` after authentication. It returns:

```json
{
  "dataset": {"name": "Synthetic Fault Benchmark v1", "production_ready": false},
  "arms": {"single-llm": "Solo Review", "multi-llm-no-critic": "Prism without Examiner", "full-agentic": "Full DiffPrism"},
  "runs": []
}
```

Populate `runs` from the existing evolution-run store and the presentation adapter; do not expose holdout case rows.

- [ ] **Step 5: Run evaluation and API tests**

Run: `python -m unittest tests.test_evaluation_harness tests.test_evaluation_experiments tests.test_agentic_evaluation tests.test_advanced -v`

Expected: PASS.

- [ ] **Step 6: Commit benchmark integration**

```text
git add evaluation_data/pr_diff_100.jsonl evoagent/presentation.py evoagent/evaluation_v2.py evoagent/api.py tests/test_evaluation_harness.py tests/test_presentation.py tests/test_evaluation_experiments.py tests/test_agentic_evaluation.py tests/test_advanced.py
git commit -m "feat: add the DiffPrism synthetic benchmark"
```

---

### Task 6: Present Skills as Review Packs

**Files:**

- Modify: `evoagent/presentation.py`
- Modify: `evoagent/service.py` `list_skills`
- Modify: `web/index.html:210-230`
- Modify: `web/app.js:310-329`
- Test: `tests/test_presentation.py`
- Test: `tests/test_skill_evolution.py`

**Interfaces:**

- Produces: `present_review_pack(skill: Dict[str, Any]) -> Dict[str, Any]`.
- Extends each `/api/skills` item with `display_name`, `scope`, and `status_label`; existing keys remain unchanged.

- [ ] **Step 1: Add a failing Review Pack adapter test**

```python
def test_review_pack_adapter_keeps_machine_identity(self):
    presented = present_review_pack({
        "name": "security-review", "description": "security", "version": 2,
        "source": "builtin", "sandboxed": True, "allowed_tools": ["read_file"],
    })
    self.assertEqual("security-review", presented["name"])
    self.assertEqual("Security Boundaries", presented["display_name"])
    self.assertEqual("Sandboxed", presented["status_label"])
```

- [ ] **Step 2: Run the adapter test and confirm failure**

Run: `python -m unittest tests.test_presentation.PresentationTests.test_review_pack_adapter_keeps_machine_identity -v`

Expected: FAIL because `present_review_pack` is absent.

- [ ] **Step 3: Implement the adapter and apply it at the API boundary**

```python
def present_review_pack(skill):
    value = dict(skill)
    value["display_name"] = REVIEW_PACK_LABELS.get(value.get("name"), value.get("name", "Unknown pack"))
    value["status_label"] = "Sandboxed" if value.get("sandboxed") else "Active"
    value["scope"] = str(value.get("description") or "No scope description available")
    return value
```

Apply the adapter to `ReviewService.list_skills` results. Update the cards to show public label, machine ID, version, source, sandbox state, allowed-tool count, and scope.

- [ ] **Step 4: Run Skill and presentation tests**

Run: `python -m unittest tests.test_presentation tests.test_skill_evolution -v`

Expected: PASS.

- [ ] **Step 5: Commit Review Pack presentation**

```text
git add evoagent/presentation.py evoagent/service.py web/index.html web/app.js tests/test_presentation.py tests/test_skill_evolution.py
git commit -m "feat: present skills as DiffPrism review packs"
```

---

### Task 7: Build the structured Review Workspace and Benchmark Lab

**Files:**

- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/app.css`
- Modify: `web/login.css`
- Create: `tests/test_web_ui.py`

**Interfaces:**

- Produces: `renderReviewWorkspace(task: object) -> void`.
- Produces: `findingCard(finding: object, index: number) -> string`, with every dynamic value passed through `escapeHtml`.
- Produces: `renderBenchmark(data: object) -> void`.
- Consumes: existing `/api/dashboard`, `/api/tasks`, `/v1/tasks/{id}`, `/api/skills`, `/api/benchmark`, `/api/failures`, and `/v1/evolution/*` responses.

- [ ] **Step 1: Write failing static UI contract tests**

```python
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class WebUiTests(unittest.TestCase):
    def test_diffprism_navigation_and_workspace_exist(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("DiffPrism", html)
        self.assertIn('data-view="inbox"', html)
        self.assertIn('id="review-workspace"', html)
        self.assertIn('id="benchmark-summary"', html)

    def test_structured_renderer_replaces_raw_task_json(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderReviewWorkspace", script)
        self.assertIn("function findingCard", script)
        self.assertNotIn('$("#task-report").textContent = formatJson(task)', script)
```

- [ ] **Step 2: Run UI tests and confirm the old structure fails**

Run: `python -m unittest tests.test_web_ui -v`

Expected: FAIL on missing DiffPrism workspace and renderer functions.

- [ ] **Step 3: Replace navigation and page markup**

Build five views: `inbox`, `review`, `workspace`, `packs`, and `benchmark`. Keep existing forms and element IDs required by behavior, but move the feedback form into the workspace. Add a collapsed `<details id="diagnostic-json">` for escaped debug JSON.

Replace the orbit hero with an inline SVG prism mark. Do not add image or icon dependencies.

- [ ] **Step 4: Implement safe structured renderers**

Use helper functions that escape each scalar and map only arrays:

```javascript
function findingCard(finding, index) {
  const severity = String(finding?.severity || "medium").toLowerCase();
  return `<article class="finding-card severity-${escapeHtml(severity)}">
    <header><span>#${index + 1}</span><strong>${escapeHtml(finding?.title || "Untitled finding")}</strong></header>
    <p class="finding-location">${escapeHtml(finding?.path || "unknown")}:${escapeHtml(finding?.line || "?")}</p>
    <dl>
      <dt>Trigger</dt><dd>${escapeHtml(finding?.trigger || "Not established")}</dd>
      <dt>Evidence</dt><dd><code>${escapeHtml(finding?.evidence || "Not established")}</code></dd>
      <dt>Impact</dt><dd>${escapeHtml(finding?.impact || finding?.explanation || "Not established")}</dd>
      <dt>Suggested fix</dt><dd>${escapeHtml(finding?.fix || "Not provided")}</dd>
      <dt>Suggested verification</dt><dd>${escapeHtml(finding?.test || "Not provided")}</dd>
    </dl>
  </article>`;
}
```

`renderReviewWorkspace` renders verdict, change map, cards, agent trail, execution facts, feedback, and diagnostic JSON. `renderBenchmark` renders dataset identity, limitations, arm labels, metric deltas, and promotion decisions. Preserve authentication and existing request behavior.

- [ ] **Step 5: Replace CSS with the DiffPrism visual system**

Use CSS custom properties for graphite surfaces, white text, muted slate, and violet/cyan/amber accents. Add responsive grid rules at existing breakpoints, visible focus states, reduced-motion handling, severity colors, verdict badges, and scroll-safe code evidence. Avoid excessive glow and animation.

- [ ] **Step 6: Run static UI and Python regressions**

Run: `python -m unittest tests.test_web_ui tests.test_service tests.test_production_features -v`

Expected: PASS.

- [ ] **Step 7: Commit the web workspace**

```text
git add web/index.html web/app.js web/app.css web/login.css tests/test_web_ui.py
git commit -m "feat: build the DiffPrism review workspace"
```

---

### Task 8: Documentation and deterministic examples

**Files:**

- Modify: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/agent-protocol.md`
- Create: `docs/evaluation.md`
- Create: `examples/sample-review.json`
- Create: `examples/sample-report.md`
- Create: `CHANGELOG.md`
- Create: `SECURITY.md`
- Test: `tests/test_presentation.py`

**Interfaces:**

- Consumes the final role names, report schema, benchmark status, commands, and compatibility rules from Tasks 1-7.
- Produces a reproducible onboarding path and checked-in sample artifacts containing no fabricated runtime claims.

- [ ] **Step 1: Add failing documentation-contract checks**

```python
def test_documentation_names_limits_and_references(self):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    evaluation = (ROOT / "docs" / "evaluation.md").read_text(encoding="utf-8")
    self.assertIn("Split the diff. Verify the risk.", readme)
    self.assertIn("Synthetic Fault Benchmark v1", evaluation)
    self.assertIn("not real public PR data", evaluation)
    self.assertIn("PR-Agent", readme)
    self.assertIn("Semgrep", readme)
    self.assertNotIn("# EvoAgent PR Reviewer", readme)
```

- [ ] **Step 2: Run the documentation test and confirm missing files/copy**

Run: `python -m unittest tests.test_presentation.PresentationTests.test_documentation_names_limits_and_references -v`

Expected: FAIL because the new documentation files and copy are absent.

- [ ] **Step 3: Write README and supporting documentation**

README order:

1. Product promise and one-sentence scope.
2. Sixty-second local demo.
3. Four-stage review flow.
4. Evidence-backed report example.
5. Synthetic benchmark command and limitations.
6. Architecture and deployment.
7. Review Pack authoring.
8. Security boundaries and known limitations.
9. Design references and direct dependencies.

Use the checked-in dataset digest and measured counts. Do not insert a benchmark score until a command has generated it. Generate example JSON deterministically from `ReviewReport.to_dict()` and generate example Markdown with `to_markdown`; mark both as examples rather than captured production runs.

- [ ] **Step 4: Run documentation and report tests**

Run: `python -m unittest tests.test_presentation tests.test_report -v`

Expected: PASS.

- [ ] **Step 5: Commit documentation and examples**

```text
git add README.md docs/architecture.md docs/agent-protocol.md docs/evaluation.md examples CHANGELOG.md SECURITY.md tests/test_presentation.py
git commit -m "docs: document the DiffPrism workflow"
```

---

### Task 9: Full verification, browser QA, and delivery

**Files:**

- Modify only files required to fix failures found by the checks below.

**Interfaces:**

- Consumes every deliverable from Tasks 1-8.
- Produces a verified local `main` commit series pushed to the configured GitHub repository.

- [ ] **Step 1: Run the complete unit-test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with zero failures and zero errors.

- [ ] **Step 2: Run package and dataset smoke checks**

Run:

```powershell
python -m pip install -e .
python -c "import diffprism, evoagent; assert diffprism.__version__ == '0.1.0'"
python scripts/run_accuracy_experiment.py
python scripts/run_real_pr_benchmark.py evaluation_data/pr_diff_100.jsonl --minimum 100
```

Expected: editable installation and imports succeed; controlled accuracy completes; `run_real_pr_benchmark.py` exits nonzero with its readiness-gate explanation because this repository-disjoint fixture has no train split and is not real PR data. Record that expected outcome in `docs/evaluation.md`; the dedicated synthetic benchmark status and tests must still pass.

- [ ] **Step 3: Start the service for browser QA**

Seed one completed review with the existing deterministic test client, then run the service in a background terminal against the same disposable SQLite database:

```powershell
$env:DIFFPRISM_AUTH_REQUIRED='false'
$env:DIFFPRISM_LLM_PROVIDER='local'
$env:DIFFPRISM_DB_PATH='diffprism-ui-preview.db'
python -c "import sys; sys.path.insert(0, 'tests'); from agentic_fake import enable_agentic_service; from evoagent.config import Settings; from evoagent.service import ReviewService; service = enable_agentic_service(ReviewService(Settings.from_env())); result = service.create_review('demo/diffprism', 'diff --git a/auth.py b/auth.py`n--- a/auth.py`n+++ b/auth.py`n@@ -1 +1,2 @@`n def authorize(token):`n+    # TODO finish validation', 42); print(result['task_id']); service.queue.close()"
python -m diffprism
```

Verify `/health`, PR Inbox, New Review, Review Workspace with the seeded completed task, Review Packs, and Benchmark Lab at desktop width and a narrow mobile width. Confirm there is no horizontal page overflow, all focusable controls have visible focus, raw JSON is collapsed, and all five views remain usable with reduced motion. Stop the service, then remove only the generated `diffprism-ui-preview.db` after confirming its resolved path is inside the workspace.

- [ ] **Step 4: Run repository hygiene checks**

Run:

```powershell
git diff --check
git status --short
rg -n "EvoAgent|lead-workers-v3|correctness-reliability|Security Agent|Critic worker" README.md web diffprism evoagent tests docs examples .env.example docker-compose.yml
Get-ChildItem -Recurse -Force -File | Where-Object { $_.Name -match '^(\.env|.*\.db|.*\.sqlite|.*\.pem|.*\.key)$' }
```

Expected: no whitespace errors; only documented compatibility references to EvoAgent remain; no obsolete role/protocol names remain in active behavior; no sensitive local artifacts are staged.

- [ ] **Step 5: Commit any verification-only corrections**

If Step 1-4 required corrections, commit only those reviewed changes:

```text
git add -u
git commit -m "fix: complete DiffPrism verification"
```

If no corrections were needed, do not create an empty commit.

- [ ] **Step 6: Verify final local and remote-ready state**

Run:

```powershell
git status --short --branch
git log --oneline --decorate -10
git remote -v
```

Expected: clean `main`, ahead of `origin/main` only by the reviewed DiffPrism commits, with `origin` pointing to `https://github.com/royd132/pr-agent.git`.

- [ ] **Step 7: Push and verify the remote commit**

Run:

```powershell
git -c http.curloptResolve=github.com:443:140.82.112.4 push origin main
$local = git rev-parse HEAD
$remote = (git -c http.curloptResolve=github.com:443:140.82.112.4 ls-remote origin refs/heads/main).Split("`t")[0]
if ($local -ne $remote) { throw 'local and remote commits differ' }
```

Expected: push succeeds and local/remote hashes are identical.

The repository remains at `royd132/pr-agent` during this plan. Renaming it to `royd132/diffprism` is a separate GitHub setting change and requires explicit authorization at action time.
