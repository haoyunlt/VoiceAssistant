"""
Database Connection and Session Management

数据库连接和会话管理
"""

import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()

# Global engine and session maker
_engine: Optional[any] = None
_async_session_maker: Optional[async_sessionmaker] = None


def init_database(database_url: str, echo: bool = False) -> None:
    """初始化数据库连接

    Args:
        database_url: 数据库 URL (postgresql+asyncpg://user:pass@host/db)
        echo: 是否输出 SQL 日志
    """
    global _engine, _async_session_maker

    _engine = create_async_engine(
        database_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600
    )

    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    logger.info(f"Database initialized: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")


async def create_tables() -> None:
    """创建所有表"""
    global _engine

    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    # Import models to register them with Base.metadata
    from app.db import models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created")


async def drop_tables() -> None:
    """删除所有表（仅用于测试）"""
    global _engine

    if _engine is None:
        raise RuntimeError("Database not initialized.")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.info("Database tables dropped")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入）

    Yields:
        AsyncSession: 数据库会话
    """
    global _async_session_maker

    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database() -> None:
    """关闭数据库连接"""
    global _engine

    if _engine is not None:
        await _engine.dispose()
        logger.info("Database connection closed")
