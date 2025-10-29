package clients

import (
	"context"
	"fmt"

	analyticspb "voicehelper/api/proto/analytics/v1"
	grpcpkg "voicehelper/pkg/grpc"

	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// AnalyticsClient Analytics 服务客户端包装器
type AnalyticsClient struct {
	client  analyticspb.AnalyticsServiceClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewAnalyticsClient 创建 Analytics 服务客户端
func NewAnalyticsClient(factory *grpcpkg.ClientFactory, target string) (*AnalyticsClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &AnalyticsClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *AnalyticsClient) getClient(ctx context.Context) (analyticspb.AnalyticsServiceClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "analytics-service", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get analytics service connection: %w", err)
	}

	c.client = analyticspb.NewAnalyticsServiceClient(conn)
	return c.client, nil
}

// TrackEvent 记录事件
func (c *AnalyticsClient) TrackEvent(ctx context.Context, req *analyticspb.TrackEventRequest) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.TrackEvent(ctx, req)
	return err
}

// TrackEventBatch 批量记录事件
func (c *AnalyticsClient) TrackEventBatch(ctx context.Context, events []*analyticspb.TrackEventRequest) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.TrackEventBatch(ctx, &analyticspb.TrackEventBatchRequest{
		Events: events,
	})
	return err
}

// GetMetric 获取指标
func (c *AnalyticsClient) GetMetric(ctx context.Context, req *analyticspb.GetMetricRequest) (*analyticspb.MetricResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetMetric(ctx, req)
}

// GetReport 获取报表
func (c *AnalyticsClient) GetReport(ctx context.Context, req *analyticspb.GetReportRequest) (*analyticspb.ReportResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetReport(ctx, req)
}

// CreateReport 创建自定义报表
func (c *AnalyticsClient) CreateReport(ctx context.Context, req *analyticspb.CreateReportRequest) (*analyticspb.Report, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CreateReport(ctx, req)
}

// GetDashboard 获取实时仪表盘数据
func (c *AnalyticsClient) GetDashboard(ctx context.Context, req *analyticspb.GetDashboardRequest) (*analyticspb.DashboardResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetDashboard(ctx, req)
}

// HealthCheck 健康检查
func (c *AnalyticsClient) HealthCheck(ctx context.Context) (*analyticspb.HealthResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.HealthCheck(ctx, &emptypb.Empty{})
}

// 便捷方法

// TrackSimpleEvent 记录简单事件
func (c *AnalyticsClient) TrackSimpleEvent(
	ctx context.Context,
	tenantID, userID, eventName string,
	properties map[string]string,
) error {
	return c.TrackEvent(ctx, &analyticspb.TrackEventRequest{
		TenantId:   tenantID,
		UserId:     userID,
		EventName:  eventName,
		Properties: properties,
		Timestamp:  timestamppb.Now(),
	})
}

// GetMetricSimple 获取简单指标
func (c *AnalyticsClient) GetMetricSimple(
	ctx context.Context,
	tenantID, metricName, aggregation string,
) (*analyticspb.MetricResponse, error) {
	return c.GetMetric(ctx, &analyticspb.GetMetricRequest{
		TenantId:    tenantID,
		MetricName:  metricName,
		Aggregation: aggregation,
	})
}
