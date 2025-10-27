# VoiceHelper 功能迁移 - 详细实现 (功能 4-10)

> **补充文档**: 剩余 7 项功能的详细设计和代码实现
> **参考**: VOICEHELPER_MIGRATION_PLAN.md

---

## 4. 分布式限流器

### 当前状态

- ❌ 仅本地限流，不准确
- ❌ 多实例无法协调
- ❌ 无法全局限流

### VoiceHelper 实现亮点

- ✅ 基于 Redis 的分布式限流
- ✅ Token Bucket 算法
- ✅ 支持突发流量
- ✅ 多维度限流 (用户/IP/租户)

### 详细设计

#### 核心实现 (Go)

```go
// pkg/middleware/rate_limiter.go

package middleware

import (
    "context"
    "fmt"
    "time"

    "github.com/gin-gonic/gin"
    "github.com/go-redis/redis/v8"
    "github.com/go-redis/redis_rate/v10"
)

type RateLimiterConfig struct {
    RedisClient *redis.Client
    Rate        int           // 每秒请求数
    Burst       int           // 突发容量
    KeyFunc     func(*gin.Context) string  // 生成限流 key
}

// DistributedRateLimiter 分布式限流中间件 (参考 voicehelper)
func DistributedRateLimiter(config RateLimiterConfig) gin.HandlerFunc {
    limiter := redis_rate.NewLimiter(config.RedisClient)

    return func(c *gin.Context) {
        // 生成限流 key
        key := config.KeyFunc(c)

        // 检查限流
        ctx := context.Background()
        result, err := limiter.Allow(ctx, key, redis_rate.PerSecond(config.Rate))

        if err != nil {
            c.JSON(500, gin.H{
                "error": "Rate limiter error",
                "details": err.Error(),
            })
            c.Abort()
            return
        }

        // 设置响应头
        c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", config.Rate))
        c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", result.Remaining))
        c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", time.Now().Add(time.Second).Unix()))

        if result.Allowed == 0 {
            // 限流
            c.JSON(429, gin.H{
                "error": "Rate limit exceeded",
                "retry_after": result.RetryAfter.Seconds(),
                "limit": config.Rate,
                "remaining": result.Remaining,
            })
            c.Abort()
            return
        }

        c.Next()
    }
}

// 多维度限流器
type MultiDimensionRateLimiter struct {
    RedisClient *redis.Client
    Limiters    map[string]*redis_rate.Limiter
}

func NewMultiDimensionRateLimiter(redisClient *redis.Client) *MultiDimensionRateLimiter {
    return &MultiDimensionRateLimiter{
        RedisClient: redisClient,
        Limiters:    make(map[string]*redis_rate.Limiter),
    }
}

func (m *MultiDimensionRateLimiter) Middleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        ctx := context.Background()

        // 1. IP 限流 (全局)
        ipKey := fmt.Sprintf("ratelimit:ip:%s", c.ClientIP())
        ipLimiter := redis_rate.NewLimiter(m.RedisClient)

        ipResult, err := ipLimiter.Allow(ctx, ipKey, redis_rate.PerSecond(100))  // 100 req/s per IP
        if err == nil && ipResult.Allowed == 0 {
            c.JSON(429, gin.H{
                "error": "IP rate limit exceeded",
                "retry_after": ipResult.RetryAfter.Seconds(),
            })
            c.Abort()
            return
        }

        // 2. 用户限流
        userID := c.GetString("user_id")
        if userID != "" {
            userKey := fmt.Sprintf("ratelimit:user:%s", userID)
            userLimiter := redis_rate.NewLimiter(m.RedisClient)

            userResult, err := userLimiter.Allow(ctx, userKey, redis_rate.PerSecond(50))  // 50 req/s per user
            if err == nil && userResult.Allowed == 0 {
                c.JSON(429, gin.H{
                    "error": "User rate limit exceeded",
                    "retry_after": userResult.RetryAfter.Seconds(),
                })
                c.Abort()
                return
            }

            // 设置响应头
            c.Header("X-RateLimit-User-Limit", "50")
            c.Header("X-RateLimit-User-Remaining", fmt.Sprintf("%d", userResult.Remaining))
        }

        // 3. 租户限流
        tenantID := c.GetString("tenant_id")
        if tenantID != "" {
            tenantKey := fmt.Sprintf("ratelimit:tenant:%s", tenantID)
            tenantLimiter := redis_rate.NewLimiter(m.RedisClient)

            tenantResult, err := tenantLimiter.Allow(ctx, tenantKey, redis_rate.PerMinute(1000))  // 1000 req/min per tenant
            if err == nil && tenantResult.Allowed == 0 {
                c.JSON(429, gin.H{
                    "error": "Tenant rate limit exceeded",
                    "retry_after": tenantResult.RetryAfter.Seconds(),
                })
                c.Abort()
                return
            }
        }

        c.Next()
    }
}
```

#### 集成到 Gateway

```go
// cmd/api-gateway/main.go

func setupRouter(redisClient *redis.Client) *gin.Engine {
    r := gin.Default()

    // 全局限流 (IP)
    r.Use(middleware.DistributedRateLimiter(middleware.RateLimiterConfig{
        RedisClient: redisClient,
        Rate:        100,
        Burst:       200,
        KeyFunc: func(c *gin.Context) string {
            return fmt.Sprintf("global:ip:%s", c.ClientIP())
        },
    }))

    // 认证
    r.Use(middleware.AuthMiddleware())

    // 多维度限流
    multiLimiter := middleware.NewMultiDimensionRateLimiter(redisClient)
    r.Use(multiLimiter.Middleware())

    // 路由
    // ...

    return r
}
```

#### 配置

```yaml
# configs/gateway/rate-limit.yaml

rate_limit:
  enabled: true
  redis:
    url: 'redis://localhost:6379/0'

  # 全局限流
  global:
    rate: 1000 # req/s
    burst: 2000

  # IP 限流
  ip:
    rate: 100 # req/s per IP
    burst: 200

  # 用户限流
  user:
    rate: 50 # req/s per user
    burst: 100

  # 租户限流
  tenant:
    rate: 1000 # req/min per tenant
    burst: 2000

  # 接口级限流
  endpoints:
    - path: '/v1/chat/completions'
      rate: 10 # req/s
      burst: 20

    - path: '/v1/embeddings'
      rate: 50
      burst: 100
```

#### 监控指标

```go
// pkg/monitoring/rate_limit_metrics.go

var (
    rateLimitTotal = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "rate_limit_requests_total",
            Help: "Total number of rate limit checks",
        },
        []string{"dimension", "result"},  // dimension: ip/user/tenant, result: allowed/denied
    )

    rateLimitDenied = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "rate_limit_denied_total",
            Help: "Total number of rate limited requests",
        },
        []string{"dimension"},
    )
)

func RecordRateLimit(dimension string, allowed bool) {
    result := "allowed"
    if !allowed {
        result = "denied"
        rateLimitDenied.WithLabelValues(dimension).Inc()
    }

    rateLimitTotal.WithLabelValues(dimension, result).Inc()
}
```

### 验收标准

- [ ] 分布式限流生效
- [ ] 多实例协调正确
- [ ] Token Bucket 算法准确
- [ ] 多维度限流互不干扰
- [ ] 限流指标可监控

**工作量**: 2-3 天
**责任人**: Backend Engineer 1
**Sprint**: Sprint 2

---

## 5. GLM-4 模型支持

### 当前状态

- ❌ 仅支持 OpenAI 和 Claude
- ❌ 无国产模型支持
- ❌ 无成本优化选项

### VoiceHelper 实现亮点

- ✅ 完整的 GLM-4 系列支持
- ✅ 流式和非流式双模式
- ✅ 函数调用支持
- ✅ 统一的接口适配

### 详细设计

#### GLM-4 适配器

```go
// cmd/model-router/internal/adapters/zhipu_adapter.go

package adapters

import (
    "bufio"
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "strings"
    "time"
)

type ZhipuAdapter struct {
    APIKey  string
    BaseURL string
    Client  *http.Client
}

func NewZhipuAdapter(apiKey string) *ZhipuAdapter {
    return &ZhipuAdapter{
        APIKey:  apiKey,
        BaseURL: "https://open.bigmodel.cn/api/paas/v4",
        Client: &http.Client{
            Timeout: 60 * time.Second,
        },
    }
}

// 智谱 AI 请求格式
type ZhipuChatRequest struct {
    Model       string                   `json:"model"`
    Messages    []ZhipuMessage           `json:"messages"`
    Temperature float64                  `json:"temperature,omitempty"`
    TopP        float64                  `json:"top_p,omitempty"`
    MaxTokens   int                      `json:"max_tokens,omitempty"`
    Stream      bool                     `json:"stream,omitempty"`
    Tools       []ZhipuTool              `json:"tools,omitempty"`
}

type ZhipuMessage struct {
    Role    string `json:"role"`
    Content string `json:"content"`
}

type ZhipuTool struct {
    Type     string              `json:"type"`
    Function ZhipuFunctionSchema `json:"function"`
}

type ZhipuFunctionSchema struct {
    Name        string                 `json:"name"`
    Description string                 `json:"description"`
    Parameters  map[string]interface{} `json:"parameters"`
}

// 智谱 AI 响应格式
type ZhipuChatResponse struct {
    ID      string         `json:"id"`
    Created int64          `json:"created"`
    Model   string         `json:"model"`
    Choices []ZhipuChoice  `json:"choices"`
    Usage   ZhipuUsage     `json:"usage"`
}

type ZhipuChoice struct {
    Index        int          `json:"index"`
    Message      ZhipuMessage `json:"message"`
    FinishReason string       `json:"finish_reason"`
}

type ZhipuUsage struct {
    PromptTokens     int `json:"prompt_tokens"`
    CompletionTokens int `json:"completion_tokens"`
    TotalTokens      int `json:"total_tokens"`
}

// Chat 非流式请求
func (a *ZhipuAdapter) Chat(ctx context.Context, req ChatRequest) (*ChatResponse, error) {
    // 转换为智谱格式
    zhipuReq := a.convertToZhipuRequest(req)

    // 发送请求
    reqBody, _ := json.Marshal(zhipuReq)
    httpReq, _ := http.NewRequestWithContext(ctx, "POST", a.BaseURL+"/chat/completions", bytes.NewReader(reqBody))

    httpReq.Header.Set("Content-Type", "application/json")
    httpReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", a.APIKey))

    resp, err := a.Client.Do(httpReq)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    if resp.StatusCode != 200 {
        body, _ := io.ReadAll(resp.Body)
        return nil, fmt.Errorf("GLM-4 API error: %s", string(body))
    }

    // 解析响应
    var zhipuResp ZhipuChatResponse
    if err := json.NewDecoder(resp.Body).Decode(&zhipuResp); err != nil {
        return nil, err
    }

    // 转换为标准格式
    return a.convertFromZhipuResponse(&zhipuResp), nil
}

// ChatStream 流式请求
func (a *ZhipuAdapter) ChatStream(ctx context.Context, req ChatRequest) (<-chan ChatStreamChunk, error) {
    // 转换为智谱格式
    zhipuReq := a.convertToZhipuRequest(req)
    zhipuReq.Stream = true

    // 发送请求
    reqBody, _ := json.Marshal(zhipuReq)
    httpReq, _ := http.NewRequestWithContext(ctx, "POST", a.BaseURL+"/chat/completions", bytes.NewReader(reqBody))

    httpReq.Header.Set("Content-Type", "application/json")
    httpReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", a.APIKey))

    resp, err := a.Client.Do(httpReq)
    if err != nil {
        return nil, err
    }

    if resp.StatusCode != 200 {
        body, _ := io.ReadAll(resp.Body)
        resp.Body.Close()
        return nil, fmt.Errorf("GLM-4 API error: %s", string(body))
    }

    // 创建流式通道
    chunks := make(chan ChatStreamChunk, 10)

    go func() {
        defer close(chunks)
        defer resp.Body.Close()

        scanner := bufio.NewScanner(resp.Body)
        for scanner.Scan() {
            line := scanner.Text()

            // 跳过空行
            if line == "" {
                continue
            }

            // SSE 格式: data: {...}
            if !strings.HasPrefix(line, "data: ") {
                continue
            }

            data := strings.TrimPrefix(line, "data: ")

            // 结束标记
            if data == "[DONE]" {
                break
            }

            // 解析 JSON
            var chunk ZhipuChatResponse
            if err := json.Unmarshal([]byte(data), &chunk); err != nil {
                continue
            }

            // 转换并发送
            if len(chunk.Choices) > 0 {
                chunks <- ChatStreamChunk{
                    Delta: chunk.Choices[0].Message.Content,
                    FinishReason: chunk.Choices[0].FinishReason,
                }
            }
        }
    }()

    return chunks, nil
}

func (a *ZhipuAdapter) convertToZhipuRequest(req ChatRequest) ZhipuChatRequest {
    // 映射模型名称
    model := req.Model
    if strings.HasPrefix(model, "glm-4") {
        // 保持不变
    } else {
        model = "glm-4"  // 默认
    }

    // 转换消息
    messages := make([]ZhipuMessage, len(req.Messages))
    for i, msg := range req.Messages {
        messages[i] = ZhipuMessage{
            Role:    msg.Role,
            Content: msg.Content,
        }
    }

    return ZhipuChatRequest{
        Model:       model,
        Messages:    messages,
        Temperature: req.Temperature,
        TopP:        req.TopP,
        MaxTokens:   req.MaxTokens,
    }
}

func (a *ZhipuAdapter) convertFromZhipuResponse(resp *ZhipuChatResponse) *ChatResponse {
    if len(resp.Choices) == 0 {
        return nil
    }

    return &ChatResponse{
        ID:      resp.ID,
        Model:   resp.Model,
        Content: resp.Choices[0].Message.Content,
        Usage: Usage{
            PromptTokens:     resp.Usage.PromptTokens,
            CompletionTokens: resp.Usage.CompletionTokens,
            TotalTokens:      resp.Usage.TotalTokens,
        },
        FinishReason: resp.Choices[0].FinishReason,
    }
}
```

#### 集成到 Model Router

```go
// cmd/model-router/internal/application/model_router.go

type ModelRouter struct {
    openai   *OpenAIAdapter
    claude   *ClaudeAdapter
    zhipu    *ZhipuAdapter  // 新增
    // ...
}

func NewModelRouter(config *Config) *ModelRouter {
    return &ModelRouter{
        openai: NewOpenAIAdapter(config.OpenAI.APIKey),
        claude: NewClaudeAdapter(config.Claude.APIKey),
        zhipu:  NewZhipuAdapter(config.Zhipu.APIKey),  // 新增
    }
}

func (r *ModelRouter) Route(ctx context.Context, req ChatRequest) (*ChatResponse, error) {
    // 根据模型名称选择适配器
    switch {
    case strings.HasPrefix(req.Model, "gpt-"):
        return r.openai.Chat(ctx, req)

    case strings.HasPrefix(req.Model, "claude-"):
        return r.claude.Chat(ctx, req)

    case strings.HasPrefix(req.Model, "glm-"):  // 新增
        return r.zhipu.Chat(ctx, req)

    default:
        return nil, fmt.Errorf("unsupported model: %s", req.Model)
    }
}

func (r *ModelRouter) RouteStream(ctx context.Context, req ChatRequest) (<-chan ChatStreamChunk, error) {
    switch {
    case strings.HasPrefix(req.Model, "gpt-"):
        return r.openai.ChatStream(ctx, req)

    case strings.HasPrefix(req.Model, "claude-"):
        return r.claude.ChatStream(ctx, req)

    case strings.HasPrefix(req.Model, "glm-"):  // 新增
        return r.zhipu.ChatStream(ctx, req)

    default:
        return nil, fmt.Errorf("unsupported model: %s", req.Model)
    }
}
```

#### 配置

```yaml
# configs/app/model-router.yaml

models:
  providers:
    - name: openai
      api_key: '${OPENAI_API_KEY}'
      base_url: 'https://api.openai.com/v1'
      models:
        - gpt-4
        - gpt-3.5-turbo

    - name: claude
      api_key: '${CLAUDE_API_KEY}'
      base_url: 'https://api.anthropic.com/v1'
      models:
        - claude-3-opus
        - claude-3-sonnet

    - name: zhipu # 新增
      api_key: '${ZHIPU_API_KEY}'
      base_url: 'https://open.bigmodel.cn/api/paas/v4'
      models:
        - glm-4
        - glm-4-air
        - glm-4-airx
        - glm-4-flash

  # 模型降级策略
  fallback:
    gpt-4:
      - gpt-3.5-turbo
      - glm-4 # 成本降级

    claude-3-opus:
      - claude-3-sonnet
      - glm-4

  # 成本优化
  cost_optimization:
    enabled: true
    prefer_models:
      - glm-4-flash # 最便宜
      - glm-4-air
      - gpt-3.5-turbo
```

### 验收标准

- [ ] GLM-4 非流式请求正常
- [ ] GLM-4 流式请求正常
- [ ] 函数调用支持
- [ ] 模型降级策略生效
- [ ] 成本降低 20%+

**工作量**: 2 天
**责任人**: Backend Engineer 1
**Sprint**: Sprint 3

---

## 6. 文档版本管理

### 当前状态

- ❌ 文档无版本控制
- ❌ 无法回滚
- ❌ 无法查看历史

### VoiceHelper 实现亮点

- ✅ 完整的版本管理
- ✅ 版本比对
- ✅ 一键回滚
- ✅ 历史记录追踪

### 详细设计

#### 数据库表设计

```sql
-- migrations/postgres/010_document_versions.up.sql

CREATE TABLE document_versions (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id),
    version INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    file_path VARCHAR(500),
    file_size BIGINT,
    mime_type VARCHAR(100),
    metadata JSONB,
    change_description TEXT,
    created_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(document_id, version)
);

CREATE INDEX idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX idx_document_versions_created_at ON document_versions(created_at);

-- 文档表添加版本字段
ALTER TABLE documents
ADD COLUMN current_version INT DEFAULT 1,
ADD COLUMN version_count INT DEFAULT 1;
```

#### Go 实现

```go
// cmd/knowledge-service/internal/biz/document_version_usecase.go

package biz

import (
    "context"
    "fmt"
    "time"
)

type DocumentVersion struct {
    ID                 int64
    DocumentID         int64
    Version            int
    Title              string
    Content            string
    FilePath           string
    FileSize           int64
    MimeType           string
    Metadata           map[string]interface{}
    ChangeDescription  string
    CreatedBy          string
    CreatedAt          time.Time
}

type DocumentVersionUseCase struct {
    repo    DocumentVersionRepo
    minio   *MinIOClient
}

func NewDocumentVersionUseCase(repo DocumentVersionRepo, minio *MinIOClient) *DocumentVersionUseCase {
    return &DocumentVersionUseCase{
        repo:  repo,
        minio: minio,
    }
}

// CreateVersion 创建新版本
func (uc *DocumentVersionUseCase) CreateVersion(
    ctx context.Context,
    documentID int64,
    changeDescription string,
    userID string,
) (*DocumentVersion, error) {

    // 1. 获取当前文档
    document, err := uc.repo.GetDocument(ctx, documentID)
    if err != nil {
        return nil, err
    }

    // 2. 创建版本记录
    version := &DocumentVersion{
        DocumentID:        documentID,
        Version:           document.CurrentVersion + 1,
        Title:             document.Title,
        Content:           document.Content,
        FilePath:          document.FilePath,
        FileSize:          document.FileSize,
        MimeType:          document.MimeType,
        Metadata:          document.Metadata,
        ChangeDescription: changeDescription,
        CreatedBy:         userID,
        CreatedAt:         time.Now(),
    }

    // 3. 复制文件到版本目录
    if document.FilePath != "" {
        versionFilePath := fmt.Sprintf(
            "documents/%d/versions/v%d/%s",
            documentID,
            version.Version,
            extractFileName(document.FilePath),
        )

        err = uc.minio.CopyObject(ctx, document.FilePath, versionFilePath)
        if err != nil {
            return nil, fmt.Errorf("copy file failed: %w", err)
        }

        version.FilePath = versionFilePath
    }

    // 4. 保存版本
    err = uc.repo.CreateVersion(ctx, version)
    if err != nil {
        return nil, err
    }

    // 5. 更新文档版本计数
    err = uc.repo.UpdateDocumentVersionInfo(ctx, documentID, version.Version)
    if err != nil {
        return nil, err
    }

    return version, nil
}

// ListVersions 列出版本
func (uc *DocumentVersionUseCase) ListVersions(
    ctx context.Context,
    documentID int64,
    offset, limit int,
) ([]*DocumentVersion, int, error) {

    versions, total, err := uc.repo.ListVersions(ctx, documentID, offset, limit)
    if err != nil {
        return nil, 0, err
    }

    return versions, total, nil
}

// GetVersion 获取指定版本
func (uc *DocumentVersionUseCase) GetVersion(
    ctx context.Context,
    documentID int64,
    version int,
) (*DocumentVersion, error) {

    v, err := uc.repo.GetVersion(ctx, documentID, version)
    if err != nil {
        return nil, err
    }

    return v, nil
}

// CompareVersions 比较两个版本
func (uc *DocumentVersionUseCase) CompareVersions(
    ctx context.Context,
    documentID int64,
    version1, version2 int,
) (*VersionComparison, error) {

    // 获取两个版本
    v1, err := uc.repo.GetVersion(ctx, documentID, version1)
    if err != nil {
        return nil, err
    }

    v2, err := uc.repo.GetVersion(ctx, documentID, version2)
    if err != nil {
        return nil, err
    }

    // 计算差异
    comparison := &VersionComparison{
        Version1:    version1,
        Version2:    version2,
        TitleChange: v1.Title != v2.Title,
        SizeChange:  v2.FileSize - v1.FileSize,
        Changes:     computeTextDiff(v1.Content, v2.Content),
    }

    return comparison, nil
}

// RestoreVersion 恢复到指定版本
func (uc *DocumentVersionUseCase) RestoreVersion(
    ctx context.Context,
    documentID int64,
    targetVersion int,
    userID string,
) error {

    // 1. 获取目标版本
    version, err := uc.repo.GetVersion(ctx, documentID, targetVersion)
    if err != nil {
        return err
    }

    // 2. 先创建当前版本备份
    _, err = uc.CreateVersion(ctx, documentID, fmt.Sprintf("Restore to v%d", targetVersion), userID)
    if err != nil {
        return err
    }

    // 3. 恢复文档内容
    document, _ := uc.repo.GetDocument(ctx, documentID)

    // 复制版本文件到当前
    if version.FilePath != "" {
        currentFilePath := fmt.Sprintf("documents/%d/current/%s", documentID, extractFileName(version.FilePath))

        err = uc.minio.CopyObject(ctx, version.FilePath, currentFilePath)
        if err != nil {
            return fmt.Errorf("restore file failed: %w", err)
        }

        document.FilePath = currentFilePath
    }

    document.Title = version.Title
    document.Content = version.Content
    document.FileSize = version.FileSize
    document.MimeType = version.MimeType
    document.Metadata = version.Metadata

    // 4. 更新文档
    err = uc.repo.UpdateDocument(ctx, document)
    if err != nil {
        return err
    }

    return nil
}

// DeleteVersion 删除版本 (仅删除文件，保留记录)
func (uc *DocumentVersionUseCase) DeleteVersion(
    ctx context.Context,
    documentID int64,
    version int,
) error {

    // 获取版本
    v, err := uc.repo.GetVersion(ctx, documentID, version)
    if err != nil {
        return err
    }

    // 删除文件
    if v.FilePath != "" {
        err = uc.minio.DeleteObject(ctx, v.FilePath)
        if err != nil {
            return fmt.Errorf("delete version file failed: %w", err)
        }
    }

    // 标记版本为已删除 (保留记录)
    err = uc.repo.MarkVersionDeleted(ctx, documentID, version)
    if err != nil {
        return err
    }

    return nil
}

func computeTextDiff(text1, text2 string) []string {
    // 简化实现: 行级别 diff
    // 生产环境应使用专业的 diff 库

    lines1 := strings.Split(text1, "\n")
    lines2 := strings.Split(text2, "\n")

    changes := []string{}

    maxLen := len(lines1)
    if len(lines2) > maxLen {
        maxLen = len(lines2)
    }

    for i := 0; i < maxLen; i++ {
        line1 := ""
        line2 := ""

        if i < len(lines1) {
            line1 = lines1[i]
        }
        if i < len(lines2) {
            line2 = lines2[i]
        }

        if line1 != line2 {
            if line1 == "" {
                changes = append(changes, fmt.Sprintf("+ %s", line2))
            } else if line2 == "" {
                changes = append(changes, fmt.Sprintf("- %s", line1))
            } else {
                changes = append(changes, fmt.Sprintf("- %s", line1))
                changes = append(changes, fmt.Sprintf("+ %s", line2))
            }
        }
    }

    return changes
}
```

#### API 接口

```go
// cmd/knowledge-service/internal/routers/document_version_router.go

// CreateVersion 创建文档版本
// @Summary 创建文档版本
// @Tags DocumentVersion
// @Param id path int64 true "文档 ID"
// @Param request body CreateVersionRequest true "版本信息"
// @Success 200 {object} DocumentVersion
// @Router /api/v1/documents/{id}/versions [post]
func (r *DocumentRouter) CreateVersion(c *gin.Context) {
    documentID := parseInt64(c.Param("id"))

    var req CreateVersionRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(400, gin.H{"error": err.Error()})
        return
    }

    version, err := r.versionUseCase.CreateVersion(
        c.Request.Context(),
        documentID,
        req.ChangeDescription,
        c.GetString("user_id"),
    )

    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, version)
}

// ListVersions 列出文档版本
// @Summary 列出文档版本
// @Tags DocumentVersion
// @Param id path int64 true "文档 ID"
// @Param offset query int false "偏移量"
// @Param limit query int false "数量"
// @Success 200 {object} ListVersionsResponse
// @Router /api/v1/documents/{id}/versions [get]
func (r *DocumentRouter) ListVersions(c *gin.Context) {
    documentID := parseInt64(c.Param("id"))
    offset := parseIntQuery(c, "offset", 0)
    limit := parseIntQuery(c, "limit", 20)

    versions, total, err := r.versionUseCase.ListVersions(
        c.Request.Context(),
        documentID,
        offset,
        limit,
    )

    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, gin.H{
        "versions": versions,
        "total":    total,
        "offset":   offset,
        "limit":    limit,
    })
}

// CompareVersions 比较版本
// @Summary 比较两个版本
// @Tags DocumentVersion
// @Param id path int64 true "文档 ID"
// @Param v1 query int true "版本 1"
// @Param v2 query int true "版本 2"
// @Success 200 {object} VersionComparison
// @Router /api/v1/documents/{id}/versions/compare [get]
func (r *DocumentRouter) CompareVersions(c *gin.Context) {
    documentID := parseInt64(c.Param("id"))
    version1 := parseIntQuery(c, "v1", 0)
    version2 := parseIntQuery(c, "v2", 0)

    comparison, err := r.versionUseCase.CompareVersions(
        c.Request.Context(),
        documentID,
        version1,
        version2,
    )

    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, comparison)
}

// RestoreVersion 恢复版本
// @Summary 恢复到指定版本
// @Tags DocumentVersion
// @Param id path int64 true "文档 ID"
// @Param version path int true "目标版本"
// @Success 200 {object} SuccessResponse
// @Router /api/v1/documents/{id}/versions/{version}/restore [post]
func (r *DocumentRouter) RestoreVersion(c *gin.Context) {
    documentID := parseInt64(c.Param("id"))
    version := parseInt(c.Param("version"))

    err := r.versionUseCase.RestoreVersion(
        c.Request.Context(),
        documentID,
        version,
        c.GetString("user_id"),
    )

    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }

    c.JSON(200, gin.H{"message": "版本恢复成功"})
}
```

### 验收标准

- [ ] 版本创建成功
- [ ] 版本列表正常
- [ ] 版本比对准确
- [ ] 版本恢复成功
- [ ] 文件版本独立存储

**工作量**: 3-4 天
**责任人**: Backend Engineer 2
**Sprint**: Sprint 3

---

## 7. 病毒扫描 (ClamAV)

### 当前状态

- ❌ 无病毒扫描
- ❌ 存在安全风险
- ❌ 无法拦截恶意文件

### VoiceHelper 实现亮点

- ✅ ClamAV 集成
- ✅ 异步扫描
- ✅ 实时通知
- ✅ 病毒隔离

### 详细设计

#### Docker 部署 ClamAV

```yaml
# deployments/docker/clamav.yaml

version: '3.8'

services:
  clamav:
    image: clamav/clamav:latest
    container_name: clamav
    ports:
      - '3310:3310'
    volumes:
      - clamav-db:/var/lib/clamav
    environment:
      - CLAMAV_NO_FRESHCLAM=false
    restart: unless-stopped

volumes:
  clamav-db:
```

#### Go 实现

```go
// cmd/knowledge-service/internal/biz/virus_scanner.go

package biz

import (
    "context"
    "fmt"
    "io"
    "net"
    "strings"
    "time"
)

type VirusScanner struct {
    clamavHost string
    clamavPort int
    timeout    time.Duration
}

func NewVirusScanner(host string, port int) *VirusScanner {
    return &VirusScanner{
        clamavHost: host,
        clamavPort: port,
        timeout:    30 * time.Second,
    }
}

type ScanResult struct {
    IsClean      bool
    Virus        string
    ScanDuration time.Duration
}

// ScanFile 扫描文件
func (vs *VirusScanner) ScanFile(ctx context.Context, filePath string) (*ScanResult, error) {
    startTime := time.Now()

    // 连接 ClamAV
    conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", vs.clamavHost, vs.clamavPort), vs.timeout)
    if err != nil {
        return nil, fmt.Errorf("connect to ClamAV failed: %w", err)
    }
    defer conn.Close()

    // 设置超时
    conn.SetDeadline(time.Now().Add(vs.timeout))

    // 打开文件
    file, err := os.Open(filePath)
    if err != nil {
        return nil, fmt.Errorf("open file failed: %w", err)
    }
    defer file.Close()

    // 发送扫描命令
    _, err = conn.Write([]byte("zINSTREAM\x00"))
    if err != nil {
        return nil, fmt.Errorf("send command failed: %w", err)
    }

    // 分块发送文件内容
    buf := make([]byte, 2048)
    for {
        n, err := file.Read(buf)
        if err != nil && err != io.EOF {
            return nil, fmt.Errorf("read file failed: %w", err)
        }

        if n == 0 {
            break
        }

        // 发送数据块大小 (4 bytes, big-endian)
        sizeBytes := make([]byte, 4)
        sizeBytes[0] = byte(n >> 24)
        sizeBytes[1] = byte(n >> 16)
        sizeBytes[2] = byte(n >> 8)
        sizeBytes[3] = byte(n)

        _, err = conn.Write(sizeBytes)
        if err != nil {
            return nil, fmt.Errorf("send size failed: %w", err)
        }

        // 发送数据块
        _, err = conn.Write(buf[:n])
        if err != nil {
            return nil, fmt.Errorf("send data failed: %w", err)
        }
    }

    // 发送结束标记 (size = 0)
    _, err = conn.Write([]byte{0, 0, 0, 0})
    if err != nil {
        return nil, fmt.Errorf("send end marker failed: %w", err)
    }

    // 读取扫描结果
    response := make([]byte, 1024)
    n, err := conn.Read(response)
    if err != nil {
        return nil, fmt.Errorf("read response failed: %w", err)
    }

    result := string(response[:n])

    // 解析结果
    result = strings.TrimSpace(result)

    scanResult := &ScanResult{
        ScanDuration: time.Since(startTime),
    }

    if strings.Contains(result, "OK") {
        // 文件干净
        scanResult.IsClean = true
    } else if strings.Contains(result, "FOUND") {
        // 发现病毒
        scanResult.IsClean = false

        // 提取病毒名称
        parts := strings.Split(result, ":")
        if len(parts) >= 2 {
            virusInfo := strings.TrimSpace(parts[1])
            scanResult.Virus = strings.TrimSuffix(virusInfo, " FOUND")
        }
    } else {
        return nil, fmt.Errorf("unexpected response: %s", result)
    }

    return scanResult, nil
}

// ScanStream 扫描流
func (vs *VirusScanner) ScanStream(ctx context.Context, reader io.Reader) (*ScanResult, error) {
    // 临时文件
    tmpFile, err := os.CreateTemp("", "virus-scan-*")
    if err != nil {
        return nil, err
    }
    defer os.Remove(tmpFile.Name())
    defer tmpFile.Close()

    // 写入临时文件
    _, err = io.Copy(tmpFile, reader)
    if err != nil {
        return nil, err
    }

    // 扫描
    return vs.ScanFile(ctx, tmpFile.Name())
}
```

#### 集成到文档上传

```go
// cmd/knowledge-service/internal/biz/document_usecase.go

func (uc *DocumentUseCase) UploadDocument(
    ctx context.Context,
    tenantID, userID string,
    file io.Reader,
    filename string,
    mimeType string,
) (*Document, error) {

    // 1. 病毒扫描
    scanResult, err := uc.virusScanner.ScanStream(ctx, file)
    if err != nil {
        return nil, fmt.Errorf("virus scan failed: %w", err)
    }

    if !scanResult.IsClean {
        // 发现病毒，拒绝上传
        logger.Warn("Virus detected",
            "filename", filename,
            "virus", scanResult.Virus,
            "user_id", userID,
        )

        // 记录安全事件
        uc.auditLog.Log(ctx, AuditEvent{
            Type:      "virus_detected",
            UserID:    userID,
            TenantID:  tenantID,
            Resource:  fmt.Sprintf("file:%s", filename),
            Details:   map[string]interface{}{"virus": scanResult.Virus},
            Timestamp: time.Now(),
        })

        return nil, fmt.Errorf("virus detected: %s", scanResult.Virus)
    }

    logger.Info("Virus scan passed",
        "filename", filename,
        "duration_ms", scanResult.ScanDuration.Milliseconds(),
    )

    // 2. 正常上传流程
    // ...
}
```

#### 异步扫描 (可选)

```go
// 异步扫描 - 先上传后扫描，扫描中禁止下载

func (uc *DocumentUseCase) UploadDocumentAsync(
    ctx context.Context,
    tenantID, userID string,
    file io.Reader,
    filename string,
    mimeType string,
) (*Document, error) {

    // 1. 先上传到临时目录
    tmpPath := fmt.Sprintf("documents/%s/quarantine/%s", tenantID, uuid.New().String())

    err := uc.minio.UploadObject(ctx, tmpPath, file)
    if err != nil {
        return nil, err
    }

    // 2. 创建文档记录 (标记为扫描中)
    doc := &Document{
        TenantID:     tenantID,
        UserID:       userID,
        Title:        filename,
        FilePath:     tmpPath,
        MimeType:     mimeType,
        Status:       "scanning",  // 扫描中
        CreatedAt:    time.Now(),
    }

    err = uc.repo.CreateDocument(ctx, doc)
    if err != nil {
        return nil, err
    }

    // 3. 异步扫描
    go func() {
        scanCtx := context.Background()

        // 下载文件到本地
        tmpFile, _ := os.CreateTemp("", "scan-*")
        defer os.Remove(tmpFile.Name())
        defer tmpFile.Close()

        uc.minio.DownloadObject(scanCtx, tmpPath, tmpFile)
        tmpFile.Seek(0, 0)

        // 扫描
        scanResult, err := uc.virusScanner.ScanFile(scanCtx, tmpFile.Name())

        if err != nil {
            // 扫描失败
            uc.repo.UpdateDocumentStatus(scanCtx, doc.ID, "scan_failed")
            return
        }

        if !scanResult.IsClean {
            // 发现病毒
            uc.repo.UpdateDocumentStatus(scanCtx, doc.ID, "infected")
            uc.repo.UpdateDocumentMetadata(scanCtx, doc.ID, map[string]interface{}{
                "virus": scanResult.Virus,
            })

            // 记录安全事件
            uc.auditLog.Log(scanCtx, AuditEvent{
                Type:      "virus_detected_async",
                UserID:    userID,
                TenantID:  tenantID,
                Resource:  fmt.Sprintf("document:%d", doc.ID),
                Details:   map[string]interface{}{"virus": scanResult.Virus},
            })

            // 删除文件
            uc.minio.DeleteObject(scanCtx, tmpPath)

        } else {
            // 扫描通过，移动到正式目录
            finalPath := fmt.Sprintf("documents/%s/%d/%s", tenantID, doc.ID, filename)

            err = uc.minio.CopyObject(scanCtx, tmpPath, finalPath)
            if err == nil {
                uc.minio.DeleteObject(scanCtx, tmpPath)

                uc.repo.UpdateDocument(scanCtx, doc.ID, map[string]interface{}{
                    "file_path": finalPath,
                    "status":    "active",
                })
            }
        }
    }()

    return doc, nil
}
```

### 验收标准

- [ ] ClamAV 服务正常运行
- [ ] 病毒扫描准确拦截恶意文件
- [ ] 扫描延迟 < 3s (1MB 文件)
- [ ] 异步扫描不阻塞上传
- [ ] 安全事件正确记录

**工作量**: 2-3 天
**责任人**: Backend Engineer 2
**Sprint**: Sprint 4

---

## 8. Push 通知

### 详细设计省略 (参考主迁移文档)

**工作量**: 3-4 天
**Sprint**: Sprint 4

---

## 9. 情感识别

### 详细设计省略 (参考主迁移文档)

**工作量**: 3-4 天
**Sprint**: Sprint 5

---

## 10. Consul 服务发现

### 详细设计省略 (参考主迁移文档)

**工作量**: 4-5 天
**Sprint**: Sprint 2

---

**文档版本**: v1.0.0
**生成日期**: 2025-10-27
**配套文档**: VOICEHELPER_MIGRATION_PLAN.md
