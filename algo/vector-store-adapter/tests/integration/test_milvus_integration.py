"""Integration tests for Milvus backend (requires real Milvus instance)"""

import pytest

from app.backends.milvus_backend import MilvusBackend


@pytest.mark.integration
@pytest.mark.milvus
@pytest.mark.skip(reason="Requires Milvus instance - use testcontainers in CI")
class TestMilvusIntegration:
    """Integration tests for Milvus backend"""

    @pytest.fixture
    async def backend(self):
        """Create and initialize Milvus backend"""
        config = {
            "host": "localhost",
            "port": 19530,
            "user": "",
            "password": "",
        }
        backend = MilvusBackend(config)
        await backend.initialize()
        yield backend
        await backend.cleanup()

    @pytest.mark.asyncio
    async def test_full_workflow(self, backend):
        """Test full workflow: create, insert, search, delete"""
        collection_name = "test_integration"

        # Create collection
        await backend.create_collection(collection_name, dimension=128)

        # Insert vectors
        data = [
            {
                "chunk_id": f"chunk_{i}",
                "document_id": "doc_1",
                "content": f"Test content {i}",
                "embedding": [0.1 * i] * 128,
                "tenant_id": "tenant_test",
            }
            for i in range(10)
        ]
        await backend.insert_vectors(collection_name, data)

        # Search
        query_vector = [0.5] * 128
        results = await backend.search_vectors(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=5,
        )
        assert len(results) > 0

        # Delete
        await backend.delete_by_document(collection_name, "doc_1")

        # Clean up
        await backend.drop_collection(collection_name)

# TODO: Add more integration tests when testcontainers is set up
