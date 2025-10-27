# 这是一个模板，展示如何在main.py中集成common模块
# 应用到: indexing-service, retrieval-service

# 1. 添加导入 (在main.py顶部)
import sys
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware

# 添加 common 模块到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

# 导入统一基础设施模块
from cors_config import get_cors_config
from cost_tracking import cost_tracking_middleware
from exception_handlers import register_exception_handlers
from structured_logging import logging_middleware, setup_logging
from telemetry import TracingConfig, init_tracing

# 2. 替换日志配置
# setup_logging(service_name="SERVICE_NAME")  # 替换SERVICE_NAME
# logger = logging.getLogger(__name__)

# 3. 在lifespan函数中添加追踪初始化
# tracing_config = TracingConfig(
#     service_name="SERVICE_NAME",
#     service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
#     environment=os.getenv("ENV", "development"),
# )
# tracer = init_tracing(tracing_config)
# if tracer:
#     logger.info("OpenTelemetry tracing initialized")

# 4. 替换CORS配置
# cors_config = get_cors_config()
# app.add_middleware(CORSMiddleware, **cors_config)

# 5. 添加中间件
# app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)
# app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)

# 6. 注册异常处理器
# register_exception_handlers(app)
