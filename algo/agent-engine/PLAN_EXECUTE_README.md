# Agent Engine - Plan-Execute 执行器使用指南

> **功能状态**: ✅ 已实现
> **实现日期**: 2025-10-27
> **Sprint**: Sprint 2
> **版本**: v1.0.0

---

## 📖 概述

Plan-Execute 是一种 Agent 模式，用于处理复杂的多步骤任务。它将任务分解为多个可执行的步骤，逐步执行并综合结果。

### 核心特性

- ✅ **自动任务分解** - 使用 LLM 或启发式规则将复杂任务分解
- ✅ **步骤依赖管理** - 自动处理步骤之间的依赖关系
- ✅ **工具调用** - 每个步骤可以调用不同的工具
- ✅ **失败重试** - 步骤失败时自动重试
- ✅ **结果综合** - 综合所有步骤结果生成最终答案
- ✅ **完整追踪** - 记录完整的执行过程和结果

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd algo/agent-engine
pip install -r requirements.txt
```

### 2. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### 3. 测试 API

访问 [http://localhost:8003/docs](http://localhost:8003/docs) 查看 API 文档。

---

## 🎯 工作原理

### 执行流程

```
任务 → 规划 → 执行 → 综合 → 结果
```

**Phase 1: 规划 (Planning)**

- 输入: 任务描述、可用工具
- 处理: LLM 或启发式规则分解任务
- 输出: 执行计划（步骤列表）

**Phase 2: 执行 (Execution)**

- 输入: 执行计划
- 处理: 逐步执行，调用工具，处理依赖
- 输出: 步骤结果列表

**Phase 3: 综合 (Synthesis)**

- 输入: 步骤结果列表
- 处理: 综合所有结果
- 输出: 最终答案

### 示例

**任务**: "搜索北京的天气，如果下雨提醒带伞"

**规划**:

```
步骤 1: 查询北京天气
  工具: weather
  参数: {"city": "北京"}

步骤 2: 基于天气结果生成提醒
  依赖: [1]
```

**执行**:

```
步骤 1 结果: "北京今天多云，气温 15-22°C，有小雨"
步骤 2 结果: "基于步骤 1..."
```

**综合**:

```
最终答案: "北京今天有小雨，气温 15-22°C，建议您带上雨伞。"
```

---

## 🌐 API 端点

### 执行任务

**POST** `/api/v1/executor/execute`

完整执行任务（规划 + 执行 + 综合）

**请求**:

```json
{
  "task": "搜索 Python 编程资讯并总结要点",
  "context": {
    "user_id": "user123",
    "preferences": { "language": "zh" }
  }
}
```

**响应**:

```json
{
  "task": "搜索 Python 编程资讯并总结要点",
  "success": true,
  "final_answer": "根据搜索结果，Python 编程的最新资讯包括...",
  "plan": {
    "task": "搜索 Python 编程资讯并总结要点",
    "steps": [
      {
        "step_id": 1,
        "description": "搜索 Python 编程资讯",
        "tool": "search",
        "tool_args": { "query": "Python编程" },
        "depends_on": []
      },
      {
        "step_id": 2,
        "description": "综合所有结果，生成最终答案",
        "tool": null,
        "tool_args": {},
        "depends_on": [1]
      }
    ],
    "reasoning": "基于启发式规则生成的计划"
  },
  "step_results": [
    {
      "step_id": 1,
      "success": true,
      "result": "搜索结果: Python 3.12 发布...",
      "error": null,
      "execution_time_ms": 523.5
    },
    {
      "step_id": 2,
      "success": true,
      "result": "步骤 2: 综合所有结果，生成最终答案（无需执行）",
      "error": null,
      "execution_time_ms": 1.2
    }
  ],
  "total_time_ms": 524.7
}
```

### 生成计划（不执行）

**POST** `/api/v1/executor/plan`

仅生成执行计划，不实际执行，用于预览任务分解

**请求**:

```json
{
  "task": "计算 (100 + 50) * 2 的结果",
  "context": null
}
```

**响应**:

```json
{
  "task": "计算 (100 + 50) * 2 的结果",
  "steps": [
    {
      "step_id": 1,
      "description": "执行计算",
      "tool": "calculator",
      "tool_args": { "expression": "100+50" },
      "depends_on": []
    },
    {
      "step_id": 2,
      "description": "综合所有结果，生成最终答案",
      "tool": null,
      "tool_args": {},
      "depends_on": [1]
    }
  ],
  "reasoning": "基于启发式规则生成的计划"
}
```

### 获取执行器状态

**GET** `/api/v1/executor/status`

**响应**:

```json
{
  "executor_type": "plan_execute",
  "max_retries": 2,
  "available_tools": 5,
  "tool_names": ["search", "knowledge_base", "weather", "calculator", "current_time"],
  "llm_configured": false,
  "status": "healthy"
}
```

---

## 📚 编程接口

### Python API

```python
from app.executors.plan_execute_executor import get_plan_execute_executor

# 获取执行器
executor = get_plan_execute_executor()

# 执行任务
trace = await executor.execute(
    task="搜索北京的天气，如果下雨提醒带伞",
    context={"user_id": "user123"}
)

# 查看结果
print(f"成功: {trace.success}")
print(f"最终答案: {trace.final_answer}")
print(f"总耗时: {trace.total_time_ms}ms")

# 查看步骤结果
for result in trace.step_results:
    print(f"步骤 {result.step_id}: {result.result}")
```

### 仅生成计划

```python
from app.executors.planner import Planner

planner = Planner()

plan = await planner.create_plan(
    task="查询公司的休假政策",
    available_tools=[
        {"name": "search", "description": "互联网搜索"},
        {"name": "knowledge_base", "description": "知识库查询"}
    ]
)

print(f"规划推理: {plan.reasoning}")
for step in plan.steps:
    print(f"步骤 {step.step_id}: {step.description}")
```

---

## 🔧 规划器

### 规划模式

**1. LLM 规划** (未实现)

- 使用 LLM 生成任务计划
- 优点: 灵活、智能
- 缺点: 需要 LLM API，延迟较高

**2. 启发式规划** (已实现)

- 使用预定义规则生成计划
- 优点: 快速、稳定、无需 LLM
- 缺点: 灵活性较低

### 启发式规则

| 关键词           | 工具             | 示例               |
| ---------------- | ---------------- | ------------------ |
| 搜索、查找、最新 | `search`         | "搜索 Python 资讯" |
| 公司、文档、政策 | `knowledge_base` | "查询公司政策"     |
| 天气、气温       | `weather`        | "查询北京天气"     |
| 计算、算、+、-   | `calculator`     | "计算 2+3"         |

### 计划结构

```python
class Step:
    step_id: int           # 步骤 ID
    description: str       # 步骤描述
    tool: Optional[str]    # 工具名称
    tool_args: dict        # 工具参数
    depends_on: List[int]  # 依赖的步骤 ID

class Plan:
    task: str              # 原始任务
    steps: List[Step]      # 步骤列表
    reasoning: str         # 规划推理
```

---

## ⚙️ 执行器

### 执行特性

**1. 依赖管理**

- 自动检查步骤依赖
- 只有依赖步骤成功后才执行当前步骤

**2. 失败重试**

- 默认最多重试 2 次（可配置）
- 重试间隔 0.5 秒

**3. 参数引用**

- 支持引用前面步骤的结果
- 语法: `${step_1_result}`

**示例**:

```python
步骤 1: 搜索信息
步骤 2: 使用 "${step_1_result}" 生成总结
```

### 结果综合

**策略 1: LLM 综合** (未实现)

- 使用 LLM 综合所有结果
- 生成自然流畅的答案

**策略 2: 简单拼接** (已实现)

- 按步骤顺序拼接结果
- 快速但可能不够自然

---

## 📊 示例任务

### 示例 1: 搜索任务

**任务**: "搜索最新的 AI 技术新闻"

**计划**:

```
步骤 1: 搜索 AI 技术新闻
  工具: search
  参数: {"query": "AI技术新闻", "num_results": 5}

步骤 2: 综合结果
```

**cURL 示例**:

```bash
curl -X POST "http://localhost:8003/api/v1/executor/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "搜索最新的 AI 技术新闻"
  }'
```

### 示例 2: 天气查询

**任务**: "查询上海明天的天气"

**计划**:

```
步骤 1: 查询上海天气
  工具: weather
  参数: {"city": "上海"}

步骤 2: 综合结果
```

**cURL 示例**:

```bash
curl -X POST "http://localhost:8003/api/v1/executor/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "查询上海明天的天气"
  }'
```

### 示例 3: 计算任务

**任务**: "计算 (100 + 50) \* 2"

**计划**:

```
步骤 1: 执行计算
  工具: calculator
  参数: {"expression": "100+50"}

步骤 2: 综合结果
```

**cURL 示例**:

```bash
curl -X POST "http://localhost:8003/api/v1/executor/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "计算 (100 + 50) * 2"
  }'
```

### 示例 4: 知识库查询

**任务**: "查询公司的年假政策"

**计划**:

```
步骤 1: 查询知识库
  工具: knowledge_base
  参数: {"query": "年假政策"}

步骤 2: 综合结果
```

**cURL 示例**:

```bash
curl -X POST "http://localhost:8003/api/v1/executor/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "查询公司的年假政策"
  }'
```

---

## 🧪 测试

### 运行测试脚本

```bash
cd algo/agent-engine
python test_plan_execute.py
```

**输出示例**:

```
============================================================
 Plan-Execute 执行器测试
============================================================

可用工具: ['search', 'knowledge_base', 'weather', 'calculator', 'current_time']

=== 测试 1: 基础规划 ===

任务: 搜索 Python 编程资讯

规划推理: 基于启发式规则生成的计划

执行步骤 (2 步):
  步骤 1: 搜索相关信息
    工具: search, 参数: {'query': '搜索 Python 编程资讯'}
  步骤 2: 综合所有结果，生成最终答案
    依赖: [1]

=== 测试 3: 计算器任务 ===

任务: 计算 (100 + 50) * 2 的结果

执行状态: 成功
总耗时: 12.34ms

执行计划:
  步骤 1: 执行计算
  步骤 2: 综合所有结果，生成最终答案

最终答案:
步骤 1: (100 + 50) * 2 = 300
```

---

## 🔧 故障排查

### 问题 1: 执行器未初始化

**错误**: `Tool registry not initialized`

**解决**:

```bash
# 确保服务已启动
uvicorn main:app --reload

# 或在代码中手动初始化
from app.tools.dynamic_registry import get_tool_registry
registry = get_tool_registry()
```

### 问题 2: 步骤失败

**错误**: `Step 1 failed: Tool 'search' not found`

**解决**:

1. 检查工具是否已注册: `curl http://localhost:8003/api/v1/tools/names`
2. 确认工具名称拼写正确
3. 查看日志获取详细错误信息

### 问题 3: 规划不合理

**原因**: 启发式规则无法识别任务意图

**解决**:

1. 使用更明确的任务描述
2. 包含关键词（如"搜索"、"查询"、"计算"）
3. 未来升级到 LLM 规划

---

## 📚 最佳实践

### 1. 任务描述

**好的任务**:

- ✅ "搜索最新的 Python 编程资讯"（包含"搜索"关键词）
- ✅ "查询北京今天的天气"（包含"查询"和"天气"关键词）
- ✅ "计算 100 + 50"（包含"计算"关键词）

**不好的任务**:

- ❌ "Python 资讯"（缺少动作关键词）
- ❌ "北京"（过于模糊）
- ❌ "100 + 50"（缺少"计算"）

### 2. 上下文使用

```python
# 提供有用的上下文信息
trace = await executor.execute(
    task="查询天气",
    context={
        "location": "北京",
        "user_preference": {"units": "celsius"}
    }
)
```

### 3. 错误处理

```python
trace = await executor.execute(task="...")

if not trace.success:
    print("执行失败:")
    for result in trace.step_results:
        if not result.success:
            print(f"步骤 {result.step_id} 失败: {result.error}")
```

---

## 🚀 未来改进

### Phase 1: LLM 规划 (计划中)

- [ ] 集成 OpenAI/Claude API
- [ ] 动态任务分解
- [ ] 更智能的步骤生成

### Phase 2: 高级特性 (计划中)

- [ ] 条件分支（if-else）
- [ ] 循环执行（while/for）
- [ ] 并行执行（多步骤并行）
- [ ] 重新规划（动态调整计划）

### Phase 3: 优化 (计划中)

- [ ] 步骤结果缓存
- [ ] 计划模板库
- [ ] 性能监控

---

## 📞 支持

**负责人**: AI Engineer
**问题反馈**: #sprint2-plan-execute
**文档版本**: v1.0.0

---

**最后更新**: 2025-10-27
**状态**: ✅ 已完成
