package biz

import (
	"context"
	"time"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// TaskWorker 后台任务执行器
type TaskWorker struct {
	queue     TaskQueue
	taskUC    *TaskUsecase
	logger    *log.Helper
	workerNum int
	stopChan  chan struct{}
}

// NewTaskWorker 创建新的TaskWorker
func NewTaskWorker(queue TaskQueue, taskUC *TaskUsecase, workerNum int, logger log.Logger) *TaskWorker {
	return &TaskWorker{
		queue:     queue,
		taskUC:    taskUC,
		logger:    log.NewHelper(logger),
		workerNum: workerNum,
		stopChan:  make(chan struct{}),
	}
}

// Start 启动Worker
func (w *TaskWorker) Start(ctx context.Context) {
	w.logger.Infof("Starting %d task workers...", w.workerNum)
	for i := 0; i < w.workerNum; i++ {
		go w.runWorker(ctx, i)
	}
}

// Stop 停止Worker
func (w *TaskWorker) Stop(ctx context.Context) error {
	w.logger.Info("Stopping task workers...")
	close(w.stopChan) // 发送停止信号
	// 可以添加等待所有worker退出的逻辑
	return nil
}

// runWorker 单个Worker的执行逻辑
func (w *TaskWorker) runWorker(ctx context.Context, workerID int) {
	w.logger.Infof("Task worker %d started.", workerID)
	for {
		select {
		case <-w.stopChan:
			w.logger.Infof("Task worker %d stopped.", workerID)
			return
		case <-ctx.Done():
			w.logger.Infof("Task worker %d received context done, stopping.", workerID)
			return
		default:
			task, err := w.queue.Dequeue(ctx)
			if err != nil {
				if err == context.Canceled || err == context.DeadlineExceeded {
					w.logger.Debugf("Worker %d: Dequeue context error: %v", workerID, err)
				} else {
					w.logger.Errorf("Worker %d: Failed to dequeue task: %v", workerID, err)
				}
				time.Sleep(time.Second) // 避免CPU空转
				continue
			}
			if task == nil {
				time.Sleep(time.Second) // 队列为空，等待
				continue
			}

			w.logger.Infof("Worker %d: Processing task %s (Type: %s)", workerID, task.ID, task.Type)

			// 异步任务需要先持久化到DB
			if err := w.taskUC.repo.Create(ctx, task); err != nil {
				w.logger.Errorf("Worker %d: Failed to persist task %s: %v", workerID, task.ID, err)
				task.Fail(err.Error())
				w.taskUC.repo.Update(ctx, task) // 更新任务状态为失败
				continue
			}

			// 执行任务
			taskCtx, cancel := context.WithTimeout(context.Background(), 5*time.Minute) // 每个任务独立超时
			_, err = w.taskUC.ExecuteTask(taskCtx, task.ID)
			cancel()

			if err != nil {
				w.logger.Errorf("Worker %d: Task %s execution failed: %v", workerID, task.ID, err)
				// ExecuteTask内部会更新任务状态为Failed
			} else {
				w.logger.Infof("Worker %d: Task %s executed successfully.", workerID, task.ID)
			}
		}
	}
}
