# AI Orchestrator 服务功能清单与迭代计划

## 服务概述

AI Orchestrator 是 AI 任务编排服务，负责统一调度和编排所有 AI 引擎，支持工作流编排和任务管理。

**技术栈**: Go + Kratos + Redis + NATS/Kafka

**端口**: 9003

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. 基础框架

- ✅ Kratos 框架搭建
- ✅ 配置管理
- ✅ 基础 HTTP 服务

### ⚠️ 待完成功能

#### 1. 核心编排逻辑

- ⚠️ 任务路由（占位代码）
- ⚠️ 工作流引擎（未实现）
- ⚠️ 流式响应（TODO）
- ⚠️ 服务发现（TODO）

---

## 二、待完成功能清单

### 🔄 P0 - 核心功能（迭代 1：2 周）

#### 1. 任务编排引擎实现

**当前状态**: 基础框架

**待实现**:

```go
// 文件: cmd/ai-orchestrator/internal/application/orchestrator_service.go

package application

import (
	"context"
	"fmt"
	"time"
)

type OrchestratorService struct {
	agentClient      *AgentEngineClient
	ragClient        *RAGEngineClient
	voiceClient      *VoiceEngineClient
	multimodalClient *MultimodalEngineClient
	redis            *redis.Client
	logger           *log.Logger
}

// ExecuteTask 执行单个任务
func (s *OrchestratorService) ExecuteTask(
	ctx context.Context,
	req *TaskRequest,
) (*TaskResponse, error) {
	// 1. 验证请求
	if err := s.validateRequest(req); err != nil {
		return nil, err
	}

	// 2. 创建任务记录
	task := &Task{
		ID:        generateTaskID(),
		Type:      req.TaskType,
		TenantID:  req.TenantID,
		UserID:    req.UserID,
		Status:    TaskStatusPending,
		CreatedAt: time.Now(),
	}

	// 保存到 Redis
	s.saveTask(ctx, task)

	// 3. 路由到对应引擎
	result, err := s.routeToEngine(ctx, req)
	if err != nil {
		task.Status = TaskStatusFailed
		task.Error = err.Error()
		s.saveTask(ctx, task)
		return nil, err
	}

	// 4. 更新任务状态
	task.Status = TaskStatusCompleted
	task.Result = result
	task.CompletedAt = time.Now()
	s.saveTask(ctx, task)

	return &TaskResponse{
		TaskID:    task.ID,
		Status:    task.Status,
		Engine:    s.getEngineName(req.TaskType),
		Result:    result,
		Duration:  task.CompletedAt.Sub(task.CreatedAt).Milliseconds(),
	}, nil
}

// routeToEngine 路由到对应引擎
func (s *OrchestratorService) routeToEngine(
	ctx context.Context,
	req *TaskRequest,
) (interface{}, error) {
	switch req.TaskType {
	case "agent":
		return s.executeAgentTask(ctx, req)

	case "rag":
		return s.executeRAGTask(ctx, req)

	case "voice_asr":
		return s.executeASRTask(ctx, req)

	case "voice_tts":
		return s.executeTTSTask(ctx, req)

	case "multimodal_ocr":
		return s.executeOCRTask(ctx, req)

	case "multimodal_vision":
		return s.executeVisionTask(ctx, req)

	default:
		return nil, fmt.Errorf("unsupported task type: %s", req.TaskType)
	}
}

// executeAgentTask 执行 Agent 任务
func (s *OrchestratorService) executeAgentTask(
	ctx context.Context,
	req *TaskRequest,
) (interface{}, error) {
	// 调用 Agent Engine
	resp, err := s.agentClient.Execute(ctx, &AgentRequest{
		Task:          req.Query,
		Tools:         req.Options["tools"].([]string),
		MaxIterations: req.Options["max_iterations"].(int),
	})

	if err != nil {
		return nil, fmt.Errorf("agent execution failed: %w", err)
	}

	return resp, nil
}

// executeRAGTask 执行 RAG 任务
func (s *OrchestratorService) executeRAGTask(
	ctx context.Context,
	req *TaskRequest,
) (interface{}, error) {
	// 调用 RAG Engine
	resp, err := s.ragClient.Generate(ctx, &RAGRequest{
		Query:           req.Query,
		KnowledgeBaseID: req.Options["knowledge_base_id"].(string),
		TopK:            req.Options["top_k"].(int),
		EnableRerank:    req.Options["enable_rerank"].(bool),
	})

	if err != nil {
		return nil, fmt.Errorf("rag generation failed: %w", err)
	}

	return resp, nil
}

// executeASRTask 执行 ASR 任务
func (s *OrchestratorService) executeASRTask(
	ctx context.Context,
	req *TaskRequest,
) (interface{}, error) {
	// 调用 Voice Engine ASR
	resp, err := s.voiceClient.Recognize(ctx, &ASRRequest{
		AudioBase64: req.Options["audio_base64"].(string),
		Language:    req.Options["language"].(string),
		EnableVAD:   req.Options["enable_vad"].(bool),
	})

	if err != nil {
		return nil, fmt.Errorf("asr failed: %w", err)
	}

	return resp, nil
}

// executeTTSTask 执行 TTS 任务
func (s *OrchestratorService) executeTTSTask(
	ctx context.Context,
	req *TaskRequest,
) (interface{}, error) {
	// 调用 Voice Engine TTS
	resp, err := s.voiceClient.Synthesize(ctx, &TTSRequest{
		Text:  req.Query,
		Voice: req.Options["voice"].(string),
		Rate:  req.Options["rate"].(string),
	})

	if err != nil {
		return nil, fmt.Errorf("tts failed: %w", err)
	}

	return resp, nil
}

// GetTask 获取任务状态
func (s *OrchestratorService) GetTask(ctx context.Context, taskID string) (*Task, error) {
	key := fmt.Sprintf("task:%s", taskID)

	data, err := s.redis.Get(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("task not found: %s", taskID)
	}

	var task Task
	if err := json.Unmarshal([]byte(data), &task); err != nil {
		return nil, err
	}

	return &task, nil
}

func (s *OrchestratorService) validateRequest(req *TaskRequest) error {
	if req.TaskType == "" {
		return fmt.Errorf("task_type is required")
	}

	if req.TenantID == "" {
		return fmt.Errorf("tenant_id is required")
	}

	if req.UserID == "" {
		return fmt.Errorf("user_id is required")
	}

	return nil
}

func (s *OrchestratorService) saveTask(ctx context.Context, task *Task) error {
	key := fmt.Sprintf("task:%s", task.ID)

	data, err := json.Marshal(task)
	if err != nil {
		return err
	}

	return s.redis.Set(ctx, key, data, 24*time.Hour).Err()
}

func (s *OrchestratorService) getEngineName(taskType string) string {
	engineMap := map[string]string{
		"agent":             "agent-engine",
		"rag":               "rag-engine",
		"voice_asr":         "voice-engine",
		"voice_tts":         "voice-engine",
		"multimodal_ocr":    "multimodal-engine",
		"multimodal_vision": "multimodal-engine",
	}

	return engineMap[taskType]
}

func generateTaskID() string {
	return fmt.Sprintf("task_%d_%s", time.Now().Unix(), uuid.New().String()[:8])
}
```

**验收标准**:

- [ ] 支持 6 种任务类型
- [ ] 任务状态管理
- [ ] 错误处理完善
- [ ] 性能监控

#### 2. 工作流引擎实现

**当前状态**: 未实现

**待实现**:

```go
// 文件: cmd/ai-orchestrator/internal/application/workflow_engine.go

package application

type WorkflowEngine struct {
	orchestrator *OrchestratorService
	redis        *redis.Client
	logger       *log.Logger
}

// ExecuteWorkflow 执行工作流
func (we *WorkflowEngine) ExecuteWorkflow(
	ctx context.Context,
	workflow *Workflow,
) (*WorkflowResult, error) {
	// 1. 验证工作流
	if err := we.validateWorkflow(workflow); err != nil {
		return nil, err
	}

	// 2. 创建工作流实例
	instance := &WorkflowInstance{
		ID:         generateWorkflowID(),
		WorkflowID: workflow.ID,
		Status:     WorkflowStatusRunning,
		StartedAt:  time.Now(),
		Context:    make(map[string]interface{}),
	}

	// 保存实例
	we.saveInstance(ctx, instance)

	// 3. 执行步骤
	for i, step := range workflow.Steps {
		// 检查是否应该执行（条件判断）
		if !we.shouldExecuteStep(ctx, step, instance) {
			continue
		}

		// 执行步骤
		result, err := we.executeStep(ctx, step, instance)
		if err != nil {
			instance.Status = WorkflowStatusFailed
			instance.Error = err.Error()
			we.saveInstance(ctx, instance)
			return nil, err
		}

		// 保存步骤结果到上下文
		instance.Context[fmt.Sprintf("step_%d_result", i)] = result

		// 检查是否应该终止
		if step.IsTerminal {
			break
		}
	}

	// 4. 工作流完成
	instance.Status = WorkflowStatusCompleted
	instance.CompletedAt = time.Now()
	we.saveInstance(ctx, instance)

	return &WorkflowResult{
		InstanceID: instance.ID,
		Status:     instance.Status,
		Duration:   instance.CompletedAt.Sub(instance.StartedAt),
		Result:     instance.Context,
	}, nil
}

// executeStep 执行单个步骤
func (we *WorkflowEngine) executeStep(
	ctx context.Context,
	step *WorkflowStep,
	instance *WorkflowInstance,
) (interface{}, error) {
	// 替换变量
	req := we.buildTaskRequest(step, instance)

	// 执行任务
	resp, err := we.orchestrator.ExecuteTask(ctx, req)
	if err != nil {
		return nil, err
	}

	return resp.Result, nil
}

// shouldExecuteStep 判断是否应该执行步骤
func (we *WorkflowEngine) shouldExecuteStep(
	ctx context.Context,
	step *WorkflowStep,
	instance *WorkflowInstance,
) bool {
	// 无条件，直接执行
	if step.Condition == nil {
		return true
	}

	// 评估条件
	return we.evaluateCondition(step.Condition, instance.Context)
}

// evaluateCondition 评估条件
func (we *WorkflowEngine) evaluateCondition(
	condition *Condition,
	context map[string]interface{},
) bool {
	// 获取左值
	leftValue := we.resolveValue(condition.Left, context)

	// 获取右值
	rightValue := we.resolveValue(condition.Right, context)

	// 比较
	switch condition.Operator {
	case "==":
		return leftValue == rightValue
	case "!=":
		return leftValue != rightValue
	case "contains":
		return strings.Contains(fmt.Sprint(leftValue), fmt.Sprint(rightValue))
	default:
		return false
	}
}

// buildTaskRequest 构建任务请求
func (we *WorkflowEngine) buildTaskRequest(
	step *WorkflowStep,
	instance *WorkflowInstance,
) *TaskRequest {
	// 替换模板变量
	query := we.replaceVariables(step.Query, instance.Context)

	// 构建请求
	req := &TaskRequest{
		TaskType:  step.Type,
		TenantID:  instance.TenantID,
		UserID:    instance.UserID,
		Query:     query,
		Options:   step.Options,
	}

	// 替换选项中的变量
	for key, value := range req.Options {
		if strValue, ok := value.(string); ok {
			req.Options[key] = we.replaceVariables(strValue, instance.Context)
		}
	}

	return req
}

// replaceVariables 替换变量
func (we *WorkflowEngine) replaceVariables(
	template string,
	context map[string]interface{},
) string {
	result := template

	// 查找所有 {{variable}} 形式的变量
	re := regexp.MustCompile(`\{\{([^}]+)\}\}`)
	matches := re.FindAllStringSubmatch(template, -1)

	for _, match := range matches {
		varName := strings.TrimSpace(match[1])
		value := context[varName]

		// 替换变量
		result = strings.ReplaceAll(result, match[0], fmt.Sprint(value))
	}

	return result
}

// validateWorkflow 验证工作流
func (we *WorkflowEngine) validateWorkflow(workflow *Workflow) error {
	if workflow == nil {
		return fmt.Errorf("workflow is nil")
	}

	if len(workflow.Steps) == 0 {
		return fmt.Errorf("workflow has no steps")
	}

	for i, step := range workflow.Steps {
		if step.Type == "" {
			return fmt.Errorf("step %d: type is required", i)
		}
	}

	return nil
}

func (we *WorkflowEngine) saveInstance(ctx context.Context, instance *WorkflowInstance) error {
	key := fmt.Sprintf("workflow:instance:%s", instance.ID)

	data, err := json.Marshal(instance)
	if err != nil {
		return err
	}

	return we.redis.Set(ctx, key, data, 24*time.Hour).Err()
}

func (we *WorkflowEngine) resolveValue(value string, context map[string]interface{}) interface{} {
	// 如果是变量引用
	if strings.HasPrefix(value, "$") {
		varName := strings.TrimPrefix(value, "$")
		return context[varName]
	}

	// 字面量
	return value
}

func generateWorkflowID() string {
	return fmt.Sprintf("wf_%d_%s", time.Now().Unix(), uuid.New().String()[:8])
}
```

**验收标准**:

- [ ] 工作流定义和执行
- [ ] 条件分支支持
- [ ] 变量替换正确
- [ ] 错误处理完善

#### 3. 流式响应实现

**当前状态**: TODO

**位置**: `cmd/ai-orchestrator/main.go` (第 172 行)

**待实现**:

```go
// 文件: cmd/ai-orchestrator/internal/server/http.go

// HandleStreamTask 处理流式任务
func (s *HTTPServer) HandleStreamTask(c *gin.Context) {
	var req TaskRequest
	if err := c.BindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}

	// 设置 SSE 头
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")

	// 创建流式通道
	streamChan := make(chan StreamEvent)
	defer close(streamChan)

	// 启动任务执行
	go func() {
		ctx := c.Request.Context()

		// 执行任务（流式）
		err := s.orchestrator.ExecuteTaskStream(ctx, &req, streamChan)
		if err != nil {
			streamChan <- StreamEvent{
				Type: "error",
				Data: map[string]interface{}{"error": err.Error()},
			}
		}

		// 发送完成事件
		streamChan <- StreamEvent{
			Type: "done",
			Data: nil,
		}
	}()

	// 发送流式事件
	for event := range streamChan {
		data, _ := json.Marshal(event.Data)
		fmt.Fprintf(c.Writer, "event: %s\ndata: %s\n\n", event.Type, string(data))
		c.Writer.Flush()

		if event.Type == "done" || event.Type == "error" {
			break
		}
	}
}

// ExecuteTaskStream 流式执行任务
func (s *OrchestratorService) ExecuteTaskStream(
	ctx context.Context,
	req *TaskRequest,
	stream chan<- StreamEvent,
) error {
	switch req.TaskType {
	case "agent":
		return s.executeAgentTaskStream(ctx, req, stream)

	case "rag":
		return s.executeRAGTaskStream(ctx, req, stream)

	default:
		return fmt.Errorf("streaming not supported for task type: %s", req.TaskType)
	}
}

// executeAgentTaskStream 流式执行 Agent 任务
func (s *OrchestratorService) executeAgentTaskStream(
	ctx context.Context,
	req *TaskRequest,
	stream chan<- StreamEvent,
) error {
	// 调用 Agent Engine 的流式接口
	agentStream, err := s.agentClient.ExecuteStream(ctx, &AgentRequest{
		Task:          req.Query,
		Tools:         req.Options["tools"].([]string),
		MaxIterations: req.Options["max_iterations"].(int),
	})
	if err != nil {
		return err
	}

	// 转发流式事件
	for event := range agentStream {
		stream <- StreamEvent{
			Type: event.Type,
			Data: event.Data,
		}
	}

	return nil
}
```

**验收标准**:

- [ ] SSE 流式响应
- [ ] 支持 Agent 流式
- [ ] 支持 RAG 流式
- [ ] 错误处理完善

---

### 🔄 P1 - 高级功能（迭代 2：1 周）

#### 1. 服务发现集成

```go
// 文件: cmd/ai-orchestrator/internal/discovery/service_discovery.go

type ServiceDiscovery struct {
	consul *api.Client
	cache  sync.Map
}

// DiscoverService 发现服务
func (sd *ServiceDiscovery) DiscoverService(serviceName string) (string, error) {
	// 先查缓存
	if cached, ok := sd.cache.Load(serviceName); ok {
		if endpoint, ok := cached.(string); ok {
			return endpoint, nil
		}
	}

	// 查询 Consul
	services, _, err := sd.consul.Health().Service(serviceName, "", true, nil)
	if err != nil {
		return "", err
	}

	if len(services) == 0 {
		return "", fmt.Errorf("service not found: %s", serviceName)
	}

	// 选择实例（简单轮询）
	service := services[rand.Intn(len(services))]
	endpoint := fmt.Sprintf("http://%s:%d", service.Service.Address, service.Service.Port)

	// 缓存
	sd.cache.Store(serviceName, endpoint)

	return endpoint, nil
}
```

**验收标准**:

- [ ] Consul 集成
- [ ] 服务发现正常
- [ ] 缓存机制有效

#### 2. 并行执行优化

```go
// ExecuteParallel 并行执行多个任务
func (s *OrchestratorService) ExecuteParallel(
	ctx context.Context,
	tasks []*TaskRequest,
) ([]*TaskResponse, error) {
	results := make([]*TaskResponse, len(tasks))
	errors := make([]error, len(tasks))

	var wg sync.WaitGroup

	for i, task := range tasks {
		wg.Add(1)
		go func(index int, req *TaskRequest) {
			defer wg.Done()

			resp, err := s.ExecuteTask(ctx, req)
			results[index] = resp
			errors[index] = err
		}(i, task)
	}

	wg.Wait()

	// 检查错误
	for _, err := range errors {
		if err != nil {
			return results, err
		}
	}

	return results, nil
}
```

**验收标准**:

- [ ] 并行执行正常
- [ ] 错误处理完善
- [ ] 性能提升明显

---

## 三、实施方案

### 阶段 1：核心功能（Week 1-2）

#### Day 1-5: 任务编排

1. 任务路由实现
2. 引擎客户端集成
3. 错误处理
4. 测试

#### Day 6-10: 工作流引擎

1. 工作流定义
2. 步骤执行
3. 条件分支
4. 变量替换
5. 测试

#### Day 11-14: 流式响应

1. SSE 实现
2. 流式路由
3. 测试

### 阶段 2：高级功能（Week 3）

#### Day 15-17: 服务发现

1. Consul 集成
2. 服务注册
3. 健康检查

#### Day 18-21: 优化

1. 并行执行
2. 缓存优化
3. 性能测试

---

## 四、验收标准

### 功能验收

- [ ] 任务路由正常
- [ ] 工作流执行正常
- [ ] 流式响应正常
- [ ] 服务发现正常

### 性能验收

- [ ] 任务编排延迟 < 100ms
- [ ] 支持 200 QPS
- [ ] 工作流执行稳定

### 质量验收

- [ ] 单元测试 > 70%
- [ ] 所有 TODO 清理
- [ ] 文档完整

---

## 总结

AI Orchestrator 的主要待完成功能：

1. **任务编排**: 统一路由到各引擎
2. **工作流引擎**: 多步骤编排执行
3. **流式响应**: SSE 流式输出
4. **服务发现**: 动态发现服务
5. **并行优化**: 并发执行任务

完成后将提供强大的 AI 任务编排能力。
