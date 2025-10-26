package infra

import (
	"context"
	"fmt"
	"io"
	"path/filepath"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// MinIOClient MinIO 客户端
type MinIOClient struct {
	client     *minio.Client
	bucketName string
}

// MinIOConfig MinIO 配置
type MinIOConfig struct {
	Endpoint   string // e.g., "localhost:9000"
	AccessKey  string
	SecretKey  string
	BucketName string
	UseSSL     bool
}

// NewMinIOClient 创建 MinIO 客户端
func NewMinIOClient(config *MinIOConfig) (*MinIOClient, error) {
	// 创建 MinIO 客户端
	client, err := minio.New(config.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(config.AccessKey, config.SecretKey, ""),
		Secure: config.UseSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create minio client: %w", err)
	}

	mc := &MinIOClient{
		client:     client,
		bucketName: config.BucketName,
	}

	// 确保 bucket 存在
	if err := mc.ensureBucket(context.Background()); err != nil {
		return nil, err
	}

	return mc, nil
}

// ensureBucket 确保 bucket 存在
func (m *MinIOClient) ensureBucket(ctx context.Context) error {
	exists, err := m.client.BucketExists(ctx, m.bucketName)
	if err != nil {
		return fmt.Errorf("failed to check bucket: %w", err)
	}

	if !exists {
		err = m.client.MakeBucket(ctx, m.bucketName, minio.MakeBucketOptions{})
		if err != nil {
			return fmt.Errorf("failed to create bucket: %w", err)
		}
	}

	return nil
}

// UploadFile 上传文件
func (m *MinIOClient) UploadFile(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) (*UploadResult, error) {
	// 上传选项
	opts := minio.PutObjectOptions{
		ContentType: contentType,
		UserMetadata: map[string]string{
			"uploaded_at": time.Now().Format(time.RFC3339),
		},
	}

	// 上传文件
	info, err := m.client.PutObject(ctx, m.bucketName, objectName, reader, size, opts)
	if err != nil {
		return nil, fmt.Errorf("failed to upload file: %w", err)
	}

	return &UploadResult{
		Bucket:      m.bucketName,
		ObjectName:  objectName,
		Size:        info.Size,
		ETag:        info.ETag,
		ContentType: contentType,
		UploadedAt:  time.Now(),
	}, nil
}

// DownloadFile 下载文件
func (m *MinIOClient) DownloadFile(ctx context.Context, objectName string) (io.ReadCloser, error) {
	object, err := m.client.GetObject(ctx, m.bucketName, objectName, minio.GetObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to download file: %w", err)
	}

	return object, nil
}

// GetFileInfo 获取文件信息
func (m *MinIOClient) GetFileInfo(ctx context.Context, objectName string) (*FileInfo, error) {
	info, err := m.client.StatObject(ctx, m.bucketName, objectName, minio.StatObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to get file info: %w", err)
	}

	return &FileInfo{
		Bucket:       m.bucketName,
		ObjectName:   objectName,
		Size:         info.Size,
		ETag:         info.ETag,
		ContentType:  info.ContentType,
		LastModified: info.LastModified,
		Metadata:     info.UserMetadata,
	}, nil
}

// DeleteFile 删除文件
func (m *MinIOClient) DeleteFile(ctx context.Context, objectName string) error {
	err := m.client.RemoveObject(ctx, m.bucketName, objectName, minio.RemoveObjectOptions{})
	if err != nil {
		return fmt.Errorf("failed to delete file: %w", err)
	}

	return nil
}

// ListFiles 列出文件
func (m *MinIOClient) ListFiles(ctx context.Context, prefix string) ([]*FileInfo, error) {
	objectCh := m.client.ListObjects(ctx, m.bucketName, minio.ListObjectsOptions{
		Prefix:    prefix,
		Recursive: true,
	})

	files := make([]*FileInfo, 0)
	for object := range objectCh {
		if object.Err != nil {
			return nil, fmt.Errorf("failed to list files: %w", object.Err)
		}

		files = append(files, &FileInfo{
			Bucket:       m.bucketName,
			ObjectName:   object.Key,
			Size:         object.Size,
			ETag:         object.ETag,
			ContentType:  object.ContentType,
			LastModified: object.LastModified,
		})
	}

	return files, nil
}

// GeneratePresignedURL 生成预签名 URL
func (m *MinIOClient) GeneratePresignedURL(ctx context.Context, objectName string, expiry time.Duration) (string, error) {
	url, err := m.client.PresignedGetObject(ctx, m.bucketName, objectName, expiry, nil)
	if err != nil {
		return "", fmt.Errorf("failed to generate presigned url: %w", err)
	}

	return url.String(), nil
}

// GenerateUploadURL 生成上传 URL
func (m *MinIOClient) GenerateUploadURL(ctx context.Context, objectName string, expiry time.Duration) (string, error) {
	url, err := m.client.PresignedPutObject(ctx, m.bucketName, objectName, expiry)
	if err != nil {
		return "", fmt.Errorf("failed to generate upload url: %w", err)
	}

	return url.String(), nil
}

// CopyFile 复制文件
func (m *MinIOClient) CopyFile(ctx context.Context, srcObjectName, destObjectName string) error {
	src := minio.CopySrcOptions{
		Bucket: m.bucketName,
		Object: srcObjectName,
	}
	dest := minio.CopyDestOptions{
		Bucket: m.bucketName,
		Object: destObjectName,
	}

	_, err := m.client.CopyObject(ctx, dest, src)
	if err != nil {
		return fmt.Errorf("failed to copy file: %w", err)
	}

	return nil
}

// GetObjectURL 获取对象 URL（公开访问）
func (m *MinIOClient) GetObjectURL(objectName string) string {
	endpoint := m.client.EndpointURL().String()
	return fmt.Sprintf("%s/%s/%s", endpoint, m.bucketName, objectName)
}

// UploadResult 上传结果
type UploadResult struct {
	Bucket      string
	ObjectName  string
	Size        int64
	ETag        string
	ContentType string
	UploadedAt  time.Time
}

// FileInfo 文件信息
type FileInfo struct {
	Bucket       string
	ObjectName   string
	Size         int64
	ETag         string
	ContentType  string
	LastModified time.Time
	Metadata     map[string]string
}

// GetFileName 获取文件名（不包含路径）
func (f *FileInfo) GetFileName() string {
	return filepath.Base(f.ObjectName)
}

// GetExtension 获取文件扩展名
func (f *FileInfo) GetExtension() string {
	return filepath.Ext(f.ObjectName)
}

// IsDocument 是否为文档文件
func (f *FileInfo) IsDocument() bool {
	ext := f.GetExtension()
	documentExts := []string{".pdf", ".doc", ".docx", ".txt", ".md", ".xlsx", ".xls", ".ppt", ".pptx"}
	for _, docExt := range documentExts {
		if ext == docExt {
			return true
		}
	}
	return false
}

// FileStorage 文件存储接口（用于依赖注入）
type FileStorage interface {
	UploadFile(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) (*UploadResult, error)
	DownloadFile(ctx context.Context, objectName string) (io.ReadCloser, error)
	GetFileInfo(ctx context.Context, objectName string) (*FileInfo, error)
	DeleteFile(ctx context.Context, objectName string) error
	ListFiles(ctx context.Context, prefix string) ([]*FileInfo, error)
	GeneratePresignedURL(ctx context.Context, objectName string, expiry time.Duration) (string, error)
	GenerateUploadURL(ctx context.Context, objectName string, expiry time.Duration) (string, error)
}

// 确保 MinIOClient 实现了 FileStorage 接口
var _ FileStorage = (*MinIOClient)(nil)
