# DiffPrism product redesign

Date: 2026-09-06

## 1. Objective

Repackage EvoAgent as **DiffPrism**, an evidence-driven pull-request review system, while preserving the existing service architecture. The redesign must be materially visible in the product, agent protocol, review result, evaluation workflow, and documentation. It must not replace the persistence, queue, GitHub integration, runtime, or authorization subsystems.

Product promise:

> Split the diff. Verify the risk.

DiffPrism turns one code change into a change map, adversarial failure analysis, independently verified findings, and a merge verdict. It favors supported findings over comment volume and exposes what the system knows, rejects, and cannot establish.

## 2. Reference patterns

The design borrows patterns, not source code, from the following projects:

- PR-Agent: explicit PR-oriented actions and concise developer workflow.
- Semgrep: review packs, triage, and emphasis on findings introduced by the current change.
- SWE-agent: inspectable trajectories and tool/action evidence.
- Promptfoo: repeatable evaluation cases, assertions, comparison arms, latency, and cost measurements.
- Langfuse and Phoenix: experiment-run comparison and trace-oriented result presentation.

The README will identify these as design references. Existing third-party dependencies will remain separately documented. No license or authorship claim will be invented.

## 3. Scope boundaries

### In scope

- Public rename and packaging as DiffPrism.
- New public CLI/entry-point alias while keeping the legacy module entry point.
- Replacement of the current domain-role protocol with a stage-oriented four-role protocol.
- Structured change map, evidence decision, and merge verdict in reports.
- A redesigned static web console using the existing HTML/CSS/JavaScript stack.
- Review Pack presentation over the existing Skill packages.
- Benchmark Lab presentation over the existing evaluation engines.
- Integration of the supplied 100-case synthetic JSONL benchmark.
- Updated tests, examples, architecture documentation, and reproducibility instructions.

### Out of scope

- Replacing SQLite/PostgreSQL persistence.
- Replacing Redis Streams or the in-process queue.
- Changing GitHub webhook authentication, GitHub App authentication, or HMAC verification.
- Replacing the agent runtime, repository tool registry, memory service, or checkpoint store.
- Changing the `/v1/*` API route family.
- Database migrations.
- Adding a frontend framework.
- Claiming the supplied dataset contains real public pull requests.
- Fabricating benchmark scores, project history, licenses, or provenance.

## 4. Brand and compatibility

The public product name becomes **DiffPrism**. The subtitle is **Evidence-driven PR Review** and the short promise is **Split the diff. Verify the risk.** The visual system uses a graphite background, restrained spectral accents, and a small prism mark. The current glowing orbit illustration and `E` monogram are removed.

The implementation package `evoagent` remains in place to avoid an unnecessary import migration. A thin `diffprism` entry package and a `pyproject.toml` console command expose the new name. `python -m evoagent` remains supported as a legacy entry point during this redesign.

Public HTML titles, Markdown report titles, logs, GitHub User-Agent values, local-storage keys, Docker service labels, example configuration, and README prose use DiffPrism. Compatibility-sensitive stored data and API paths remain unchanged unless a public display label can be layered over them.

New environment names use `DIFFPRISM_*`. Configuration resolution checks the new name first and the corresponding `EVOAGENT_*` name second. Existing deployments therefore continue to work without configuration changes.

## 5. Agent protocol

The orchestration topology remains one lead, two parallel workers, one independent critic, and final synthesis. Role responsibilities and internal identifiers change.

### Prism Lead

Internal id: `prism-lead`

Responsibilities:

- Infer the change intent from the diff and available repository context.
- Classify risk and assign distinct objectives to both workers.
- Require each proposed finding to include a trigger, impact, changed-line location, evidence, remediation, and a targeted test.
- Resolve examiner objections and produce the final merge verdict.

### Scope Mapper

Internal id: `scope-mapper`

Responsibilities:

- Produce a change map before making defect claims.
- Identify changed contracts, data boundaries, control-flow surfaces, callers, and related tests.
- Report test gaps and explicit unknowns.
- Propose a finding only when the mapping reveals a concrete defect introduced by the patch.

### Failure Hunter

Internal id: `failure-hunter`

Responsibilities:

- Use the change map and repository evidence to construct concrete failure conditions.
- Cover security, authorization, state, exceptions, concurrency, resources, compatibility, and data integrity according to selected Review Packs.
- Avoid style-only comments and pre-existing defects.
- Include an executable or precisely described verification test for each proposed finding.

### Evidence Examiner

Internal id: `evidence-examiner`

Responsibilities:

- Review anonymized candidates without source-agent identity.
- Classify each candidate as `verified`, `weak`, `rejected`, or `duplicate`.
- Verify that the cited location is part of the change and that the evidence establishes the stated trigger and impact.
- Reject findings that rely on unsupported assumptions or generic best practice.

Only `verified` findings are eligible for publication. The checkpoint protocol becomes `prism-review-v1`; incompatible incomplete legacy checkpoints are restarted rather than migrated. Completed stored reports remain readable through defensive defaults.

## 6. Report contract

`ReviewReport` gains two defaulted fields:

```json
{
  "change_map": {
    "intent": "",
    "surfaces": [],
    "affected_files": [],
    "test_gaps": [],
    "unknowns": []
  },
  "verdict": {
    "decision": "pass | warn | block",
    "reason": "",
    "required_actions": [],
    "verified_findings": 0,
    "rejected_findings": 0
  }
}
```

`Finding` gains defaulted `trigger`, `impact`, `verification`, and `examiner_reason` fields. Existing finding fields remain valid. Old stored findings render with sensible empty states rather than failing.

The Markdown report order becomes:

1. Merge verdict
2. Change map
3. Verified findings
4. Required actions
5. Review trail and execution facts
6. Explicit unknowns

The report must never imply that a test ran unless process evidence exists. Suggested tests are labeled as suggestions; executed checks include exit status and available trace evidence.

## 7. Web information architecture

The static frontend remains dependency-free. Navigation becomes:

- PR Inbox
- New Review
- Review Workspace
- Review Packs
- Benchmark Lab

The review form keeps repository, PR number, mode, diff, and async controls. The current API contract is preserved. Copy is rewritten around a PR workflow rather than model configuration.

The task detail raw JSON block is replaced by a Review Workspace containing:

- Repository, PR number, state, risk, and merge verdict header.
- Change Map with intent, affected surfaces, files, test gaps, and unknowns.
- Verified Finding cards with severity, path/line, trigger, evidence, impact, fix, test, confidence, and examiner reason.
- Agent Trail with the four phases and counts, not hidden chain-of-thought.
- Execution facts for calls, tools, tokens, cost, latency, and context compression.
- Feedback controls attached to each rendered finding.
- Fix Preview using the existing fix endpoint response.

Internal JSON remains available through a collapsed diagnostic view for debugging. UI rendering must escape untrusted report content and must not use unsanitized HTML.

## 8. Review Packs

On disk, existing Skill package names and manifests remain valid. The UI introduces public display labels:

- Security Boundaries
- Behavioral Correctness
- Failure Recovery
- Data Integrity
- Contract Compatibility
- Performance Risk
- Test Coverage
- Runtime Signals
- Maintainability

Each card shows version, source, sandbox status, allowed tools, and a concise scope statement. The loader and hot-reload behavior remain unchanged.

## 9. Benchmark Lab

Existing evaluation engines and canonical internal arm keys remain compatible. Public labels are:

- `single-model` -> Solo Review
- `multi-llm-no-critic` -> Prism without Examiner
- `full-agentic` -> Full DiffPrism

Primary displayed metrics are Finding F1, high-risk recall, evidence accuracy, invalid comments per PR, fix verification rate, cost per verified finding, and p95 review latency. Existing detailed metrics remain in downloadable JSON.

Promotion requires:

- Validation F1 improvement at or above the configured threshold.
- No high-risk recall regression.
- No increase in invalid comments per PR beyond the configured tolerance.
- No protected holdout regression.
- A complete, reproducible run record with dataset fingerprint, model, configuration, and cost/latency evidence.

The Benchmark Lab replaces raw JSON output with baseline/candidate cards, metric deltas, split labels, dataset fingerprint, and a visible `PROMOTE` or `BLOCK` decision.

## 10. Supplied benchmark dataset

Source file during design: `C:\Users\HPC\Downloads\pr_diff_100.jsonl`

Verified properties:

- SHA-256: `65F301C0C75125676D5DA482FFA00828399B7041D4DB378BC52E48BAAB36B1B6`
- 100 unique cases across 10 fictional repositories.
- 80 validation cases and 20 holdout cases.
- Repository-disjoint validation and holdout splits.
- 40 positive cases with 40 labeled findings and 60 clean cases.
- 21 distinct rule identifiers.
- Severity distribution: 4 critical, 15 high, 16 medium, 5 low.
- Every source is marked `offline-fixture`; no case has a public URL.
- There is no training split.

The file will be copied to `evaluation_data/pr_diff_100.jsonl` without altering case contents. Documentation and UI label it **Synthetic Fault Benchmark v1**. It can support deterministic accuracy, orchestration ablation, and regression demonstrations. It cannot satisfy the existing real-dataset production readiness gate that requires a train split and at least 300 labeled public or historical PRs.

The Benchmark Lab must report both facts explicitly:

- Synthetic benchmark: available and reproducible.
- Production real-PR benchmark: not ready until an independently labeled, repository-disjoint dataset meeting the existing gate is provided.

Holdout rows are never exposed through the ordinary evaluation-case API.

## 11. Packaging and documentation

Add:

- `pyproject.toml` with package metadata and a `diffprism` console command.
- `diffprism/__init__.py` and `diffprism/__main__.py` compatibility wrappers.
- `docs/architecture.md`.
- `docs/agent-protocol.md`.
- `docs/evaluation.md`.
- `examples/sample-review.json` and `examples/sample-report.md` generated from deterministic sample data.
- `CHANGELOG.md` and `SECURITY.md`.

Rewrite the README around the product promise, a sixty-second local demo, the four-stage review protocol, one complete evidence-backed report example, reproducible evaluation, architecture, deployment, limitations, and acknowledgements.

A license file is not added until the source-code ownership and intended license are explicitly confirmed. The README must not claim that the entire codebase was created from scratch.

## 12. Testing and acceptance

Implementation follows test-driven development for behavior changes. Required checks:

- Agent tests verify delegation to Scope Mapper and Failure Hunter, blind Evidence Examiner decisions, final synthesis, checkpoint resume, and bounded revision behavior.
- Model/report tests verify backward-compatible defaults and the new change-map/verdict/finding fields.
- Markdown tests verify the new section order and correct distinction between suggested and executed tests.
- Evaluation tests verify public arm labels, metric derivation, promotion gates, dataset fingerprint, split isolation, and holdout API protection.
- Frontend tests or minimal DOM checks verify escaping and structured report rendering; manual browser QA covers desktop and narrow layouts.
- Configuration tests verify `DIFFPRISM_*` precedence and `EVOAGENT_*` fallback.
- The complete existing unit-test suite passes.
- `python -m diffprism` and the legacy `python -m evoagent` both start the same service.
- The supplied dataset is validated by the controlled benchmark command and its limitations are visible in generated output.
- No secrets, local databases, caches, generated benchmark outputs, or private credentials are committed.

## 13. Expected implementation footprint

The redesign is expected to modify approximately 15-20 existing files and add 8-12 packaging, documentation, example, and dataset files. Most changes are concentrated in:

- `evoagent/agentic_core.py`
- `evoagent/models.py`
- `evoagent/report.py`
- `evoagent/modes.py`
- `evoagent/config.py`
- `evoagent/api.py`
- `evoagent/github.py`
- `web/index.html`
- `web/app.js`
- `web/app.css`
- agent, report, service, configuration, and evaluation tests

Completion means the implementation, tests, browser QA, local commit, and push to the configured GitHub `main` branch have all succeeded. The remote repository itself is renamed only if the user separately authorizes that external repository-setting change.
