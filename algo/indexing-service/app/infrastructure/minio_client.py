"""
MinIO 客户端
用于从 MinIO 下载文档文件
"""

import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioClient:
    """MinIO 客户端"""

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "voiceassistant",
        secret_key: str = "voiceassistant_dev_password",
        secure: bool = False,
        bucket_name: str = "voiceassistant-documents"
    ):
        """
        初始化 MinIO 客户端

        Args:
            endpoint: MinIO 服务地址
            access_key: 访问密钥
            secret_key: 密钥
            secure: 是否使用 HTTPS
            bucket_name: 桶名称
        """
        self.endpoint = endpoint
        self.bucket_name = bucket_name

        try:
            # 创建 MinIO 客户端
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )

            # 确保桶存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")

            logger.info(f"MinIO client initialized: {endpoint}/{bucket_name}")

        except S3Error as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise

    def download_file(self, object_name: str) -> Optional[bytes]:
        """
        下载文件

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件内容（字节），失败返回 None
        """
        try:
            logger.debug(f"Downloading file: {object_name}")

            # 获取对象
            response = self.client.get_object(self.bucket_name, object_name)

            # 读取内容
            content = response.read()

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

    def upload_file(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> bool:
        """
        上传文件

        Args:
            object_name: 对象名称（路径）
            data: 文件内容
            content_type: Content-Type

        Returns:
            是否成功
        """
        try:
            logger.debug(f"Uploading file: {object_name}, size={len(data)} bytes")

            # 上传对象
            self.client.put_object(
                self.bucket_name,
                object_name,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type
            )

            logger.info(f"Uploaded file: {object_name}")

            return True

        except S3Error as e:
            logger.error(f"Failed to upload file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading file {object_name}: {e}")
            return False

    def delete_file(self, object_name: str) -> bool:
        """
        删除文件

        Args:
            object_name: 对象名称（路径）

        Returns:
            是否成功
        """
        try:
            logger.debug(f"Deleting file: {object_name}")

            self.client.remove_object(self.bucket_name, object_name)

            logger.info(f"Deleted file: {object_name}")

            return True

        except S3Error as e:
            logger.error(f"Failed to delete file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file {object_name}: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        """
        检查文件是否存在

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件是否存在
        """
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False
        except Exception:
            return False

    def get_file_info(self, object_name: str) -> Optional[dict]:
        """
        获取文件信息

        Args:
            object_name: 对象名称（路径）

        Returns:
            文件信息字典，失败返回 None
        """
        try:
            stat = self.client.stat_object(self.bucket_name, object_name)

            return {
                "object_name": object_name,
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata
            }

        except S3Error as e:
            logger.error(f"Failed to get file info {object_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting file info {object_name}: {e}")
            return None

    def list_files(self, prefix: str = "") -> list:
        """
        列出文件

        Args:
            prefix: 前缀过滤

        Returns:
            文件列表
        """
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True
            )

            files = []
            for obj in objects:
                files.append({
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "etag": obj.etag,
                    "last_modified": obj.last_modified
                })

            logger.info(f"Listed {len(files)} files with prefix: {prefix}")

            return files

        except S3Error as e:
            logger.error(f"Failed to list files: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return []
