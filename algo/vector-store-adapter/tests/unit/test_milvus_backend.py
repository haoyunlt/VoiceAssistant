"""Unit tests for Milvus backend"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from app.backends.milvus_backend import MilvusBackend


@pytest.mark.unit
class TestMilvusBackend:
    """Test Milvus backend implementation"""

    @pytest.fixture
    def backend(self, milvus_config):
        """Create Milvus backend instance"""
        return MilvusBackend(milvus_config)

    @pytest.mark.asyncio
    async def test_initialize_success(self, backend, milvus_config):
        """Test successful initialization"""
        with patch("app.backends.milvus_backend.connections") as mock_conn:
            mock_conn.connect = Mock()
            await backend.initialize()

            assert backend.initialized is True
            mock_conn.connect.assert_called_once_with(
                alias="default",
                host=milvus_config["host"],
                port=milvus_config["port"],
                user=milvus_config["user"],
                password=milvus_config["password"],
            )

    @pytest.mark.asyncio
    async def test_initialize_failure(self, backend):
        """Test initialization failure"""
        with patch("app.backends.milvus_backend.connections") as mock_conn:
            mock_conn.connect = Mock(side_effect=Exception("Connection failed"))

            with pytest.raises(Exception, match="Connection failed"):
                await backend.initialize()

            assert backend.initialized is False

    @pytest.mark.asyncio
    async def test_cleanup(self, backend):
        """Test cleanup"""
        backend.initialized = True

        with patch("app.backends.milvus_backend.connections") as mock_conn:
            mock_conn.disconnect = Mock()
            await backend.cleanup()

            assert backend.initialized is False
            mock_conn.disconnect.assert_called_once_with("default")

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        """Test health check success"""
        with patch("app.backends.milvus_backend.utility") as mock_utility:
            mock_utility.list_collections = Mock(return_value=[])
            result = await backend.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, backend):
        """Test health check failure"""
        with patch("app.backends.milvus_backend.utility") as mock_utility:
            mock_utility.list_collections = Mock(side_effect=Exception("Failed"))
            result = await backend.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_insert_vectors(self, backend, sample_vector_data_batch):
        """Test vector insertion"""
        collection_name = "test_collection"

        with (
            patch("app.backends.milvus_backend.Collection") as mock_collection_cls,
            patch("app.backends.milvus_backend.utility") as mock_utility,
        ):
            mock_collection = MagicMock()
            mock_collection.insert = Mock(return_value=MagicMock(primary_keys=[1, 2, 3]))
            mock_collection.flush = Mock()
            mock_collection_cls.return_value = mock_collection

            mock_utility.has_collection = Mock(return_value=True)

            result = await backend.insert_vectors(collection_name, sample_vector_data_batch)

            assert result is not None
            mock_collection.insert.assert_called_once()
            mock_collection.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_vectors_empty_data(self, backend):
        """Test insert with empty data"""
        result = await backend.insert_vectors("test_collection", [])
        assert result is None

    @pytest.mark.asyncio
    async def test_search_vectors(self, backend, sample_query_vector):
        """Test vector search"""
        collection_name = "test_collection"

        with (
            patch("app.backends.milvus_backend.Collection") as mock_collection_cls,
            patch("app.backends.milvus_backend.utility") as mock_utility,
        ):
            # Mock search results
            mock_hit = MagicMock()
            mock_hit.entity.get = Mock(
                side_effect=lambda k: {
                    "chunk_id": "chunk_1",
                    "document_id": "doc_1",
                    "content": "test content",
                    "tenant_id": "tenant_1",
                }.get(k)
            )
            mock_hit.score = 0.95
            mock_hit.distance = 0.05

            mock_collection = MagicMock()
            mock_collection.search = Mock(return_value=[[mock_hit]])
            mock_collection_cls.return_value = mock_collection

            mock_utility.has_collection = Mock(return_value=True)

            results = await backend.search_vectors(
                collection_name=collection_name,
                query_vector=sample_query_vector,
                top_k=10,
            )

            assert len(results) == 1
            assert results[0]["chunk_id"] == "chunk_1"
            assert results[0]["score"] == 0.95
            assert results[0]["backend"] == "milvus"

    @pytest.mark.asyncio
    async def test_search_vectors_with_filters(self, backend, sample_query_vector):
        """Test vector search with filters"""
        collection_name = "test_collection"
        tenant_id = "tenant_test"

        with (
            patch("app.backends.milvus_backend.Collection") as mock_collection_cls,
            patch("app.backends.milvus_backend.utility") as mock_utility,
        ):
            mock_collection = MagicMock()
            mock_collection.search = Mock(return_value=[[]])
            mock_collection_cls.return_value = mock_collection

            mock_utility.has_collection = Mock(return_value=True)

            await backend.search_vectors(
                collection_name=collection_name,
                query_vector=sample_query_vector,
                top_k=10,
                tenant_id=tenant_id,
            )

            # Verify expr parameter contains tenant filter
            call_args = mock_collection.search.call_args
            assert 'tenant_id == "tenant_test"' in call_args.kwargs.get("expr", "")

    @pytest.mark.asyncio
    async def test_delete_by_document(self, backend):
        """Test delete by document ID"""
        collection_name = "test_collection"
        document_id = "doc_123"

        with (
            patch("app.backends.milvus_backend.Collection") as mock_collection_cls,
            patch("app.backends.milvus_backend.utility") as mock_utility,
        ):
            mock_collection = MagicMock()
            mock_collection.delete = Mock()
            mock_collection_cls.return_value = mock_collection

            mock_utility.has_collection = Mock(return_value=True)

            await backend.delete_by_document(collection_name, document_id)

            mock_collection.delete.assert_called_once()
            call_args = mock_collection.delete.call_args
            assert 'document_id == "doc_123"' in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_count(self, backend):
        """Test get collection count"""
        collection_name = "test_collection"

        with (
            patch("app.backends.milvus_backend.Collection") as mock_collection_cls,
            patch("app.backends.milvus_backend.utility") as mock_utility,
        ):
            mock_collection = MagicMock()
            mock_collection.num_entities = 12345
            mock_collection_cls.return_value = mock_collection

            mock_utility.has_collection = Mock(return_value=True)

            count = await backend.get_count(collection_name)
            assert count == 12345

    @pytest.mark.asyncio
    async def test_get_count_nonexistent_collection(self, backend):
        """Test get count for nonexistent collection"""
        with patch("app.backends.milvus_backend.utility") as mock_utility:
            mock_utility.has_collection = Mock(return_value=False)
            count = await backend.get_count("nonexistent")
            assert count == 0

    @pytest.mark.asyncio
    async def test_create_collection(self, backend):
        """Test collection creation"""
        collection_name = "new_collection"
        dimension = 1024

        with (
            patch("app.backends.milvus_backend.Collection") as mock_collection_cls,
            patch("app.backends.milvus_backend.utility") as mock_utility,
        ):
            mock_collection = MagicMock()
            mock_collection.create_index = Mock()
            mock_collection.load = Mock()
            mock_collection_cls.return_value = mock_collection

            mock_utility.has_collection = Mock(return_value=False)

            await backend.create_collection(collection_name, dimension)

            mock_collection.create_index.assert_called_once()
            mock_collection.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_drop_collection(self, backend):
        """Test collection deletion"""
        collection_name = "old_collection"

        with patch("app.backends.milvus_backend.utility") as mock_utility:
            mock_utility.has_collection = Mock(return_value=True)
            mock_utility.drop_collection = Mock()

            await backend.drop_collection(collection_name)

            mock_utility.drop_collection.assert_called_once_with(collection_name)
