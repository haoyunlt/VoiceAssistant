package saga

import (
	"context"
	"errors"
	"fmt"
	"time"
)

var (
	// ErrSagaAborted saga被中止
	ErrSagaAborted = errors.New("saga aborted")
	// ErrCompensationFailed 补偿失败
	ErrCompensationFailed = errors.New("compensation failed")
)

// Step saga步骤
type Step struct {
	// Name 步骤名称
	Name string
	// Execute 执行函数
	Execute func(ctx context.Context) error
	// Compensate 补偿函数（回滚）
	Compensate func(ctx context.Context) error
	// Timeout 超时时间
	Timeout time.Duration
}

// Saga saga协调器
type Saga struct {
	steps          []Step
	executedSteps  []int // 已执行的步骤索引
	onStepComplete func(stepName string, err error)
}

// NewSaga 创建saga
func NewSaga() *Saga {
	return &Saga{
		steps:         make([]Step, 0),
		executedSteps: make([]int, 0),
	}
}

// AddStep 添加步骤
func (s *Saga) AddStep(step Step) *Saga {
	s.steps = append(s.steps, step)
	return s
}

// OnStepComplete 设置步骤完成回调
func (s *Saga) OnStepComplete(fn func(stepName string, err error)) *Saga {
	s.onStepComplete = fn
	return s
}

// Execute 执行saga
func (s *Saga) Execute(ctx context.Context) error {
	// 执行所有步骤
	for i, step := range s.steps {
		// 创建带超时的context
		stepCtx := ctx
		cancel := func() {} // 默认空函数，避免nil调用

		if step.Timeout > 0 {
			stepCtx, cancel = context.WithTimeout(ctx, step.Timeout)
		}

		// 执行步骤
		err := step.Execute(stepCtx)

		// 立即释放context资源，避免泄漏
		cancel()

		// 回调
		if s.onStepComplete != nil {
			s.onStepComplete(step.Name, err)
		}

		if err != nil {
			// 执行失败，进行补偿
			compensateErr := s.compensate(ctx, i-1)
			if compensateErr != nil {
				return errors.Join(err, compensateErr)
			}
			return fmt.Errorf("saga step '%s' failed: %w", step.Name, err)
		}

		// 记录已执行的步骤
		s.executedSteps = append(s.executedSteps, i)
	}

	return nil
}

// compensate 执行补偿（从最后一个成功的步骤开始回滚）
func (s *Saga) compensate(ctx context.Context, lastSuccessIndex int) error {
	var errs []error

	// 逆序执行补偿
	for i := lastSuccessIndex; i >= 0; i-- {
		step := s.steps[i]

		if step.Compensate == nil {
			continue
		}

		// 创建带超时的context
		compensateCtx := ctx
		cancel := func() {}

		if step.Timeout > 0 {
			compensateCtx, cancel = context.WithTimeout(ctx, step.Timeout)
		}

		// 执行补偿
		if err := step.Compensate(compensateCtx); err != nil {
			errs = append(errs, fmt.Errorf("compensation for step '%s' failed: %w", step.Name, err))
		}

		// 立即释放context资源
		cancel()
	}

	if len(errs) > 0 {
		return errors.Join(append([]error{ErrCompensationFailed}, errs...)...)
	}

	return nil
}

// Builder saga构建器
type Builder struct {
	saga *Saga
}

// NewBuilder 创建构建器
func NewBuilder() *Builder {
	return &Builder{
		saga: NewSaga(),
	}
}

// AddStep 添加步骤
func (b *Builder) AddStep(name string, execute func(ctx context.Context) error, compensate func(ctx context.Context) error) *Builder {
	b.saga.AddStep(Step{
		Name:       name,
		Execute:    execute,
		Compensate: compensate,
	})
	return b
}

// AddStepWithTimeout 添加带超时的步骤
func (b *Builder) AddStepWithTimeout(name string, execute func(ctx context.Context) error, compensate func(ctx context.Context) error, timeout time.Duration) *Builder {
	b.saga.AddStep(Step{
		Name:       name,
		Execute:    execute,
		Compensate: compensate,
		Timeout:    timeout,
	})
	return b
}

// OnStepComplete 设置步骤完成回调
func (b *Builder) OnStepComplete(fn func(stepName string, err error)) *Builder {
	b.saga.OnStepComplete(fn)
	return b
}

// Build 构建saga
func (b *Builder) Build() *Saga {
	return b.saga
}

// Execute 执行saga
func (b *Builder) Execute(ctx context.Context) error {
	return b.saga.Execute(ctx)
}

// AsyncSaga 异步saga（基于事件）
type AsyncSaga struct {
	steps    []AsyncStep
	state    SagaState
	eventBus EventBus
}

// AsyncStep 异步步骤
type AsyncStep struct {
	Name           string
	TriggerEvent   string // 触发事件
	CompletedEvent string // 完成事件
	FailedEvent    string // 失败事件
	Compensate     func(ctx context.Context, data interface{}) error
}

// SagaState saga状态
type SagaState struct {
	ID          string
	CurrentStep int
	Status      string // pending/running/completed/compensating/failed
	Data        interface{}
	LastUpdated time.Time
}

// EventBus 事件总线接口
type EventBus interface {
	Publish(ctx context.Context, topic string, data interface{}) error
	Subscribe(ctx context.Context, topic string, handler func(ctx context.Context, data interface{}) error) error
}

// NewAsyncSaga 创建异步saga
func NewAsyncSaga(eventBus EventBus) *AsyncSaga {
	return &AsyncSaga{
		steps:    make([]AsyncStep, 0),
		eventBus: eventBus,
		state: SagaState{
			Status: "pending",
		},
	}
}

// AddAsyncStep 添加异步步骤
func (s *AsyncSaga) AddAsyncStep(step AsyncStep) *AsyncSaga {
	s.steps = append(s.steps, step)
	return s
}

// Start 启动异步saga
func (s *AsyncSaga) Start(ctx context.Context, initialData interface{}) error {
	s.state.Status = "running"
	s.state.Data = initialData
	s.state.LastUpdated = time.Now()

	// 触发第一个步骤
	if len(s.steps) > 0 {
		return s.eventBus.Publish(ctx, s.steps[0].TriggerEvent, initialData)
	}

	return nil
}
