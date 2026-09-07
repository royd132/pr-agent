# DiffPrism

> Split the diff. Verify the risk.

DiffPrism 是一个证据优先的 Pull Request 审查系统。它把一次审查拆成范围映射、故障假设、证据复核和合并裁决四个阶段，并把每条最终发现约束为可定位、可解释、可修复、可验证的结构化记录。

这不是一个只改了名称的 PR-Agent 分支。当前实现保留了原项目内部 `evoagent` Python 包以兼容已有导入，在公开入口、角色协议、报告 schema、Review Packs、Benchmark Lab、评测数据和 Web 工作台上进行了独立改造。项目不会隐瞒其设计参考；具体边界见下方“设计参考与依赖”。

## 60 秒本地演示

需要 Python 3.11+：

```powershell
python -m pip install -e .
$env:DIFFPRISM_AUTH_REQUIRED = 'false'
$env:DIFFPRISM_LLM_PROVIDER = 'local'
python -m diffprism
```

打开 `http://127.0.0.1:8080/`。`local` provider 可启动控制台与确定性规则路径；完整四角色 LLM 审查需要在 `.env.example` 的 `DIFFPRISM_LLM_*` 中配置 OpenAI Chat Completions 兼容端点。

也可以直接使用 API：

```powershell
$body = @{
  repository = 'demo/payments'
  pull_request = 42
  mode = 'agentic'
  diff = "diff --git a/app.py b/app.py`n--- a/app.py`n+++ b/app.py`n@@ -1 +1,2 @@`n def run(user):`n+    eval(user)"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/v1/reviews -ContentType application/json -Body $body
```

## 四阶段 Prism Review

```text
PR / unified diff
        │
        ▼
Prism Lead ── 选择 Review Packs、管理预算、形成裁决
        │
        ▼
Scope Mapper ── 变更意图、入口、边界、状态、影响面
        │
        ▼
Failure Hunter ── 针对本次变更提出可复现的故障假设
        │
        ▼
Evidence Examiner ── verified / weak / rejected / duplicate
        │
        ▼
ReviewReport ── verdict + change_map + verified findings
```

Evidence Examiner 只把 `verified` 发现交给完整拓扑的最终报告。每条发现包含 `trigger`、`evidence`、`impact`、`fix`、`test`、`verification` 和 `examiner_reason`。协议细节见 [docs/agent-protocol.md](docs/agent-protocol.md)，组件关系见 [docs/architecture.md](docs/architecture.md)。

## Review Packs

磁盘上的 Skill 包格式保持兼容，工作台将其呈现为面向 PR 风险面的 Review Packs：

- Security Boundaries
- Behavioral Correctness
- Failure Recovery
- Data Integrity
- Contract Compatibility
- Performance Risk
- Test Coverage
- Runtime Signals
- Maintainability

每个 Pack 仍以 `skills/<machine-id>/SKILL.md` 定义，可声明 `allowed-tools`，可热加载、版本化和经独立回放门禁后激活。

## Synthetic Fault Benchmark v1

仓库包含 `evaluation_data/pr_diff_100.jsonl`，其固定事实是：100 个合成 diff、10 个虚构仓库、80 个 validation 样本、20 个 repository-disjoint holdout 样本、40 个带缺陷样本、60 个 clean 样本、40 条预期发现。

```powershell
python scripts/run_accuracy_experiment.py
python scripts/run_prompt_evolution_proof.py
```

该数据不是来自真实公开 PR，没有 train split，不足以证明生产效果，也不能用于宣称线上准确率。Benchmark Lab 会显式显示这一限制。完整评测契约见 [docs/evaluation.md](docs/evaluation.md)。

## 配置与兼容

优先使用 `DIFFPRISM_*`。对应的旧 `EVOAGENT_*` 变量仍可作为迁移期 fallback；若两者同时存在，非空 `DIFFPRISM_*` 胜出。

```env
DIFFPRISM_HOST=127.0.0.1
DIFFPRISM_PORT=8080
DIFFPRISM_AUTH_REQUIRED=true
DIFFPRISM_LLM_PROVIDER=custom
DIFFPRISM_LLM_BASE_URL=https://example.com/v1
DIFFPRISM_LLM_API_KEY=<token>
DIFFPRISM_LLM_MODEL=<model>
```

不要提交 `.env`、模型密钥、GitHub token 或生产 diff。完整字段见 [.env.example](.env.example)。

## GitHub 与部署

- `POST /webhooks/github` 接收签名校验后的 `pull_request` 事件。
- `POST /v1/reviews` 创建同步或异步审查。
- `GET /v1/tasks/{id}` 返回状态、轨迹与结构化报告。
- `GET /api/skills` 返回底层身份及 Review Pack 展示字段。
- `GET /api/benchmark` 返回数据集身份、公开 arm 名称和公开指标。
- `GET /metrics` 暴露 Prometheus 文本指标。

生产环境可使用 PostgreSQL、Redis Streams、OpenTelemetry 和 GitHub App/PAT。容器入口为 `python -m diffprism`；部署前必须启用认证、限定 GitHub 权限、隔离执行环境并配置真实的回放数据。

Compose 启动前必须设置 `DIFFPRISM_POSTGRES_PASSWORD`、`DIFFPRISM_AUTH_SECRET` 和 `DIFFPRISM_BOOTSTRAP_ADMIN_PASSWORD`；示例不会提供固定生产凭据。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall diffprism evoagent tests
```

示例输出在 [examples/sample-review.json](examples/sample-review.json) 和 [examples/sample-report.md](examples/sample-report.md)。它们是由报告契约构造的确定性示例，不是一次真实生产运行。

## 设计参考与直接依赖

以下项目提供了设计启发，但 DiffPrism 没有把它们声明为直接代码依赖，也不声称与其兼容或获得背书：

- [PR-Agent](https://github.com/The-PR-Agent/pr-agent)：围绕 PR 命令、审查输出和 Git 平台工作流组织产品体验。
- [Semgrep](https://github.com/semgrep/semgrep)：规则/工具提供事实、语义层解释结果的分层思路。
- [SWE-agent](https://github.com/SWE-agent/SWE-agent)：把 agent 与受约束的计算机/仓库接口分开。
- [AutoGen](https://github.com/microsoft/autogen)：专业角色、消息传递和可组合多 agent 协作。
- [OpenHands](https://github.com/OpenHands/OpenHands)：软件 agent 的工具、事件、工作区与运行时边界。
- [promptfoo](https://github.com/promptfoo/promptfoo)：以版本化数据、对比实验和门禁驱动 prompt/agent 变更。
- [Langfuse](https://github.com/langfuse/langfuse) 与 [Arize Phoenix](https://github.com/Arize-ai/phoenix)：trace、成本、延迟、数据集和实验的可观测呈现。

直接运行依赖以 [pyproject.toml](pyproject.toml) 和 [requirements.txt](requirements.txt) 为准。仓库当前未声明许可证；公开可见不等于获得复制、修改或分发许可，添加许可证前请先确认全部来源代码的权利链。

## 项目材料

- [架构](docs/architecture.md)
- [四角色协议](docs/agent-protocol.md)
- [评测与数据边界](docs/evaluation.md)
- [安全策略](SECURITY.md)
- [变更记录](CHANGELOG.md)
