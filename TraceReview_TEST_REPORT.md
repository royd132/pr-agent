# TraceReview v2.1 验证报告

## 1. 单元测试

命令：

```bash
python -m unittest discover -s tests -v
```

结果：

```text
Ran 77 tests in ~1.6s
OK (skipped=1)
```

唯一 skip：

```text
optional prompt_evolution_130.jsonl was not supplied
```

项目没有构造或伪造该可选数据集。

本轮新增/重点覆盖：

- RiskProfile 对 Boundary Inspector / Behavior Inspector 的按风险路由；
- High-risk Finding 的 precondition / impact / evidence strength Gate；
- AgentTool side_effect / retryable / timeout contract；
- Fix prepare -> awaiting-approval -> publish 两阶段；
- 审批期间 PR Head 变化时拒绝 stale patch；
- Shadow observation 达标后只进入 awaiting_approval，必须显式人工 promotion；
- Checkpoint / Resume / Redis DLQ / RBAC / Memory isolation 等原有回归测试继续通过。

## 2. Python 语法与导入 Smoke Test

```bash
python -m compileall -q evoagent tracereview scripts tests
```

通过。

公开 `tracereview` facade 和 legacy `evoagent` package 均可导入；RiskProfile smoke case `eval(user_input)` 被识别为 `dynamic-execution / high`，路由 Boundary Inspector，推荐 Evidence Auditor。

## 3. 100 条受控离线实验

命令：

```bash
python scripts/run_controlled_experiments.py \
  --dataset evaluation_data/pr_diff_100.jsonl \
  --output output/controlled-experiments/evaluation.json
```

执行模式：

```text
controlled-offline-no-llm
```

因此下面结果只证明确定性规则、受控编排和候选门禁行为，不作为真实生产 LLM 效果声明。

### 规则基线

| Metric | Result |
|---|---:|
| Precision | 82.50% |
| Recall | 82.50% |
| F1 | 82.50% |
| High-risk Recall | 94.74% |
| Clean Accuracy | 91.67% |
| Safe Fix | 78.79% |
| E2E Fix | 65.00% |

### 五臂受控离线消融

| Arm | F1 | High-risk Recall | Clean Accuracy | Simulated role calls / PR |
|---|---:|---:|---:|---:|
| model-baseline | 71.43% | 84.21% | 91.67% | 1.00 |
| model-plus-scanner | 82.50% | 94.74% | 91.67% | 1.00 |
| routed-specialists | 82.50% | 94.74% | 91.67% | 3.82 |
| routed-specialists-audited | 90.41% | 94.74% | 100.00% | 4.05 |
| routed-specialists-policy | 90.41% | 94.74% | 100.00% | 4.55 |

报告明确指出隐藏 Holdout 上 Evidence Auditor / Multi-Agent / Review Policy 对应增益不能由该离线受控运行单独证明。

### Review Policy 候选

受控 Skill/Policy candidate 在 Validation 没有达到最小 F1 提升，decision 为 rejected，Holdout activation gate blocked。系统没有为了“自进化”叙事强制激活无提升候选。

## 4. 已知验证边界

- 当前容器没有连接真实 PostgreSQL/Redis/GitHub 服务，因此 PostgreSQL 新增 Shadow/HITL 方法做了代码路径与语法校验，但没有现场 PostgreSQL integration test。
- GitHub 写操作通过 fake client 单测验证了“批准前零写入、批准后写入”和 stale Head 拦截；真实 GitHub API 仍需使用实际 token/repository 做端到端验证。
- 真实 LLM 质量取决于配置的 Provider/Model，受控离线脚本不替代在线 Agent benchmark。
