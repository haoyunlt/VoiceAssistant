"""Unit tests for pgvector backend"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.backends.pgvector_backend import PgVectorBackend
from app.core.exceptions import VectorStoreException


@pytest.mark.unit
class TestPgVectorBackend:
    """Test pgvector backend implementation"""

    @pytest.fixture
    def backend(self, pgvector_config):
        """Create pgvector backend instance"""
        return PgVectorBackend(pgvector_config)

    @pytest.mark.asyncio
    async def test_initialize_success(self, backend, _pgvector_config):
        """Test successful initialization"""
        with (
            patch("app.backends.pgvector_backend.asyncpg.create_pool") as mock_create_pool,
            patch("app.backends.pgvector_backend.register_vector") as mock_register,
        ):
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()

            acquire_mock = AsyncMock()
            acquire_mock.__aenter__ = AsyncMock(return_value=mock_conn)
            acquire_mock.__aexit__ = AsyncMock(return_value=None)
            mock_pool.acquire = Mock(return_value=acquire_mock)

            mock_create_pool.return_value = mock_pool
            mock_register.return_value = None

            await backend.initialize()

            assert backend.initialized is True
            assert backend.pool is not None

    @pytest.mark.asyncio
    async def test_initialize_failure(self, backend):
        """Test initialization failure"""
        with patch("app.backends.pgvector_backend.asyncpg.create_pool") as mock_create_pool:
            mock_create_pool.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await backend.initialize()

            assert backend.initialized is False

    @pytest.mark.asyncio
    async def test_cleanup(self, backend, mock_pgvector_pool):
        """Test cleanup"""
        backend.pool = mock_pgvector_pool
        backend.initialized = True

        await backend.cleanup()

        assert backend.initialized is False
        mock_pgvector_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend, mock_pgvector_pool):
        """Test health check success"""
        backend.pool = mock_pgvector_pool

        result = await backend.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, backend, mock_pgvector_pool):
        """Test health check failure"""
        backend.pool = mock_pgvector_pool
        mock_pgvector_pool.acquire.side_effect = Exception("Failed")

        result = await backend.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_no_pool(self, backend):
        """Test health check with no pool"""
        backend.pool = None
        result = await backend.health_check()
        assert result is False

    def test_validate_table_name_valid(self):
        """Test table name validation with valid names"""
        valid_names = ["test_table", "kb_v1", "table123", "a"]
        for name in valid_names:
            result = PgVectorBackend._validate_table_name(name)
            assert result == name

    def test_validate_table_name_invalid(self):
        """Test table name validation with invalid names"""
        invalid_names = [
            "123table",  # starts with number
            "table-name",  # contains hyphen
            "table name",  # contains space
            "table;drop",  # SQL injection attempt
            "",  # empty
        ]
        for name in invalid_names:
            with pytest.raises(VectorStoreException):
                PgVectorBackend._validate_table_name(name)

    @pytest.mark.asyncio
    async def test_insert_vectors(self, backend, mock_pgvector_pool, sample_vector_data_batch):
        """Test vector insertion"""
        backend.pool = mock_pgvector_pool
        collection_name = "test_collection"

        result = await backend.insert_vectors(collection_name, sample_vector_data_batch)

        assert result == {"inserted": len(sample_vector_data_batch)}

    @pytest.mark.asyncio
    async def test_insert_vectors_empty_data(self, backend):
        """Test insert with empty data"""
        result = await backend.insert_vectors("test_collection", [])
        assert result is None

    @pytest.mark.asyncio
    async def test_search_vectors(self, backend, mock_pgvector_pool, sample_query_vector):
        """Test vector search"""
        backend.pool = mock_pgvector_pool
        collection_name = "test_collection"

        # Mock search results
        mock_row = {
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "content": "test content",
            "tenant_id": "tenant_1",
            "score": 0.95,
        }

        acquire_mock = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        backend.pool.acquire = Mock(return_value=acquire_mock)

        results = await backend.search_vectors(
            collection_name=collection_name,
            query_vector=sample_query_vector,
            top_k=10,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk_1"
        assert results[0]["backend"] == "pgvector"

    @pytest.mark.asyncio
    async def test_search_vectors_with_tenant_filter(
        self, backend, mock_pgvector_pool, sample_query_vector
    ):
        """Test vector search with tenant filter"""
        backend.pool = mock_pgvector_pool
        collection_name = "test_collection"
        tenant_id = "tenant_test"

        acquire_mock = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        backend.pool.acquire = Mock(return_value=acquire_mock)

        await backend.search_vectors(
            collection_name=collection_name,
            query_vector=sample_query_vector,
            top_k=10,
            tenant_id=tenant_id,
        )

        # Verify tenant filter was applied
        call_args = mock_conn.fetch.call_args
        assert tenant_id in str(call_args)

    @pytest.mark.asyncio
    async def test_delete_by_document(self, backend, mock_pgvector_pool):
        """Test delete by document ID"""
        backend.pool = mock_pgvector_pool
        collection_name = "test_collection"
        document_id = "doc_123"

        acquire_mock = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 5")
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        backend.pool.acquire = Mock(return_value=acquire_mock)

        result = await backend.delete_by_document(collection_name, document_id)

        assert "deleted" in result
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_count(self, backend, mock_pgvector_pool):
        """Test get collection count"""
        backend.pool = mock_pgvector_pool
        collection_name = "test_collection"

        acquire_mock = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=12345)
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        backend.pool.acquire = Mock(return_value=acquire_mock)

        count = await backend.get_count(collection_name)
        assert count == 12345

    @pytest.mark.asyncio
    async def test_get_count_error(self, backend, mock_pgvector_pool):
        """Test get count with error"""
        backend.pool = mock_pgvector_pool
        backend.pool.acquire.side_effect = Exception("Error")

        count = await backend.get_count("test_collection")
        assert count == 0

    @pytest.mark.asyncio
    async def test_create_collection(self, backend, mock_pgvector_pool):
        """Test collection creation"""
        backend.pool = mock_pgvector_pool
        collection_name = "new_collection"
        dimension = 1024

        await backend.create_collection(collection_name, dimension)

        # Verify connection was acquired
        backend.pool.acquire.assert_called()

    @pytest.mark.asyncio
    async def test_drop_collection(self, backend, mock_pgvector_pool):
        """Test collection deletion"""
        backend.pool = mock_pgvector_pool
        collection_name = "old_collection"

        acquire_mock = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        acquire_mock.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_mock.__aexit__ = AsyncMock(return_value=None)
        backend.pool.acquire = Mock(return_value=acquire_mock)

        await backend.drop_collection(collection_name)

        mock_conn.execute.assert_called_once()
        assert "DROP TABLE" in str(mock_conn.execute.call_args)
