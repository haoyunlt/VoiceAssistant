"""
MinIO Storage Client

MinIO 对象存储客户端，用于文档文件的存储和检索
"""

import io
import logging
from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class FileInfo:
    """文件信息"""

    def __init__(
        self,
        name: str,
        size: int,
        content_type: str,
        last_modified: str,
        etag: str
    ):
        self.name = name
        self.size = size
        self.content_type = content_type
        self.last_modified = last_modified
        self.etag = etag


class MinIOClient:
    """MinIO 客户端封装"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False
    ):
        """初始化 MinIO 客户端

        Args:
            endpoint: MinIO 服务地址 (不包含 http://)
            access_key: Access Key
            secret_key: Secret Key
            bucket_name: 存储桶名称
            secure: 是否使用 HTTPS
        """
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = bucket_name
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.info(f"Bucket exists: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket: {e}")
            raise

    async def upload_file(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> None:
        """上传文件

        Args:
            object_name: 对象名称（路径）
            data: 文件数据
            content_type: 内容类型
        """
        try:
            data_stream = io.BytesIO(data)
            self.client.put_object(
                self.bucket_name,
                object_name,
                data_stream,
                length=len(data),
                content_type=content_type
            )
            logger.info(f"Uploaded file: {object_name}")
        except S3Error as e:
            logger.error(f"Failed to upload file {object_name}: {e}")
            raise

    async def download_file(self, object_name: str) -> bytes:
        """下载文件

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件数据
        """
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Downloaded file: {object_name}")
            return data
        except S3Error as e:
            logger.error(f"Failed to download file {object_name}: {e}")
            raise

    async def delete_file(self, object_name: str) -> None:
        """删除文件

        Args:
            object_name: 对象名称（路径）
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"Deleted file: {object_name}")
        except S3Error as e:
            logger.error(f"Failed to delete file {object_name}: {e}")
            raise

    async def get_presigned_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """获取预签名 URL

        Args:
            object_name: 对象名称（路径）
            expires: 过期时间

        Returns:
            预签名 URL
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=expires
            )
            logger.info(f"Generated presigned URL for: {object_name}")
            return url
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            raise

    async def get_file_info(self, object_name: str) -> Optional[FileInfo]:
        """获取文件信息

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件信息
        """
        try:
            stat = self.client.stat_object(self.bucket_name, object_name)
            return FileInfo(
                name=stat.object_name,
                size=stat.size,
                content_type=stat.content_type,
                last_modified=stat.last_modified.isoformat(),
                etag=stat.etag
            )
        except S3Error as e:
            logger.error(f"Failed to get file info for {object_name}: {e}")
            return None

    async def list_files(self, prefix: str = "") -> list[FileInfo]:
        """列出文件

        Args:
            prefix: 对象名称前缀

        Returns:
            文件信息列表
        """
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            files = []
            for obj in objects:
                files.append(FileInfo(
                    name=obj.object_name,
                    size=obj.size,
                    content_type=obj.content_type or "application/octet-stream",
                    last_modified=obj.last_modified.isoformat(),
                    etag=obj.etag
                ))
            return files
        except S3Error as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            raise


# 全局单例
_minio_client: Optional[MinIOClient] = None


def get_minio_client(
    endpoint: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    bucket_name: Optional[str] = None,
    secure: bool = False
) -> MinIOClient:
    """获取 MinIO 客户端单例

    Args:
        endpoint: MinIO 服务地址
        access_key: Access Key
        secret_key: Secret Key
        bucket_name: 存储桶名称
        secure: 是否使用 HTTPS

    Returns:
        MinIO 客户端实例
    """
    global _minio_client

    if _minio_client is None:
        if not all([endpoint, access_key, secret_key, bucket_name]):
            raise ValueError("MinIO client not initialized. Provide all required parameters.")
        _minio_client = MinIOClient(endpoint, access_key, secret_key, bucket_name, secure)

    return _minio_client


async def close_minio_client() -> None:
    """关闭 MinIO 客户端"""
    global _minio_client
    _minio_client = None
    logger.info("MinIO client closed")
