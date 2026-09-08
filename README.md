# TraceReview

**Evidence-driven, risk-aware Pull Request review runtime.**

TraceReview 接收 Git unified diff 或 GitHub Pull Request 事件，把一次代码审查当成可恢复、可评测、可审计的业务任务，而不是一次模型调用。项目保留了成熟的 `ReviewHarness -> AgentRuntime -> BoundedRole` 执行骨架，在此基础上增加 **Risk Profile 按需路由、条件 Evidence Auditor、Evidence/Severity Gate、人工审批修复和人工审批 Review Policy**。

> 内部 `evoagent` Python package 暂时保留，用于兼容历史 checkpoint、数据库记录和已有 import；对外入口、环境变量、报告和 UI 使用 `TraceReview`。新入口为 `python -m tracereview`。

## 为什么这样设计

PR 审查里不同变更的风险面差异很大。文档改动、普通业务逻辑、认证边界、并发状态机不应该无条件消耗同样的多 Agent 预算。TraceReview 先做确定性的 Risk Profile，再决定是否调用 Boundary Inspector、Behavior Inspector 与 Evidence Auditor；对高风险结论使用确定性 Finding Gate 兜底，对写 GitHub 的修复动作要求显式人工批准。

核心目标不是“Agent 越多越好”，而是让每个组件都能回答：**为什么存在、失败怎么办、如何验证。**

## 核心链路

```text
Manual Diff / GitHub Pull Request
                │
                ▼
          DiffParser
                │
                ▼
          Risk Profile
     paths / signals / complexity
                │
                ▼
        Local Scanner / Skills
                │
                ▼
              Review Coordinator
       ┌────────┴────────┐
       │                 │
 Boundary Inspector   Behavior Inspector
   conditional          conditional
       │                 │
       └────────┬────────┘
                ▼
             Findings
                │
     high risk / weak evidence /
        conflicting sources ?
          │              │
         no             yes
          │              ▼
          │        Evidence Auditor (conditional)
          └───────┬──────┘
                  ▼
             FindingGate
       location / evidence /
     severity / confidence /
             release
                  │
                  ▼
             ReviewReport
          ┌───────┴────────┐
          ▼                ▼
   GitHub Comment      Fix Proposal
                           │
                    Verify before/after
                           │
                    WAITING_APPROVAL
                           │
                    Human approval
                           │
                           ▼
                       Draft PR
```

外层执行仍然由：

```text
ReviewHarness
└── AgentRuntime
    ├── planning
    ├── executing
    │   └── Review Coordinator / Specialist / conditional Evidence Auditor
    │       └── BoundedRole tool/final loop
    └── reviewing
```

`AgentRuntime` 管预算、timeout、node retry、cancel、checkpoint、resume 和 trace；`ReviewHarness` 管 PR Review 的业务状态和报告生命周期；`BoundedRole` 管单角色的有界 Tool Calling 循环。

## 这版重点改动

### 1. Risk-aware Multi-Agent Routing

`evoagent/risk_profile.py` 在调用 LLM 前根据文件路径、新增行信号、复杂度、测试变化生成可解释的 `RiskProfile`：

- `requires_security_review`
- `requires_reliability_review`
- `auditor_recommended`
- `risk_domains`
- `complexity_score`
- `reasons`

例如 `eval(user_input)` 会进入 Boundary Inspector；普通生产代码默认进入 Behavior Inspector；认证 + 状态/并发类复杂变更可同时调用两个 Specialist。显式指定的 Agent Skill 可以覆盖自动裁剪，避免 Routing 把用户明确要求的 Specialist 路径裁掉。

### 2. Conditional Evidence Audit

Evidence Auditor 不再固定执行。只有以下情况才进入盲审：

- Risk Profile 建议复核；
- 存在 High/Critical Finding；
- 置信度较低；
- 证据弱；
- 多来源候选需要独立裁决。

`collaboration.audit_policy` 会记录是否调用和原因，因此可以直接评估 Evidence Auditor 的成本与收益。

### 3. Evidence-oriented Finding Contract

保留代码审查领域自然的 `Finding` 模型，同时增加：

- `category`
- `precondition`
- `impact`
- `evidence_strength`

`FindingGate` 按 Location、Evidence、Severity、Confidence、Release 五类规则检查。High/Critical 模型 Finding 在声明新证据契约后，需要同时说明成立前提与影响，并要求强工具证据或 call chain、修复建议和验证建议。

### 4. Tool Contract Metadata

`AgentTool` 在原来的 `name / description / parameters / handler` 之外增加：

- `side_effect`
- `retryable`
- `timeout_seconds`

这样运行时和 UI 能区分只读证据工具与有副作用动作。真正的 GitHub 写操作仍由 Service 层显式控制，不交给普通 Specialist 自由调用。

### 5. Human-in-the-loop Repair

自动修复拆成两个阶段：

1. `POST /v1/tasks/{id}/fix`：生成 patch，执行结构检查、before/after 测试；**不写 GitHub**，成功后返回 `awaiting-approval` 并保存 checkpoint。
2. `POST /v1/tasks/{id}/fix/approve`：重新校验 PR Head SHA；只有仍然与验证时一致，才创建 `tracereview/fix-pr-*` 分支和 Draft PR。

PR 在等待审批期间发生新提交时，旧 proposal 会被拒绝，必须重新生成和验证。

### 6. Feedback-driven Review Policy Optimization

保留 Prompt / Agent Skill 版本化与 Validation/Holdout 回放能力，但不再将“自动激活”作为默认行为：

```text
confirmed feedback
    -> failure case
    -> candidate Prompt / SKILL.md
    -> Validation replay
    -> Holdout non-regression
    -> awaiting_approval
    -> explicit activation
    -> rollback available
```

Skill candidate 与 Prompt candidate 都只有通过回放门禁后才进入待审批状态。自动 feedback case 在 Skill 被批准后再标记为 resolved。可选 Canary/Shadow 仍用于上线观察和错误预算回滚，但 Shadow 达标只进入 `awaiting_approval`，不会自动提升 stable version。

### 7. Context Engineering 与 Memory 简化

上下文压缩仍使用 risk-ranked hunk Map/Reduce、Observation summarization 和 token budget；新增在严重上下文压力下对 Tool Catalog 的压缩，仍保留工具名称、必填参数与副作用元数据。

Memory 在业务层按三类解释：

- **Task Context**：本任务 Tool Observation / Specialist 状态；
- **Review History**：历史 Finding、Gate 结果与任务摘要；
- **Repository Feedback**：误报、漏报、坏修复、仓库特定约定。

底层 `working / episodic / semantic / procedural` scope 为兼容历史数据暂时保留，但新文档不再把四层 Memory 当成项目卖点。

### 8. Evaluation 与 Observability

100 条受控 PR Diff 数据集随项目放在 `evaluation_data/pr_diff_100.jsonl`。原有 Precision / Recall / F1 / High Risk Recall / Clean Accuracy 保留，并增加 Gate 维度：

- `pre_gate_precision`
- `post_gate_precision`
- `gate_fp_filter_rate`
- `gate_tp_loss_rate`
- `gate_rejected_per_pr`

同时记录 Agent / Tool / Token / latency / cost / revision / audit acceptance 等执行事实。受控离线实验只证明当前 deterministic/scanner/orchestration 行为，不宣称等价于生产 LLM 效果。

## 快速开始

要求 Python 3.11+。

```bash
python -m pip install -r requirements.txt
cp .env.example .env
python -m tracereview
```

默认监听：`http://127.0.0.1:8080/`

### 推荐环境变量

```env
TRACEREVIEW_AUTH_REQUIRED=true
TRACEREVIEW_AUTH_SECRET=<至少 32 字节随机值>
TRACEREVIEW_BOOTSTRAP_ADMIN_USERNAME=admin
TRACEREVIEW_BOOTSTRAP_ADMIN_PASSWORD=<强密码>

TRACEREVIEW_LLM_PROVIDER=custom
TRACEREVIEW_LLM_BASE_URL=https://example.com/v1
TRACEREVIEW_LLM_API_KEY=<token>
TRACEREVIEW_LLM_MODEL=<model>
```

也支持：

```env
TRACEREVIEW_LLM_PROVIDER=deepseek
TRACEREVIEW_DEEPSEEK_API_KEY=<key>
```

或 OpenRouter 兼容路由。完整配置见 `.env.example`。

为了兼容旧部署，`EVOAGENT_*` 变量仍可使用；当新旧变量同时存在时，`TRACEREVIEW_*` 优先。

## 手动提交 Review

登录后：

```bash
curl -X POST http://127.0.0.1:8080/v1/reviews \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "repository":"demo/api",
    "pull_request":12,
    "mode":"agentic",
    "diff":"--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+eval(user_input)"
  }'
```

异步：

```text
POST /v1/reviews?async=true
GET  /v1/tasks/{task_id}
POST /v1/tasks/{task_id}/cancel
POST /v1/tasks/{task_id}/resume
```

## GitHub Webhook

```env
TRACEREVIEW_GITHUB_WEBHOOK_SECRET=<random secret>
TRACEREVIEW_GITHUB_TOKEN=<fine-grained PAT>
TRACEREVIEW_AUTO_POST_REVIEW=true
```

Webhook：

```text
POST /webhooks/github
```

支持 `pull_request.opened / reopened / synchronize`。请求用原始 body 做 HMAC-SHA256 校验，Delivery ID + payload SHA-256 做幂等 claim。PR 评论使用 TraceReview marker 做 Upsert，同时能识别旧 EvoAgent marker 并迁移到新 marker。

## 修复审批

```text
POST /v1/tasks/{task_id}/fix
```

如果返回：

```json
{
  "status": "awaiting-approval",
  "approval_required": true
}
```

表示结构检查与配置的 repository test 已通过，但 GitHub 还没有写操作。管理员确认后：

```text
POST /v1/tasks/{task_id}/fix/approve
```

服务会再次比较当前 PR Head SHA 与 proposal 的 `source_sha`，防止批准过期 patch。

## Review Policy 审批

候选 Prompt / Skill 通过 Validation 与 Holdout 后返回：

```json
{
  "decision": "awaiting_approval"
}
```

随后通过已有 version activation API 显式批准。Skill approval 也会关闭该 candidate 对应的 feedback failure cases。

## API 摘要

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | 运行状态、模型、队列、组件 |
| `POST` | `/v1/auth/login` | 登录 |
| `POST` | `/v1/reviews` | 同步 Review |
| `POST` | `/v1/reviews?async=true` | 异步 Review |
| `GET` | `/v1/tasks/{id}` | 任务、Trace、Report |
| `GET` | `/v1/tasks/{id}/report` | Markdown 报告 |
| `POST` | `/v1/tasks/{id}/feedback` | 误报/漏报/坏修复反馈 |
| `POST` | `/v1/tasks/{id}/fix` | 生成并验证 repair proposal |
| `POST` | `/v1/tasks/{id}/fix/approve` | 人工批准后创建 Draft PR |
| `POST` | `/v1/tasks/{id}/cancel` | 协作式取消 |
| `POST` | `/v1/tasks/{id}/resume` | checkpoint 续跑 |
| `POST` | `/v1/skill-evolution/auto` | 从确认反馈生成 Skill candidate |
| `POST` | `/v1/skill-evolution/{name}/versions/{version}/activate` | 显式批准/切换 Skill 版本 |
| `POST` | `/v1/evolution/propose` | Prompt candidate 回放 |
| `POST` | `/v1/deployments/{name}/approve` | 人工批准通过 Shadow 观察的 candidate |
| `POST` | `/v1/skills/{name}/versions/{version}/activate` | 显式批准/切换 Prompt 版本 |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/audit` | 审计日志 |
| `GET` | `/api/queue/dead-letters` | DLQ |

## 存储、队列与多租户

- 本地：SQLite + in-process queue；
- 多实例：PostgreSQL + Redis Streams；
- Redis worker：consumer group、lease、ACK、retry、DLQ；
- RBAC：admin / maintainer / auditor；
- tenant / repository grants；
- checkpoint、agent memories、evaluation、skill versions、audit log 都有持久化表。

Docker Compose：

```bash
docker compose up --build
```

## Agent Skills

`skills/<name>/SKILL.md` 是声明式能力包，可声明领域说明、allowed tools 和 supporting resources。它解决的是“领域 Review 规则不要全部硬编码进一个 Prompt”，不是为了增加 Agent 数量。

内置示例包括：

- security-review
- correctness-review
- reliability-review
- database-review
- api-compatibility
- performance-review
- observability-review
- test-quality
- code-quality

## Evaluation

运行单测：

```bash
PYTHONPATH=tests:. python -m unittest discover -s tests -v
```

运行 100 条受控实验：

```bash
python scripts/run_controlled_experiments.py \
  --dataset evaluation_data/pr_diff_100.jsonl \
  --output output/controlled-experiments/evaluation.json
```

可选的 `evaluation_data/prompt_evolution_130.jsonl` 没有随当前交付输入提供，因此相关 proof test 会 `skip`，项目不会伪造该数据集。

## 代码地图

```text
tracereview/            public entrypoint

evoagent/
  agentic_core.py       Review Coordinator / Specialist / conditional Evidence Auditor
  risk_profile.py       deterministic risk-aware routing
  runtime.py            AgentRuntime + ToolRegistry
  harness.py            PR Review lifecycle
  context_manager.py    semantic diff/context compression
  memory.py             task/history/repository feedback memory
  gates.py              deterministic FindingGate
  patching.py           verified repair + human approval boundary
  skill_evolution.py    replay-gated Skill candidate lifecycle
  evolution.py          replay-gated Prompt candidate lifecycle
  evaluation_v2.py      production-style evaluation metrics
  service.py            application service / workflow boundary
  api.py                HTTP API
  store.py              SQLite persistence
  postgres_store.py     PostgreSQL persistence
  task_queue.py         in-process / Redis Streams queue
  observability.py      traces / alerts
  report.py             Markdown output

web/                    management UI
skills/                 declarative Agent Skills
tests/                  behavior and regression tests
evaluation_data/        supplied controlled dataset
```

## 设计取舍

TraceReview 没有为了“看起来更 Agent”把所有确定性能力都改成 LLM Role：DiffParser、Risk Profile、Scanner、FindingGate、RepairVerifier 都保持确定性；Multi-Agent 只处理需要上下文推理、职责隔离和独立复核的部分。这样在失败时可以定位到底是 parsing、routing、tool、model、gate 还是业务写操作出了问题。
