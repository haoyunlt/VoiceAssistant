"""
MinIO 客户端
用于从 MinIO 下载文档文件
"""

import asyncio
import io
import logging
import os

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioClient:
    """MinIO 客户端（异步封装）"""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        bucket_name: str | None = None,
    ):
        """
        初始化 MinIO 客户端

        Args:
            endpoint: MinIO 服务地址（从环境变量 MINIO_ENDPOINT 读取）
            access_key: 访问密钥（从环境变量 MINIO_ACCESS_KEY 读取）
            secret_key: 密钥（从环境变量 MINIO_SECRET_KEY 读取）
            secure: 是否使用 HTTPS（从环境变量 MINIO_SECURE 读取）
            bucket_name: 桶名称（从环境变量 MINIO_BUCKET 读取）
        """
        # 从环境变量读取配置，不再使用默认值
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT")
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET", "documents")

        access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")
        secure = (
            secure if secure is not None else os.getenv("MINIO_SECURE", "false").lower() == "true"
        )

        # 验证必需的配置
        if not self.endpoint:
            raise ValueError("MINIO_ENDPOINT is required (set via environment variable)")
        if not access_key:
            raise ValueError("MINIO_ACCESS_KEY is required (set via environment variable)")
        if not secret_key:
            raise ValueError("MINIO_SECRET_KEY is required (set via environment variable)")

        try:
            # 创建 MinIO 客户端
            self.client = Minio(
                self.endpoint, access_key=access_key, secret_key=secret_key, secure=secure
            )

            # 确保桶存在
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")

            logger.info(f"MinIO client initialized: {self.endpoint}/{self.bucket_name}")

        except S3Error as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    async def download_file(self, object_name: str) -> bytes | None:
        """
        下载文件（异步）

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件内容（字节），失败返回 None
        """
        try:
            logger.debug(f"Downloading file: {object_name}")

            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self.client.get_object, self.bucket_name, object_name
            )

            # 读取内容
            content = await loop.run_in_executor(None, response.read)

            response.close()
            response.release_conn()

            logger.info(f"Downloaded file: {object_name}, size={len(content)} bytes")

            return content

        except S3Error as e:
            logger.error(f"Failed to download file {object_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading file {object_name}: {e}")
            return None

    async def upload_file(
        self, object_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> bool:
        """
        上传文件（异步）

        Args:
            object_name: 对象名称（路径）
            data: 文件内容
            content_type: Content-Type

        Returns:
            是否成功
        """
        try:
            logger.debug(f"Uploading file: {object_name}, size={len(data)} bytes")

            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.client.put_object,
                self.bucket_name,
                object_name,
                io.BytesIO(data),
                len(data),
                content_type,
            )

            logger.info(f"Uploaded file: {object_name}")

            return True

        except S3Error as e:
            logger.error(f"Failed to upload file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading file {object_name}: {e}")
            return False

    async def delete_file(self, object_name: str) -> bool:
        """
        删除文件（异步）

        Args:
            object_name: 对象名称（路径）

        Returns:
            是否成功
        """
        try:
            logger.debug(f"Deleting file: {object_name}")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.client.remove_object, self.bucket_name, object_name
            )

            logger.info(f"Deleted file: {object_name}")

            return True

        except S3Error as e:
            logger.error(f"Failed to delete file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file {object_name}: {e}")
            return False

    async def file_exists(self, object_name: str) -> bool:
        """
        检查文件是否存在（异步）

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件是否存在
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.stat_object, self.bucket_name, object_name)
            return True
        except S3Error:
            return False
        except Exception:
            return False

    async def close(self):
        """关闭客户端连接"""
        # MinIO Python SDK 不需要显式关闭
        logger.info("MinIO client closed")

    async def get_file_info(self, object_name: str) -> dict | None:
        """
        获取文件信息（异步）

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件信息字典，失败返回 None
        """
        try:
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(
                None, self.client.stat_object, self.bucket_name, object_name
            )

            return {
                "object_name": object_name,
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata,
            }

        except S3Error as e:
            logger.error(f"Failed to get file info {object_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting file info {object_name}: {e}")
            return None

    async def list_files(self, prefix: str = "") -> list:
        """
        列出文件（异步）

        Args:
            prefix: 前缀过滤

        Returns:
            文件列表
        """
        try:
            loop = asyncio.get_event_loop()
            objects = await loop.run_in_executor(
                None,
                lambda: list(
                    self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
                ),
            )

            files = []
            for obj in objects:
                files.append(
                    {
                        "object_name": obj.object_name,
                        "size": obj.size,
                        "etag": obj.etag,
                        "last_modified": obj.last_modified,
                    }
                )

            logger.info(f"Listed {len(files)} files with prefix: {prefix}")

            return files

        except S3Error as e:
            logger.error(f"Failed to list files: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return []
