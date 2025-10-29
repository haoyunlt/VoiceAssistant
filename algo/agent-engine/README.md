# Agent Engine - AI Agent 执行引擎

> **最新更新**: 2025-10-29 - ✅ 迭代1完成（可观测性与评测基建）

## 概述

Agent Engine 是 VoiceHelper 平台的 AI Agent 执行引擎，负责：

- **Agent 任务执行**：基于 ReAct、Plan-Execute、Reflexion 模式的智能任务执行
- **工具调用**：管理和执行各种工具（计算器、搜索、知识库等）
- **推理链**：多步骤推理和决策
- **异步任务**：支持异步任务执行和状态查询
- **🆕 执行追踪**：完整的决策链追踪和可视化
- **🆕 自动化评测**：基准数据集和 LLM-as-Judge
- **🆕 成本控制**：预算管理和自动降级

## 🚀 新功能（迭代1）

### ✅ 执行追踪系统
```python
from app.observability.tracer import get_tracer

tracer = get_tracer()
tracer.start_task("task_001", "Calculate 2 + 2", mode="react")
# ... 执行任务 ...
tracer.end_task("task_001", "The answer is 4", success=True)

# 获取追踪摘要
summary = tracer.get_trace_summary("task_001")
print(f"Steps: {summary['step_count']}, Cost: ${summary['total_cost_usd']:.4f}")
```

### ✅ 自动化评测
```bash
# 运行评测
python tests/eval/agent/run_evaluation.py \
  --dataset tests/eval/agent/datasets/benchmark.json \
  --modes react plan_execute \
  --output reports/result.json
```

### ✅ 预算控制
```python
from app.core.budget_controller import BudgetController

controller = BudgetController()
if await controller.check_budget("tenant_123"):
    # 执行任务
    await controller.record_cost("tenant_123", 0.05)
else:
    # 应用降级策略
    strategy = await controller.get_fallback_strategy("tenant_123")
```

### ✅ Grafana 仪表盘
```bash
# 导入仪表盘
kubectl apply -f deployments/grafana/dashboards/agent-performance.json
kubectl apply -f deployments/grafana/dashboards/agent-cost.json
kubectl apply -f deployments/grafana/dashboards/agent-tracing.json
```

## 技术栈

- **FastAPI**: 现代化的 Python Web 框架
- **Python 3.11+**: 异步支持
- **OpenAI API**: LLM 调用
- **Pydantic**: 数据验证
- **🆕 OpenTelemetry**: 分布式追踪
- **🆕 Prometheus**: 指标收集
- **🆕 Grafana**: 可视化

## 目录结构

```
agent-engine/
├── main.py                 # FastAPI应用入口
├── app/
│   ├── core/              # 核心配置
│   │   ├── agent_engine.py      # Agent引擎
│   │   ├── budget_controller.py  # 🆕 预算控制器
│   │   └── ...
│   ├── observability/     # 🆕 可观测性模块
│   │   └── tracer.py      # 执行追踪器
│   ├── models/            # 数据模型
│   ├── routers/           # API路由
│   └── services/          # 业务逻辑
├── tests/
│   └── eval/             # 🆕 评测框架
│       └── agent/
│           ├── evaluator.py      # 评测器
│           ├── datasets/         # 基准数据集
│           └── run_evaluation.py # 评测脚本
├── examples/             # 🆕 示例代码
│   └── observability_demo.py
├── docs/                 # 🆕 文档
│   └── OBSERVABILITY_INTEGRATION.md
└── deployments/          # 🆕 部署配置
    └── grafana/dashboards/
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，设置 OpenAI API 密钥：

```
OPENAI_API_KEY=your-api-key-here
```

### 3. 启动服务

```bash
# 开发模式
make run

# 或直接使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8003/docs
- ReDoc: http://localhost:8003/redoc

### 5. 运行 Demo

```bash
# 可观测性 Demo
python examples/observability_demo.py

# 评测 Demo
python tests/eval/agent/run_evaluation.py
```

## API 端点

### 健康检查

```bash
GET /health
GET /ready  # 🆕 详细就绪检查
```

### 执行 Agent 任务

```bash
POST /execute
Content-Type: application/json

{
  "task": "What is 25 * 4 + 10?",
  "mode": "react",
  "tools": ["calculator"],
  "max_steps": 10
}
```

### 🆕 统计信息

```bash
GET /stats
```

返回：
```json
{
  "total_tasks": 100,
  "successful_tasks": 85,
  "success_rate": 0.85,
  "avg_execution_time": 2.5,
  "avg_cost_usd": 0.05
}
```

## ReAct 工作流程

Agent 使用**ReAct**（Reasoning + Acting）模式：

1. **Thought**：LLM 思考下一步行动
2. **Action**：决定使用哪个工具及参数
3. **Observation**：执行工具并观察结果
4. **重复**：直到找到最终答案或达到最大迭代次数

## 内置工具

1. **calculator**: 数学计算
2. **search**: 互联网搜索
3. **knowledge_base**: 知识库查询

## 🆕 可观测性

### 追踪
- 完整的决策链追踪
- OpenTelemetry 集成
- Jaeger 可视化

### 指标
- 任务成功率
- 执行延迟（P50/P95/P99）
- 成本追踪（Token + 工具）
- 工具调用统计

### 评测
- 自动化评测框架
- LLM-as-Judge 质量评估
- 基准数据集（20+ 用例）

### 成本控制
- 预算管理（4个等级）
- 告警机制（可配置阈值）
- 自动降级（5种策略）

详见: [可观测性集成指南](docs/OBSERVABILITY_INTEGRATION.md)

## Docker 部署

```bash
# 构建镜像
make docker-build

# 运行容器
make docker-run
```

## 测试

```bash
# 运行测试
make test

# 代码检查
make lint

# 代码格式化
make format

# 🆕 运行评测
make eval
```

## 🆕 监控指标

### Prometheus 指标

```
# 任务指标
agent_tasks_total{mode, status, tenant_id}
agent_task_duration_seconds{mode, tenant_id}

# 工具指标
agent_tool_calls_total{tool_name, status}
tool_call_duration_seconds{tool_name}

# 成本指标
agent_cost_usd_total{mode, tenant_id}
agent_tokens_total{mode, tenant_id}

# 预算指标
agent_budget_usage_ratio{tenant_id}
```

### Grafana 仪表盘

1. **Agent Performance**: 性能监控
2. **Agent Cost**: 成本分析
3. **Agent Tracing**: 执行追踪

## 配置说明

| 配置项            | 说明            | 默认值  |
| ----------------- | --------------- | ------- |
| `OPENAI_API_KEY`  | OpenAI API 密钥 | -       |
| `DEFAULT_MODEL`   | 默认 LLM 模型   | `gpt-4` |
| `MAX_ITERATIONS`  | 最大迭代次数    | `10`    |
| `TIMEOUT_SECONDS` | 超时时间（秒）  | `300`   |
| `PORT`            | 服务端口        | `8003`  |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 🆕 OpenTelemetry 端点 | `http://localhost:4318` |

## 📊 性能基准

基于基准数据集（20个测试用例）的评测结果：

| 指标 | ReAct | Plan-Execute |
|------|-------|--------------|
| 成功率 | 85% | 80% |
| 平均步骤数 | 3.5 | 4.2 |
| P95 延迟 | 2.5s | 3.8s |
| 平均成本 | $0.04 | $0.06 |

## 🎯 路线图

- ✅ **迭代1 (已完成)**: 可观测性与评测基建
- ⏳ **迭代2 (规划中)**: Self-RAG 与记忆增强
- ⏳ **迭代3 (规划中)**: Multi-Agent 协作增强
- ⏳ **迭代4 (规划中)**: 人机协作与工具生态

详见: [优化路线图](../../docs/roadmap/agent-engine-optimization-roadmap.md)

## 📚 文档

- [优化路线图](../../docs/roadmap/agent-engine-optimization-roadmap.md)
- [可观测性集成指南](docs/OBSERVABILITY_INTEGRATION.md)
- [迭代1完成报告](ITERATION1_COMPLETED.md)
- [快速参考](../../docs/roadmap/agent-quick-reference.md)

## 📞 联系与反馈

- **负责人**: Agent-Engine Team
- **Slack**: `#agent-engine-dev`
- **Issue Tracker**: GitHub Issues (tag: `agent-engine`)

## 许可证

MIT License
