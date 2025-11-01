"""Unit tests for VectorStoreManager"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.core.exceptions import BackendNotAvailableException
from app.core.vector_store_manager import VectorStoreManager


@pytest.mark.unit
class TestVectorStoreManager:
    """Test VectorStoreManager"""

    @pytest.fixture
    def manager(self):
        """Create VectorStoreManager instance"""
        with patch("app.core.vector_store_manager.settings") as mock_settings:
            mock_settings.default_backend = "milvus"
            mock_settings.get_backend_config = Mock(return_value={})
            return VectorStoreManager()

    @pytest.mark.asyncio
    async def test_initialize_backends(self, manager):
        """Test backend initialization"""
        with (
            patch("app.core.vector_store_manager.MilvusBackend") as mock_milvus,
            patch("app.core.vector_store_manager.PgVectorBackend") as mock_pgvector,
            patch("app.core.vector_store_manager.settings") as mock_settings,
        ):
            # Mock backend instances
            mock_milvus_instance = AsyncMock()
            mock_milvus_instance.initialize = AsyncMock()
            mock_milvus.return_value = mock_milvus_instance

            mock_pgvector_instance = AsyncMock()
            mock_pgvector_instance.initialize = AsyncMock()
            mock_pgvector.return_value = mock_pgvector_instance

            mock_settings.get_backend_config = Mock(return_value={})

            await manager.initialize()

            assert "milvus" in manager.backends
            assert "pgvector" in manager.backends

    @pytest.mark.asyncio
    async def test_initialize_backend_failure(self, manager):
        """Test backend initialization with failure"""
        with (
            patch("app.core.vector_store_manager.MilvusBackend") as mock_milvus,
            patch("app.core.vector_store_manager.settings") as mock_settings,
        ):
            mock_milvus.side_effect = Exception("Init failed")
            mock_settings.get_backend_config = Mock(return_value={})

            # Should not raise, just log error
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        """Test cleanup"""
        mock_backend = AsyncMock()
        mock_backend.cleanup = AsyncMock()
        manager.backends["test"] = mock_backend

        await manager.cleanup()

        mock_backend.cleanup.assert_called_once()
        assert len(manager.backends) == 0

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health check"""
        mock_backend1 = AsyncMock()
        mock_backend1.health_check = AsyncMock(return_value=True)

        mock_backend2 = AsyncMock()
        mock_backend2.health_check = AsyncMock(return_value=False)

        manager.backends["healthy"] = mock_backend1
        manager.backends["unhealthy"] = mock_backend2

        checks = await manager.health_check()

        assert checks["healthy"] is True
        assert checks["unhealthy"] is False

    def test_get_backend_exists(self, manager):
        """Test getting existing backend"""
        mock_backend = MagicMock()
        manager.backends["milvus"] = mock_backend

        result = manager._get_backend("milvus")
        assert result is mock_backend

    def test_get_backend_not_exists(self, manager):
        """Test getting non-existent backend"""
        with pytest.raises(BackendNotAvailableException):
            manager._get_backend("nonexistent")

    @pytest.mark.asyncio
    async def test_insert_vectors(self, manager, sample_vector_data_batch):
        """Test insert vectors"""
        mock_backend = AsyncMock()
        mock_backend.insert_vectors = AsyncMock(return_value={"inserted": 10})
        manager.backends["milvus"] = mock_backend

        result = await manager.insert_vectors(
            collection_name="test_collection",
            backend="milvus",
            data=sample_vector_data_batch,
        )

        assert result == {"inserted": 10}
        mock_backend.insert_vectors.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_vectors(self, manager, sample_query_vector):
        """Test search vectors"""
        mock_backend = AsyncMock()
        mock_backend.search_vectors = AsyncMock(return_value=[{"chunk_id": "chunk_1"}])
        manager.backends["milvus"] = mock_backend

        results = await manager.search_vectors(
            collection_name="test_collection",
            backend="milvus",
            query_vector=sample_query_vector,
            top_k=10,
        )

        assert len(results) == 1
        mock_backend.search_vectors.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_document(self, manager):
        """Test delete by document"""
        mock_backend = AsyncMock()
        mock_backend.delete_by_document = AsyncMock(return_value={"deleted": 5})
        manager.backends["milvus"] = mock_backend

        result = await manager.delete_by_document(
            collection_name="test_collection",
            backend="milvus",
            document_id="doc_123",
        )

        assert result == {"deleted": 5}
        mock_backend.delete_by_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_count(self, manager):
        """Test get count"""
        mock_backend = AsyncMock()
        mock_backend.get_count = AsyncMock(return_value=12345)
        manager.backends["milvus"] = mock_backend

        count = await manager.get_count(
            collection_name="test_collection",
            backend="milvus",
        )

        assert count == 12345

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """Test get stats"""
        mock_backend = AsyncMock()
        mock_backend.initialized = True
        mock_backend.health_check = AsyncMock(return_value=True)
        manager.backends["milvus"] = mock_backend
        manager.default_backend = "milvus"

        stats = await manager.get_stats()

        assert stats["default_backend"] == "milvus"
        assert "milvus" in stats["backends"]
        assert stats["backends"]["milvus"]["initialized"] is True
        assert stats["backends"]["milvus"]["healthy"] is True
