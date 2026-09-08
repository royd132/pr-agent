# TraceReview 项目笔记

> 本笔记按用户上传的原始 **EvoAgent PDF** 章节顺序逐章改写，并对应当前 `TraceReview_v2.1` 代码实现。
>
> 改造原则不是推翻原有工程底盘，而是保留已经合理的 `ReviewHarness -> AgentRuntime -> BoundedRole`、Checkpoint、Redis/PostgreSQL、Tool Registry、Evaluation Harness、SafeFix 等能力，集中修改 **固定 Multi-Agent、Evidence Auditor 常驻、Memory 叙事、自进化自动上线、修复写操作与评测指标**。
>
> 两份补充材料给出的判断标准被贯彻到每个模块：**为什么存在、失败怎么办、如何验证**。因此这版刻意没有把所有确定性能力都 Agent 化，也没有为了“技术名词更多”增加无必要的角色。

---

## 改造总览：哪些保留，哪些修改

| 模块 | 处理 | 当前设计 |
|---|---|---|
| PR Review 业务场景 | 保留 | 仍以 unified diff / GitHub Pull Request 为输入 |
| ReviewHarness | 强保留 | 仍负责 Planning / Executing / Reviewing 生命周期 |
| AgentRuntime | 强保留 | 仍负责预算、重试、超时、取消、Checkpoint、Resume、Trace |
| BoundedRole | 强保留 | 单角色有界 Tool/Observation/Final Loop |
| Review Coordinator / Boundary Inspector / Behavior Inspector | 保留并修改 | 不再固定全量 fan-out，改为 RiskProfile 按风险路由 |
| Evidence Auditor | 保留并修改 | 从 always-on 改为 conditional independent review |
| Scanner / 本地规则 | 强保留 | 确定性底线，不用 LLM 替代 |
| Finding | 保留并增强 | 新增 category / precondition / impact / evidence_strength |
| FindingGate | 强保留并增强 | 增加 Severity Contract，明确五类 Gate |
| Tool Registry | 保留并增强 | 新增 side_effect / retryable / timeout_seconds 元数据 |
| ContextManager | 强保留并增强 | 保留 Hunk Map-Reduce，并增加 Tool Catalog 压缩 |
| Memory | 简化叙事 | 对外解释为 Task Context / Review History / Repository Feedback |
| Skill | 保留 | 继续作为可版本化领域 Review 能力包，不再强调“Agent 越多越好” |
| Prompt/Skill Evolution | 降温重构 | 改为 Feedback-driven Review Policy Optimization，默认人工批准 |
| Canary / Shadow | 弱化 | 保留观察与错误预算；Shadow 达标只进入 awaiting_approval |
| Safe Fix | 强保留并修改 | 先生成和验证 proposal，再人工批准后写 GitHub |
| Evaluation Harness | 强保留并增强 | 新增 Pre/Post Gate、FP Filter、TP Loss 等指标 |
| SQLite/PostgreSQL/Redis/RBAC | 保留 | 作为完整后端与多租户能力 |
| OTel / Prometheus / Audit | 保留 | 用于 Trace、成本、失败定位 |
| 品牌与公开入口 | 修改 | 对外 `TraceReview` / `TRACEREVIEW_*`，内部 `evoagent` namespace 暂留兼容 |

---

# 一、项目简介

## 1.1 项目定位

**TraceReview** 是一个面向 Pull Request 的 **Evidence-driven、Risk-aware 研发风险审查与安全修复系统**。

它接收 Git unified diff 或 GitHub Pull Request 事件，先通过确定性解析、Scanner 与 RiskProfile 判断风险面，再按需调用 Boundary Inspector / Behavior Inspector；只有高风险、弱证据或冲突场景才调用 Evidence Auditor。最终 Finding 经过确定性的 FindingGate 后，才能进入 ReviewReport。

这不是一次模型调用，而是一条可恢复、可重试、可审计、可评测的执行链：

```text
Manual Diff / GitHub PR
        │
        ▼
   DiffParser
        │
        ▼
   RiskProfile
        │
        ├── Local Scanner / Agent Skills
        │
        ▼
       Review Coordinator
   ┌────┴────┐
   ▼         ▼
Boundary Inspector   Behavior Inspector
按需执行      按需执行
   └────┬────┘
        ▼
     Findings
        │
  高风险/低置信/弱证据/冲突？
      │        │
     No       Yes
      │        ▼
      │     Evidence Auditor
      │      按需
      └───┬────┘
          ▼
      FindingGate
          │
          ▼
      ReviewReport
       ┌──┴─────────┐
       ▼            ▼
 GitHub Comment   Fix Proposal
                    │
             Before/After Verify
                    │
             WAITING_APPROVAL
                    │
              Human Approval
                    │
                    ▼
                 Draft PR
```

## 1.2 三层执行架构仍然保留

```text
ReviewHarness（PR Review 业务状态机）
└── AgentRuntime（通用执行引擎）
    ├── planning
    ├── executing
    │   └── Review Coordinator / Specialist / conditional Evidence Auditor
    │       └── BoundedRole（单角色 Tool/Final Loop）
    └── reviewing
```

职责边界：

- **ReviewHarness**：知道“一次 PR Review”有哪些业务阶段、什么时候生成最终报告。
- **AgentRuntime**：不知道模型具体如何思考，只负责节点执行、预算、重试、取消、Checkpoint、Resume 和 Trace。
- **BoundedRole**：负责一个 LLM Role 的 Tool Calling 循环、Token/时间预算和 Final 输出契约。

这三个抽象不为了包装而改名，因为它们本身能清楚回答“为什么存在”。

## 1.3 多 Agent 不再固定全量执行

当前角色重新命名为 Review Coordinator、Boundary Inspector、Behavior Inspector、Evidence Auditor，并保留原有职责边界但调整执行策略：

1. **Review Coordinator**：任务拆解、委派、返工、最终综合。
2. **Boundary Inspector**：输入边界、认证授权、敏感数据、注入、危险执行链。
3. **Behavior Inspector**：状态变化、异常、并发、资源生命周期、兼容性、测试相关风险。
4. **Evidence Auditor**：不发现新问题，只对候选 Finding 做匿名独立质疑；现在只在需要时调用。

新增的 `RiskProfile` 是确定性路由层，不是新 Agent。

## 1.4 Human-in-the-loop 成为显式边界

读代码、扫描和生成建议可以自动执行；**写 GitHub 的修复动作不能由 Specialist 直接完成**。

修复流程变为：

```text
Finding
  -> generate patch
  -> structural verification
  -> before/after repository tests
  -> awaiting-approval
  -> human approve
  -> re-check PR head SHA
  -> create fix branch
  -> Draft PR
```

Policy candidate 也采用同样思想：通过 Validation/Holdout 只能说明“候选可进入审批”，不能自动等价成“上线”。

---

# 二、简历写法

## 2.1 不再堆技术名词

不建议把下面这些全部并列写在简历第一行：

```text
Harness / Multi-Agent / Memory / Skill / Self-Evolution /
Redis / PostgreSQL / OTel / Prometheus / Canary / Shadow ...
```

真正应突出 5 个可被追问、且代码能支撑的工程判断。

## 2.2 推荐项目描述

**TraceReview：面向 Pull Request 的可恢复、风险感知多 Agent 代码审查与安全修复系统**

技术栈可写：Python、Agent Runtime、Tool Calling、SQLite/PostgreSQL、Redis Streams、GitHub Webhook、OpenTelemetry、Prometheus、Docker。

### 项目亮点 1：可恢复 Agent Runtime

针对 PR 审查涉及多次模型/工具调用、单节点失败后全量重跑成本高的问题，设计 `ReviewHarness -> AgentRuntime -> BoundedRole` 三层执行结构，统一管理节点预算、超时、重试、协作式取消、Checkpoint 和断点续跑，并记录完整 Run Trace。

### 项目亮点 2：Risk-aware Multi-Agent

针对固定 fan-out 导致简单 PR 也无条件调用所有 Reviewer、增加延迟和 Token 的问题，在 Planning/Executing 之间增加确定性 `RiskProfile`，根据变更路径、代码信号和复杂度按需启用 Boundary Inspector / Behavior Inspector；Evidence Auditor 只在高风险、弱证据、低置信或候选冲突时介入。

### 项目亮点 3：Context Engineering + Tool Contract

针对大 Diff、历史 Observation 和工具描述挤占上下文的问题，采用风险排序 Hunk Map-Reduce、Observation 摘要和 Tool Catalog 压缩；Tool Registry 对每个工具声明参数 Schema、角色权限、`side_effect / retryable / timeout_seconds`，让工具失败和副作用边界可控。

### 项目亮点 4：Evidence Gate + HITL Safe Fix

对模型 Finding 增加成立前提、影响和证据强度，通过 Location / Evidence / Severity / Confidence / Release 五类确定性 Gate 过滤不满足发布条件的结论。修复先在本地生成 patch 并执行 before/after 测试，进入 `awaiting-approval` 后由人工批准，批准时再次校验 PR Head SHA，再创建独立 Draft PR。

### 项目亮点 5：Evaluation + Observability

建设基于 100 个受控 PR Diff 的 Evaluation Harness，保留 Precision/Recall/F1/High-risk Recall/Clean Accuracy，并增加 Pre-Gate/Post-Gate Precision、FP Filter Rate、TP Loss Rate，同时记录 Agent/Tool/Token/Latency/Cost/Revision/Evidence Auditor 事实，支持效果迭代与失败归因。

## 2.3 面试时的叙事顺序

不要从“我用了多 Agent”开始。建议顺序：

```text
业务问题
→ 为什么单次 LLM Review 不够
→ 为什么 Scanner 与 Gate 必须确定性
→ 为什么部分场景需要多 Agent
→ 为什么不固定调用所有 Agent
→ 为什么修复需要 Human Approval
→ 怎么证明改动真的有效
```

---

# 三、前置知识

## 3.1 Pull Request 和 unified diff

TraceReview 的核心输入仍是 unified diff，不需要默认把整个仓库全量输入模型。

```diff
--- a/app.py
+++ b/app.py
@@ -1 +1,2 @@
-safe_call()
+password = "secret-value"
+eval(user_input)
```

`DiffParser` 会解析：

- 文件路径；
- hunk；
- 新增行行号；
- 删除行和上下文；
- 供后续 RiskProfile / Scanner / Gate 使用的精确位置。

本地规则仍尽量约束到新增行，避免把仓库原有旧问题作为“本次 PR 新引入风险”发布。

## 3.2 Webhook 和 HMAC-SHA256

GitHub 通过：

```text
POST /webhooks/github
```

向服务发送 PR 事件。

服务对**原始 body** 使用 Webhook Secret 计算 HMAC-SHA256，并使用常量时间比较校验 `X-Hub-Signature-256`。

Delivery ID + payload SHA-256 做幂等 claim：

- 同一 delivery 重放不会重复创建任务；
- 同一个 delivery ID 如果绑定了不同 payload，会拒绝；
- 评论采用 hidden marker 做 Upsert，避免重试产生重复评论。

新版 marker 为 TraceReview，同时能识别旧 EvoAgent marker 并迁移已有评论。

## 3.3 Review Coordinator/Specialist 主-子 Agent 协作：改成风险感知

核心主从结构保留，但 Review Coordinator 不再默认“Boundary Inspector + Behavior Inspector + Evidence Auditor 全部执行”。

`RiskProfile` 先输出：

```json
{
  "risk_domains": ["dynamic-execution"],
  "risk_level": "high",
  "requires_security_review": true,
  "requires_reliability_review": false,
  "auditor_recommended": true,
  "reasons": ["dynamic execution signal on changed line"]
}
```

然后 Review Coordinator 只对需要的 Specialist 创建 Assignment。

这样能回答：**为什么不是单 Agent？为什么也不是固定四 Agent？**

## 3.4 同步任务和异步任务

同步：

```text
POST /v1/reviews
```

适合本地调试和短 Diff。

异步：

```text
POST /v1/reviews?async=true
GET  /v1/tasks/{task_id}
```

GitHub Webhook 默认适合异步，因为多个 LLM Role 和 Repository Tool 调用不应该阻塞 Webhook HTTP 生命周期。

## 3.5 Agent Loop 与 Runtime

- Runtime 外层：Planning / Executing / Reviewing。
- Role 内层：Tool -> Observation -> Tool -> Final。

`BoundedRole` 有明确最大步数、Token 预算和时间预算，避免 Agent 无界循环。

## 3.6 Checkpoint 与幂等

两者解决不同问题：

- **Checkpoint**：计算执行到哪里；失败后从哪里恢复。
- **幂等**：外部副作用是否会重复发生。

外层保存 planning/executing/reviewing；内层保存 Review Coordinator session、Scanner、Delegation、Specialist、Revision、Evidence Auditor、Final 与 Execution Ledger。

修复 proposal 和最终 publication 也分别保存 checkpoint，人工批准不会重新“猜”之前验证过什么。

## 3.7 Scanner、Agent 与 Gate

三类组件职责仍然不同：

| 类型 | LLM | 作用 |
|---|---|---|
| Scanner | 否 | 确定性规则、AST/文本信号、动态 Scanner / Skill 底线 |
| Agent | 是 | 根据上下文理解风险、调用工具、补充证据 |
| Gate | 否 | 最终检查位置、证据、严重度、置信度、发布资格 |

**不把 Scanner/Gate Agent 化** 是一个重要架构取舍：这些约束越确定，越适合用程序逻辑保证。

## 3.8 OpenAI 兼容接口

仍支持 Chat Completions 风格 HTTP API，因此可连接 DeepSeek、OpenRouter 或自定义兼容服务。

新的公开环境变量以 `TRACEREVIEW_*` 为主；旧 `EVOAGENT_*` 保留兼容，且新变量优先。

## 3.9 Precision、Recall、F1 与 Gate 指标

基础指标：

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2PR / (P + R)
```

新版新增：

```text
Pre-Gate Precision
Post-Gate Precision
Gate FP Filter Rate
Gate TP Loss Rate
Gate Rejected / PR
```

原因：只看最终 F1 无法证明 FindingGate 是否真有价值；必须分别看 Gate 前后。

## 3.10 Validation 和 Holdout

Validation 用来选择候选；Holdout 用来检查是否针对公开验证集过拟合。

当前受控数据原始文件为 80 validation + 20 holdout，实验适配器可进一步按 repository 隔离形成 60 train / 20 validation / 20 holdout，用于受控对照。

## 3.11 SQLite、PostgreSQL 和 Redis

- SQLite：本地单机、测试。
- PostgreSQL：多实例共享 Task、Checkpoint、Memory、Evaluation、Skill、Audit。
- Redis Streams：异步队列、consumer group、lease、ACK、retry、DLQ，不作为主数据库。

本版还修复了 SQLite 测试中 connection 未及时关闭导致的 ResourceWarning：自定义 connection context manager 在事务结束后显式 close。

## 3.12 GitHub PAT

Fine-grained PAT 用于：

- 读取 PR diff / files；
- Upsert PR Review 评论；
- **人工批准后**创建 fix branch 与 Draft PR。

它不是登录 Secret、Webhook Secret，也不是 LLM API Key。

## 3.13 Harness Engineering

Harness 的价值没有变化：不让模型自由发挥，而是给 Agent 一条受约束执行轨道。

```text
目标/边界
→ 规划
→ Tool
→ 环境 Observation
→ 修正
→ Gate
→ 可审计结果
```

## 3.14 从“自进化”改为 Feedback-driven Review Policy Optimization

原来的反馈回流、Prompt/Skill candidate、Validation/Holdout、版本追踪和回滚能力保留，但**默认自动上线被取消**。

新版流程：

```text
confirmed feedback
    ↓
failure case
    ↓
candidate Prompt / SKILL.md
    ↓
Validation replay
    ↓
Holdout non-regression
    ↓
awaiting_approval
    ↓
human approval
    ↓
activate
```

可选 Canary / Shadow 可以继续做上线观察；Error Budget 超限可自动 fail-safe rollback，但 Shadow 达标只表示 `awaiting_approval`，不会自动提升 stable version。

这个改动的核心不是“名字变了”，而是**验证通过 ≠ 自动上线**。

---

# 四、项目背景

## 4.1 PR Review 的现实问题

### 问题一：单个大模型直接吃完整 PR 容易上下文过载

表现为：行号漂移、风格类误报、泛泛测试建议、上下文无关信息过多。

对应方案：DiffParser + Risk-ranked Hunk Map/Reduce + Tool Catalog/Observation 压缩。

### 问题二：安全、可靠性、业务正确性的关注点不同

对应方案：保留 Boundary Inspector 和 Behavior Inspector，但改为 RiskProfile 决定是否需要，而非为了展示多 Agent 全部调用。

### 问题三：LLM 结论缺少确定性证据约束

对应方案：Finding 中增加 `precondition / impact / evidence_strength`，最终由 FindingGate 验证。

### 问题四：写操作比读操作风险高

对应方案：评论可以幂等 Upsert；Fix 必须“生成/验证”和“写 GitHub”两阶段分离，后者人工批准。

### 问题五：Agent 效果难量化

对应方案：Evaluation Harness + Agent/Tool/Cost Trace；不仅报 F1，还看 Gate、Evidence Auditor 和 Runtime 的实际贡献。

## 4.2 TraceReview 解决什么

```text
DiffParser              精确变更范围
RiskProfile             决定需要谁审
Scanner/Skills          确定性底线与领域策略
Review Coordinator/Specialist             上下文推理与证据收集
Conditional Evidence Audit      只处理高风险/冲突/弱证据
FindingGate             确定性发布门禁
ReviewHarness/Runtime   状态、恢复、预算、Trace
GitHub integration      自动化入口和幂等评论
VerifiedPatchFixer      受限 patch + before/after verification
Human approval          高风险写操作边界
Evaluation              效果和迭代依据
```

---

# 五、项目运行

## 5.1 环境要求

Python 3.11+：

```bash
python -m pip install -r requirements.txt
```

## 5.2 配置管理员和认证

推荐：

```env
TRACEREVIEW_AUTH_REQUIRED=true
TRACEREVIEW_AUTH_SECRET=<至少 32 字节随机值>
TRACEREVIEW_BOOTSTRAP_ADMIN_USERNAME=admin
TRACEREVIEW_BOOTSTRAP_ADMIN_PASSWORD=<强密码>
```

角色继续保留 admin / maintainer / auditor；权限由 RBAC 控制。

## 5.3 配置模型

自定义兼容端点：

```env
TRACEREVIEW_LLM_PROVIDER=custom
TRACEREVIEW_LLM_BASE_URL=https://example.com/v1
TRACEREVIEW_LLM_API_KEY=<token>
TRACEREVIEW_LLM_MODEL=<model>
```

也可配置 DeepSeek/OpenRouter。旧 `EVOAGENT_*` 作为兼容 alias。

## 5.4 启动

```bash
python -m tracereview
```

默认：

```text
http://127.0.0.1:8080/
```

内部 `evoagent` package 继续保留，目的是兼容历史 import、checkpoint 和 DB 记录，不是对外品牌。

## 5.5 手动提交同步审查

```text
POST /v1/reviews
```

Payload 仍包含 repository、pull_request、mode、diff。

## 5.6 异步审查、取消与恢复

```text
POST /v1/reviews?async=true
GET  /v1/tasks/{task_id}
POST /v1/tasks/{task_id}/cancel
POST /v1/tasks/{task_id}/resume
```

取消是协作式取消：在 Runtime 节点边界检查；恢复从持久化 Checkpoint 继续。

## 5.7 关键参数

仍保留：

- Diff 大小限制；
- Runtime max steps；
- Runtime timeout；
- 单 Role Token / time budget；
- enabled agents；
- repository repair test command；
- Redis / DB / OTel / Prometheus 配置。

新版本不要求通过配置“硬启用所有 Agent”，RiskProfile 会进一步裁剪实际角色。

## 5.8 前端使用方式

1. 手动 Review：粘贴 Diff。
2. GitHub 自动 Review：Webhook 创建任务和评论。
3. 任务详情页可以查看 Risk Profile、协作摘要、Gate 结果、Execution Trace。
4. Fix 按钮先生成和验证 proposal；UI 再显式确认是否批准写 GitHub。
5. Review Policy 实验室显示 candidate 的 replay 结果与 `awaiting_approval` 状态。

---

# 六、GitHub Pull Request 连接说明

## 6.1 Webhook 地址

GitHub 必须访问：

```text
https://<public-host>/webhooks/github
```

本地调试仍可用 Cloudflare Quick Tunnel 或其他 HTTPS 隧道。

## 6.2 Webhook 配置

```text
Settings -> Webhooks -> Add webhook
Content type: application/json
Event: Pull requests
Secret: 与 TRACEREVIEW_GITHUB_WEBHOOK_SECRET 一致
```

## 6.3 Fine-grained Token 权限

最小权限仍应按仓库限定，通常需要：

- Contents: Read（修复创建分支时需要相应写权限，按实际 GitHub API 配置）；
- Pull requests: Read/Write；
- Issues: 若评论 API 路径需要则 Read/Write。

原则：权限只授予项目真实需要的仓库和动作。

## 6.4 Webhook 幂等

Delivery ID claim + body hash 绑定；重复 delivery 不会重复入队。

## 6.5 评论 Upsert

评论带隐藏 marker：

```text
<!-- tracereview-review:<task-id> -->
```

同时识别旧 marker，避免品牌迁移后重复评论。

## 6.6 修复流程发生了关键变化

以前“验证通过 -> 直接创建 Draft PR”被拆为：

```text
POST /v1/tasks/{task_id}/fix
    ↓
awaiting-approval
    ↓
POST /v1/tasks/{task_id}/fix/approve
    ↓
重新校验 PR Head SHA
    ↓
Draft PR
```

如果等待期间 PR 有新 commit，旧 patch 会被拒绝，必须重新生成并验证。

---

# 七、项目流程

## 7.1 整体架构

```text
API / GitHub Webhook
→ 鉴权、Tenant/Repository Authorization、大小校验
→ Task + 原始 Diff 落库
→ 同步 Runtime 或 Redis Streams
→ ReviewHarness
→ Planning
→ RiskProfile + Scanner + Skills
→ Risk-aware Review Coordinator/Specialist
→ Conditional Evidence Audit
→ FindingGate
→ Reviewing / Report
→ GitHub Comment / Feedback / Policy Candidate / Fix Proposal
→ 高风险写操作 Human Approval
```

## 7.2 Planning

`parse_unified_diff()` 解析文件和新增行。无有效新增行会生成 execution error，而不是让后续模型猜输入。

Planning Checkpoint 仍保存 parsed diff 信息。

## 7.3 RiskProfile（新版新增的关键步骤）

`evoagent/risk_profile.py` 根据：

- 文件路径；
- 新增行代码信号；
- auth / injection / dynamic execution / state / concurrency / resource lifecycle / compatibility；
- TODO/FIXME/debug/print 等 quality regression signal；
- production file / test file 比例；
- changed-line 数量和复杂度；

生成确定性 Profile。

它的作用不是替代 LLM 判断风险，而是回答：**本次 Review 值不值得调用哪个 Specialist？**

## 7.4 Scanner

系统先运行本地规则、动态 Scanner、激活 Skill。重复结果按 Finding identity 归并。

Scanner 仍然是 deterministic baseline。

## 7.5 Review Coordinator 委派

Review Coordinator 收到 Diff、RiskProfile、Scanner、可用 Specialist 和 Skill。

自动 Routing 规则：

- Boundary signal -> Boundary Inspector；
- 普通 production change -> Behavior Inspector fallback；
- behavior/reliability signal -> Behavior Inspector；
- 明确指定 Skill 可以覆盖自动裁剪；
- 文档/纯测试变化可减少无必要角色调用。

## 7.6 Specialist 并发与返工

需要的 Specialist 可以并发；失败结果写入 session，不一定立即导致整个 Review 失败。

Review Coordinator 可发起 revision，要求原 Specialist 补充证据。Revision 仍受最大轮数、Runtime/Role budget 限制。

## 7.7 Conditional Evidence Audit

Evidence Auditor 只在以下情况介入：

- RiskProfile recommend；
- High/Critical；
- confidence < 0.70；
- evidence weak；
- 多来源候选需要独立裁决。

Evidence Auditor 看到隐藏来源身份的 candidate，不能创建新 Finding。

如果不需要 Evidence Auditor，系统记录：

```json
{
  "audit_policy": {
    "mode": "conditional",
    "invoked": false,
    "reasons": []
  }
}
```

这使 Evidence Auditor 的成本/收益可以直接评测。

## 7.8 FindingGate

五类 Gate：

1. **Location Gate**：必须与本次 changed line 对齐。
2. **Evidence Gate**：检查 precise code / evidence refs / call chain。
3. **Severity Gate**：声明新契约的 High/Critical 必须有 precondition + impact。
4. **Confidence Gate**：低于发布阈值拒绝。
5. **Release Gate**：高危结论必须有 fix 和 verification/test 建议。

被拒 Finding 写入 `execution.rejected_findings`，并形成 Gate effect 指标。

## 7.9 Reviewing 与报告

ReviewReport 汇总：

- risk；
- accepted findings；
- RiskProfile；
- actual roles；
- Evidence Auditor policy；
- gate effect；
- Tool/Model/Token/Cost/Latency；
- checkpoint / trace；
- repository context。

## 7.10 Checkpoint 与恢复

仍保存两级 checkpoint。

新增值得注意的两个业务 checkpoint：

```text
repair-proposal
repair-publication
```

它们把“已验证 patch”和“真正写 GitHub”分离。

## 7.11 任务结束后的可选动作

- GitHub comment Upsert；
- 人工 feedback；
- 生成 Review Policy candidate；
- 生成 verified repair proposal；
- 人工批准后 Draft PR。

---

# 八、多 Agent 协作

## 8.1 为什么仍然保留多 Agent

这里不是因为“多 Agent 比单 Agent 高级”，而是因为 PR Review 里 Boundary Inspector 和 Behavior Inspector 的：

- 目标不同；
- 工具权限不同；
- 关注上下文不同；
- Finding 判断标准不同。

拆分后可以限制每个 Role 看到的上下文与 Tool，减少职责混杂。

## 8.2 为什么又不固定全量调用

简单 logging/refactor 不需要 Boundary Inspector + Behavior Inspector + Evidence Auditor 都跑。

RiskProfile 先决定角色，可减少：

- Token；
- latency；
- 不相关上下文；
- 不必要的候选合并冲突。

## 8.3 角色契约

| Role | 主要职责 | 典型 Tool | 输出 |
|---|---|---|---|
| Review Coordinator | 任务规划、Delegation、Revision、Final | 读 diff / symbol / repo controls | Delegation / Final indices |
| Boundary Inspector | 输入边界、权限、敏感数据、注入 | search/read/symbol/AST | Findings |
| Behavior Inspector | 状态、异常、并发、资源、兼容性 | search/read/tests/checks | Findings |
| Evidence Auditor | 匿名复核证据和 severity | 只读 evidence 工具 | accept/reject/adjust |

## 8.4 为什么没有单独增加 TestImpact Agent

Test impact 更适合作为 Behavior Inspector 可调用的**确定性工具**：例如 locate tests、changed-symbol test reference、repository checks。

这体现“不是所有能力都要 Agent 化”。

## 8.5 Handoff 失败怎么处理

- Specialist failed：记录状态，Review Coordinator 可基于剩余结果继续或 Revision；
- 超时：Role/Runtime budget 终止；
- 重复 Finding：Finding identity 去重；
- Evidence Auditor 不可用且不是必需：走 Gate；
- Runtime 节点失败：Checkpoint + node retry / resume；
- Task cancel：协作式取消。

---

# 九、Agent Runtime

## 9.1 Runtime 仍是通用执行引擎

它不理解 Boundary Inspector Prompt，也不决定 Finding 对不对。

主要负责：

```text
node state
max steps
node retries
timeout
cancel
checkpoint
resume
trace / span
```

## 9.2 节点错误分类

可重试异常与不可重试异常仍通过 Runtime 边界处理。节点失败写 failed checkpoint，成功写 completed checkpoint。

## 9.3 Resume

已完成节点从 checkpoint 恢复，不重新执行；Agentic session 也可以从内层 checkpoint 恢复，避免重复模型调用。

## 9.4 Tool metadata（新增）

`AgentTool` 现在包含：

```python
name
description
parameters
handler
side_effect
retryable
timeout_seconds
```

Tool Catalog 将这些元数据带入上下文，方便 Agent 和系统知道某个失败能否重试，以及动作是否有副作用。

## 9.5 写操作为什么不放普通 ToolRegistry

普通 Specialist 主要使用只读工具。GitHub branch / Draft PR 等写操作仍放 Service + explicit approval 边界，避免模型通过自然语言 Tool Call 直接产生不可逆副作用。

---

# 十、Agent Loop

## 10.1 BoundedRole

每个 Role 执行：

```text
Managed Context
  ↓
model response
  ├─ tool -> validate args -> invoke -> observation -> next step
  └─ final -> schema validation -> return
```

最大步数、Token 和时间均有界。

## 10.2 Tool 参数先验证

ToolRegistry 使用参数 Schema 检查 required 字段和基本类型，Handler 不直接接收未经验证的任意 JSON。

## 10.3 Tool failure 的策略

- `retryable=true`：可在上层策略允许时重试；
- `retryable=false`：应换路径或结束；
- `side_effect=true`：不能盲目自动重放；
- timeout：工具自身有时间边界。

## 10.4 Final 不是统一结构

- Review Coordinator Final：选择/综合 Finding；
- Specialist Final：Finding 列表；
- Evidence Auditor Final：accept/reject、objection、confidence adjustment；

保留角色输出差异，而不是为了统一 JSON 抹平职责。

---

# 十一、Harness

## 11.1 ReviewHarness 负责业务语义

它回答：

> 一次 PR 审查从收到到出报告，完整生命周期如何管理？

Runtime 则回答：

> 这些节点怎样可靠执行？

## 11.2 三节点

```text
planning
executing
reviewing
```

失败/取消仍有明确任务状态，终态落库。

## 11.3 HITL 为什么不塞进 AgentRuntime

“是否批准写 GitHub”是业务决策，不是通用执行引擎能力，因此审批状态保存在 Service/Checkpoint 业务边界；Runtime 不应该知道“Draft PR 是什么”。

---

# 十二、上下文压缩详解

## 12.1 为什么上下文工程是核心

大 PR 的问题不是只有 token 不够，更重要的是无关 hunk、旧 Observation、完整 Tool Schema 会降低当前判断质量。

## 12.2 Diff 的 Hunk Map-Reduce

流程：

1. parse Hunk；
2. risk score；
3. 高风险 Hunk 优先；
4. Map 每个 Hunk 的关键信息；
5. Reduce 成受 Token budget 限制的 semantic diff。

Risk signal 会考虑 auth/security/dynamic execution/state/concurrency 等。

## 12.3 Observation 摘要

旧 Tool Observation 不全文堆叠：

- 保留 Tool 名称；
- 保留成功/失败；
- 保留 evidence ref；
- 保留 Finding 仍引用的 Observation；
- 压缩旧内容摘要。

## 12.4 Tool Catalog 压缩（新版新增）

上下文压力高时：

```text
完整 description + 完整 schema
        ↓
clipped description + typed args
        ↓
name + required + argument names + side_effect + retryable
```

目的不是删掉工具，而是在极端预算下仍保留“能否调用、需要什么参数、是否有副作用”这些决策信息。

## 12.5 Memory recall 进入上下文

长期历史不是无条件加载。按 tenant / repository / scope / query 召回，并进行数量、长度和 TTL 限制。

---

# 十三、Tool Calling 详解

## 13.1 Tool Registry

每个工具由：

```python
AgentTool(
    name,
    description,
    parameters,
    handler,
    side_effect=False,
    retryable=True,
    timeout_seconds=None,
)
```

组成。

## 13.2 为什么不直接开放 Shell

项目对不同 Role 使用 allowlist，Agent 只能调用它职责范围内的 Repository Tool；这比“模型自己生成 shell”更可控。

## 13.3 典型只读工具

例如：

- list repository；
- search repository/diff；
- read file；
- changed line；
- symbol / AST；
- git context；
- locate tests；
- run scanner / repository checks。

## 13.4 工具 Observation 与 Evidence

Tool Handler 返回结构化 Observation，系统写入 Execution Ledger。Finding 可以通过 `evidence_refs` 指向 Observation ID，而不是只写一句自然语言“我看到了问题”。

## 13.5 Tool failure 怎么兜底

- 参数不完整：调用前拒绝；
- 找不到文件/符号：Observation 标记失败，Agent 可换工具；
- repository check 超时：由 timeout 边界终止；
- 写操作：不通过普通 Specialist tool 自动执行，转业务审批。

---

# 十四、Memory 记忆管理

## 14.1 新版不再主打“四层 Memory”

代码底层为了历史 DB 兼容，仍接受：

```text
working / episodic / semantic / procedural
```

但业务解释简化为三个真正有用的概念。

## 14.2 Task Context

对应 legacy `working`：

- 当前 Tool Observation；
- Role 状态；
- Evidence ID；
- 当前 task 执行信息。

任务结束后可以释放。

## 14.3 Review History

对应 legacy `episodic`：

- 历史 Finding；
- Gate accepted/rejected；
- Task summary；
- 过去协作结果。

用于相似仓库 Review 时参考历史经验。

## 14.4 Repository Feedback

对应 legacy `semantic`：

- false positive；
- missed issue；
- bad fix；
- 仓库约定。

它是 Review Policy candidate 的重要输入，但反馈 note 不会被直接当作高权限系统指令。

## 14.5 Procedural 兼容范围

legacy `procedural` 暂保用于历史数据和已有 API/测试兼容，但不作为新版简历亮点。

## 14.6 召回与隔离

Memory 由 tenant + repository 隔离；Working 还按 task + agent 隔离。

支持 TTL、importance、recall limit 和 expired purge。

---

# 十五、Skill

## 15.1 Skill 为什么保留

Skill 不是为了增加 Agent 数量，而是为了**把领域 Review 规则、allowed tools 和 supporting resources 从核心 Prompt 中解耦**。

标准包：

```text
skills/<name>/
├── SKILL.md
└── supporting files...
```

## 15.2 Skill Registry

负责：

- YAML frontmatter；
- 名称/描述；
- allowed tools；
- supporting resources；
- 文件大小与路径安全；
- tenant/version；
- active version。

## 15.3 内置领域

可包括 security、correctness、reliability、database、api compatibility、performance、observability、test quality、code quality。

## 15.4 Skill 与 Specialist 的关系

RiskProfile 自动决定基础 Specialist；显式选择的 Skill 可以让对应 Specialist/领域任务不被自动裁剪。

## 15.5 Skill candidate 生命周期已修改

以前候选通过 replay gate 后可以走自动激活逻辑；新版默认：

```text
propose
→ validate artifact
→ replay Validation
→ Holdout non-regression
→ awaiting_approval
→ explicit activate
```

只有批准后 active version 才切换，自动 feedback 才 resolve。

## 15.6 Shadow/Canary

可选部署观察仍保留：

- Canary 可以按 hash 稳定分桶；
- Error Budget 超限自动 rollback；
- Shadow 记录 candidate / primary disagreement；
- 达到样本量且 disagreement/error 合格时进入 `awaiting_approval`；
- `POST /v1/deployments/{name}/approve` 才人工提升 stable version。

---

# 十六、任务队列与持久化

## 16.1 本地队列

默认 in-process worker 适合开发和单实例。

## 16.2 Redis Streams

多实例时：

```text
producer
→ Redis Stream
→ consumer group worker
→ lease
→ execute
→ ACK
```

失败超过上限进入 DLQ；Pending Entry、claim/lease 用于 worker 崩溃恢复。

## 16.3 PostgreSQL

共享保存：Task、payload、Trace、Checkpoint、Agent messages、Memory、Feedback、Evaluation、Skill versions、deployments、Audit 等。

本版补齐 PostgreSQL 对 Shadow observation / human deployment approval 的 schema 和方法，与 SQLite 行为保持一致。

## 16.4 SQLite

单文件本地运行。新版连接 context manager 在事务结束后显式关闭 connection，避免大量测试 ResourceWarning。

## 16.5 多租户

Tenant ID 会进入：

- Task；
- Memory；
- Skill；
- Deployment；
- Failure case；
- Audit；
- Repository grants。

RBAC：admin / maintainer / auditor；权限和仓库授权由 Service/API 边界检查。

---

# 十七、评测

## 17.1 当前数据集

当前用户提供的 `evaluation_data/pr_diff_100.jsonl`：

- 100 条 PR Diff；
- 40 风险 case；
- 60 clean case；
- 10 个 repository，每个 10 条；
- 原始 split：80 Validation / 20 Holdout。

受控实验适配器会按 repository 重新形成 60 Train / 20 Validation / 20 Holdout，用于不同实验阶段隔离。

## 17.2 一对一 Finding Matching

Prediction 与 Ground Truth 通过：

- path；
- line/range；
- rule_id；
- CWE（存在时）；

做 one-to-one matching，避免重复预测把同一个真实问题算多次 TP。

## 17.3 基础指标

- Precision；
- Recall；
- F1；
- Severity Accuracy；
- High Risk Recall；
- Clean Accuracy；
- Safe Fix Rate；
- E2E Fix Rate；
- Execution Success Rate。

## 17.4 新增 Gate 指标

- Pre-Gate Precision；
- Post-Gate Precision；
- Gate FP Filter Rate；
- Gate TP Loss Rate；
- Gate Rejected / PR。

这些指标用于回答：**Gate 是真提升质量，还是只是把真实问题也删掉？**

## 17.5 Agent/效率指标

运行中还会记录：

- actual roles；
- Evidence Auditor invoked/reason；
- average role/LLM calls；
- Tool calls/success；
- Revision；
- Token；
- latency；
- cost。

## 17.6 当前受控离线实验的正确解读

命令：

```bash
python scripts/run_controlled_experiments.py \
  --dataset evaluation_data/pr_diff_100.jsonl \
  --output output/controlled-experiments/evaluation.json
```

当前运行明确标记：

```text
controlled-offline-no-llm
```

因此它证明的是 deterministic rules、编排计数和 Skill/Policy gate 行为，**不能把这些数字直接宣称为真实生产 LLM 的提升证据**。

当前受控运行的规则基线：

```text
Precision        82.50%
Recall           82.50%
F1               82.50%
High-risk Recall 94.74%
Clean Accuracy   91.67%
Safe Fix         78.79%
E2E Fix          65.00%
```

五臂受控离线实验当前输出：

| Arm | F1 | High-risk Recall | Clean Accuracy | 模拟角色调用/PR |
|---|---:|---:|---:|---:|
| model-baseline | 71.43% | 84.21% | 91.67% | 1.00 |
| model-plus-scanner | 82.50% | 94.74% | 91.67% | 1.00 |
| routed-specialists | 82.50% | 94.74% | 91.67% | 3.82 |
| routed-specialists-audited | 90.41% | 94.74% | 100.00% | 4.05 |
| routed-specialists-policy | 90.41% | 94.74% | 100.00% | 4.55 |

隐藏 Holdout 的报告也明确指出，Evidence Auditor / Multi-Agent / Review Policy 的对应增益不能从该离线受控结果中单独证明。因此简历和面试不要夸大。

## 17.7 Review Policy 候选实验

当前受控 Skill/Policy 候选在 Validation 没有达到最小 F1 提升，因此被 rejected，Holdout activation gate blocked。这反而证明系统没有为了“自进化故事”强行激活一个没有证据的版本。

## 17.8 可选数据缺失的处理

`evaluation_data/prompt_evolution_130.jsonl` 没有由用户提供；对应 proof test 显式 skip，而不是伪造样本让测试通过。

---

# 十八、代码解读

## 18.1 公开入口

```text
tracereview/__main__.py
```

执行 `python -m tracereview`。

内部 `evoagent/` 暂留兼容。

## 18.2 核心文件

| 文件 | 当前职责 | 本次主要改动 |
|---|---|---|
| `evoagent/harness.py` | PR Review 生命周期 | 保留三节点，品牌/报告语义更新 |
| `evoagent/runtime.py` | Runtime / BoundedRole / ToolRegistry | AgentTool 增 side_effect/retryable/timeout |
| `evoagent/risk_profile.py` | 确定性 Risk Routing | **新增** |
| `evoagent/agentic_core.py` | Review Coordinator/Specialist/Evidence Auditor 协作 | Risk-aware worker routing、conditional Evidence Auditor、pre-gate metrics |
| `evoagent/models.py` | Finding / Report 模型 | Finding 墠 contract 字段 |
| `evoagent/gates.py` | FindingGate | 新增 evidence strength / severity contract |
| `evoagent/context_manager.py` | Context Engineering | Tool Catalog 压缩，继续 Hunk Map-Reduce |
| `evoagent/memory.py` | Memory persistence/recall | 对外三类业务语义，legacy scope 兼容 |
| `evoagent/patching.py` | Verified patch | prepare / publish 两阶段 + stale SHA 拦截 |
| `evoagent/service.py` | 业务 Service | fix proposal/approval checkpoint |
| `evoagent/skill_evolution.py` | Skill candidate | replay pass 后 awaiting_approval |
| `evoagent/evolution.py` | Prompt candidate | 默认 manual activation |
| `evoagent/rollout.py` | Canary/Shadow | Shadow 合格只等待审批，不自动 promote |
| `evoagent/store.py` | SQLite | approval/deployment、connection close |
| `evoagent/postgres_store.py` | PostgreSQL | 补齐 shadow/approval parity |
| `evoagent/evaluation_v2.py` | Evaluation | pre/post Gate 等指标 |
| `evoagent/github.py` | GitHub API | 新/旧 comment marker 迁移 |
| `evoagent/api.py` | HTTP API | fix approval / deployment approval endpoints |
| `web/*` | UI | TraceReview/Risk-aware/HITL 文案与交互 |

## 18.3 代码改动规模

与原始工作目录相比，本版：

- 修改约 40 余个已有文件；
- 新增 `risk_profile.py`、`tracereview` public entrypoint、新行为测试；
- 没有为了差异删除 Runtime/Store/Queue 等成熟代码。

## 18.4 为什么没有重命名所有内部文件

全面重命名 `evoagent` namespace 会同时影响：

- checkpoint 中的组件标识；
- 旧数据库；
- import path；
- metrics / scripts / tests；
- 迁移成本。

因此本版对外使用 TraceReview，内部 namespace 暂留兼容。这是迁移策略，不是架构依赖。

---

# 十九、高频面试问答

## 1. 为什么不是直接让一个大模型 Review PR？

单模型可以作为 baseline，但大 Diff 容易上下文过载，而且安全和可靠性关注点不同。项目用 Scanner 做确定性底线，用 RiskProfile 决定需要哪个 Specialist，最后 FindingGate 统一发布约束。

## 2. 为什么一定要 Multi-Agent？

并不是所有 PR 都用 Multi-Agent。只有风险面需要不同职责/工具权限时才拆 Boundary Inspector 和 Behavior Inspector；简单场景可以只执行一个 Specialist。拆分降低的是职责混杂和上下文过载，而不是为了增加角色数量。

## 3. 为什么 RiskProfile 不直接让 LLM 判断？

Routing 是成本和可靠性边界。先用确定性 path/code signal 做可解释路由，即使模型 Provider 异常也能知道为什么选择了某个 Specialist；Specialist 仍负责更深的语义判断。

## 4. RiskProfile 判断错了怎么办？

有三层兜底：Local Scanner 独立运行；普通 production change 默认 Behavior Inspector fallback；显式指定 Skill 可以覆盖自动裁剪。Profile 也写入 Trace，便于评测误路由。

## 5. 为什么 Evidence Auditor 不再每次调用？

普通 Finding 已有 deterministic Gate。Evidence Auditor 的价值主要在高风险、弱证据、低置信和冲突候选；always-on 会增加 Token 和 latency。系统记录 Evidence Auditor invoked/reason，可以用评测决定策略是否值得。

## 6. Evidence Auditor 会不会凭空发明新漏洞？

不会。Evidence Auditor 输入隐藏候选来源，只能 accept/reject、质疑、调整置信度和 evidence；协议不允许创建新 Finding。

## 7. Runtime、Harness、BoundedRole 各做什么？

- Harness：PR Review 业务生命周期；
- Runtime：节点执行可靠性；
- BoundedRole：单个 LLM Role 的 Tool/Final 循环。

## 8. 为什么要两级 Checkpoint？

外层节点失败时不用重做 planning；内层 Agent session 失败时不用重做已经完成的 Scanner/Specialist/Evidence Auditor。这样能显著减少重复模型/工具成本。

## 9. Checkpoint 与幂等是什么关系？

Checkpoint 防重复计算；幂等防重复副作用。Webhook Delivery claim、comment marker Upsert、Fix approval 的 stale SHA 校验属于幂等/副作用治理。

## 10. FindingGate 为什么不用 LLM？

位置、证据存在性、置信阈值、High/Critical 发布条件都适合确定性代码。让 LLM 自己判断“自己是否合格”会削弱兜底价值。

## 11. 新 Finding 为什么增加 precondition 和 impact？

高严重度不应只有一句 title。必须说明在什么前提下成立、会造成什么影响，Gate 才能验证 severity 是否有依据。

## 12. Tool failure 怎么处理？

参数在 Handler 前校验；Tool 有 retryable/timeout metadata；失败 Observation 返回 Agent 决定换路径。副作用 Tool 不做盲目自动重试。

## 13. 为什么不直接给 Agent Shell？

代码审查主要需要有限的读/搜索/AST/Test 工具。Allowlist + Schema 更容易审计和控制，GitHub 写操作由 Service/HITL 边界处理。

## 14. Memory 为什么从四层改成三类？

代码底层保留 legacy scope 兼容，但业务真正需要解释的是当前任务、历史 Review、仓库反馈。避免为了“Memory 概念完整”保留没有明确业务价值的宣传。

## 15. Repository Feedback 会不会 Prompt Injection？

Feedback note 作为事实/失败案例使用，不直接变成高权限系统指令；学习规则 ID 还有格式校验，candidate 必须经过 replay gate。

## 16. 为什么 Review Policy 通过 Holdout 还要人工批准？

Holdout 只是离线证据，不能证明真实线上没有未知风险。Policy 改变的是后续 Agent 行为，因此通过 gate 只到 `awaiting_approval`。

## 17. Canary/Shadow 为什么还保留？

它们用于上线观察，不作为自动 promotion 的借口。Error Budget 超限可 fail-safe rollback；Shadow 达标后仍需人工 approve stable version。

## 18. 为什么自动修复要分两步？

生成 patch、运行测试是只读/本地验证；创建 Git branch/PR 是外部副作用。两者风险等级不同，所以必须拆开。

## 19. 等待修复审批时 PR 又有新 commit 怎么办？

批准阶段重新读取当前 PR Head SHA；与 proposal 的 source_sha 不同则拒绝，防止把基于旧代码验证的 patch 写到新版本。

## 20. 如何证明 FindingGate 有价值？

比较 Pre-Gate 和 Post-Gate Precision，同时看 FP Filter Rate 和 TP Loss Rate。只看最终 F1 无法区分是 Agent 提升还是 Gate 过滤。

## 21. 100 条数据够不够？

它适合受控回归和功能对照，不应宣称等价于生产效果。真实上线应扩充跨仓库真实 PR、边界 case、恶意输入，并锁定隐藏 Holdout。

## 22. 为什么受控实验写 `controlled-offline-no-llm`？

因为当前脚本没有真正调用 LLM。报告主动限制 claim scope，避免把确定性规则/编排模拟结果包装成模型能力。

## 23. Redis 为什么用 Streams？

Webhook 不应等待长 LLM Review；Streams 提供 consumer group、ACK、Pending/lease、重试和 DLQ，适合多 Specialist 异步任务。

## 24. SQLite 和 PostgreSQL 为什么两个都要？

本地开发用 SQLite 零部署；多实例生产需要 PostgreSQL 共享 Task、Checkpoint、Memory、Skill、Audit。Store API 保持同一语义。

## 25. 为什么内部还叫 evoagent？

这是兼容历史 import/checkpoint/DB 的迁移选择。对外入口和配置已经是 TraceReview；如果未来完成数据迁移，可以再删除 legacy namespace，而不是在功能改造阶段一次性破坏兼容。

---

# 二十一、项目面经（持续更新ing）

> 原上传 PDF 在“十九、高频面试问答”之后出现“二十一、项目面经（持续更新ing）”，没有单列“二十”。这里保持原文档的章节编号习惯。

## 21.1 面试官可能从 Runtime 深挖

**Q：一个 Task 从 PENDING 到 SUCCESS 经历哪些状态？**

可回答：Service 创建任务与 payload；Harness 切 RUNNING；Runtime 顺序执行 planning/executing/reviewing；每个 node checkpoint；成功 ReviewReport 落库，失败/取消保存终态。

**追问：Specialist 中途挂了为什么不会从头开始？**

外层 planning 已 completed，Runtime resume 直接合并 checkpoint；agentic inner session 也保存 Scanner、Delegation、Specialist、Evidence Auditor 和 Ledger。

## 21.2 从 Multi-Agent 深挖

**Q：为什么不把 Boundary Inspector 和 Behavior Inspector 合成一个 Prompt？**

回答职责/上下文/Tool 权限不同，并强调不是每次都拆；RiskProfile 能只选择一个 Specialist。

**追问：怎么量化拆分值得？**

看准确性之外还要看 calls/PR、Token/PR、p50/p95、Revision、Evidence Auditor invoke rate；用 single vs multi ablation 比较。

## 21.3 从 Tool Calling 深挖

**Q：工具为什么需要 side_effect 字段？**

因为重试语义不同。只读 search 可以安全 retry，GitHub write 不能无脑重复。副作用动作甚至不交给普通 Specialist，而走业务审批。

## 21.4 从 Context 深挖

**Q：Diff 太大怎么处理？**

Hunk Map-Reduce + risk ranking；保留 high-risk hunk 细节，压缩低风险 hunk；旧 Observation 摘要，Tool Catalog 在压力下进一步收缩。

## 21.5 从 Evaluation 深挖

**Q：为什么要 repository-level split？**

避免同一个 repository 的相似规则/代码风格同时出现在 Validation 和 Holdout，降低数据泄漏。

**Q：为什么 candidate 没提升还保留实验？**

因为评测系统的价值就是能拒绝无证据改动；“没有提升”也是有效结论。

## 21.6 从 HITL 深挖

**Q：自动修复已经测试通过了为什么不能直接发 PR？**

测试覆盖有限；且 PR 可能在验证后发生变化。审批阶段重新校验 Head SHA，并由有权限用户明确触发外部写操作。

---

# 学习总结

## 1. 好 Agent 项目首先是工程系统

这个项目真正值得保留的不是“用了几个 Agent”，而是：

```text
业务状态机
+ 通用 Runtime
+ Tool Contract
+ Context Engineering
+ Deterministic Gate
+ Persistent State
+ Evaluation
+ Observability
+ Human Approval
```

## 2. 不要把所有能力都 Agent 化

DiffParser、RiskProfile、Scanner、FindingGate、RepairVerifier 都是确定性组件；只有需要上下文推理和职责分离的部分使用 LLM Role。

## 3. 多 Agent 的关键是“什么时候不调用”

RiskProfile + Conditional Evidence Audit 比单纯增加 Reviewer 数量更能体现架构判断。

## 4. 评测通过不等于上线

Validation/Holdout 是必要门槛，但 Policy/Fix 影响后续系统行为或外部 GitHub 状态，仍需要明确审批边界。

## 5. 简历只写能解释的 5 个点

最终建议围绕：

1. Runtime + Checkpoint；
2. Risk-aware Multi-Agent；
3. Context + Tool Contract；
4. FindingGate + Safe Fix/HITL；
5. Evaluation + Observability。

其它 Redis、PostgreSQL、Skill、RBAC、OTel、Canary/Shadow 都作为被追问后的工程细节展开。

---

# 附录 A：改造前后对应表

| 原设计 | 当前设计 | 代码 |
|---|---|---|
| 固定 Boundary Inspector + Behavior Inspector | RiskProfile 按需启用 | `risk_profile.py`, `agentic_core.py` |
| Evidence Auditor 每次运行 | High-risk/weak/conflict conditional | `agentic_core.py` |
| Finding 基础字段 | + precondition/impact/evidence_strength | `models.py`, `gates.py` |
| Gate 主要检查位置/证据/置信 | + Severity Contract + Gate effect metrics | `gates.py`, `evaluation_v2.py` |
| Tool 仅 name/schema/handler | + side_effect/retryable/timeout | `runtime.py` |
| 四层 Memory 对外叙事 | Task Context / Review History / Repo Feedback | `memory.py` |
| Candidate gate 后可自动激活 | replay pass -> awaiting_approval | `evolution.py`, `skill_evolution.py` |
| Shadow 可自动 promote | Shadow pass -> awaiting_approval -> approve | `rollout.py`, stores, API |
| Fix 验证后直接 GitHub 写 | prepare -> verify -> approve -> publish | `patching.py`, `service.py`, `api.py` |
| 只看最终检测指标 | 增加 Pre/Post Gate 与 Gate FP/TP | `evaluation_v2.py` |
| EvoAgent 公开品牌 | TraceReview public facade | `tracereview/`, web/report/config |

# 附录 B：验证命令与当前结果

## 单元测试

```bash
python -m unittest discover -s tests -v
```

当前结果：

```text
Ran 77 tests
OK (skipped=1)
```

唯一 skip：用户未提供可选 `evaluation_data/prompt_evolution_130.jsonl`。

## 受控实验

```bash
python scripts/run_controlled_experiments.py \
  --dataset evaluation_data/pr_diff_100.jsonl \
  --output output/controlled-experiments/evaluation.json
```

输出：

```text
output/controlled-experiments/evaluation.json
output/controlled-experiments/summary.md
```

## 启动

```bash
python -m tracereview
```

---

# 附录 C：面试自检清单

对这个项目至少能回答：

- RiskProfile 为什么是确定性的？误路由如何兜底？
- 为什么需要 Multi-Agent，为什么又不固定全量调用？
- Evidence Auditor 为什么按条件执行？
- Tool 失败时哪些能 retry、哪些不能？
- Context 压缩保留哪些信息，为什么？
- 哪些 Memory 应跨任务保存，哪些任务结束即清理？
- FindingGate 如何避免 High/Critical 严重度夸大？
- Fix 为什么必须人工批准？审批期间 PR 改了怎么办？
- Policy candidate 为什么不能自动上线？
- 一次失败能否定位到 Parser / Routing / Tool / LLM / Gate / GitHub side effect？
- 如何用 Pre/Post Gate、Evidence Auditor invoke/cost、Token/Latency 证明模块是否真的有用？

如果这些问题都能根据代码、Trace 和 Evaluation 回答，项目的价值才来自真实工程判断，而不是技术名词数量。
