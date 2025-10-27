package biz

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// StorageService 存储服务（支持MinIO和本地存储降级）
type StorageService struct {
	storageType  string // local/minio
	basePath     string // 本地存储基础路径
	minioClient  *minio.Client
	minioBucket  string
	minioEnabled bool
	log          *log.Helper
}

// StorageConfig 存储配置
type StorageConfig struct {
	Type     string
	BasePath string
	MinIO    MinIOConfig
}

// MinIOConfig MinIO配置
type MinIOConfig struct {
	Endpoint  string
	AccessKey string
	SecretKey string
	Bucket    string
	UseSSL    bool
}

// NewStorageService 创建存储服务
func NewStorageService(config *StorageConfig, logger log.Logger) (*StorageService, error) {
	helper := log.NewHelper(log.With(logger, "module", "storage"))

	s := &StorageService{
		storageType:  config.Type,
		basePath:     config.BasePath,
		minioEnabled: false,
		log:          helper,
	}

	// 确保本地存储目录存在
	if err := os.MkdirAll(s.basePath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create base path: %w", err)
	}

	// 如果配置了MinIO，初始化MinIO客户端
	if config.Type == "minio" {
		if err := s.initMinIO(&config.MinIO); err != nil {
			helper.Warnf("MinIO初始化失败，降级到本地存储: %v", err)
			s.storageType = "local"
		} else {
			s.minioEnabled = true
			helper.Info("MinIO存储已启用")
		}
	}

	return s, nil
}

// initMinIO 初始化MinIO客户端
func (s *StorageService) initMinIO(config *MinIOConfig) error {
	// 创建MinIO客户端
	minioClient, err := minio.New(config.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(config.AccessKey, config.SecretKey, ""),
		Secure: config.UseSSL,
	})
	if err != nil {
		return fmt.Errorf("failed to create minio client: %w", err)
	}

	s.minioClient = minioClient
	s.minioBucket = config.Bucket

	// 检查bucket是否存在，不存在则创建
	ctx := context.Background()
	exists, err := minioClient.BucketExists(ctx, config.Bucket)
	if err != nil {
		return fmt.Errorf("failed to check bucket: %w", err)
	}

	if !exists {
		if err := minioClient.MakeBucket(ctx, config.Bucket, minio.MakeBucketOptions{}); err != nil {
			return fmt.Errorf("failed to create bucket: %w", err)
		}
		s.log.Infof("创建MinIO bucket: %s", config.Bucket)
	}

	return nil
}

// Upload 上传文件（自动选择存储方式）
func (s *StorageService) Upload(ctx context.Context, fileName string, content []byte) (string, error) {
	if s.minioEnabled {
		return s.uploadToMinIO(ctx, fileName, content)
	}
	return s.uploadToLocal(ctx, fileName, content)
}

// uploadToMinIO 上传到MinIO
func (s *StorageService) uploadToMinIO(ctx context.Context, fileName string, content []byte) (string, error) {
	_, err := s.minioClient.PutObject(
		ctx,
		s.minioBucket,
		fileName,
		bytes.NewReader(content),
		int64(len(content)),
		minio.PutObjectOptions{
			ContentType: "application/octet-stream",
		},
	)
	if err != nil {
		return "", fmt.Errorf("failed to upload to MinIO: %w", err)
	}

	// 返回MinIO URL
	url := fmt.Sprintf("minio://%s/%s", s.minioBucket, fileName)

	s.log.WithContext(ctx).Infof("File uploaded to MinIO: %s (size: %d)", fileName, len(content))

	return url, nil
}

// uploadToLocal 上传到本地存储
func (s *StorageService) uploadToLocal(ctx context.Context, fileName string, content []byte) (string, error) {
	filePath := filepath.Join(s.basePath, fileName)

	// 确保目录存在
	dir := filepath.Dir(filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", fmt.Errorf("failed to create directory: %w", err)
	}

	if err := os.WriteFile(filePath, content, 0644); err != nil {
		return "", fmt.Errorf("failed to write file: %w", err)
	}

	s.log.WithContext(ctx).Infof("File uploaded to local: %s (size: %d)", fileName, len(content))

	return filePath, nil
}

// Download 下载文件
func (s *StorageService) Download(ctx context.Context, fileURL string) ([]byte, error) {
	// 判断是MinIO URL还是本地路径
	if s.isMinIOURL(fileURL) {
		return s.downloadFromMinIO(ctx, fileURL)
	}
	return s.downloadFromLocal(ctx, fileURL)
}

// downloadFromMinIO 从MinIO下载
func (s *StorageService) downloadFromMinIO(ctx context.Context, fileURL string) ([]byte, error) {
	// 解析MinIO URL: minio://bucket/filename
	fileName := s.extractFileNameFromMinIOURL(fileURL)

	object, err := s.minioClient.GetObject(ctx, s.minioBucket, fileName, minio.GetObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to get object: %w", err)
	}
	defer object.Close()

	content, err := io.ReadAll(object)
	if err != nil {
		return nil, fmt.Errorf("failed to read object: %w", err)
	}

	return content, nil
}

// downloadFromLocal 从本地下载
func (s *StorageService) downloadFromLocal(ctx context.Context, filePath string) ([]byte, error) {
	content, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	return content, nil
}

// Delete 删除文件
func (s *StorageService) Delete(ctx context.Context, fileURL string) error {
	if s.isMinIOURL(fileURL) {
		return s.deleteFromMinIO(ctx, fileURL)
	}
	return s.deleteFromLocal(ctx, fileURL)
}

// deleteFromMinIO 从MinIO删除
func (s *StorageService) deleteFromMinIO(ctx context.Context, fileURL string) error {
	fileName := s.extractFileNameFromMinIOURL(fileURL)

	if err := s.minioClient.RemoveObject(ctx, s.minioBucket, fileName, minio.RemoveObjectOptions{}); err != nil {
		return fmt.Errorf("failed to remove object: %w", err)
	}

	return nil
}

// deleteFromLocal 从本地删除
func (s *StorageService) deleteFromLocal(ctx context.Context, filePath string) error {
	if err := os.Remove(filePath); err != nil {
		return fmt.Errorf("failed to remove file: %w", err)
	}

	return nil
}

// isMinIOURL 判断是否为MinIO URL
func (s *StorageService) isMinIOURL(url string) bool {
	return len(url) > 8 && url[:8] == "minio://"
}

// extractFileNameFromMinIOURL 从MinIO URL提取文件名
// minio://bucket/filename -> filename
func (s *StorageService) extractFileNameFromMinIOURL(url string) string {
	// minio://bucket/filename
	parts := strings.Split(url, "/")
	if len(parts) >= 4 {
		return strings.Join(parts[3:], "/")
	}
	return ""
}
