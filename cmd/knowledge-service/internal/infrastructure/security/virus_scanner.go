package security

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net"
	"strings"
	"time"
)

// VirusScanner 病毒扫描器接口
type VirusScanner interface {
	Scan(ctx context.Context, reader io.Reader) (*ScanResult, error)
}

// ClamAVScanner ClamAV病毒扫描器
type ClamAVScanner struct {
	host string
	port int
}

// ScanResult 扫描结果
type ScanResult struct {
	IsClean bool
	Threat  string
	Message string
}

// NewClamAVScanner 创建ClamAV扫描器
func NewClamAVScanner(host string, port int) *ClamAVScanner {
	return &ClamAVScanner{
		host: host,
		port: port,
	}
}

// Scan 扫描文件
func (s *ClamAVScanner) Scan(ctx context.Context, reader io.Reader) (*ScanResult, error) {
	// 连接到ClamAV守护进程
	conn, err := s.connect(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to clamav: %w", err)
	}
	defer conn.Close()

	// 发送INSTREAM命令
	_, err = conn.Write([]byte("zINSTREAM\x00"))
	if err != nil {
		return nil, fmt.Errorf("failed to send INSTREAM command: %w", err)
	}

	// 分块发送文件内容
	if err := s.streamFile(conn, reader); err != nil {
		return nil, fmt.Errorf("failed to stream file: %w", err)
	}

	// 读取扫描结果
	result, err := s.readResponse(conn)
	if err != nil {
		return nil, fmt.Errorf("failed to read scan result: %w", err)
	}

	return result, nil
}

// connect 连接到ClamAV
func (s *ClamAVScanner) connect(ctx context.Context) (net.Conn, error) {
	dialer := &net.Dialer{
		Timeout: 10 * time.Second,
	}

	conn, err := dialer.DialContext(ctx, "tcp", fmt.Sprintf("%s:%d", s.host, s.port))
	if err != nil {
		return nil, err
	}

	return conn, nil
}

// streamFile 流式传输文件
func (s *ClamAVScanner) streamFile(conn net.Conn, reader io.Reader) error {
	const chunkSize = 4096
	buffer := make([]byte, chunkSize)

	for {
		n, err := reader.Read(buffer)
		if n > 0 {
			// 发送块大小（4字节网络字节序）
			sizeBytes := []byte{
				byte(n >> 24),
				byte(n >> 16),
				byte(n >> 8),
				byte(n),
			}

			if _, err := conn.Write(sizeBytes); err != nil {
				return err
			}

			// 发送数据块
			if _, err := conn.Write(buffer[:n]); err != nil {
				return err
			}
		}

		if err == io.EOF {
			break
		}

		if err != nil {
			return err
		}
	}

	// 发送结束标记（0字节）
	if _, err := conn.Write([]byte{0, 0, 0, 0}); err != nil {
		return err
	}

	return nil
}

// readResponse 读取扫描响应
func (s *ClamAVScanner) readResponse(conn net.Conn) (*ScanResult, error) {
	// 设置读取超时
	conn.SetReadDeadline(time.Now().Add(30 * time.Second))

	response := make([]byte, 1024)
	n, err := conn.Read(response)
	if err != nil {
		return nil, err
	}

	responseStr := strings.TrimSpace(string(response[:n]))

	// 解析响应
	result := &ScanResult{
		Message: responseStr,
	}

	if strings.Contains(responseStr, "OK") {
		result.IsClean = true
	} else if strings.Contains(responseStr, "FOUND") {
		result.IsClean = false
		// 提取威胁名称
		parts := strings.Split(responseStr, ":")
		if len(parts) >= 2 {
			result.Threat = strings.TrimSpace(strings.Replace(parts[1], "FOUND", "", 1))
		}
	} else {
		return nil, fmt.Errorf("unexpected scan result: %s", responseStr)
	}

	return result, nil
}

// MockVirusScanner 用于测试的Mock扫描器
type MockVirusScanner struct {
	AlwaysClean bool
}

// NewMockVirusScanner 创建Mock扫描器
func NewMockVirusScanner(alwaysClean bool) *MockVirusScanner {
	return &MockVirusScanner{
		AlwaysClean: alwaysClean,
	}
}

// Scan Mock扫描
func (s *MockVirusScanner) Scan(ctx context.Context, reader io.Reader) (*ScanResult, error) {
	// 读取一部分数据以验证reader可用
	buffer := make([]byte, 1024)
	_, err := reader.Read(buffer)
	if err != nil && err != io.EOF {
		return nil, err
	}

	return &ScanResult{
		IsClean: s.AlwaysClean,
		Threat:  "",
		Message: "Mock scan completed",
	}, nil
}

// SafeVirusScanner 带重试和降级的安全扫描器
type SafeVirusScanner struct {
	scanner      VirusScanner
	maxRetries   int
	fallbackMode string // "allow" 或 "deny"
}

// NewSafeVirusScanner 创建安全扫描器
func NewSafeVirusScanner(scanner VirusScanner, maxRetries int, fallbackMode string) *SafeVirusScanner {
	return &SafeVirusScanner{
		scanner:      scanner,
		maxRetries:   maxRetries,
		fallbackMode: fallbackMode,
	}
}

// Scan 带重试的扫描
func (s *SafeVirusScanner) Scan(ctx context.Context, reader io.Reader) (*ScanResult, error) {
	// 将reader内容读入缓冲区，以便重试
	buf := &bytes.Buffer{}
	if _, err := io.Copy(buf, reader); err != nil {
		return nil, fmt.Errorf("failed to buffer file: %w", err)
	}

	var lastErr error
	for attempt := 0; attempt <= s.maxRetries; attempt++ {
		result, err := s.scanner.Scan(ctx, bytes.NewReader(buf.Bytes()))
		if err == nil {
			return result, nil
		}

		lastErr = err

		if attempt < s.maxRetries {
			time.Sleep(time.Second * time.Duration(attempt+1))
		}
	}

	// 所有重试都失败，使用降级策略
	if s.fallbackMode == "allow" {
		return &ScanResult{
			IsClean: true,
			Message: fmt.Sprintf("Scan failed after %d retries, fallback to allow: %v", s.maxRetries+1, lastErr),
		}, nil
	}

	return &ScanResult{
		IsClean: false,
		Threat:  "SCAN_UNAVAILABLE",
		Message: fmt.Sprintf("Scan failed after %d retries: %v", s.maxRetries+1, lastErr),
	}, nil
}
