package minio

import (
	"context"
	"io"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type Client struct {
	client *minio.Client
	bucket string
}

func NewMinIOClient(endpoint, accessKey, secretKey, bucket string, useSSL bool) (*Client, error) {
	minioClient, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		return nil, err
	}

	return &Client{
		client: minioClient,
		bucket: bucket,
	}, nil
}

func (c *Client) UploadFile(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) error {
	_, err := c.client.PutObject(ctx, c.bucket, objectName, reader, size, minio.PutObjectOptions{
		ContentType: contentType,
	})
	return err
}

func (c *Client) DownloadFile(ctx context.Context, objectName string) (*minio.Object, error) {
	return c.client.GetObject(ctx, c.bucket, objectName, minio.GetObjectOptions{})
}

func (c *Client) DeleteFile(ctx context.Context, objectName string) error {
	return c.client.RemoveObject(ctx, c.bucket, objectName, minio.RemoveObjectOptions{})
}

func (c *Client) FileExists(ctx context.Context, objectName string) (bool, error) {
	_, err := c.client.StatObject(ctx, c.bucket, objectName, minio.StatObjectOptions{})
	if err != nil {
		errResponse := minio.ToErrorResponse(err)
		if errResponse.Code == "NoSuchKey" {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func (c *Client) GetPresignedURL(ctx context.Context, objectName string) (string, error) {
	// 生成 1 小时有效的下载链接
	url, err := c.client.PresignedGetObject(ctx, c.bucket, objectName, 3600, nil)
	if err != nil {
		return "", err
	}
	return url.String(), nil
}
