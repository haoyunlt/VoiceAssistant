package domain

import (
	"time"

	"github.com/google/uuid"
)

// TaskType 任务类型
type TaskType string

const (
	TaskTypeRAG        TaskType = "rag"        // RAG检索增强
	TaskTypeAgent      TaskType = "agent"      // Agent执行
	TaskTypeChat       TaskType = "chat"       // 普通对话
	TaskTypeVoice      TaskType = "voice"      // 语音处理
	TaskTypeMultimodal TaskType = "multimodal" // 多模态处理
)

// TaskStatus 任务状态
type TaskStatus string

const (
	TaskStatusPending   TaskStatus = "pending"   // 待执行
	TaskStatusRunning   TaskStatus = "running"   // 执行中
	TaskStatusCompleted TaskStatus = "completed" // 已完成
	TaskStatusFailed    TaskStatus = "failed"    // 失败
	TaskStatusCancelled TaskStatus = "cancelled" // 已取消
)

// TaskPriority 任务优先级
type TaskPriority int

const (
	TaskPriorityLow    TaskPriority = 0
	TaskPriorityNormal TaskPriority = 5
	TaskPriorityHigh   TaskPriority = 10
)

// Task AI任务聚合根
type Task struct {
	ID             string
	Type           TaskType
	Status         TaskStatus
	Priority       TaskPriority
	ConversationID string
	UserID         string
	TenantID       string
	Input          *TaskInput
	Output         *TaskOutput
	Steps          []*TaskStep
	Metadata       map[string]interface{}
	CreatedAt      time.Time
	UpdatedAt      time.Time
	StartedAt      *time.Time
	CompletedAt    *time.Time
}

// TaskInput 任务输入
type TaskInput struct {
	Content string                 // 输入内容
	Mode    string                 // 模式（text/voice等）
	Context map[string]interface{} // 上下文信息
	Options map[string]interface{} // 选项配置
}

// TaskOutput 任务输出
type TaskOutput struct {
	Content    string                 // 输出内容
	Metadata   map[string]interface{} // 元数据
	TokensUsed int                    // Token使用量
	Model      string                 // 使用的模型
	CostUSD    float64                // 成本（美元）
	LatencyMS  int                    // 延迟（毫秒）
}

// TaskStep 任务步骤
type TaskStep struct {
	ID          string
	Name        string
	Service     string                 // 调用的服务
	Input       map[string]interface{} // 步骤输入
	Output      map[string]interface{} // 步骤输出
	Status      TaskStatus
	Error       string
	StartedAt   time.Time
	CompletedAt *time.Time
	DurationMS  int
}

// NewTask 创建新任务
func NewTask(taskType TaskType, conversationID, userID, tenantID string, input *TaskInput) *Task {
	id := "task_" + uuid.New().String()
	now := time.Now()

	return &Task{
		ID:             id,
		Type:           taskType,
		Status:         TaskStatusPending,
		Priority:       TaskPriorityNormal,
		ConversationID: conversationID,
		UserID:         userID,
		TenantID:       tenantID,
		Input:          input,
		Steps:          make([]*TaskStep, 0),
		Metadata:       make(map[string]interface{}),
		CreatedAt:      now,
		UpdatedAt:      now,
	}
}

// NewTaskStep 创建新步骤
func NewTaskStep(name, service string) *TaskStep {
	return &TaskStep{
		ID:        uuid.New().String(),
		Name:      name,
		Service:   service,
		Status:    TaskStatusPending,
		Input:     make(map[string]interface{}),
		Output:    make(map[string]interface{}),
		StartedAt: time.Now(),
	}
}

// Start 开始执行任务
func (t *Task) Start() {
	t.Status = TaskStatusRunning
	now := time.Now()
	t.StartedAt = &now
	t.UpdatedAt = now
}

// Complete 完成任务
func (t *Task) Complete(output *TaskOutput) {
	t.Status = TaskStatusCompleted
	t.Output = output
	now := time.Now()
	t.CompletedAt = &now
	t.UpdatedAt = now
}

// Fail 任务失败
func (t *Task) Fail(errorMsg string) {
	t.Status = TaskStatusFailed
	t.Metadata["error"] = errorMsg
	now := time.Now()
	t.CompletedAt = &now
	t.UpdatedAt = now
}

// Cancel 取消任务
func (t *Task) Cancel() {
	t.Status = TaskStatusCancelled
	now := time.Now()
	t.CompletedAt = &now
	t.UpdatedAt = now
}

// AddStep 添加执行步骤
func (t *Task) AddStep(step *TaskStep) {
	t.Steps = append(t.Steps, step)
	t.UpdatedAt = time.Now()
}

// CompleteStep 完成步骤
func (step *TaskStep) CompleteStep(output map[string]interface{}) {
	step.Status = TaskStatusCompleted
	step.Output = output
	now := time.Now()
	step.CompletedAt = &now
	step.DurationMS = int(now.Sub(step.StartedAt).Milliseconds())
}

// FailStep 步骤失败
func (step *TaskStep) FailStep(errorMsg string) {
	step.Status = TaskStatusFailed
	step.Error = errorMsg
	now := time.Now()
	step.CompletedAt = &now
	step.DurationMS = int(now.Sub(step.StartedAt).Milliseconds())
}

// IsCompleted 检查任务是否完成
func (t *Task) IsCompleted() bool {
	return t.Status == TaskStatusCompleted ||
		t.Status == TaskStatusFailed ||
		t.Status == TaskStatusCancelled
}

// Duration 获取任务执行时长
func (t *Task) Duration() time.Duration {
	if t.StartedAt == nil {
		return 0
	}
	if t.CompletedAt == nil {
		return time.Since(*t.StartedAt)
	}
	return t.CompletedAt.Sub(*t.StartedAt)
}

// SetPriority 设置优先级
func (t *Task) SetPriority(priority TaskPriority) {
	t.Priority = priority
	t.UpdatedAt = time.Now()
}

// UpdateMetadata 更新元数据
func (t *Task) UpdateMetadata(key string, value interface{}) {
	if t.Metadata == nil {
		t.Metadata = make(map[string]interface{})
	}
	t.Metadata[key] = value
	t.UpdatedAt = time.Now()
}
