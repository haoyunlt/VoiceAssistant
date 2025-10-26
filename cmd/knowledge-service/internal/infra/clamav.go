package infra

import (
	"context"
	"fmt"
	"io"
	"net"
	"strings"
	"time"
)

// ClamAVClient ClamAV 病毒扫描客户端
type ClamAVClient struct {
	address string
	timeout time.Duration
}

// ClamAVConfig ClamAV 配置
type ClamAVConfig struct {
	Address string        // e.g., "localhost:3310"
	Timeout time.Duration // 扫描超时时间
}

// NewClamAVClient 创建 ClamAV 客户端
func NewClamAVClient(config *ClamAVConfig) *ClamAVClient {
	if config.Timeout == 0 {
		config.Timeout = 30 * time.Second
	}

	return &ClamAVClient{
		address: config.Address,
		timeout: config.Timeout,
	}
}

// ScanResult 扫描结果
type ScanResult struct {
	IsClean bool
	Virus   string
	Message string
}

// Scan 扫描数据流
func (c *ClamAVClient) Scan(ctx context.Context, reader io.Reader) (*ScanResult, error) {
	// 连接到 ClamAV
	conn, err := net.DialTimeout("tcp", c.address, c.timeout)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to clamav: %w", err)
	}
	defer conn.Close()

	// 设置超时
	deadline, ok := ctx.Deadline()
	if ok {
		conn.SetDeadline(deadline)
	} else {
		conn.SetDeadline(time.Now().Add(c.timeout))
	}

	// 发送 INSTREAM 命令
	_, err = conn.Write([]byte("zINSTREAM\x00"))
	if err != nil {
		return nil, fmt.Errorf("failed to send command: %w", err)
	}

	// 流式发送数据
	buf := make([]byte, 8192)
	for {
		n, err := reader.Read(buf)
		if err != nil && err != io.EOF {
			return nil, fmt.Errorf("failed to read data: %w", err)
		}

		if n > 0 {
			// 发送数据块大小（4字节网络字节序）
			size := uint32(n)
			sizeBytes := []byte{
				byte(size >> 24),
				byte(size >> 16),
				byte(size >> 8),
				byte(size),
			}
			if _, err := conn.Write(sizeBytes); err != nil {
				return nil, fmt.Errorf("failed to send chunk size: %w", err)
			}

			// 发送数据块
			if _, err := conn.Write(buf[:n]); err != nil {
				return nil, fmt.Errorf("failed to send chunk: %w", err)
			}
		}

		if err == io.EOF {
			break
		}
	}

	// 发送结束标记（0 长度块）
	if _, err := conn.Write([]byte{0, 0, 0, 0}); err != nil {
		return nil, fmt.Errorf("failed to send end marker: %w", err)
	}

	// 读取扫描结果
	response := make([]byte, 1024)
	n, err := conn.Read(response)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	return parseScanResult(string(response[:n])), nil
}

// Ping 检查 ClamAV 是否可用
func (c *ClamAVClient) Ping(ctx context.Context) error {
	conn, err := net.DialTimeout("tcp", c.address, 5*time.Second)
	if err != nil {
		return fmt.Errorf("failed to connect to clamav: %w", err)
	}
	defer conn.Close()

	// 发送 PING 命令
	_, err = conn.Write([]byte("zPING\x00"))
	if err != nil {
		return fmt.Errorf("failed to send ping: %w", err)
	}

	// 读取响应
	response := make([]byte, 32)
	n, err := conn.Read(response)
	if err != nil {
		return fmt.Errorf("failed to read pong: %w", err)
	}

	if !strings.Contains(string(response[:n]), "PONG") {
		return fmt.Errorf("unexpected response: %s", string(response[:n]))
	}

	return nil
}

// GetVersion 获取 ClamAV 版本
func (c *ClamAVClient) GetVersion(ctx context.Context) (string, error) {
	conn, err := net.DialTimeout("tcp", c.address, 5*time.Second)
	if err != nil {
		return "", fmt.Errorf("failed to connect to clamav: %w", err)
	}
	defer conn.Close()

	// 发送 VERSION 命令
	_, err = conn.Write([]byte("zVERSION\x00"))
	if err != nil {
		return "", fmt.Errorf("failed to send version command: %w", err)
	}

	// 读取响应
	response := make([]byte, 256)
	n, err := conn.Read(response)
	if err != nil {
		return "", fmt.Errorf("failed to read version: %w", err)
	}

	return strings.TrimSpace(string(response[:n])), nil
}

// parseScanResult 解析扫描结果
func parseScanResult(response string) *ScanResult {
	response = strings.TrimSpace(response)

	// 清洁文件: "stream: OK"
	if strings.HasSuffix(response, "OK") {
		return &ScanResult{
			IsClean: true,
			Message: response,
		}
	}

	// 发现病毒: "stream: Eicar-Test-Signature FOUND"
	if strings.Contains(response, "FOUND") {
		parts := strings.Split(response, ":")
		if len(parts) >= 2 {
			virusInfo := strings.TrimSpace(parts[1])
			virusName := strings.TrimSuffix(virusInfo, " FOUND")
			return &ScanResult{
				IsClean: false,
				Virus:   strings.TrimSpace(virusName),
				Message: response,
			}
		}
		return &ScanResult{
			IsClean: false,
			Message: response,
		}
	}

	// 错误
	return &ScanResult{
		IsClean: false,
		Message: response,
	}
}

// VirusScanner 病毒扫描接口（用于依赖注入）
type VirusScanner interface {
	Scan(ctx context.Context, reader io.Reader) (*ScanResult, error)
	Ping(ctx context.Context) error
	GetVersion(ctx context.Context) (string, error)
}

// 确保 ClamAVClient 实现了 VirusScanner 接口
var _ VirusScanner = (*ClamAVClient)(nil)

// MockVirusScanner 模拟病毒扫描器（用于测试）
type MockVirusScanner struct {
	ShouldFail    bool
	DetectedVirus string
}

// NewMockVirusScanner 创建模拟扫描器
func NewMockVirusScanner() *MockVirusScanner {
	return &MockVirusScanner{}
}

// Scan 扫描（模拟）
func (m *MockVirusScanner) Scan(ctx context.Context, reader io.Reader) (*ScanResult, error) {
	if m.ShouldFail {
		return &ScanResult{
			IsClean: false,
			Virus:   m.DetectedVirus,
			Message: fmt.Sprintf("Virus detected: %s", m.DetectedVirus),
		}, nil
	}

	return &ScanResult{
		IsClean: true,
		Message: "OK",
	}, nil
}

// Ping 检查可用性（模拟）
func (m *MockVirusScanner) Ping(ctx context.Context) error {
	return nil
}

// GetVersion 获取版本（模拟）
func (m *MockVirusScanner) GetVersion(ctx context.Context) (string, error) {
	return "MockScanner 1.0.0", nil
}

// 确保 MockVirusScanner 实现了 VirusScanner 接口
var _ VirusScanner = (*MockVirusScanner)(nil)
