"""模型健康检查服务

提供全面的健康检查功能:
- OCR模型状态检查
- Vision模型状态检查
- GPU可用性检查
- 模型加载验证
- 性能基准测试
"""
import asyncio
import logging
import time
from typing import Any, Dict, Optional

import psutil
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    """健康状态模型"""
    healthy: bool
    component: str
    status: str
    details: Dict[str, Any] = {}
    timestamp: float

class HealthCheckService:
    """健康检查服务"""

    def __init__(self):
        """初始化健康检查服务"""
        self.last_check_time = {}
        self.check_cache = {}
        self.cache_ttl = 10.0  # 缓存10秒
        logger.info("Health Check Service initialized")

    async def check_all(
        self,
        ocr_service=None,
        vision_service=None,
        video_service=None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        全面健康检查

        Args:
            ocr_service: OCR服务实例
            vision_service: Vision服务实例
            video_service: Video服务实例
            use_cache: 是否使用缓存

        Returns:
            健康检查结果字典
        """
        if use_cache and "all" in self.check_cache:
            if time.time() - self.last_check_time.get("all", 0) < self.cache_ttl:
                return self.check_cache["all"]

        results = {}

        # 1. 系统资源检查
        results["system"] = await self._check_system()

        # 2. OCR服务检查
        if ocr_service:
            results["ocr"] = await self._check_ocr(ocr_service)

        # 3. Vision服务检查
        if vision_service:
            results["vision"] = await self._check_vision(vision_service)

        # 4. Video服务检查
        if video_service:
            results["video"] = await self._check_video(video_service)

        # 5. GPU检查
        results["gpu"] = await self._check_gpu()

        # 6. 依赖服务检查
        results["dependencies"] = await self._check_dependencies()

        # 汇总健康状态
        all_healthy = all(
            r.get("healthy", False)
            for r in results.values()
            if isinstance(r, dict) and "healthy" in r
        )

        response = {
            "healthy": all_healthy,
            "status": "ok" if all_healthy else "degraded",
            "timestamp": time.time(),
            "checks": results
        }

        # 更新缓存
        self.check_cache["all"] = response
        self.last_check_time["all"] = time.time()

        return response

    async def _check_system(self) -> Dict[str, Any]:
        """检查系统资源"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # 检查资源是否充足
            cpu_ok = cpu_percent < 90
            memory_ok = memory.percent < 90
            disk_ok = disk.percent < 90

            return {
                "healthy": cpu_ok and memory_ok and disk_ok,
                "cpu_usage": f"{cpu_percent:.1f}%",
                "memory_usage": f"{memory.percent:.1f}%",
                "memory_available": f"{memory.available / (1024**3):.2f} GB",
                "disk_usage": f"{disk.percent:.1f}%",
                "disk_free": f"{disk.free / (1024**3):.2f} GB",
                "warnings": [
                    "CPU usage high" if not cpu_ok else None,
                    "Memory usage high" if not memory_ok else None,
                    "Disk space low" if not disk_ok else None
                ]
            }

        except Exception as e:
            logger.error(f"System check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }

    async def _check_ocr(self, ocr_service) -> Dict[str, Any]:
        """检查OCR服务"""
        try:
            start_time = time.time()

            # 检查模型是否加载
            provider = ocr_service.provider
            model_loaded = False

            if provider == "paddleocr":
                model_loaded = ocr_service.ocr_engine is not None
            elif provider == "easyocr":
                model_loaded = ocr_service.easyocr_reader is not None

            # 简单性能测试（使用模拟图像）
            if model_loaded:
                test_passed = await self._test_ocr_inference(ocr_service)
            else:
                test_passed = False

            elapsed = time.time() - start_time

            return {
                "healthy": model_loaded and test_passed,
                "provider": provider,
                "model_loaded": model_loaded,
                "test_passed": test_passed,
                "check_time_ms": int(elapsed * 1000)
            }

        except Exception as e:
            logger.error(f"OCR check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }

    async def _test_ocr_inference(self, ocr_service) -> bool:
        """测试OCR推理（使用小图像）"""
        try:
            import io

            from PIL import Image

            # 创建测试图像（100x50白底黑字）
            test_image = Image.new('RGB', (100, 50), color='white')

            # 转换为bytes
            img_byte_arr = io.BytesIO()
            test_image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            # 执行OCR（应该快速返回空结果或错误，不崩溃即可）
            result = await ocr_service.recognize_from_bytes(
                img_bytes,
                confidence_threshold=0.5
            )

            # 只要不崩溃就算通过
            return True

        except Exception as e:
            logger.warning(f"OCR inference test failed: {e}")
            return False

    async def _check_vision(self, vision_service) -> Dict[str, Any]:
        """检查Vision服务"""
        try:
            # 检查Vision服务的API配置
            has_openai_key = hasattr(vision_service, 'openai_api_key') and vision_service.openai_api_key
            has_claude_key = hasattr(vision_service, 'claude_api_key') and vision_service.claude_api_key

            return {
                "healthy": has_openai_key or has_claude_key,
                "openai_configured": has_openai_key,
                "claude_configured": has_claude_key,
                "available_providers": [
                    "openai" if has_openai_key else None,
                    "claude" if has_claude_key else None
                ]
            }

        except Exception as e:
            logger.error(f"Vision check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }

    async def _check_video(self, video_service) -> Dict[str, Any]:
        """检查Video服务"""
        try:
            # 检查视频处理能力
            import cv2

            opencv_version = cv2.__version__

            return {
                "healthy": True,
                "opencv_version": opencv_version,
                "capabilities": ["frame_extraction", "video_analysis"]
            }

        except ImportError:
            return {
                "healthy": False,
                "error": "OpenCV not installed"
            }
        except Exception as e:
            logger.error(f"Video check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }

    async def _check_gpu(self) -> Dict[str, Any]:
        """检查GPU可用性"""
        try:
            import torch

            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "N/A"
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3) if gpu_count > 0 else 0

                return {
                    "healthy": True,
                    "available": True,
                    "device_count": gpu_count,
                    "device_name": gpu_name,
                    "total_memory_gb": f"{gpu_memory:.2f}",
                    "cuda_version": torch.version.cuda
                }
            else:
                return {
                    "healthy": True,  # CPU模式也是健康的
                    "available": False,
                    "message": "Running in CPU mode"
                }

        except ImportError:
            return {
                "healthy": True,
                "available": False,
                "message": "PyTorch not installed, CPU mode"
            }
        except Exception as e:
            logger.error(f"GPU check failed: {e}")
            return {
                "healthy": True,
                "available": False,
                "error": str(e)
            }

    async def _check_dependencies(self) -> Dict[str, Any]:
        """检查关键依赖"""
        dependencies = {}

        # 检查关键库
        required_libs = {
            "PIL": "Pillow",
            "cv2": "opencv-python",
            "paddleocr": "paddleocr",
            "easyocr": "easyocr",
            "torch": "torch",
            "httpx": "httpx",
            "numpy": "numpy"
        }

        all_installed = True

        for import_name, package_name in required_libs.items():
            try:
                __import__(import_name)
                dependencies[package_name] = {"installed": True}
            except ImportError:
                dependencies[package_name] = {"installed": False}
                all_installed = False

        return {
            "healthy": True,  # 依赖缺失不影响健康状态，只是功能降级
            "all_installed": all_installed,
            "packages": dependencies
        }

    async def check_liveness(self) -> Dict[str, Any]:
        """存活检查（快速检查）"""
        return {
            "alive": True,
            "timestamp": time.time()
        }

    async def check_readiness(
        self,
        ocr_service=None,
        vision_service=None
    ) -> Dict[str, Any]:
        """就绪检查（检查是否可以接受请求）"""
        checks = {}

        # OCR就绪检查
        if ocr_service:
            if ocr_service.provider == "paddleocr":
                checks["ocr"] = ocr_service.ocr_engine is not None
            elif ocr_service.provider == "easyocr":
                checks["ocr"] = ocr_service.easyocr_reader is not None
            else:
                checks["ocr"] = False

        # Vision就绪检查
        if vision_service:
            checks["vision"] = (
                hasattr(vision_service, 'openai_api_key') or
                hasattr(vision_service, 'claude_api_key')
            )

        all_ready = all(checks.values()) if checks else True

        return {
            "ready": all_ready,
            "checks": checks,
            "timestamp": time.time()
        }

    async def benchmark(
        self,
        ocr_service=None,
        vision_service=None
    ) -> Dict[str, Any]:
        """性能基准测试"""
        results = {}

        if ocr_service:
            results["ocr"] = await self._benchmark_ocr(ocr_service)

        if vision_service:
            results["vision"] = await self._benchmark_vision(vision_service)

        return {
            "benchmarks": results,
            "timestamp": time.time()
        }

    async def _benchmark_ocr(self, ocr_service) -> Dict[str, Any]:
        """OCR性能基准"""
        try:
            import io

            from PIL import Image, ImageDraw, ImageFont

            # 创建测试图像（800x400，包含文字）
            test_image = Image.new('RGB', (800, 400), color='white')
            draw = ImageDraw.Draw(test_image)

            # 绘制测试文字
            test_text = "Hello World 你好世界 12345"
            try:
                font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 40)
            except:
                font = None

            draw.text((50, 180), test_text, fill='black', font=font)

            # 转换为bytes
            img_byte_arr = io.BytesIO()
            test_image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            # 执行3次测试取平均
            latencies = []
            for _ in range(3):
                start = time.time()
                await ocr_service.recognize_from_bytes(img_bytes)
                latencies.append(time.time() - start)

            avg_latency = sum(latencies) / len(latencies)

            return {
                "avg_latency_ms": int(avg_latency * 1000),
                "min_latency_ms": int(min(latencies) * 1000),
                "max_latency_ms": int(max(latencies) * 1000),
                "test_runs": 3
            }

        except Exception as e:
            logger.error(f"OCR benchmark failed: {e}")
            return {
                "error": str(e)
            }

    async def _benchmark_vision(self, vision_service) -> Dict[str, Any]:
        """Vision性能基准（仅模拟，不实际调用API）"""
        return {
            "message": "Vision API benchmark requires real API call, skipped",
            "estimated_latency_ms": "1000-3000"
        }
