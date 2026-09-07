# Prism Review Protocol v1

The protocol uses four stage-oriented roles. Roles are not four independent reviewers voting on the same diff; each produces a distinct artifact consumed by the next stage.

## 1. Prism Lead (`prism-lead`)

- Establishes the review plan and selects Review Packs.
- Applies token, time, tool and revision budgets.
- Receives the scope map and evidence decisions.
- Produces `verdict.decision`, rationale, required actions and unknowns.

The Lead cannot turn a rejected hypothesis into a verified finding.

## 2. Scope Mapper (`scope-mapper`)

- Describes change intent and changed files.
- Identifies entry points, state transitions, trust boundaries and downstream effects.
- Produces `change_map`, not defect claims.

Its output narrows the search space and prevents domain reviewers from scanning the entire repository without a change-driven reason.

## 3. Failure Hunter (`failure-hunter`)

- Constructs concrete failure conditions introduced by added lines.
- Uses selected Review Packs and repository tools.
- Supplies path, line, trigger, evidence, impact, fix and verification procedure.
- Avoids style-only findings and pre-existing defects.

## 4. Evidence Examiner (`evidence-examiner`)

Each proposed finding receives one decision:

- `verified` — the changed line and supporting evidence establish an actionable defect.
- `weak` — plausible but evidence or impact is insufficient.
- `rejected` — contradicted, outside the diff, non-actionable or pre-existing.
- `duplicate` — materially the same root cause as another finding.

Only `verified` findings pass to the final report in the full protocol.

## Report contract

```json
{
  "change_map": {"intent": "...", "entry_points": [], "boundaries": []},
  "verdict": {"decision": "pass|warn|block", "reason": "...", "required_actions": []},
  "findings": [{
    "path": "app.py",
    "line": 42,
    "trigger": "...",
    "evidence": "...",
    "impact": "...",
    "fix": "...",
    "test": "...",
    "verification": "verified",
    "examiner_reason": "..."
  }]
}
```

Execution facts and agent trail remain separate from substantive findings so cost, latency and tool activity do not get confused with code risk.

## Revision policy

Normal-risk reviews use one pass. A high-risk task may request at most one targeted Failure Hunter revision when the Examiner identifies a repairable evidence gap. The checkpoint key `agentic-prism-session` allows the runtime to restore progress without replaying completed roles.
