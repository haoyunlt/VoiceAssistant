"""
统一的 CORS 配置管理

根据环境变量动态配置 CORS，避免生产环境使用 allow_origins=["*"]
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_cors_origins() -> list[str]:
    """
    从环境变量获取 CORS 白名单

    环境变量:
        CORS_ORIGINS: 逗号分隔的源列表，例如: "http://localhost:3000,https://app.example.com"
        ENV: 环境标识 (development/staging/production)

    Returns:
        允许的源列表
    """
    origins_str = os.getenv("CORS_ORIGINS", "")

    # 如果明确配置了CORS_ORIGINS，使用配置的值
    if origins_str:
        origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]
        logger.info(f"CORS origins loaded from env: {len(origins)} origins")
        return origins

    # 否则根据环境返回默认值
    env = os.getenv("ENV", "development").lower()

    if env == "development":
        # 开发环境默认允许本地访问
        default_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ]
        logger.info(f"Using default development CORS origins: {len(default_origins)} origins")
        return default_origins

    elif env == "staging":
        # 测试环境需要明确配置
        logger.warning(
            "Staging environment detected but no CORS_ORIGINS configured. Returning empty list."
        )
        return []

    else:  # production
        # 生产环境必须明确配置，不提供默认值
        logger.warning(
            "Production environment detected but no CORS_ORIGINS configured. CORS will block all origins."
        )
        return []


def get_cors_methods() -> list[str]:
    """
    获取允许的 HTTP 方法

    Returns:
        允许的方法列表
    """
    methods_str = os.getenv("CORS_METHODS", "GET,POST,PUT,DELETE,PATCH,OPTIONS")
    return [method.strip() for method in methods_str.split(",") if method.strip()]


def get_cors_headers() -> list[str]:
    """
    获取允许的请求头

    Returns:
        允许的请求头列表
    """
    headers_str = os.getenv(
        "CORS_HEADERS", "Authorization,Content-Type,X-Request-ID,X-Tenant-ID,X-User-ID"
    )
    return [header.strip() for header in headers_str.split(",") if header.strip()]


def get_cors_max_age() -> int:
    """
    获取预检请求缓存时间（秒）

    Returns:
        缓存时间
    """
    return int(os.getenv("CORS_MAX_AGE", "3600"))


def is_cors_credentials_allowed() -> bool:
    """
    是否允许携带凭证（cookies）

    Returns:
        是否允许
    """
    return os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"


def get_cors_config() -> dict:
    """
    获取完整的 CORS 配置字典

    Returns:
        CORS 配置字典，可直接传递给 CORSMiddleware
    """
    origins = get_cors_origins()
    methods = get_cors_methods()
    headers = get_cors_headers()

    config = {
        "allow_origins": origins,
        "allow_methods": methods,
        "allow_headers": headers,
        "allow_credentials": is_cors_credentials_allowed(),
        "max_age": get_cors_max_age(),
    }

    logger.info(
        f"CORS configuration: "
        f"origins={len(origins)}, "
        f"methods={len(methods)}, "
        f"headers={len(headers)}, "
        f"credentials={config['allow_credentials']}"
    )

    return config
