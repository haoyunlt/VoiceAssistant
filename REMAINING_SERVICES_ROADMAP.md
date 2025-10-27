# 其他服务功能清单与迭代计划（简要版）

## 文档说明

本文档涵盖剩余服务的待完成功能清单和迭代计划，包括：

- Analytics Service（分析服务）
- Notification Service（通知服务）
- Identity Service（身份服务）
- RAG Engine（RAG 引擎）
- Indexing Service（索引服务）
- Multimodal Engine（多模态引擎）
- Knowledge Service（知识服务）

---

## 一、Analytics Service（分析服务）

### 服务概述

**技术栈**: Go + ClickHouse + Redis
**端口**: 9006
**完成度**: 30%

### 待完成功能

#### P0 - 核心功能（9 人天）

##### 1. 报表生成实现（6 天）

**位置**: `cmd/analytics-service/internal/biz/report_usecase.go`
**TODO**: 第 105, 119, 131, 143 行

```go
// 使用报表
func (uc *ReportUsecase) GenerateUsageReport(ctx context.Context, req *UsageReportRequest) (*Report, error) {
	// 1. 查询 ClickHouse 数据
	query := `
		SELECT
			date,
			COUNT(*) as total_requests,
			SUM(tokens) as total_tokens,
			AVG(latency_ms) as avg_latency,
			SUM(cost_usd) as total_cost
		FROM ai_usage_daily
		WHERE tenant_id = ? AND date BETWEEN ? AND ?
		GROUP BY date
		ORDER BY date
	`

	rows, err := uc.clickhouse.Query(ctx, query, req.TenantID, req.StartDate, req.EndDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	// 2. 聚合数据
	data := make([]UsageData, 0)
	for rows.Next() {
		var item UsageData
		if err := rows.Scan(&item.Date, &item.Requests, &item.Tokens, &item.AvgLatency, &item.Cost); err != nil {
			return nil, err
		}
		data = append(data, item)
	}

	// 3. 生成报表
	report := &Report{
		Type:      "usage",
		TenantID:  req.TenantID,
		StartDate: req.StartDate,
		EndDate:   req.EndDate,
		Data:      data,
		Summary: ReportSummary{
			TotalRequests: sumRequests(data),
			TotalTokens:   sumTokens(data),
			TotalCost:     sumCost(data),
		},
		GeneratedAt: time.Now(),
	}

	// 4. 保存报表
	if err := uc.repo.SaveReport(ctx, report); err != nil {
		return nil, err
	}

	return report, nil
}

// 成本报表
func (uc *ReportUsecase) GenerateCostReport(ctx context.Context, req *CostReportRequest) (*Report, error) {
	// 按模型统计成本
	query := `
		SELECT
			model,
			SUM(tokens) as tokens,
			SUM(cost_usd) as cost,
			COUNT(*) as requests
		FROM ai_usage_daily
		WHERE tenant_id = ? AND date BETWEEN ? AND ?
		GROUP BY model
		ORDER BY cost DESC
	`

	// 查询和聚合...
	// 生成饼图数据、趋势图数据等

	return report, nil
}

// 模型对比报表
func (uc *ReportUsecase) GenerateModelComparisonReport(ctx context.Context, req *ModelComparisonRequest) (*Report, error) {
	// 对比多个模型的性能、成本、质量
	models := req.Models

	comparison := make([]ModelComparison, 0)
	for _, model := range models {
		stats := uc.getModelStats(ctx, model, req.StartDate, req.EndDate)
		comparison = append(comparison, ModelComparison{
			Model:      model,
			AvgLatency: stats.AvgLatency,
			AvgCost:    stats.AvgCost,
			SuccessRate: stats.SuccessRate,
			Score:      stats.QualityScore,
		})
	}

	return &Report{
		Type: "model_comparison",
		Data: comparison,
	}, nil
}
```

**验收标准**:

- [ ] 4 种报表类型
- [ ] ClickHouse 查询优化
- [ ] 数据可视化友好
- [ ] 导出 PDF/Excel

##### 2. 实时统计增强（3 天）

```go
// 实时统计服务
type RealtimeStatsService struct {
	redis     *redis.Client
	clickhouse *clickhouse.Conn
}

// 获取实时统计
func (s *RealtimeStatsService) GetRealtimeStats(ctx context.Context, tenantID string) (*RealtimeStats, error) {
	// 从 Redis 获取最近5分钟的数据
	key := fmt.Sprintf("stats:realtime:%s", tenantID)

	stats := &RealtimeStats{
		ActiveUsers:       s.getActiveUsers(ctx, tenantID),
		ActiveConversations: s.getActiveConversations(ctx, tenantID),
		MessagesPerMinute: s.getMessagesPerMinute(ctx, tenantID),
		AIRequestsPerMinute: s.getAIRequestsPerMinute(ctx, tenantID),
		AvgResponseTimeMs: s.getAvgResponseTime(ctx, tenantID),
		Timestamp:         time.Now(),
	}

	return stats, nil
}

// 更新实时统计（由各服务调用）
func (s *RealtimeStatsService) UpdateStats(ctx context.Context, event *StatsEvent) error {
	// 增量更新 Redis 计数器
	pipe := s.redis.Pipeline()

	switch event.Type {
	case "message":
		pipe.Incr(ctx, fmt.Sprintf("stats:msg_count:%s", event.TenantID))
		pipe.Expire(ctx, fmt.Sprintf("stats:msg_count:%s", event.TenantID), 5*time.Minute)

	case "ai_request":
		pipe.Incr(ctx, fmt.Sprintf("stats:ai_count:%s", event.TenantID))
		pipe.ZAdd(ctx, fmt.Sprintf("stats:latency:%s", event.TenantID), &redis.Z{
			Score:  float64(time.Now().Unix()),
			Member: event.Latency,
		})
	}

	_, err := pipe.Exec(ctx)
	return err
}
```

**验收标准**:

- [ ] 5 分钟延迟
- [ ] 高并发支持
- [ ] Redis 优化

---

## 二、Notification Service（通知服务）

### 服务概述

**技术栈**: Go + Kafka + Redis + SMTP
**端口**: 9005
**完成度**: 30%

### 待完成功能

#### P0 - 核心功能（12 人天）

##### 1. Kafka 消费者实现（3 天）

```go
// Kafka 事件消费
type EventConsumer struct {
	kafka     *kafka.Reader
	notifier  *NotificationService
}

func (ec *EventConsumer) Start(ctx context.Context) {
	for {
		msg, err := ec.kafka.ReadMessage(ctx)
		if err != nil {
			continue
		}

		// 解析事件
		var event Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			continue
		}

		// 路由到通知服务
		ec.handleEvent(ctx, &event)
	}
}

func (ec *EventConsumer) handleEvent(ctx context.Context, event *Event) {
	switch event.Type {
	case "conversation.message.sent":
		ec.notifier.NotifyNewMessage(ctx, event)

	case "document.uploaded":
		ec.notifier.NotifyDocumentUploaded(ctx, event)

	case "document.indexed":
		ec.notifier.NotifyDocumentIndexed(ctx, event)

	case "ai.task.completed":
		ec.notifier.NotifyTaskCompleted(ctx, event)
	}
}
```

##### 2. 模板系统（4 天）

```go
// 模板管理
type TemplateManager struct {
	repo  *TemplateRepository
	cache *redis.Client
}

// 渲染模板
func (tm *TemplateManager) Render(ctx context.Context, templateID string, data map[string]interface{}) (string, error) {
	// 获取模板
	template, err := tm.getTemplate(ctx, templateID)
	if err != nil {
		return "", err
	}

	// 渲染
	tmpl, err := template.New("notification").Parse(template.Content)
	if err != nil {
		return "", err
	}

	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, data); err != nil {
		return "", err
	}

	return buf.String(), nil
}
```

##### 3. 多渠道集成（5 天）

```go
// 邮件发送
type EmailChannel struct {
	smtp SMTPConfig
}

func (ec *EmailChannel) Send(ctx context.Context, notif *Notification) error {
	// 使用 SMTP 发送邮件
	m := gomail.NewMessage()
	m.SetHeader("From", ec.smtp.From)
	m.SetHeader("To", notif.Recipient)
	m.SetHeader("Subject", notif.Subject)
	m.SetBody("text/html", notif.Body)

	d := gomail.NewDialer(ec.smtp.Host, ec.smtp.Port, ec.smtp.Username, ec.smtp.Password)
	return d.DialAndSend(m)
}

// SMS 发送
type SMSChannel struct {
	twilio TwilioConfig
}

func (sc *SMSChannel) Send(ctx context.Context, notif *Notification) error {
	// 使用 Twilio 发送 SMS
	client := twilio.NewRestClient(sc.twilio.AccountSID, sc.twilio.AuthToken)

	params := &twilio.CreateMessageParams{}
	params.SetFrom(sc.twilio.From)
	params.SetTo(notif.Recipient)
	params.SetBody(notif.Body)

	_, err := client.Api.CreateMessage(params)
	return err
}

// Push 通知
type PushChannel struct {
	fcm FCMConfig
}

func (pc *PushChannel) Send(ctx context.Context, notif *Notification) error {
	// 使用 FCM 发送 Push
	// ...
}
```

**验收标准**:

- [ ] Kafka 消费正常
- [ ] 模板渲染正确
- [ ] 3 种渠道都可用
- [ ] 发送成功率 > 95%

---

## 三、Identity Service（身份服务）

### 服务概述

**技术栈**: Go + PostgreSQL + Redis + JWT
**端口**: 8000/9000
**完成度**: 85%（基本完成）

### 待完成功能

#### P1 - 优化功能（5 人天）

##### 1. 审计日志（2 天）

**文件**: `cmd/identity-service/internal/biz/audit_log.go`（已创建）

```go
// 审计日志服务
type AuditLogService struct {
	repo *AuditLogRepository
}

// 记录审计日志
func (s *AuditLogService) Log(ctx context.Context, log *AuditLog) error {
	log.ID = uuid.New().String()
	log.Timestamp = time.Now()

	return s.repo.Create(ctx, log)
}

// 查询审计日志
func (s *AuditLogService) Query(ctx context.Context, filter *AuditLogFilter) ([]*AuditLog, error) {
	return s.repo.Query(ctx, filter)
}
```

##### 2. OAuth2 集成（3 天）

```go
// OAuth2 提供商
type OAuth2Provider struct {
	config *oauth2.Config
}

// 第三方登录
func (p *OAuth2Provider) Login(ctx context.Context, code string) (*User, error) {
	// 交换 token
	token, err := p.config.Exchange(ctx, code)
	if err != nil {
		return nil, err
	}

	// 获取用户信息
	userInfo, err := p.getUserInfo(ctx, token)
	if err != nil {
		return nil, err
	}

	// 创建或更新用户
	user := &User{
		Email:    userInfo.Email,
		Name:     userInfo.Name,
		Avatar:   userInfo.Avatar,
		Provider: "google",
	}

	return user, nil
}
```

---

## 四、RAG Engine（RAG 引擎）

### 服务概述

**技术栈**: Python + FastAPI + LangChain
**端口**: 8006
**完成度**: 85%（基本完成）

### 待完成功能

#### P1 - 优化功能（4 人天）

##### 1. Self-RAG 实现（2 天）

**文件**: `algo/rag-engine/app/services/self_rag_service.py`（已创建）

```python
class SelfRAGService:
    """
    Self-RAG: 自反思 RAG
    1. 检索
    2. 评估检索质量
    3. 如果质量不够，重新检索或生成
    """

    async def generate(self, query: str, kb_id: str) -> dict:
        # 1. 首次检索
        docs = await self.retrieval_service.search(query, kb_id, top_k=5)

        # 2. 评估检索质量
        quality = await self.evaluate_retrieval(query, docs)

        if quality < 0.7:
            # 3. 重新检索（使用不同策略）
            docs = await self.retrieval_service.search(
                query, kb_id, top_k=10, strategy="diversified"
            )

        # 4. 生成答案
        answer = await self.llm_service.generate(query, docs)

        # 5. 评估答案质量
        answer_quality = await self.evaluate_answer(query, answer, docs)

        if answer_quality < 0.7:
            # 反思并重新生成
            answer = await self.regenerate_with_reflection(query, docs, answer)

        return {
            "answer": answer,
            "docs": docs,
            "quality_scores": {
                "retrieval": quality,
                "answer": answer_quality
            }
        }
```

##### 2. 缓存优化（2 天）

```python
class RAGCacheService:
    """RAG 结果缓存"""

    def __init__(self):
        self.redis = redis.Redis()

    async def get_cached(self, query: str, kb_id: str) -> Optional[dict]:
        cache_key = self.generate_cache_key(query, kb_id)

        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        return None

    async def cache_result(self, query: str, kb_id: str, result: dict):
        cache_key = self.generate_cache_key(query, kb_id)

        self.redis.setex(
            cache_key,
            3600,  # 1小时
            json.dumps(result)
        )
```

---

## 五、Indexing Service（索引服务）

### 服务概述

**技术栈**: Python + FastAPI + Milvus + Neo4j
**端口**: 8008
**完成度**: 85%（基本完成）

### 待完成功能

#### P1 - 优化功能（3 人天）

##### 1. 实体关系抽取完善（2 天）

**文件**: `algo/indexing-service/app/core/entity_extractor.py`
**TODO**: 第 233 行

```python
class EntityRelationExtractor:
    """实体关系抽取"""

    async def extract_relations(self, text: str, entities: List[Entity]) -> List[Relation]:
        """
        使用 LLM 抽取实体间关系
        """
        # 构建 prompt
        entities_text = "\n".join([f"- {e.name} ({e.type})" for e in entities])

        prompt = f"""
        文本: {text}

        已识别实体:
        {entities_text}

        请识别实体之间的关系，返回 JSON 格式:
        [
            {{"head": "实体1", "relation": "关系类型", "tail": "实体2"}},
            ...
        ]
        """

        # 调用 LLM
        response = await self.llm_client.complete(prompt)

        # 解析结果
        relations = json.loads(response)

        return [Relation(**r) for r in relations]
```

##### 2. 批量索引优化（1 天）

```python
async def bulk_index_documents(self, documents: List[Document]) -> dict:
    """批量索引优化"""
    # 1. 并发解析
    parsed_docs = await asyncio.gather(*[
        self.parse_document(doc) for doc in documents
    ])

    # 2. 批量分块
    all_chunks = []
    for doc in parsed_docs:
        chunks = self.chunk_document(doc)
        all_chunks.extend(chunks)

    # 3. 批量向量化
    embeddings = await self.embedding_service.batch_embed(
        [chunk.content for chunk in all_chunks],
        batch_size=32
    )

    # 4. 批量插入 Milvus
    await self.milvus_client.bulk_insert(all_chunks, embeddings)

    return {"indexed": len(all_chunks)}
```

---

## 六、Multimodal Engine（多模态引擎）

### 服务概述

**技术栈**: Python + FastAPI + PaddleOCR + CLIP
**端口**: 8009
**完成度**: 75%

### 待完成功能

#### P0 - 核心功能（5 人天）

##### 1. EasyOCR 集成（2 天）

**文件**: `algo/multimodal-engine/app/services/ocr_service.py`
**TODO**: 第 181 行

```python
class EasyOCRService:
    """EasyOCR 服务（备用方案）"""

    def __init__(self):
        self.reader = easyocr.Reader(['ch_sim', 'en'])

    async def recognize(self, image_data: bytes) -> List[TextBlock]:
        # 加载图像
        image = Image.open(io.BytesIO(image_data))
        image_np = np.array(image)

        # OCR 识别
        results = self.reader.readtext(image_np)

        # 格式化结果
        text_blocks = []
        for bbox, text, confidence in results:
            text_blocks.append(TextBlock(
                text=text,
                confidence=confidence,
                bbox=bbox
            ))

        return text_blocks
```

##### 2. 视觉理解增强（3 天）

```python
class VisionUnderstandingService:
    """视觉理解服务增强"""

    async def comprehensive_analysis(
        self,
        image_data: bytes
    ) -> dict:
        """综合分析"""
        # 并发执行多个任务
        results = await asyncio.gather(
            self.describe_image(image_data),
            self.detect_objects(image_data),
            self.recognize_scene(image_data),
            self.extract_colors(image_data),
            self.extract_text(image_data)
        )

        return {
            "description": results[0],
            "objects": results[1],
            "scene": results[2],
            "colors": results[3],
            "text": results[4]
        }
```

---

## 七、Knowledge Service（知识服务）

### 服务概述

**技术栈**: Python + FastAPI + Neo4j
**端口**: 8010
**完成度**: 90%（基本完成）

### 待完成功能

#### P1 - 优化功能（2 人天）

##### 1. 图谱查询优化（1 天）

```python
class KnowledgeGraphOptimizer:
    """知识图谱查询优化"""

    async def optimize_query(self, query: str) -> str:
        """优化 Cypher 查询"""
        # 添加索引提示
        # 限制遍历深度
        # 使用缓存
        pass
```

##### 2. 图谱统计（1 天）

```python
async def get_graph_statistics(self, kb_id: str) -> dict:
    """获取图谱统计信息"""
    return {
        "node_count": await self.count_nodes(kb_id),
        "relation_count": await self.count_relations(kb_id),
        "entity_types": await self.get_entity_types(kb_id),
        "relation_types": await self.get_relation_types(kb_id)
    }
```

---

## 八、优先级汇总

### 立即开始（本周）

| 服务         | 功能         | 优先级 | 工作量 |
| ------------ | ------------ | ------ | ------ |
| Analytics    | 报表生成     | P0     | 6 天   |
| Notification | Kafka 消费   | P0     | 3 天   |
| Multimodal   | EasyOCR 集成 | P0     | 2 天   |

### 第二周

| 服务         | 功能       | 优先级 | 工作量 |
| ------------ | ---------- | ------ | ------ |
| Notification | 模板系统   | P0     | 4 天   |
| Notification | 多渠道集成 | P0     | 5 天   |
| Analytics    | 实时统计   | P0     | 3 天   |

### 第三周（优化）

| 服务       | 功能     | 优先级 | 工作量 |
| ---------- | -------- | ------ | ------ |
| RAG Engine | Self-RAG | P1     | 2 天   |
| Multimodal | 视觉理解 | P0     | 3 天   |
| Identity   | 审计日志 | P1     | 2 天   |
| Indexing   | 批量优化 | P1     | 1 天   |

---

## 九、总结

### 工作量统计

| 服务         | P0        | P1        | P2       | 总计      |
| ------------ | --------- | --------- | -------- | --------- |
| Analytics    | 9 天      | 0 天      | 0 天     | 9 天      |
| Notification | 12 天     | 0 天      | 0 天     | 12 天     |
| Identity     | 0 天      | 5 天      | 0 天     | 5 天      |
| RAG Engine   | 0 天      | 4 天      | 0 天     | 4 天      |
| Indexing     | 0 天      | 3 天      | 0 天     | 3 天      |
| Multimodal   | 5 天      | 0 天      | 0 天     | 5 天      |
| Knowledge    | 0 天      | 2 天      | 0 天     | 2 天      |
| **总计**     | **26 天** | **14 天** | **0 天** | **40 天** |

### 完成标准

所有服务完成后应达到：

- [ ] 核心功能 100% 完成
- [ ] 高级功能 80% 完成
- [ ] 单元测试覆盖率 > 70%
- [ ] 所有 TODO 清理
- [ ] API 文档完整
- [ ] 运维文档完整

---

**最后更新**: 2025-10-27
