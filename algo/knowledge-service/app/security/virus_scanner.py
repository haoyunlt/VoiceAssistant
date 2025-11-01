"""
Virus Scanner Client

病毒扫描客户端，用于文件上传时的病毒检测
"""

import io
import logging
import socket

logger = logging.getLogger(__name__)


class VirusScanner:
    """病毒扫描器（ClamAV 客户端）"""

    def __init__(self, host: str = "localhost", port: int = 3310, timeout: int = 30):
        """初始化病毒扫描器

        Args:
            host: ClamAV 服务地址
            port: ClamAV 端口
            timeout: 超时时间（秒）
        """
        self.host = host
        self.port = port
        self.timeout = timeout

    async def scan(self, data: bytes) -> tuple[bool, str | None]:
        """扫描数据

        Args:
            data: 要扫描的数据

        Returns:
            (is_clean, virus_name) - 是否干净，病毒名称（如果有）
        """
        try:
            # 连接到 ClamAV
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))

            # 发送 INSTREAM 命令
            sock.sendall(b"zINSTREAM\0")

            # 发送数据
            chunk_size = 1024
            stream = io.BytesIO(data)
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                size = len(chunk).to_bytes(4, byteorder="big")
                sock.sendall(size + chunk)

            # 发送结束标记
            sock.sendall(b"\0\0\0\0")

            # 接收结果
            result = sock.recv(1024).decode("utf-8")
            sock.close()

            # 解析结果
            if "OK" in result:
                logger.info("Virus scan: clean")
                return True, None
            elif "FOUND" in result:
                virus_name = result.split(":")[1].strip().replace(" FOUND", "")
                logger.warning(f"Virus scan: infected with {virus_name}")
                return False, virus_name
            else:
                logger.error(f"Virus scan: unexpected result: {result}")
                # 默认允许通过，避免误拦截
                return True, None

        except TimeoutError:
            logger.error("Virus scan timeout")
            # 超时默认允许通过
            return True, None
        except Exception as e:
            logger.error(f"Virus scan error: {e}")
            # 出错默认允许通过
            return True, None

    async def ping(self) -> bool:
        """检查 ClamAV 服务是否可用

        Returns:
            是否可用
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.port))
            sock.sendall(b"zPING\0")
            result = sock.recv(1024).decode("utf-8")
            sock.close()
            return "PONG" in result
        except Exception as e:
            logger.error(f"ClamAV ping failed: {e}")
            return False


# 全局单例
_virus_scanner: VirusScanner | None = None


def get_virus_scanner(
    host: str | None = None, port: int | None = None, timeout: int = 30
) -> VirusScanner | None:
    """获取病毒扫描器单例

    Args:
        host: ClamAV 服务地址
        port: ClamAV 端口
        timeout: 超时时间

    Returns:
        病毒扫描器实例（如果配置了）
    """
    global _virus_scanner

    if _virus_scanner is None:
        if host and port:
            _virus_scanner = VirusScanner(host, port, timeout)
            logger.info(f"Virus scanner initialized: {host}:{port}")
        else:
            logger.info("Virus scanner not configured (optional)")
            return None

    return _virus_scanner
