# Agent Engine 可观测性集成指南

> **创建时间**: 2025-10-29
> **版本**: v1.0
> **迭代**: Phase 1 - 可观测性与评测基建

---

## 📋 概述

本文档介绍如何集成和使用 Agent Engine 的可观测性功能，包括：
- ✅ 执行追踪 (ExecutionTracer)
- ✅ 自动化评测 (AgentEvaluator)
- ✅ 成本控制 (BudgetController)
- ✅ Grafana 仪表盘

---

## 🚀 快速开始

### 1. 启用执行追踪

```python
from app.observability.tracer import ExecutionTracer, get_tracer
from app.core.agent_engine import AgentEngine

# 创建追踪器
tracer = ExecutionTracer(enable_otel=True)

# 设置为全局追踪器
from app.observability.tracer import set_tracer
set_tracer(tracer)

# 在 Agent Engine 中使用
agent_engine = AgentEngine()
await agent_engine.initialize()

# 执行任务（自动追踪）
task_id = "task_001"
tracer.start_task(task_id, "Calculate 2 + 2", mode="react")

result = await agent_engine.execute(
    task="Calculate 2 + 2",
    mode="react"
)

tracer.end_task(task_id, result["final_answer"], success=True)

# 获取追踪摘要
summary = tracer.get_trace_summary(task_id)
print(f"Steps: {summary['step_count']}, Cost: ${summary['total_cost_usd']:.4f}")
```

### 2. 运行评测

```bash
# 使用预设的基准数据集
cd algo/agent-engine
python tests/eval/agent/run_evaluation.py \
  --dataset tests/eval/agent/datasets/benchmark.json \
  --modes react plan_execute \
  --output tests/eval/agent/reports/result.json \
  --enable-llm-judge
```

### 3. 启用预算控制

```python
from app.core.budget_controller import BudgetController

# 创建预算控制器
controller = BudgetController(
    redis_client=redis_client,
    default_tier=BudgetTier.PRO,
    alert_threshold=0.8
)

# 执行前检查预算
tenant_id = "tenant_123"
if await controller.check_budget(tenant_id, estimated_cost=0.05):
    # 执行任务
    result = await agent_engine.execute(task="...")

    # 记录成本
    await controller.record_cost(
        tenant_id=tenant_id,
        cost_usd=0.05,
        metadata={"mode": "react", "task_id": "task_001"}
    )
else:
    # 应用降级策略
    strategy = await controller.get_fallback_strategy(tenant_id)
    print(f"Budget exceeded, fallback: {strategy.value}")
```

### 4. 部署 Grafana 仪表盘

```bash
# 导入仪表盘
kubectl apply -f deployments/grafana/dashboards/agent-performance.json
kubectl apply -f deployments/grafana/dashboards/agent-cost.json
kubectl apply -f deployments/grafana/dashboards/agent-tracing.json

# 访问 Grafana
open http://localhost:3000/dashboards
```

---

## 📊 执行追踪详解

### 追踪事件类型

| 事件类型 | 说明 | 使用场景 |
|---------|------|----------|
| `TASK_START` | 任务开始 | 记录任务元信息 |
| `TASK_END` | 任务结束 | 记录最终结果和统计 |
| `THOUGHT` | 思考过程 | ReAct 模式的推理步骤 |
| `ACTION` | 行动决策 | 选择工具和参数 |
| `OBSERVATION` | 观察结果 | 工具执行结果 |
| `TOOL_CALL` | 工具调用 | 记录工具调用性能 |
| `LLM_CALL` | LLM 调用 | 记录 Token 和成本 |
| `MEMORY_RETRIEVAL` | 记忆检索 | 记忆系统性能 |

### 完整示例：追踪 ReAct 执行

```python
from app.observability.tracer import get_tracer

tracer = get_tracer()

# 1. 开始任务
task_id = "task_123"
tracer.start_task(task_id, "What is 25 * 4 + 10?", mode="react")

# 2. 记录第一步思考
tracer.record_thought(
    task_id,
    "I need to calculate 25 * 4 + 10. I should use the calculator tool.",
    step_number=1
)

# 3. 记录行动
tracer.record_action(
    task_id,
    action="Use calculator to compute expression",
    tool="calculator",
    params={"expression": "25 * 4 + 10"},
    step_number=1
)

# 4. 记录工具调用（包含性能）
import time
start = time.time()
result = "110"  # 工具执行结果
duration_ms = (time.time() - start) * 1000

tracer.record_tool_call(
    task_id,
    tool_name="calculator",
    params={"expression": "25 * 4 + 10"},
    duration_ms=duration_ms,
    success=True,
    result=result
)

# 5. 记录观察
tracer.record_observation(task_id, result, step_number=1)

# 6. 记录 LLM 调用
tracer.record_llm_call(
    task_id,
    model="gpt-4",
    prompt_tokens=50,
    completion_tokens=20,
    duration_ms=500,
    cost_usd=0.002
)

# 7. 结束任务
tracer.end_task(task_id, final_result="The answer is 110", success=True)

# 8. 导出追踪记录
trace_json = tracer.export_trace_json(task_id)
with open(f"traces/{task_id}.json", "w") as f:
    f.write(trace_json)
```

---

## 🧪 评测框架使用

### 自定义测试用例

创建 `custom_tests.json`:

```json
[
  {
    "id": "custom_001",
    "category": "business_logic",
    "task": "查询客户订单状态并发送通知",
    "expected_answer": "订单状态已查询并发送通知",
    "expected_tools": ["database_query", "notification_service"],
    "max_steps": 8,
    "metadata": {
      "complexity": "medium",
      "priority": "high"
    }
  }
]
```

### 编程式运行评测

```python
from tests.eval.agent.evaluator import AgentEvaluator, TestCase
from app.core.agent_engine import AgentEngine

# 初始化
agent_engine = AgentEngine()
await agent_engine.initialize()

evaluator = AgentEvaluator(
    agent_engine=agent_engine,
    enable_llm_judge=True
)

# 加载测试用例
test_cases = evaluator.load_test_cases("custom_tests.json")

# 运行评测
results = await evaluator.evaluate(
    test_cases=test_cases,
    modes=["react", "plan_execute", "reflexion"]
)

# 生成报告
report = evaluator.generate_report(results)

# 打印摘要
evaluator.print_summary(report)

# 保存报告
evaluator.save_report(report, "reports/custom_evaluation.json")
```

### CI 集成

`.github/workflows/agent-evaluation.yml`:

```yaml
name: Agent Evaluation

on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点
  push:
    branches: [main, develop]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd algo/agent-engine
          pip install -r requirements.txt

      - name: Run evaluation
        run: |
          cd algo/agent-engine
          python tests/eval/agent/run_evaluation.py \
            --dataset tests/eval/agent/datasets/benchmark.json \
            --modes react plan_execute \
            --output reports/nightly_eval.json

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: evaluation-report
          path: algo/agent-engine/reports/nightly_eval.json

      - name: Check regression
        run: |
          python scripts/check_evaluation_regression.py \
            --baseline reports/baseline.json \
            --current reports/nightly_eval.json \
            --threshold 0.05  # 允许5%的性能下降
```

---

## 💰 成本控制详解

### 预算等级配置

```python
from app.core.budget_controller import BudgetTier

# 为租户设置预算等级
await redis_client.set("budget:tier:tenant_123", BudgetTier.PRO.value)

# PRO 等级: $10/day
# 实际预算可以根据业务需求调整
```

### 获取使用报告

```python
# 获取过去7天的使用报告
report = await controller.get_usage_report("tenant_123", days=7)

print(f"总消耗: ${report['total_usage']:.4f}")
print(f"日均消耗: ${report['daily_average']:.4f}")
print(f"预算使用率: {report['usage_ratio']:.2%}")

# 每日详情
for day in report['daily_usage']:
    print(f"{day['date']}: ${day['usage']:.4f}")
```

### 成本优化建议

```python
suggestions = await controller.get_optimization_suggestions("tenant_123")

for suggestion in suggestions:
    print(f"💡 {suggestion}")

# 输出示例:
# 💡 预算即将用尽，建议升级套餐或优化使用
# 💡 每日平均消耗较高，建议：
# 💡   - 使用更便宜的模型（如 GPT-3.5 代替 GPT-4）
# 💡   - 启用语义缓存，减少重复查询
```

---

## 📈 Grafana 仪表盘指标

### Agent Performance Dashboard

**关键指标**:
- 任务成功率: `agent_tasks_total{status="success"}`
- P95 延迟: `histogram_quantile(0.95, agent_task_duration_seconds_bucket)`
- 平均步骤数: `avg(agent_step_count)`
- 工具调用成功率: `agent_tool_calls_total{status="success"}`

**告警规则**:
```yaml
# Prometheus Alert Rules
groups:
  - name: agent_engine
    rules:
      - alert: HighTaskFailureRate
        expr: sum(rate(agent_tasks_total{status="error"}[5m])) / sum(rate(agent_tasks_total[5m])) > 0.15
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "任务失败率过高"
          description: "失败率: {{ $value | humanizePercentage }}"

      - alert: HighLatency
        expr: histogram_quantile(0.95, sum(rate(agent_task_duration_seconds_bucket[5m])) by (le)) > 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P95延迟超过10秒"
```

### Agent Cost Dashboard

**关键指标**:
- 总成本: `sum(increase(agent_cost_usd_total[24h]))`
- 每任务成本: `agent_cost_usd_total / agent_tasks_total`
- 租户排行: `topk(10, sum(increase(agent_cost_usd_total[24h])) by (tenant_id))`
- Token 消耗: `sum(increase(agent_tokens_total[24h]))`

---

## 🔧 故障排查

### 常见问题

**Q1: 追踪数据未上报到 Jaeger？**

检查 OpenTelemetry 配置:
```bash
# 查看环境变量
echo $OTEL_EXPORTER_OTLP_ENDPOINT  # 应该指向 Jaeger

# 测试连接
curl http://localhost:4318/v1/traces
```

**Q2: 评测失败率高？**

检查 Agent Engine 状态:
```python
# 获取统计信息
stats = await agent_engine.get_stats()
print(f"成功率: {stats['success_rate']:.2%}")
print(f"失败原因: {stats['error_distribution']}")
```

**Q3: 预算控制不生效？**

检查 Redis 连接和配置:
```python
# 验证预算记录
usage = await controller._get_daily_usage("tenant_123")
budget = await controller._get_budget("tenant_123")
print(f"当前消耗: ${usage:.4f} / ${budget:.4f}")
```

---

## 📚 最佳实践

### 1. 分阶段启用功能

```python
# Phase 1: 只启用追踪（无性能影响）
tracer = ExecutionTracer(enable_otel=False)

# Phase 2: 启用 OpenTelemetry（< 5% 性能开销）
tracer = ExecutionTracer(enable_otel=True)

# Phase 3: 启用完整评测（仅在开发/测试环境）
if os.getenv("ENV") != "production":
    evaluator = AgentEvaluator(agent_engine, enable_llm_judge=True)
```

### 2. 定期清理追踪数据

```python
# 任务完成后清理
tracer.clear_trace(task_id)

# 定时清理（后台任务）
async def cleanup_old_traces():
    cutoff_time = time.time() - 86400  # 24小时前
    for task_id, events in tracer.traces.items():
        if events[0].timestamp < cutoff_time:
            tracer.clear_trace(task_id)
```

### 3. 合理设置预算告警

```python
# 多级告警
controller = BudgetController(alert_threshold=0.8)  # 80% 告警

# 自定义告警回调
async def on_budget_alert(tenant_id, usage_ratio):
    if usage_ratio > 0.9:
        # 发送紧急通知
        await notification_service.send_urgent(tenant_id, "预算即将耗尽")
    elif usage_ratio > 0.8:
        # 发送提醒
        await notification_service.send_info(tenant_id, "预算使用已达80%")
```

---

## 🎯 下一步

完成迭代 1 后，继续：
- [ ] **迭代 2**: Self-RAG 与记忆增强
- [ ] **迭代 3**: Multi-Agent 协作增强
- [ ] **迭代 4**: 人机协作与工具生态

参见: [优化路线图](../../../docs/roadmap/agent-engine-optimization-roadmap.md)

---

**最后更新**: 2025-10-29
**维护者**: Agent-Engine Team
