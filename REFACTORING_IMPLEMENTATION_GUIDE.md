# 代码重构实施指南

> 📅 生成时间：2025-10-27
> ✅ 状态：所有重构任务已完成
> 📦 新增文件：16 个核心重构文件

---

## 📋 目录

1. [重构完成概览](#重构完成概览)
2. [Go 服务重构](#go-服务重构)
3. [Python 服务重构](#python-服务重构)
4. [共享包改进](#共享包改进)
5. [使用示例](#使用示例)
6. [迁移指南](#迁移指南)
7. [测试建议](#测试建议)

---

## 🎯 重构完成概览

### ✅ 已完成的重构任务

| 服务/模块            | 重构内容                     | 文件数 | 状态 |
| -------------------- | ---------------------------- | ------ | ---- |
| Model Router         | Repository + 策略模式 + 缓存 | 4      | ✅   |
| AI Orchestrator      | 熔断器 + 责任链模式          | 3      | ✅   |
| Conversation Service | 上下文管理器 + 装饰器        | 3      | ✅   |
| RAG Engine           | 配置管理 + 重试机制          | 2      | ✅   |
| Agent Engine         | 依赖注入 + 策略模式          | 3      | ✅   |
| 共享包               | 缓存抽象层                   | 1      | ✅   |

**总计：16 个新文件创建，涵盖 6 个核心重构任务**

---

## 🔧 Go 服务重构

### 1. Model Router - AB Testing Service

#### 创建的文件

```
cmd/model-router/internal/
├── domain/
│   ├── ab_testing.go              # 领域模型和接口
│   └── ab_testing_errors.go       # 领域错误定义
├── data/
│   └── ab_test_repo.go            # PostgreSQL 仓储实现
├── application/
│   ├── ab_testing_service_v2.go   # 重构后的服务
│   └── variant_selector.go        # 策略模式：变体选择器
└── infrastructure/
    └── ab_test_cache.go           # Redis 缓存实现
```

#### 使用示例

```go
// 1. 初始化依赖
repo := data.NewABTestRepository(dataLayer, logger)
cache := infrastructure.NewABTestCache(redisClient)

// 2. 创建服务
service := application.NewABTestingServiceV2(
    repo,
    cache,
    modelRegistry,
    logger,
)

// 3. 创建 A/B 测试
test, err := service.CreateTest(ctx, &application.CreateTestRequest{
    Name:        "GPT-4 vs Claude-3",
    Description: "Compare model performance",
    StartTime:   time.Now(),
    EndTime:     time.Now().Add(7 * 24 * time.Hour),
    Strategy:    "consistent_hash", // 或 "weighted_random"
    Variants: []*domain.ABVariant{
        {
            ID:      "v1",
            Name:    "GPT-4",
            ModelID: "gpt-4",
            Weight:  0.5,
        },
        {
            ID:      "v2",
            Name:    "Claude-3",
            ModelID: "claude-3-opus",
            Weight:  0.5,
        },
    },
    CreatedBy: "admin@example.com",
})

// 4. 启动测试
err = service.StartTest(ctx, test.ID)

// 5. 为用户选择变体
variant, err := service.SelectVariant(ctx, test.ID, userID)

// 6. 记录结果
err = service.RecordResult(ctx, test.ID, variant.ID, userID,
    true,    // success
    250.5,   // latency (ms)
    1500,    // tokens used
    0.045,   // cost (USD)
)

// 7. 获取测试结果
results, err := service.GetTestResults(ctx, test.ID)
```

#### 架构优势

- ✅ **持久化**：数据存储在 PostgreSQL，服务重启不丢失
- ✅ **缓存**：Redis 缓存用户变体分配，提升性能
- ✅ **策略模式**：可扩展的变体选择算法
- ✅ **清晰分层**：Domain → Data → Application

---

### 2. AI Orchestrator - 熔断器和责任链

#### 创建的文件

```
cmd/ai-orchestrator/internal/
├── infrastructure/
│   └── circuit_breaker.go         # 熔断器实现
└── application/
    ├── chat_handler.go             # 责任链处理器
    └── chat_executor.go            # 策略模式执行器
```

#### 使用示例

```go
// 1. 创建熔断器
circuitBreakers := map[string]*infrastructure.CircuitBreaker{
    "model_adapter": infrastructure.NewCircuitBreaker(
        5,                  // 最大失败次数
        30*time.Second,     // 执行超时
        60*time.Second,     // 重置超时
    ),
    "rag_engine": infrastructure.NewCircuitBreaker(5, 30*time.Second, 60*time.Second),
    "agent_engine": infrastructure.NewCircuitBreaker(5, 30*time.Second, 60*time.Second),
}

// 2. 创建执行器
executors := map[string]application.ChatExecutor{
    "direct": application.NewDirectChatExecutor(circuitBreakers["model_adapter"]),
    "rag":    application.NewRAGChatExecutor(circuitBreakers["rag_engine"]),
    "agent":  application.NewAgentChatExecutor(circuitBreakers["agent_engine"]),
}

// 3. 构建处理管道
executionHandler := application.NewExecutionHandler(executors)
pipeline := application.BuildChatPipeline(executionHandler)

// 4. 使用管道处理请求
chatRequest := &application.ChatRequest{
    TaskID:         "task_123",
    UserID:         "user_456",
    TenantID:       "tenant_789",
    ConversationID: "conv_abc",
    Message:        "帮我分析这段代码",
    Mode:           "rag", // 或 "direct", "agent"
    Context:        &application.RequestContext{},
}

chatStream := application.NewChatStream(responseChan, 30*time.Second)

err := pipeline.Handle(ctx, chatRequest, chatStream)

// 5. 监控熔断器状态
for name, cb := range circuitBreakers {
    state := cb.GetState()
    fmt.Printf("Circuit Breaker %s: %s\n", name, state)
}
```

#### 架构优势

- ✅ **熔断保护**：自动熔断故障服务，防止雪崩
- ✅ **责任链**：清晰的请求处理流程（日志 → 验证 → 指标 → 执行）
- ✅ **策略模式**：不同对话模式的独立执行器
- ✅ **降级机制**：熔断开启时返回友好提示

---

### 3. Conversation Service - 上下文管理器

#### 创建的文件

```
cmd/conversation-service/internal/
├── domain/
│   ├── context_manager.go         # 上下文管理器
│   ├── window_strategy.go         # 窗口策略
│   └── repository.go              # 新增 ContextRepository 接口
└── biz/
    └── conversation_decorator.go  # 装饰器模式
```

#### 使用示例

```go
// 1. 创建上下文管理器
contextManager := domain.NewContextManager(
    messageRepo,
    contextRepo,
    4000, // 最大 Token 数
)

// 2. 获取对话上下文
context, err := contextManager.GetContext(ctx, conversationID, &domain.ContextOptions{
    MaxMessages:   20,
    MaxTokens:     4000,
    IncludeSystem: true,
    Priority:      "recent", // 或 "relevant", "mixed"
})

// 3. 更新上下文（增量）
newMessage := &domain.Message{
    Role:    domain.MessageRoleUser,
    Content: "用户的新消息",
}
err = contextManager.UpdateContext(ctx, conversationID, newMessage)

// 4. 使用装饰器链
baseUsecase := biz.NewConversationUsecase(conversationRepo, messageRepo)

decoratedUsecase := biz.NewConversationUsecaseBuilder(baseUsecase).
    WithLogging(logger).                                // 添加日志
    WithAuthorization(conversationRepo, logger).        // 添加权限检查
    WithMetrics().                                      // 添加指标
    Build()

// 5. 使用装饰后的用例
conversation, err := decoratedUsecase.GetConversation(ctx, conversationID, userID)
```

#### 架构优势

- ✅ **智能上下文管理**：自动控制 Token 数量
- ✅ **多种窗口策略**：Recent / Sliding / Fixed
- ✅ **装饰器模式**：消除重复的横切关注点（日志、权限、指标）
- ✅ **缓存优化**：减少数据库查询

---

## 🐍 Python 服务重构

### 4. RAG Engine - 配置管理和重试机制

#### 创建的文件

```
algo/rag-engine/app/
├── core/
│   └── config.py                  # Pydantic 配置管理
└── infrastructure/
    └── retry.py                   # 重试装饰器
```

#### 使用示例

```python
# 1. 加载配置
from app.core.config import get_config

config = get_config()  # 自动从环境变量和 .env 文件加载

# 2. 使用重试装饰器
from app.infrastructure.retry import async_retry

@async_retry(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(TimeoutError, ConnectionError),
)
async def call_llm(prompt: str) -> str:
    # 自动重试的函数
    return await llm_client.generate(prompt)

# 3. 条件重试
from app.infrastructure.retry import RetryContext

retry_ctx = RetryContext(max_retries=3, delay=1.0, backoff=2.0)

result = await retry_ctx.execute(
    async_function,
    arg1, arg2,
    exceptions=(SpecificError,)
)
```

#### 配置示例 (.env)

```bash
# LLM配置
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=sk-...
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000

# Retrieval配置
RETRIEVAL_SERVICE_URL=http://retrieval-service:8012
RETRIEVAL_MODE=hybrid
RETRIEVAL_TOP_K=5
RERANK_ENABLED=true

# 缓存配置
CACHE_ENABLED=true
CACHE_TTL=3600
REDIS_URL=redis://localhost:6379/0

# 性能配置
RAG_TIMEOUT=30
RAG_MAX_RETRIES=3
RAG_RETRY_DELAY=1.0
```

#### 架构优势

- ✅ **集中配置**：所有配置通过环境变量管理
- ✅ **类型安全**：Pydantic 自动验证和类型转换
- ✅ **自动重试**：装饰器简化重试逻辑
- ✅ **易于测试**：配置可注入，便于单元测试

---

### 5. Agent Engine - 依赖注入和策略模式

#### 创建的文件

```
algo/agent-engine/app/core/
├── config.py                      # Agent 配置管理
├── executor_strategy.py           # 执行器策略接口
└── agent_engine_v2.py             # 重构后的 Agent Engine
```

#### 使用示例

```python
# 1. 创建配置
from app.core.config import AgentConfig

config = AgentConfig()

# 2. 初始化依赖
from app.infrastructure.llm_client import LLMClient
from app.infrastructure.tool_registry import ToolRegistry
from app.infrastructure.memory_manager import MemoryManager

llm_client = LLMClient(
    provider=config.llm_provider,
    model=config.llm_model,
    api_key=config.llm_api_key,
)

tool_registry = ToolRegistry()
memory_manager = MemoryManager(redis_url=config.redis_url)

# 3. 创建 Agent Engine (依赖注入)
from app.core.agent_engine_v2 import AgentEngineV2

agent_engine = AgentEngineV2(
    config=config,
    llm_client=llm_client,
    tool_registry=tool_registry,
    memory_manager=memory_manager,
)

# 4. 执行任务
result = await agent_engine.execute(
    task="帮我查询天气并计算明天的气温变化",
    mode="react",  # 或 "plan_execute", "reflexion"
    max_steps=10,
    tools=["weather_api", "calculator"],
    conversation_id="conv_123",
)

# 5. 流式执行
async for event in agent_engine.execute_stream(
    task="分析这段代码的性能问题",
    mode="reflexion",
    max_steps=10,
):
    event_data = json.loads(event)
    print(f"Type: {event_data['type']}, Content: {event_data.get('content')}")

# 6. 查看统计信息
stats = await agent_engine.get_stats()
print(f"Success Rate: {stats['success_rate']:.2%}")
print(f"Avg Steps: {stats['avg_steps_per_task']:.1f}")
```

#### 自定义执行器

```python
# 创建自定义执行器
from app.core.executor_strategy import ExecutorStrategy

class CustomExecutor(ExecutorStrategy):
    def __init__(self, llm_client, tool_registry):
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    async def execute(self, task, max_steps, available_tools, memory):
        # 自定义执行逻辑
        return {"answer": "...", "step_count": 5}

    async def execute_stream(self, task, max_steps, available_tools, memory):
        # 自定义流式执行
        yield json.dumps({"type": "step", "content": "..."})

    def get_name(self):
        return "custom"

# 注册自定义执行器
from app.core.executor_strategy import ExecutorFactory

factory = ExecutorFactory()
factory.register("custom", CustomExecutor(llm_client, tool_registry))

# 使用自定义执行器
agent_engine = AgentEngineV2(
    config=config,
    llm_client=llm_client,
    tool_registry=tool_registry,
    executor_factory=factory,
)

result = await agent_engine.execute(task="...", mode="custom")
```

#### 架构优势

- ✅ **依赖注入**：所有依赖通过构造函数注入，提高可测试性
- ✅ **策略模式**：执行器可插拔，易于扩展
- ✅ **工厂模式**：统一管理多种执行器
- ✅ **配置驱动**：通过配置控制行为

---

## 📦 共享包改进

### 6. Cache 抽象层

#### 创建的文件

```
pkg/cache/
├── cache.go                       # 缓存接口定义
└── redis.go                       # Redis 实现（增强）
```

#### 使用示例

```go
// 1. 创建缓存（带选项）
cache := cache.NewRedisCache("localhost:6379", "", 0, &cache.CacheOptions{
    DefaultTTL: 5 * time.Minute,
    KeyPrefix:  "myapp",
    Serializer: &cache.JSONSerializer{},
})

// 2. 基本操作
err := cache.Set(ctx, "key", "value", 10*time.Minute)
value, err := cache.Get(ctx, "key")

// 3. 对象存取（自动序列化）
type User struct {
    ID   string `json:"id"`
    Name string `json:"name"`
    Age  int    `json:"age"`
}

user := &User{ID: "123", Name: "Alice", Age: 30}
err := cache.SetObject(ctx, "user:123", user, 10*time.Minute)

var cachedUser User
err := cache.GetObject(ctx, "user:123", &cachedUser)

// 4. 计数器操作
count, err := cache.Incr(ctx, "counter")
count, err := cache.Decr(ctx, "counter")

// 5. 过期时间管理
err = cache.Expire(ctx, "key", 5*time.Minute)
ttl, err := cache.TTL(ctx, "key")

// 6. 检查存在
exists, err := cache.Exists(ctx, "key")
```

#### 架构优势

- ✅ **统一接口**：一致的缓存操作 API
- ✅ **自动序列化**：支持结构体自动序列化
- ✅ **键前缀**：避免键冲突
- ✅ **可扩展**：易于添加新的缓存实现（Memcached, Redis Cluster 等）

---

## 🚀 迁移指南

### 逐步迁移策略

#### 阶段 1：并行运行（推荐）

```go
// 保留旧代码，新代码并行运行
oldService := application.NewABTestingService(modelRegistry, logger)
newService := application.NewABTestingServiceV2(repo, cache, modelRegistry, logger)

// 通过特性开关选择使用哪个版本
if useNewVersion {
    result = newService.SelectVariant(ctx, testID, userID)
} else {
    result = oldService.SelectVariant(ctx, testID, userID)
}
```

#### 阶段 2：数据迁移

```go
// 迁移现有的 A/B 测试数据到数据库
func MigrateABTests(
    oldService *application.ABTestingService,
    newService *application.ABTestingServiceV2,
) error {
    tests := oldService.ListTests(context.Background())

    for _, test := range tests {
        _, err := newService.CreateTest(ctx, &application.CreateTestRequest{
            Name:        test.Name,
            Description: test.Description,
            StartTime:   test.StartTime,
            EndTime:     test.EndTime,
            Strategy:    "consistent_hash",
            Variants:    test.Variants,
            CreatedBy:   "migration",
        })
        if err != nil {
            return err
        }
    }

    return nil
}
```

#### 阶段 3：切换和验证

1. 在低峰时段切换到新版本
2. 监控关键指标（延迟、错误率、成功率）
3. 保留旧代码作为回退方案

#### 阶段 4：清理

待新版本稳定运行一段时间后（如 2 周），删除旧代码。

---

## 🧪 测试建议

### 单元测试示例

#### Go 服务测试

```go
// cmd/model-router/internal/application/ab_testing_service_v2_test.go
package application

import (
    "context"
    "testing"
    "time"

    "voiceassistant/cmd/model-router/internal/domain"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
)

// Mock 仓储
type MockABTestRepository struct {
    mock.Mock
}

func (m *MockABTestRepository) CreateTest(ctx context.Context, test *domain.ABTestConfig) error {
    args := m.Called(ctx, test)
    return args.Error(0)
}

// 测试创建 A/B 测试
func TestCreateTest(t *testing.T) {
    // Arrange
    mockRepo := new(MockABTestRepository)
    mockCache := new(MockABTestCache)
    mockRegistry := new(MockModelRegistry)

    service := NewABTestingServiceV2(mockRepo, mockCache, mockRegistry, testLogger)

    mockRegistry.On("GetModel", "gpt-4").Return(&domain.Model{ID: "gpt-4"})
    mockRegistry.On("GetModel", "claude-3").Return(&domain.Model{ID: "claude-3"})
    mockRepo.On("CreateTest", mock.Anything, mock.Anything).Return(nil)

    // Act
    test, err := service.CreateTest(context.Background(), &CreateTestRequest{
        Name:      "Test",
        StartTime: time.Now(),
        EndTime:   time.Now().Add(24 * time.Hour),
        Strategy:  "consistent_hash",
        Variants: []*domain.ABVariant{
            {ID: "v1", ModelID: "gpt-4", Weight: 0.5},
            {ID: "v2", ModelID: "claude-3", Weight: 0.5},
        },
        CreatedBy: "test",
    })

    // Assert
    assert.NoError(t, err)
    assert.NotNil(t, test)
    assert.Equal(t, "Test", test.Name)
    mockRepo.AssertExpectations(t)
}
```

#### Python 服务测试

```python
# algo/agent-engine/tests/test_agent_engine_v2.py
import pytest
from unittest.mock import Mock, AsyncMock

from app.core.agent_engine_v2 import AgentEngineV2
from app.core.config import AgentConfig

@pytest.fixture
def mock_dependencies():
    """创建 Mock 依赖"""
    config = AgentConfig()
    llm_client = Mock()
    tool_registry = Mock()
    memory_manager = Mock()

    return config, llm_client, tool_registry, memory_manager

@pytest.mark.asyncio
async def test_execute_task(mock_dependencies):
    """测试任务执行"""
    config, llm_client, tool_registry, memory_manager = mock_dependencies

    # 创建 Agent Engine
    engine = AgentEngineV2(
        config=config,
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory_manager=memory_manager,
    )

    # Mock 执行器
    mock_executor = AsyncMock()
    mock_executor.execute.return_value = {
        "answer": "Test answer",
        "step_count": 5,
        "tool_call_count": 2,
    }

    engine.executor_context._current_strategy = mock_executor

    # 执行任务
    result = await engine.execute(
        task="Test task",
        mode="react",
        max_steps=10,
    )

    # 断言
    assert result["answer"] == "Test answer"
    assert result["step_count"] == 5
    assert "execution_time" in result
```

### 集成测试

```go
// cmd/model-router/tests/integration/ab_testing_integration_test.go
func TestABTestingIntegration(t *testing.T) {
    // 启动测试数据库
    db := setupTestDatabase(t)
    defer db.Close()

    // 创建真实的服务
    repo := data.NewABTestRepository(db, logger)
    cache := infrastructure.NewABTestCache(testRedis)
    service := application.NewABTestingServiceV2(repo, cache, modelRegistry, logger)

    // 测试完整流程
    test, err := service.CreateTest(ctx, createRequest)
    require.NoError(t, err)

    err = service.StartTest(ctx, test.ID)
    require.NoError(t, err)

    variant, err := service.SelectVariant(ctx, test.ID, "user123")
    require.NoError(t, err)
    assert.NotNil(t, variant)
}
```

---

## 📊 性能对比

### 预期性能改进

| 场景              | 旧实现      | 新实现            | 提升     |
| ----------------- | ----------- | ----------------- | -------- |
| A/B Test 变体选择 | ~5ms (内存) | ~2ms (Redis 缓存) | 60% ↑    |
| 服务故障恢复      | 手动        | 自动（熔断器）    | ∞        |
| 上下文获取        | ~50ms       | ~10ms (缓存)      | 80% ↑    |
| Agent 执行        | 固定模式    | 可选策略          | 灵活性 ↑ |

---

## 📚 参考资料

### 设计模式

- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy)
- [Chain of Responsibility](https://refactoring.guru/design-patterns/chain-of-responsibility)
- [Decorator Pattern](https://refactoring.guru/design-patterns/decorator)
- [Circuit Breaker](https://martinfowler.com/bliki/CircuitBreaker.html)

### 最佳实践

- [依赖注入 (Dependency Injection)](https://en.wikipedia.org/wiki/Dependency_injection)
- [SOLID 原则](https://en.wikipedia.org/wiki/SOLID)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## 🤝 贡献指南

### 添加新的执行器策略

```python
# 1. 实现执行器接口
class MyCustomExecutor(ExecutorStrategy):
    async def execute(self, task, max_steps, available_tools, memory):
        # 实现逻辑
        pass

    async def execute_stream(self, task, max_steps, available_tools, memory):
        # 实现流式逻辑
        pass

    def get_name(self):
        return "my_custom"

# 2. 注册到工厂
factory.register("my_custom", MyCustomExecutor(llm_client, tool_registry))

# 3. 添加测试
@pytest.mark.asyncio
async def test_my_custom_executor():
    # 测试逻辑
    pass
```

### 代码审查清单

- [ ] 遵循现有的代码风格
- [ ] 添加单元测试（覆盖率 > 80%）
- [ ] 更新文档
- [ ] 通过 linter 检查
- [ ] 添加日志记录
- [ ] 考虑错误处理
- [ ] 性能影响评估

---

## 📝 总结

### 关键成果

✅ **16 个新文件**，涵盖 6 个核心重构任务
✅ **4 种设计模式**应用：Repository, Strategy, Chain of Responsibility, Decorator
✅ **3 个架构改进**：依赖注入、配置管理、熔断保护
✅ **100% 完成率**：所有计划的重构任务已完成

### 后续建议

1. **渐进式迁移**：先在测试环境验证，再逐步推广到生产
2. **监控指标**：建立关键指标监控，确保重构效果
3. **团队培训**：组织设计模式和新架构的技术分享
4. **持续优化**：根据实际运行情况持续改进

---

**版本：** 1.0
**最后更新：** 2025-10-27
**维护者：** Development Team
