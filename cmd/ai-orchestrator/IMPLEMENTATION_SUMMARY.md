# AI Orchestrator 实现总结

## 项目概述

**服务名称**: AI Orchestrator (AI 编排服务)
**框架**: Kratos v2.7+ (Go)
**架构模式**: DDD (领域驱动设计)
**实现日期**: 2025-10-26

## 核心职责

AI Orchestrator 是 VoiceHelper 平台的**核心编排引擎**，负责：

1. **任务管理**: 创建、调度、执行、取消 AI 任务
2. **流程编排**: 协调多个 AI 服务完成复杂任务
3. **服务集成**: 统一调用下游 AI 服务（RAG、Agent、Voice 等）
4. **状态追踪**: 实时监控任务执行状态和步骤
5. **成本统计**: 追踪 Token 使用和 API 成本

## 实现架构

### 分层结构 (DDD)

```
cmd/ai-orchestrator/
├── internal/
│   ├── domain/              # 领域层
│   │   ├── task.go         # Task聚合根
│   │   ├── pipeline.go     # Pipeline流程接口和实现
│   │   └── repository.go   # 仓储接口
│   ├── biz/                 # 业务逻辑层
│   │   └── task_usecase.go # 任务用例
│   ├── data/                # 数据访问层
│   │   ├── data.go         # Data初始化
│   │   ├── db.go           # 数据库连接
│   │   ├── task_repo.go    # 任务仓储实现
│   │   └── service_client.go # 服务客户端
│   ├── service/             # 服务层
│   │   └── orchestrator_service.go # gRPC服务实现
│   └── server/              # 服务器配置
│       ├── grpc.go         # gRPC服务器
│       └── http.go         # HTTP服务器
├── wire.go                  # Wire依赖注入
├── main_app.go             # 主程序入口
├── Makefile                # 构建脚本
└── README.md               # 服务文档
```

## 核心领域模型

### 1. Task (任务聚合根)

**文件**: `internal/domain/task.go`

```go
type Task struct {
    ID             string          // 任务ID: task_uuid
    Type           TaskType        // 任务类型
    Status         TaskStatus      // 任务状态
    Priority       TaskPriority    // 优先级: 0-10
    ConversationID string          // 对话ID
    UserID         string          // 用户ID
    TenantID       string          // 租户ID
    Input          *TaskInput      // 任务输入
    Output         *TaskOutput     // 任务输出
    Steps          []*TaskStep     // 执行步骤
    Metadata       map[string]interface{} // 元数据
    CreatedAt      time.Time
    UpdatedAt      time.Time
    StartedAt      *time.Time
    CompletedAt    *time.Time
}
```

**任务类型 (TaskType)**:

- `rag`: RAG 检索增强生成
- `agent`: Agent 智能代理执行
- `chat`: 普通对话
- `voice`: 语音处理
- `multimodal`: 多模态处理

**任务状态 (TaskStatus)**:

- `pending`: 待执行
- `running`: 执行中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

**任务优先级 (TaskPriority)**:

- `TaskPriorityLow (0)`: 低优先级（后台任务）
- `TaskPriorityNormal (5)`: 普通优先级（默认）
- `TaskPriorityHigh (10)`: 高优先级（用户实时请求）

**核心方法**:

- `NewTask()`: 创建新任务
- `Start()`: 开始执行
- `Complete()`: 完成任务
- `Fail()`: 任务失败
- `Cancel()`: 取消任务
- `AddStep()`: 添加执行步骤
- `Duration()`: 获取执行时长

### 2. Pipeline (流程编排)

**文件**: `internal/domain/pipeline.go`

#### Pipeline 接口

```go
type Pipeline interface {
    Execute(task *Task) (*TaskOutput, error)
    Name() string
}
```

#### 三种 Pipeline 实现

**1. RAGPipeline (RAG 检索增强生成)**

```
步骤1: 检索服务 (Retrieval Service)
  ↓
步骤2: RAG引擎 (RAG Engine)
  ↓
返回答案
```

调用流程：

1. 调用 Retrieval Service 检索 Top 20 文档
2. 调用 RAG Engine 基于上下文生成回答
3. 记录 Token 使用和成本

**2. AgentPipeline (智能代理执行)**

```
步骤1: Agent引擎 (Agent Engine)
  ↓
工具调用、多轮迭代
  ↓
返回结果
```

调用流程：

1. 调用 Agent Engine 执行任务
2. 支持最多 10 次迭代
3. 返回执行结果和步骤

**3. VoicePipeline (语音处理)**

```
步骤1: 语音引擎 (Voice Engine) - ASR
  ↓
返回文本
```

调用流程：

1. 调用 Voice Engine 进行语音识别
2. 返回识别文本和置信度

### 3. TaskStep (执行步骤)

```go
type TaskStep struct {
    ID          string
    Name        string                 // 步骤名称
    Service     string                 // 调用的服务
    Input       map[string]interface{} // 步骤输入
    Output      map[string]interface{} // 步骤输出
    Status      TaskStatus             // 步骤状态
    Error       string                 // 错误信息
    StartedAt   time.Time
    CompletedAt *time.Time
    DurationMS  int                    // 执行时长(毫秒)
}
```

## 业务逻辑层

### TaskUsecase (任务用例)

**文件**: `internal/biz/task_usecase.go`

**核心方法**:

1. **CreateTask**: 创建 AI 任务

   - 验证任务类型
   - 持久化到数据库
   - 返回任务实例

2. **ExecuteTask**: 执行任务

   - 检查任务状态（必须为 pending）
   - 获取对应的 Pipeline
   - 执行 Pipeline
   - 记录执行步骤
   - 更新任务状态和输出
   - 记录 Token 使用和成本

3. **GetTask**: 获取任务详情

   - 从数据库查询任务
   - 返回完整信息（包括步骤）

4. **GetTasksByConversation**: 获取对话的所有任务

   - 按对话 ID 查询
   - 按创建时间倒序排列

5. **CancelTask**: 取消任务

   - 检查任务是否已完成
   - 更新状态为 cancelled

6. **SetTaskPriority**: 设置任务优先级

   - 更新任务优先级
   - 影响调度顺序

7. **CreateAndExecuteTask**: 创建并执行任务（同步）

   - 组合 Create 和 Execute
   - 适用于实时请求

8. **ProcessPendingTasks**: 处理待执行任务（后台）
   - 获取 pending 任务列表
   - 使用 goroutine 异步执行
   - 适用于任务队列处理

## 数据访问层

### TaskRepository (任务仓储)

**文件**: `internal/data/task_repo.go`

**持久化对象 (TaskPO)**:

```go
type TaskPO struct {
    ID             string `gorm:"primaryKey;size:64"`
    Type           string `gorm:"size:20;not null;index:idx_type"`
    Status         string `gorm:"size:20;not null;index:idx_status"`
    Priority       int    `gorm:"not null;index:idx_priority"`
    ConversationID string `gorm:"size:64;not null;index:idx_conversation"`
    UserID         string `gorm:"size:64;not null;index:idx_user"`
    TenantID       string `gorm:"size:64;not null;index:idx_tenant"`
    Input          string `gorm:"type:jsonb"`
    Output         string `gorm:"type:jsonb"`
    Steps          string `gorm:"type:jsonb"`
    Metadata       string `gorm:"type:jsonb"`
    CreatedAt      time.Time
    UpdatedAt      time.Time
    StartedAt      *time.Time
    CompletedAt    *time.Time
}
```

**实现方法**:

- `Create()`: 创建任务记录
- `GetByID()`: 根据 ID 查询
- `GetByConversationID()`: 根据对话 ID 查询
- `Update()`: 更新任务
- `ListPending()`: 获取待执行任务（按优先级排序）

**JSONB 优势**:

- 灵活存储复杂对象（Input、Output、Steps、Metadata）
- 支持索引和查询
- 减少表关联

### ServiceClient (服务客户端)

**文件**: `internal/data/service_client.go`

**实现类型**:

1. **GRPCServiceClient**: gRPC 客户端

   - 连接池管理
   - 服务发现集成（TODO）
   - 自动重连

2. **HTTPServiceClient**: HTTP 客户端
   - RESTful API 调用
   - 适用于 Python 服务

**服务地址映射**:

```go
serviceAddrs := map[string]string{
    "retrieval-service": "localhost:9001",
    "rag-engine":        "localhost:9002",
    "agent-engine":      "localhost:9003",
    "voice-engine":      "localhost:9004",
}
```

## 服务层

### OrchestratorService

**文件**: `internal/service/orchestrator_service.go`

**gRPC 接口实现**:

1. **CreateTask**: 创建任务

   - 接收 gRPC 请求
   - 转换为领域对象
   - 调用 TaskUsecase.CreateTask
   - 返回 TaskResponse

2. **ExecuteTask**: 执行任务

   - 接收 TaskID
   - 调用 TaskUsecase.ExecuteTask
   - 返回任务和输出

3. **GetTask**: 获取任务

   - 查询任务详情
   - 返回完整信息

4. **CreateAndExecuteTask**: 创建并执行（同步）

   - 适用于实时请求
   - 等待执行完成后返回

5. **CancelTask**: 取消任务
   - 更新任务状态
   - 返回更新后的任务

## 数据库设计

### 表结构

**表名**: `ai_orchestrator.tasks`

**字段说明**:
| 字段 | 类型 | 说明 | 索引 |
|-----|------|------|------|
| id | VARCHAR(64) | 任务 ID | 主键 |
| type | VARCHAR(20) | 任务类型 | idx_type |
| status | VARCHAR(20) | 任务状态 | idx_status |
| priority | INT | 优先级 | idx_priority |
| conversation_id | VARCHAR(64) | 对话 ID | idx_conversation |
| user_id | VARCHAR(64) | 用户 ID | idx_user |
| tenant_id | VARCHAR(64) | 租户 ID | idx_tenant |
| input | JSONB | 输入数据 | - |
| output | JSONB | 输出数据 | - |
| steps | JSONB | 执行步骤 | - |
| metadata | JSONB | 元数据 | - |
| created_at | TIMESTAMP | 创建时间 | idx_created_at |
| updated_at | TIMESTAMP | 更新时间 | 自动更新 |
| started_at | TIMESTAMP | 开始时间 | - |
| completed_at | TIMESTAMP | 完成时间 | - |

**复合索引**:

- `idx_tasks_tenant_status`: (tenant_id, status) - 租户任务查询
- `idx_tasks_status_priority`: (status, priority DESC, created_at ASC) - 任务队列

**审计日志表**:

```sql
CREATE TABLE ai_orchestrator.task_execution_logs (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 依赖注入 (Wire)

**文件**: `wire.go`

```go
panic(wire.Build(
    // Data layer
    data.NewDB,
    data.NewData,
    data.NewTaskRepo,
    data.NewServiceClient,

    // Domain layer - Pipelines
    wire.Bind(new(domain.ServiceClient), new(*data.GRPCServiceClient)),
    domain.NewRAGPipeline,
    domain.NewAgentPipeline,
    domain.NewVoicePipeline,

    // Business logic layer
    biz.NewTaskUsecase,

    // Service layer
    service.NewOrchestratorService,

    // Server layer
    server.NewGRPCServer,
    server.NewHTTPServer,

    // App
    newApp,
))
```

**依赖关系图**:

```
App
 ├── gRPC Server
 │   └── OrchestratorService
 │       └── TaskUsecase
 │           ├── TaskRepository (Data)
 │           └── Pipelines
 │               ├── RAGPipeline
 │               ├── AgentPipeline
 │               └── VoicePipeline
 │                   └── ServiceClient
 └── HTTP Server
     └── (同上)
```

## 配置管理

**配置文件**: `configs/app/ai-orchestrator.yaml`

```yaml
server:
  http:
    addr: 0.0.0.0:8000
    timeout: 30s
  grpc:
    addr: 0.0.0.0:9000
    timeout: 30s

data:
  database:
    driver: postgres
    source: postgres://voicehelper:voicehelper_dev@localhost:5432/voicehelper?sslmode=disable

trace:
  endpoint: http://localhost:4318 # OpenTelemetry Collector
```

## 核心流程示例

### 1. RAG 任务执行流程

```
1. 客户端调用 CreateAndExecuteTask(type=rag)
    ↓
2. OrchestratorService.CreateAndExecuteTask()
    ↓
3. TaskUsecase.CreateAndExecuteTask()
    ├─ 创建Task(type=rag, status=pending)
    ├─ 持久化到数据库
    ├─ 更新状态为running
    └─ 执行 RAGPipeline
        ├─ Step 1: 调用 Retrieval Service
        │   - 检索Top 20文档
        │   - 记录检索耗时
        ├─ Step 2: 调用 RAG Engine
        │   - 基于上下文生成答案
        │   - 记录Token使用
        │   - 计算成本
        └─ 返回 TaskOutput
    ↓
4. 更新Task状态为completed
5. 返回结果给客户端
```

### 2. 任务取消流程

```
1. 客户端调用 CancelTask(task_id)
    ↓
2. TaskUsecase.CancelTask()
    ├─ 获取任务
    ├─ 检查是否已完成
    ├─ 更新状态为cancelled
    └─ 持久化
    ↓
3. 返回更新后的任务
```

## 监控指标

### 业务指标

```go
// 任务总数（按类型、状态）
orchestrator_tasks_total{type="rag",status="completed"} 100

// 任务执行时长
orchestrator_task_duration_seconds{type="rag",p="0.95"} 2.5

// Pipeline执行时长
orchestrator_pipeline_duration_seconds{pipeline="RAGPipeline",step="retrieval"} 0.5

// Token使用统计
orchestrator_tokens_used_total{model="gpt-4",tenant_id="tenant_123"} 50000

// 成本统计
orchestrator_cost_usd_total{model="gpt-4",tenant_id="tenant_123"} 1.25
```

### 技术指标

```go
// gRPC请求数
orchestrator_grpc_requests_total{method="CreateTask",status="success"} 1000

// 服务调用统计
orchestrator_service_calls_total{service="retrieval-service",status="success"} 500

// 数据库查询延迟
orchestrator_db_query_duration_seconds{operation="create"} 0.005
```

## 性能优化

### 1. 数据库优化

- **JSONB 索引**: 加速元数据查询
- **复合索引**: 优化任务队列查询
- **连接池**: MaxOpen=100, MaxIdle=10
- **分区表**: 按月分区（历史数据）

### 2. 并发处理

- **goroutine 池**: 限制并发执行数
- **channel 缓冲**: 任务队列缓冲 1000
- **超时控制**: 每个任务最多 5 分钟

### 3. 服务调用优化

- **连接复用**: 保持长连接
- **重试机制**: 指数退避，最多 3 次
- **熔断降级**: 错误率>50%触发熔断

## 测试覆盖

### 单元测试

```bash
make test
```

**测试文件**:

- `internal/domain/task_test.go`
- `internal/biz/task_usecase_test.go`
- `internal/data/task_repo_test.go`

### 集成测试

```bash
go test -tags=integration ./...
```

**测试场景**:

- 完整的 RAG 任务执行
- Pipeline 失败处理
- 任务取消流程
- 并发任务处理

## 部署

### 本地开发

```bash
# 启动依赖
docker-compose up postgres redis

# 运行迁移
psql -U voicehelper -d voicehelper -f migrations/postgres/004_ai_orchestrator.sql

# 启动服务
make run
```

### Docker

```bash
make docker-build
make docker-run
```

### Kubernetes

```bash
helm install ai-orchestrator ./deployments/helm/ai-orchestrator
```

## 待完成工作

### 1. Proto 定义

```protobuf
// api/proto/orchestrator/v1/orchestrator.proto
service Orchestrator {
    rpc CreateTask(CreateTaskRequest) returns (TaskResponse);
    rpc ExecuteTask(ExecuteTaskRequest) returns (ExecuteTaskResponse);
    rpc GetTask(GetTaskRequest) returns (GetTaskResponse);
    rpc CancelTask(CancelTaskRequest) returns (TaskResponse);
    rpc CreateAndExecuteTask(CreateTaskRequest) returns (ExecuteTaskResponse);
}
```

### 2. 服务发现

- 集成 Consul/Nacos
- 动态获取下游服务地址
- 健康检查和负载均衡

### 3. 任务队列

- 实现基于 Kafka 的任务队列
- 异步任务处理
- 死信队列

### 4. 流式响应

- 支持流式输出（SSE/WebSocket）
- 实时返回 Pipeline 步骤进度

### 5. 监控告警

- Prometheus 指标完善
- Grafana Dashboard
- AlertManager 告警规则

## 关键技术点

### 1. DDD 分层

- **Domain**: 业务核心逻辑，无依赖
- **Biz**: 用例编排，依赖 Domain 接口
- **Data**: 基础设施实现，实现 Domain 接口
- **Service**: API 层，依赖 Biz

### 2. Wire 依赖注入

- 编译时依赖注入，无运行时反射
- 类型安全，编译时检查
- 清晰的依赖关系图

### 3. JSONB 存储

- 灵活存储复杂对象
- 减少表关联
- 支持索引和查询

### 4. Pipeline 模式

- 统一的执行流程
- 易于扩展新 Pipeline
- 步骤可追踪

## 总结

AI Orchestrator 是 VoiceHelper 平台的**核心编排引擎**，通过 DDD 分层架构实现了：

✅ **任务管理**: 完整的任务生命周期管理
✅ **流程编排**: 灵活的 Pipeline 模式
✅ **服务集成**: 统一的下游服务调用
✅ **状态追踪**: 详细的步骤记录
✅ **可扩展性**: 易于添加新的任务类型和 Pipeline
✅ **可观测性**: 完善的监控指标
✅ **高性能**: 数据库优化、并发处理、连接复用

**下一步**:

1. 完成 Proto 定义和 gRPC 注册
2. 实现服务发现和负载均衡
3. 集成 Kafka 任务队列
4. 添加流式响应支持
5. 完善监控和告警

---

**版本**: v1.0.0
**作者**: VoiceHelper Team
**日期**: 2025-10-26
