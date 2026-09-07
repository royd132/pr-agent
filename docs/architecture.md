# DiffPrism architecture

## Design goal

DiffPrism separates probabilistic reasoning from deterministic control. Models can map scope, generate hypotheses and explain evidence; the runtime owns state transitions, budgets, tool permissions, persistence, retries, release gates and the final report contract.

## Request path

```text
Browser / REST / GitHub webhook
              │
              ▼
         HTTP API + Auth
              │
              ▼
         ReviewService
       ┌──────┼────────┐
       ▼      ▼        ▼
 TaskStore  Queue   GitHub client
       │      │
       └──┬───┘
          ▼
     ReviewHarness
          │
          ▼
 AgenticReviewer (prism-review-v1)
          │
  ┌───────┼───────────────┐
  ▼       ▼               ▼
Context  Tools        Review Packs
          │
          ▼
      ReviewReport
```

## Layers

1. **Presentation** — the `diffprism` package, `evoagent.presentation`, structured Web workspace, public role and benchmark labels.
2. **Application** — `ReviewService` handles validation, auth scope, task creation, feedback, fixes and evolution operations.
3. **Runtime** — `ReviewHarness`, queue and checkpoints enforce task lifecycle, budget and resumability.
4. **Reasoning** — `AgenticReviewer` executes the four role protocol and records collaboration metadata.
5. **Evidence** — repository tools, diff parser, rule scanners and Review Packs constrain what agents may inspect.
6. **State** — SQLite or PostgreSQL stores tasks, traces, feedback, prompts, evaluation runs and audit records; Redis can back asynchronous delivery.

## Stable boundaries

- Public command: `diffprism` or `python -m diffprism`.
- Compatibility command: `python -m evoagent`.
- Preferred settings: `DIFFPRISM_*`; legacy fallback: `EVOAGENT_*`.
- Public protocol: `prism-review-v1`.
- Internal package name `evoagent` remains intentionally unchanged to avoid breaking imports.
- Existing REST task, webhook and evolution endpoints remain compatible.

## Trust boundaries

Pull request content, model output, Review Pack resources and diagnostic JSON are untrusted data. Tool arguments are schema-checked, repository paths are constrained, webhook signatures are verified, browser renderers escape dynamic values, and only Evidence Examiner decisions marked `verified` enter a full agentic report.

The runtime is not a general-purpose sandbox. Any configured repair test command, model endpoint, Skill resource or repository checkout must be treated according to the operator's deployment boundary. See [../SECURITY.md](../SECURITY.md).

## Extension points

- Add a Review Pack under `skills/<name>/SKILL.md`.
- Add deterministic scanners through `SkillRegistry`.
- Configure an OpenAI-compatible chat endpoint.
- Replace SQLite/in-process execution with PostgreSQL/Redis.
- Export OpenTelemetry traces and Prometheus metrics.
- Add evaluation cases through the versioned case API, keeping protected holdout data separate.
