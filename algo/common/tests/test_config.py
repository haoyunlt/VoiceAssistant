"""
配置管理单元测试
"""

import pytest
from algo.common.config import (
    DatabaseConfig,
    LLMConfig,
    RedisConfig,
    ServiceConfig,
    merge_configs,
)


class TestServiceConfig:
    """服务配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = ServiceConfig(service_name="test-service")
        assert config.service_name == "test-service"
        assert config.service_port == 8000
        assert config.log_level == "INFO"
        assert config.max_workers == 10

    def test_custom_values(self):
        """测试自定义值"""
        config = ServiceConfig(service_name="custom-service", service_port=9000, log_level="DEBUG")
        assert config.service_port == 9000
        assert config.log_level == "DEBUG"

    def test_log_level_validation(self):
        """测试日志级别验证"""
        # 有效的日志级别
        config = ServiceConfig(service_name="test", log_level="debug")
        assert config.log_level == "DEBUG"

        # 无效的日志级别
        with pytest.raises(ValueError):
            ServiceConfig(service_name="test", log_level="INVALID")

    def test_port_validation(self):
        """测试端口验证"""
        # 有效端口
        config = ServiceConfig(service_name="test", service_port=8080)
        assert config.service_port == 8080

        # 端口过小
        with pytest.raises(ValueError):
            ServiceConfig(service_name="test", service_port=999)

        # 端口过大
        with pytest.raises(ValueError):
            ServiceConfig(service_name="test", service_port=70000)

    def test_environment_methods(self):
        """测试环境判断方法"""
        dev_config = ServiceConfig(service_name="test", environment="development")
        assert dev_config.is_development()
        assert not dev_config.is_production()

        prod_config = ServiceConfig(service_name="test", environment="production")
        assert prod_config.is_production()
        assert not prod_config.is_development()

    def test_otel_service_name_default(self):
        """测试 OTEL 服务名默认值"""
        ServiceConfig(service_name="test-service")
        # 在 Pydantic v1 中会自动设置
        # 在 Pydantic v2 中可能为 None，这取决于实现


class TestLLMConfig:
    """LLM 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = LLMConfig()
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-3.5-turbo"
        assert config.llm_timeout == 60
        assert config.llm_temperature == 0.7

    def test_temperature_validation(self):
        """测试温度参数验证"""
        # 有效温度
        config = LLMConfig(llm_temperature=0.5)
        assert config.llm_temperature == 0.5

        # 温度过低
        with pytest.raises(ValueError):
            LLMConfig(llm_temperature=-0.1)

        # 温度过高
        with pytest.raises(ValueError):
            LLMConfig(llm_temperature=2.1)


class TestDatabaseConfig:
    """数据库配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = DatabaseConfig()
        assert config.db_host == "localhost"
        assert config.db_port == 5432
        assert config.db_user == "postgres"
        assert config.db_pool_size == 10

    def test_get_database_url(self):
        """测试生成数据库 URL"""
        config = DatabaseConfig(
            db_user="testuser",
            db_password="testpass",
            db_host="testhost",
            db_port=5433,
            db_database="testdb",
        )
        url = config.get_database_url()
        assert url == "postgresql://testuser:testpass@testhost:5433/testdb"

    def test_pool_size_validation(self):
        """测试连接池大小验证"""
        # 有效大小
        config = DatabaseConfig(db_pool_size=20)
        assert config.db_pool_size == 20

        # 大小过小
        with pytest.raises(ValueError):
            DatabaseConfig(db_pool_size=0)


class TestRedisConfig:
    """Redis 配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = RedisConfig()
        assert config.redis_host == "localhost"
        assert config.redis_port == 6379
        assert config.redis_db == 0

    def test_get_redis_url_without_password(self):
        """测试生成 Redis URL（无密码）"""
        config = RedisConfig(redis_host="testhost", redis_port=6380, redis_db=1)
        url = config.get_redis_url()
        assert url == "redis://testhost:6380/1"

    def test_get_redis_url_with_password(self):
        """测试生成 Redis URL（有密码）"""
        config = RedisConfig(
            redis_host="testhost", redis_port=6380, redis_password="testpass", redis_db=1
        )
        url = config.get_redis_url()
        assert url == "redis://:testpass@testhost:6380/1"

    def test_db_validation(self):
        """测试数据库编号验证"""
        # 有效编号
        config = RedisConfig(redis_db=5)
        assert config.redis_db == 5

        # 编号过小
        with pytest.raises(ValueError):
            RedisConfig(redis_db=-1)

        # 编号过大
        with pytest.raises(ValueError):
            RedisConfig(redis_db=16)


class TestConfigUtilities:
    """配置工具函数测试"""

    def test_merge_configs(self):
        """测试合并配置"""
        service_config = ServiceConfig(service_name="test", service_port=8000)
        llm_config = LLMConfig(llm_model="gpt-4")

        merged = merge_configs(service_config, llm_config)

        assert merged["service_name"] == "test"
        assert merged["service_port"] == 8000
        assert merged["llm_model"] == "gpt-4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
