package domain

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// ParallelPipeline 并行Pipeline（简单并行，无依赖）
type ParallelPipeline struct {
	steps   []PipelineStep
	merger  StepMerger // 结果合并器
	client  ServiceClient
	logger  *log.Helper
	timeout time.Duration
}

// StepResult 步骤执行结果
type StepResult struct {
	Name   string
	Output map[string]interface{}
	Error  error
	Took   time.Duration
}

// StepMerger 步骤结果合并器接口
type StepMerger interface {
	Merge(results map[string]*StepResult) (*TaskOutput, error)
}

// NewParallelPipeline 创建并行Pipeline
func NewParallelPipeline(
	steps []PipelineStep,
	merger StepMerger,
	client ServiceClient,
	logger log.Logger,
) *ParallelPipeline {
	return &ParallelPipeline{
		steps:   steps,
		merger:  merger,
		client:  client,
		logger:  log.NewHelper(logger),
		timeout: 5 * time.Minute,
	}
}

// Execute 并行执行所有步骤
func (p *ParallelPipeline) Execute(task *Task) (*TaskOutput, error) {
	ctx, cancel := context.WithTimeout(context.Background(), p.timeout)
	defer cancel()

	p.logger.Infof("starting parallel execution for task %s with %d steps", task.ID, len(p.steps))

	// 创建结果通道
	results := make(chan *StepResult, len(p.steps))
	var wg sync.WaitGroup

	// 并行执行所有步骤
	for _, step := range p.steps {
		wg.Add(1)
		go func(s PipelineStep) {
			defer wg.Done()
			p.executeStep(ctx, task, s, results)
		}(step)
	}

	// 等待所有步骤完成
	go func() {
		wg.Wait()
		close(results)
	}()

	// 收集结果
	stepResults := make(map[string]*StepResult)
	for result := range results {
		stepResults[result.Name] = result
		if result.Error != nil {
			p.logger.Errorf("step %s failed: %v", result.Name, result.Error)
		} else {
			p.logger.Infof("step %s completed in %v", result.Name, result.Took)
		}
	}

	// 检查是否有步骤失败
	for _, result := range stepResults {
		if result.Error != nil {
			return nil, fmt.Errorf("step %s failed: %w", result.Name, result.Error)
		}
	}

	// 合并结果
	output, err := p.merger.Merge(stepResults)
	if err != nil {
		p.logger.Errorf("failed to merge results: %v", err)
		return nil, err
	}

	p.logger.Infof("parallel execution completed for task %s", task.ID)
	return output, nil
}

// executeStep 执行单个步骤
func (p *ParallelPipeline) executeStep(
	ctx context.Context,
	task *Task,
	step PipelineStep,
	results chan<- *StepResult,
) {
	startTime := time.Now()
	result := &StepResult{Name: step.Name()}

	// 执行步骤
	output, err := step.Execute(task.Input.Context)
	result.Output = output
	result.Error = err
	result.Took = time.Since(startTime)

	// 发送结果
	select {
	case results <- result:
	case <-ctx.Done():
		p.logger.Warnf("step %s cancelled: %v", step.Name(), ctx.Err())
	}
}

// Name 返回Pipeline名称
func (p *ParallelPipeline) Name() string {
	return "parallel_pipeline"
}

// DAGPipeline DAG（有向无环图）Pipeline，支持复杂依赖
type DAGPipeline struct {
	nodes   map[string]*DAGNode
	edges   map[string][]string // nodeID -> dependency nodeIDs
	merger  StepMerger
	logger  *log.Helper
	timeout time.Duration
}

// DAGNode DAG节点
type DAGNode struct {
	ID           string
	Step         PipelineStep
	Dependencies []string // 依赖的节点ID
}

// NewDAGPipeline 创建DAG Pipeline
func NewDAGPipeline(
	nodes []*DAGNode,
	merger StepMerger,
	logger log.Logger,
) *DAGPipeline {
	// 构建邻接表
	nodesMap := make(map[string]*DAGNode)
	edges := make(map[string][]string)

	for _, node := range nodes {
		nodesMap[node.ID] = node
		edges[node.ID] = node.Dependencies
	}

	return &DAGPipeline{
		nodes:   nodesMap,
		edges:   edges,
		merger:  merger,
		logger:  log.NewHelper(logger),
		timeout: 10 * time.Minute,
	}
}

// Execute DAG执行（拓扑排序+并行）
func (p *DAGPipeline) Execute(task *Task) (*TaskOutput, error) {
	ctx, cancel := context.WithTimeout(context.Background(), p.timeout)
	defer cancel()

	p.logger.Infof("starting DAG execution for task %s with %d nodes", task.ID, len(p.nodes))

	// 拓扑排序
	order, err := p.topologicalSort()
	if err != nil {
		return nil, fmt.Errorf("topological sort failed: %w", err)
	}

	p.logger.Debugf("DAG execution order: %v", order)

	// 执行结果存储
	results := make(map[string]*StepResult)
	resultsMu := sync.Mutex{}

	// 完成信号
	completed := make(map[string]chan struct{})
	for nodeID := range p.nodes {
		completed[nodeID] = make(chan struct{})
	}

	var wg sync.WaitGroup

	// 按拓扑顺序执行
	for _, nodeID := range order {
		node := p.nodes[nodeID]

		wg.Add(1)
		go func(n *DAGNode) {
			defer wg.Done()
			defer close(completed[n.ID])

			// 等待依赖完成
			for _, depID := range n.Dependencies {
				select {
				case <-completed[depID]:
					// 依赖完成
				case <-ctx.Done():
					p.logger.Warnf("node %s cancelled: %v", n.ID, ctx.Err())
					return
				}
			}

			// 执行节点
			startTime := time.Now()
			result := &StepResult{Name: n.ID}

			// 收集依赖结果
			depOutputs := make(map[string]interface{})
			resultsMu.Lock()
			for _, depID := range n.Dependencies {
				if depResult, ok := results[depID]; ok {
					depOutputs[depID] = depResult.Output
				}
			}
			resultsMu.Unlock()

			// 执行步骤（传入依赖结果）
			output, err := n.Step.Execute(depOutputs)
			result.Output = output
			result.Error = err
			result.Took = time.Since(startTime)

			// 存储结果
			resultsMu.Lock()
			results[n.ID] = result
			resultsMu.Unlock()

			if err != nil {
				p.logger.Errorf("node %s failed: %v", n.ID, err)
			} else {
				p.logger.Infof("node %s completed in %v", n.ID, result.Took)
			}
		}(node)
	}

	// 等待所有节点完成
	wg.Wait()

	// 检查是否有节点失败
	for _, result := range results {
		if result.Error != nil {
			return nil, fmt.Errorf("node %s failed: %w", result.Name, result.Error)
		}
	}

	// 合并结果
	output, err := p.merger.Merge(results)
	if err != nil {
		p.logger.Errorf("failed to merge DAG results: %v", err)
		return nil, err
	}

	p.logger.Infof("DAG execution completed for task %s", task.ID)
	return output, nil
}

// topologicalSort 拓扑排序（Kahn算法）
func (p *DAGPipeline) topologicalSort() ([]string, error) {
	// 计算入度
	inDegree := make(map[string]int)
	for nodeID := range p.nodes {
		inDegree[nodeID] = 0
	}
	for _, deps := range p.edges {
		for _, dep := range deps {
			inDegree[dep]++
		}
	}

	// 找出入度为0的节点
	queue := []string{}
	for nodeID, degree := range inDegree {
		if degree == 0 {
			queue = append(queue, nodeID)
		}
	}

	// Kahn算法
	result := []string{}
	for len(queue) > 0 {
		// 出队
		nodeID := queue[0]
		queue = queue[1:]
		result = append(result, nodeID)

		// 减少后继节点的入度
		for nextID, deps := range p.edges {
			for _, dep := range deps {
				if dep == nodeID {
					inDegree[nextID]--
					if inDegree[nextID] == 0 {
						queue = append(queue, nextID)
					}
				}
			}
		}
	}

	// 检查是否有环
	if len(result) != len(p.nodes) {
		return nil, fmt.Errorf("DAG contains cycle")
	}

	return result, nil
}

// Name 返回Pipeline名称
func (p *DAGPipeline) Name() string {
	return "dag_pipeline"
}

// RAGParallelMerger RAG并行步骤合并器
type RAGParallelMerger struct{}

// Merge 合并检索和画像结果
func (m *RAGParallelMerger) Merge(results map[string]*StepResult) (*TaskOutput, error) {
	retrievalResult := results["retrieval"]
	profileResult := results["user_profile"]

	if retrievalResult == nil || profileResult == nil {
		return nil, fmt.Errorf("missing required step results")
	}

	// 合并上下文
	context := make(map[string]interface{})
	context["chunks"] = retrievalResult.Output["chunks"]
	context["user_profile"] = profileResult.Output["profile"]

	// 构建输出
	output := &TaskOutput{
		Content: "检索和画像完成",
		Metadata: map[string]interface{}{
			"retrieval_time": retrievalResult.Took.Milliseconds(),
			"profile_time":   profileResult.Took.Milliseconds(),
			"total_time":     maxDuration(retrievalResult.Took, profileResult.Took).Milliseconds(),
		},
		Context: context,
	}

	return output, nil
}

// maxDuration 返回最大时长
func maxDuration(a, b time.Duration) time.Duration {
	if a > b {
		return a
	}
	return b
}
