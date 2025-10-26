# AI Orchestrator - AI编排服务

## 概述

AI Orchestrator 是 VoiceHelper 平台的核心编排服务，负责协调和管理所有AI相关任务的执行流程。

## 核心功能

### 1. 任务管理
- **任务创建**: 接收并创建各类AI任务
- **任务调度**: 根据优先级和资源调度任务执行
- **状态跟踪**: 实时追踪任务执行状态和进度
- **任务取消**: 支持取消正在执行或待执行的任务

### 2. 流程编排（Pipeline）

#### RAG Pipeline (检索增强生成)
```
用户查询 → 检索服务(Retrieval) → RAG引擎(RAG Engine) → 返回结果
```
- 调用 Retrieval Service 检索相关文档
- 调用 RAG Engine 生成基于上下文的回答
- 记录Token使用和成本

#### Agent Pipeline (智能代理)
```
用户任务 → Agent引擎(Agent Engine) → 工具调用 → 返回结果
```
- 调用 Agent Engine 执行复杂任务
- 支持多轮迭代和工具调用
- 自主决策和问题解决

#### Voice Pipeline (语音处理)
```
语音输入 → ASR(语音识别) → 文本输出
```
- 调用 Voice Engine 进行语音识别
- 支持实时和批量处理

### 3. 服务集成
- **gRPC客户端**: 调用下游AI服务
- **服务发现**: 动态发现和连接服务
- **负载均衡**: 智能分配请求
- **熔断降级**: 处理服务故障

## 架构设计

### 分层架构 (DDD)

```
┌─────────────────────────────────────────┐
│          Service Layer                   │  gRPC/HTTP API
├─────────────────────────────────────────┤
│          Business Logic (Biz)            │  任务用例、流程编排
├─────────────────────────────────────────┤
│          Domain Layer                    │  Task、Pipeline、Repository
├─────────────────────────────────────────┤
│          Data Layer                      │  GORM、Service Client
└─────────────────────────────────────────┘
```

### 核心领域模型

#### Task (任务)
```go
type Task struct {
    ID             string          // 任务ID
    Type           TaskType        // 任务类型
    Status         TaskStatus      // 任务状态
    Priority       TaskPriority    // 优先级
    ConversationID string          // 对话ID
    Input          *TaskInput      // 输入
    Output         *TaskOutput     // 输出
    Steps          []*TaskStep     // 执行步骤
}
```

#### TaskType (任务类型)
- `rag`: RAG检索增强
- `agent`: Agent执行
- `chat`: 普通对话
- `voice`: 语音处理
- `multimodal`: 多模态处理

#### TaskStatus (任务状态)
- `pending`: 待执行
- `running`: 执行中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

#### Pipeline (流程)
```go
type Pipeline interface {
    Execute(task *Task) (*TaskOutput, error)
    Name() string
}
```

## API 接口

### gRPC API

#### CreateTask - 创建任务
```protobuf
rpc CreateTask(CreateTaskRequest) returns (TaskResponse);
```

#### ExecuteTask - 执行任务
```protobuf
rpc ExecuteTask(ExecuteTaskRequest) returns (ExecuteTaskResponse);
```

#### GetTask - 获取任务详情
```protobuf
rpc GetTask(GetTaskRequest) returns (GetTaskResponse);
```

#### CreateAndExecuteTask - 创建并执行任务（同步）
```protobuf
rpc CreateAndExecuteTask(CreateTaskRequest) returns (ExecuteTaskResponse);
```

#### CancelTask - 取消任务
```protobuf
rpc CancelTask(CancelTaskRequest) returns (TaskResponse);
```

## 数据库设计

### tasks 表
| 字段 | 类型 | 说明 |
|-----|------|------|
| id | VARCHAR(64) | 任务ID |
| type | VARCHAR(20) | 任务类型 |
| status | VARCHAR(20) | 任务状态 |
| priority | INT | 优先级 |
| conversation_id | VARCHAR(64) | 对话ID |
| user_id | VARCHAR(64) | 用户ID |
| tenant_id | VARCHAR(64) | 租户ID |
| input | JSONB | 输入数据 |
| output | JSONB | 输出数据 |
| steps | JSONB | 执行步骤 |
| metadata | JSONB | 元数据 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| started_at | TIMESTAMP | 开始时间 |
| completed_at | TIMESTAMP | 完成时间 |

### 索引
- `idx_tasks_type`: 按类型查询
- `idx_tasks_status`: 按状态查询
- `idx_tasks_priority`: 按优先级排序
- `idx_tasks_conversation`: 按对话查询
- `idx_tasks_tenant_status`: 租户+状态复合查询
- `idx_tasks_status_priority`: 任务队列查询优化

## 配置

### 配置文件 (`configs/app/ai-orchestrator.yaml`)
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
  endpoint: http://localhost:4318
```

## 运行指南

### 本地开发

1. **安装依赖**
```bash
make init
```

2. **生成Wire代码**
```bash
make wire
```

3. **运行服务**
```bash
make run
```

### Docker运行

```bash
make docker-build
make docker-run
```

### 数据库迁移

```bash
psql -U voicehelper -d voicehelper -f migrations/postgres/004_ai_orchestrator.sql
```

## 监控指标

### 业务指标
- `orchestrator_tasks_total`: 任务总数（按类型、状态）
- `orchestrator_task_duration_seconds`: 任务执行时长
- `orchestrator_pipeline_duration_seconds`: Pipeline执行时长
- `orchestrator_task_errors_total`: 任务错误数

### 技术指标
- `orchestrator_grpc_requests_total`: gRPC请求数
- `orchestrator_grpc_duration_seconds`: gRPC请求延迟
- `orchestrator_service_calls_total`: 下游服务调用数
- `orchestrator_service_call_errors_total`: 下游服务调用错误数

## 依赖服务

### 上游服务
- **Conversation Service**: 对话管理
- **Knowledge Service**: 知识管理

### 下游服务
- **Retrieval Service**: 文档检索
- **RAG Engine**: RAG生成
- **Agent Engine**: Agent执行
- **Voice Engine**: 语音处理
- **Multimodal Engine**: 多模态处理

## 错误处理

### 错误类型
- `ErrTaskNotFound`: 任务不存在
- `ErrInvalidTaskType`: 无效的任务类型
- `ErrTaskNotPending`: 任务状态不正确
- `ErrServiceUnavailable`: 下游服务不可用
- `ErrPipelineExecution`: Pipeline执行失败

### 重试策略
- **指数退避**: 失败时使用指数退避重试
- **最大重试次数**: 3次
- **超时时间**: 5分钟

## 最佳实践

### 1. 任务优先级管理
```go
// 高优先级任务（用户实时请求）
task.SetPriority(domain.TaskPriorityHigh)

// 普通优先级（异步任务）
task.SetPriority(domain.TaskPriorityNormal)

// 低优先级（后台任务）
task.SetPriority(domain.TaskPriorityLow)
```

### 2. Pipeline扩展
```go
// 实现自定义Pipeline
type CustomPipeline struct {
    // ...
}

func (p *CustomPipeline) Execute(task *domain.Task) (*domain.TaskOutput, error) {
    // 实现自定义逻辑
}

func (p *CustomPipeline) Name() string {
    return "Custom Pipeline"
}
```

### 3. 服务客户端配置
```go
// 配置连接池和超时
client := data.NewServiceClient(logger)
defer client.Close()
```

## 性能优化

### 1. 数据库优化
- 使用JSONB索引加速元数据查询
- 分区表按月分区（处理大量历史任务）
- 定期清理过期任务

### 2. 并发处理
- 使用goroutine异步执行任务
- 实现任务队列限流
- 资源池管理

### 3. 缓存策略
- 缓存服务连接
- 缓存Pipeline实例

## 测试

### 单元测试
```bash
make test
```

### 集成测试
```bash
go test -tags=integration ./...
```

### 覆盖率
```bash
make coverage
```

## 部署

### Kubernetes
```bash
helm install ai-orchestrator ./deployments/helm/ai-orchestrator
```

### 健康检查
- **HTTP**: `GET /health`
- **gRPC**: `grpc.health.v1.Health/Check`

## 故障排查

### 常见问题

1. **任务长时间pending**
   - 检查下游服务状态
   - 检查任务优先级设置
   - 查看数据库连接

2. **Pipeline执行失败**
   - 查看服务日志
   - 检查网络连接
   - 验证输入数据格式

3. **性能问题**
   - 检查数据库慢查询
   - 查看服务调用延迟
   - 监控资源使用

## 开发团队

- **Maintainer**: VoiceHelper Team
- **Created**: 2025-10-26
- **Version**: v1.0.0

## 相关文档

- [架构设计](../../docs/arch/ai-orchestrator.md)
- [API文档](../../docs/api/orchestrator.md)
- [部署指南](../../docs/runbook/ai-orchestrator.md)
