package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/elastic/go-elasticsearch/v8"
	"github.com/elastic/go-elasticsearch/v8/esapi"
	"github.com/go-kratos/kratos/v2/log"
)

// SearchService 搜索服务
type SearchService struct {
	es     *elasticsearch.Client
	logger *log.Helper
	config *SearchConfig
}

// SearchConfig 搜索配置
type SearchConfig struct {
	IndexName          string   // 索引名称
	MaxResults         int      // 最大结果数
	HighlightEnabled   bool     // 是否启用高亮
	HighlightPreTag    string   // 高亮前缀标签
	HighlightPostTag   string   // 高亮后缀标签
	SearchFields       []string // 搜索字段
	MinScore           float64  // 最小相关度分数
}

// SearchResult 搜索结果
type SearchResult struct {
	MessageID      string             `json:"message_id"`
	ConversationID string             `json:"conversation_id"`
	UserID         string             `json:"user_id"`
	TenantID       string             `json:"tenant_id"`
	Content        string             `json:"content"`
	Highlight      string             `json:"highlight,omitempty"`
	Score          float64            `json:"score"`
	Role           string             `json:"role"`
	CreatedAt      time.Time          `json:"created_at"`
	Metadata       map[string]string  `json:"metadata,omitempty"`
}

// SearchResponse 搜索响应
type SearchResponse struct {
	Results    []*SearchResult `json:"results"`
	Total      int64           `json:"total"`
	TimeTookMs int64           `json:"time_took_ms"`
	MaxScore   float64         `json:"max_score"`
}

// NewSearchService 创建搜索服务
func NewSearchService(es *elasticsearch.Client, config *SearchConfig, logger log.Logger) *SearchService {
	if config == nil {
		config = &SearchConfig{
			IndexName:        "messages",
			MaxResults:       50,
			HighlightEnabled: true,
			HighlightPreTag:  "<em>",
			HighlightPostTag: "</em>",
			SearchFields:     []string{"content", "metadata.tags"},
			MinScore:         0.0,
		}
	}

	return &SearchService{
		es:     es,
		logger: log.NewHelper(log.With(logger, "module", "search-service")),
		config: config,
	}
}

// SearchMessages 搜索消息
func (s *SearchService) SearchMessages(
	ctx context.Context,
	tenantID, userID string,
	query string,
	options *SearchOptions,
) (*SearchResponse, error) {
	if query == "" {
		return nil, fmt.Errorf("search query cannot be empty")
	}

	s.logger.Infof("Searching messages: tenant=%s, user=%s, query=%s", tenantID, userID, query)

	// 应用默认选项
	if options == nil {
		options = &SearchOptions{
			Limit:  20,
			Offset: 0,
		}
	}

	// 构建 Elasticsearch 查询
	esQuery := s.buildSearchQuery(tenantID, userID, query, options)

	// 执行搜索
	results, total, timeTook, maxScore, err := s.executeSearch(ctx, esQuery)
	if err != nil {
		return nil, err
	}

	s.logger.Infof("Search completed: found %d results in %dms", total, timeTook)

	return &SearchResponse{
		Results:    results,
		Total:      total,
		TimeTookMs: timeTook,
		MaxScore:   maxScore,
	}, nil
}

// buildSearchQuery 构建搜索查询
func (s *SearchService) buildSearchQuery(
	tenantID, userID, query string,
	options *SearchOptions,
) map[string]interface{} {
	// 基础布尔查询
	boolQuery := map[string]interface{}{
		"must": []interface{}{
			// 全文搜索
			map[string]interface{}{
				"multi_match": map[string]interface{}{
					"query":  query,
					"fields": s.config.SearchFields,
					"type":   "best_fields",
					"fuzziness": "AUTO",
				},
			},
		},
		"filter": []interface{}{
			// 租户过滤
			map[string]interface{}{
				"term": map[string]interface{}{
					"tenant_id": tenantID,
				},
			},
			// 用户过滤
			map[string]interface{}{
				"term": map[string]interface{}{
					"user_id": userID,
				},
			},
		},
	}

	// 如果指定了对话 ID
	if options.ConversationID != "" {
		boolQuery["filter"] = append(boolQuery["filter"].([]interface{}),
			map[string]interface{}{
				"term": map[string]interface{}{
					"conversation_id": options.ConversationID,
				},
			},
		)
	}

	// 如果指定了角色
	if options.Role != "" {
		boolQuery["filter"] = append(boolQuery["filter"].([]interface{}),
			map[string]interface{}{
				"term": map[string]interface{}{
					"role": options.Role,
				},
			},
		)
	}

	// 如果指定了时间范围
	if !options.StartTime.IsZero() || !options.EndTime.IsZero() {
		rangeQuery := map[string]interface{}{}
		if !options.StartTime.IsZero() {
			rangeQuery["gte"] = options.StartTime.Format(time.RFC3339)
		}
		if !options.EndTime.IsZero() {
			rangeQuery["lte"] = options.EndTime.Format(time.RFC3339)
		}

		boolQuery["filter"] = append(boolQuery["filter"].([]interface{}),
			map[string]interface{}{
				"range": map[string]interface{}{
					"created_at": rangeQuery,
				},
			},
		)
	}

	// 最小分数过滤
	query := map[string]interface{}{
		"query": map[string]interface{}{
			"bool": boolQuery,
		},
		"from": options.Offset,
		"size": options.Limit,
		"sort": []interface{}{
			map[string]interface{}{
				"_score": map[string]string{"order": "desc"},
			},
			map[string]interface{}{
				"created_at": map[string]string{"order": "desc"},
			},
		},
	}

	// 添加最小分数
	if s.config.MinScore > 0 {
		query["min_score"] = s.config.MinScore
	}

	// 添加高亮
	if s.config.HighlightEnabled {
		query["highlight"] = map[string]interface{}{
			"fields": map[string]interface{}{
				"content": map[string]interface{}{
					"pre_tags":  []string{s.config.HighlightPreTag},
					"post_tags": []string{s.config.HighlightPostTag},
					"fragment_size": 150,
					"number_of_fragments": 3,
				},
			},
		}
	}

	return query
}

// executeSearch 执行搜索
func (s *SearchService) executeSearch(
	ctx context.Context,
	query map[string]interface{},
) ([]*SearchResult, int64, int64, float64, error) {
	// 序列化查询
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		return nil, 0, 0, 0, fmt.Errorf("failed to encode query: %w", err)
	}

	// 执行搜索
	res, err := s.es.Search(
		s.es.Search.WithContext(ctx),
		s.es.Search.WithIndex(s.config.IndexName),
		s.es.Search.WithBody(&buf),
		s.es.Search.WithTrackTotalHits(true),
	)
	if err != nil {
		return nil, 0, 0, 0, fmt.Errorf("search request failed: %w", err)
	}
	defer res.Body.Close()

	// 检查响应状态
	if res.IsError() {
		var e map[string]interface{}
		if err := json.NewDecoder(res.Body).Decode(&e); err != nil {
			return nil, 0, 0, 0, fmt.Errorf("error parsing error response: %w", err)
		}
		return nil, 0, 0, 0, fmt.Errorf("search error: %v", e)
	}

	// 解析响应
	var response map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&response); err != nil {
		return nil, 0, 0, 0, fmt.Errorf("error parsing response: %w", err)
	}

	// 提取结果
	hits := response["hits"].(map[string]interface{})
	total := int64(hits["total"].(map[string]interface{})["value"].(float64))
	timeTook := int64(response["took"].(float64))
	
	maxScore := 0.0
	if hits["max_score"] != nil {
		maxScore = hits["max_score"].(float64)
	}

	results := make([]*SearchResult, 0)
	for _, hit := range hits["hits"].([]interface{}) {
		hitMap := hit.(map[string]interface{})
		source := hitMap["_source"].(map[string]interface{})

		result := &SearchResult{
			MessageID:      source["id"].(string),
			ConversationID: source["conversation_id"].(string),
			UserID:         source["user_id"].(string),
			TenantID:       source["tenant_id"].(string),
			Content:        source["content"].(string),
			Role:           source["role"].(string),
			Score:          hitMap["_score"].(float64),
		}

		// 解析时间
		if createdAt, ok := source["created_at"].(string); ok {
			if t, err := time.Parse(time.RFC3339, createdAt); err == nil {
				result.CreatedAt = t
			}
		}

		// 提取高亮
		if highlight, ok := hitMap["highlight"].(map[string]interface{}); ok {
			if contentHL, ok := highlight["content"].([]interface{}); ok && len(contentHL) > 0 {
				highlights := make([]string, len(contentHL))
				for i, h := range contentHL {
					highlights[i] = h.(string)
				}
				result.Highlight = strings.Join(highlights, " ... ")
			}
		}

		// 提取元数据
		if metadata, ok := source["metadata"].(map[string]interface{}); ok {
			result.Metadata = make(map[string]string)
			for k, v := range metadata {
				if str, ok := v.(string); ok {
					result.Metadata[k] = str
				}
			}
		}

		results = append(results, result)
	}

	return results, total, timeTook, maxScore, nil
}

// IndexMessage 索引消息
func (s *SearchService) IndexMessage(ctx context.Context, message *MessageDocument) error {
	s.logger.Debugf("Indexing message: id=%s", message.ID)

	// 序列化消息
	data, err := json.Marshal(message)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	// 索引文档
	req := esapi.IndexRequest{
		Index:      s.config.IndexName,
		DocumentID: message.ID,
		Body:       bytes.NewReader(data),
		Refresh:    "true",
	}

	res, err := req.Do(ctx, s.es)
	if err != nil {
		return fmt.Errorf("failed to index message: %w", err)
	}
	defer res.Body.Close()

	if res.IsError() {
		return fmt.Errorf("error indexing message: %s", res.String())
	}

	return nil
}

// DeleteMessage 删除消息索引
func (s *SearchService) DeleteMessage(ctx context.Context, messageID string) error {
	s.logger.Debugf("Deleting message: id=%s", messageID)

	req := esapi.DeleteRequest{
		Index:      s.config.IndexName,
		DocumentID: messageID,
		Refresh:    "true",
	}

	res, err := req.Do(ctx, s.es)
	if err != nil {
		return fmt.Errorf("failed to delete message: %w", err)
	}
	defer res.Body.Close()

	if res.IsError() && res.StatusCode != 404 {
		return fmt.Errorf("error deleting message: %s", res.String())
	}

	return nil
}

// BulkIndexMessages 批量索引消息
func (s *SearchService) BulkIndexMessages(ctx context.Context, messages []*MessageDocument) error {
	if len(messages) == 0 {
		return nil
	}

	s.logger.Infof("Bulk indexing %d messages", len(messages))

	var buf bytes.Buffer
	for _, message := range messages {
		// 元数据行
		meta := map[string]interface{}{
			"index": map[string]interface{}{
				"_index": s.config.IndexName,
				"_id":    message.ID,
			},
		}
		if err := json.NewEncoder(&buf).Encode(meta); err != nil {
			return fmt.Errorf("failed to encode meta: %w", err)
		}

		// 文档行
		if err := json.NewEncoder(&buf).Encode(message); err != nil {
			return fmt.Errorf("failed to encode message: %w", err)
		}
	}

	res, err := s.es.Bulk(
		bytes.NewReader(buf.Bytes()),
		s.es.Bulk.WithContext(ctx),
		s.es.Bulk.WithRefresh("true"),
	)
	if err != nil {
		return fmt.Errorf("bulk index failed: %w", err)
	}
	defer res.Body.Close()

	if res.IsError() {
		return fmt.Errorf("bulk index error: %s", res.String())
	}

	return nil
}

// CreateIndex 创建索引（初始化时调用）
func (s *SearchService) CreateIndex(ctx context.Context) error {
	s.logger.Infof("Creating index: %s", s.config.IndexName)

	// 索引映射
	mapping := `{
		"mappings": {
			"properties": {
				"id": { "type": "keyword" },
				"conversation_id": { "type": "keyword" },
				"user_id": { "type": "keyword" },
				"tenant_id": { "type": "keyword" },
				"role": { "type": "keyword" },
				"content": {
					"type": "text",
					"analyzer": "standard",
					"fields": {
						"keyword": { "type": "keyword" }
					}
				},
				"created_at": { "type": "date" },
				"metadata": {
					"type": "object",
					"enabled": true
				}
			}
		},
		"settings": {
			"number_of_shards": 1,
			"number_of_replicas": 1,
			"analysis": {
				"analyzer": {
					"default": {
						"type": "standard"
					}
				}
			}
		}
	}`

	res, err := s.es.Indices.Create(
		s.config.IndexName,
		s.es.Indices.Create.WithContext(ctx),
		s.es.Indices.Create.WithBody(strings.NewReader(mapping)),
	)
	if err != nil {
		return fmt.Errorf("failed to create index: %w", err)
	}
	defer res.Body.Close()

	if res.IsError() {
		// 忽略索引已存在的错误
		if !strings.Contains(res.String(), "resource_already_exists_exception") {
			return fmt.Errorf("error creating index: %s", res.String())
		}
	}

	s.logger.Infof("Index created successfully: %s", s.config.IndexName)
	return nil
}

// SearchOptions 搜索选项
type SearchOptions struct {
	ConversationID string    // 对话 ID 过滤
	Role           string    // 角色过滤
	StartTime      time.Time // 开始时间
	EndTime        time.Time // 结束时间
	Limit          int       // 返回数量
	Offset         int       // 偏移量
}

// MessageDocument 消息文档（用于索引）
type MessageDocument struct {
	ID             string            `json:"id"`
	ConversationID string            `json:"conversation_id"`
	UserID         string            `json:"user_id"`
	TenantID       string            `json:"tenant_id"`
	Role           string            `json:"role"`
	Content        string            `json:"content"`
	CreatedAt      time.Time         `json:"created_at"`
	Metadata       map[string]string `json:"metadata,omitempty"`
}

