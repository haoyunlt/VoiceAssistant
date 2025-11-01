"""Unit tests for API endpoints"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.mark.unit
class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_endpoint(self, test_client):
        """Test /health endpoint"""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data

    def test_ready_endpoint_not_initialized(self, test_client):
        """Test /ready endpoint when not initialized"""
        response = test_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        # May be not ready if backends not initialized
        assert "ready" in data


@pytest.mark.unit
class TestVectorOperations:
    """Test vector operation endpoints"""

    @pytest.fixture
    def app_with_manager(self, monkeypatch):
        """Create app with mocked vector store manager"""
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
        monkeypatch.setenv("IDEMPOTENCY_ENABLED", "false")

        from main import app, vector_store_manager

        # Mock the manager
        mock_manager = MagicMock()
        mock_manager.insert_vectors = AsyncMock(return_value={"inserted": 10})
        mock_manager.search_vectors = AsyncMock(return_value=[{
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "content": "test",
            "score": 0.95,
        }])
        mock_manager.delete_by_document = AsyncMock(return_value={"deleted": 5})
        mock_manager.get_count = AsyncMock(return_value=100)

        with patch("main.vector_store_manager", mock_manager):
            with TestClient(app) as client:
                yield client, mock_manager

    def test_insert_vectors(self, app_with_manager):
        """Test POST /collections/{name}/insert"""
        client, mock_manager = app_with_manager

        response = client.post(
            "/collections/test_collection/insert",
            json={
                "backend": "milvus",
                "data": {
                    "chunk_id": "chunk_1",
                    "document_id": "doc_1",
                    "content": "test content",
                    "embedding": [0.1] * 1024,
                    "tenant_id": "tenant_1",
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["inserted"] == 10

    def test_insert_vectors_validation_error(self, test_client):
        """Test insert with invalid data"""
        response = test_client.post(
            "/collections/test_collection/insert",
            json={
                "backend": "milvus",
                "data": {
                    "chunk_id": "chunk_1",
                    # Missing required fields
                }
            }
        )

        assert response.status_code == 422  # Validation error

    def test_search_vectors(self, app_with_manager):
        """Test POST /collections/{name}/search"""
        client, mock_manager = app_with_manager

        response = client.post(
            "/collections/test_collection/search",
            json={
                "backend": "milvus",
                "query_vector": [0.1] * 1024,
                "top_k": 10,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["results"]) > 0

    def test_search_vectors_with_filters(self, app_with_manager):
        """Test search with tenant filter"""
        client, mock_manager = app_with_manager

        response = client.post(
            "/collections/test_collection/search",
            json={
                "backend": "milvus",
                "query_vector": [0.1] * 1024,
                "top_k": 10,
                "tenant_id": "tenant_test",
            }
        )

        assert response.status_code == 200

    def test_delete_by_document(self, app_with_manager):
        """Test DELETE /collections/{name}/documents/{document_id}"""
        client, mock_manager = app_with_manager

        response = client.delete(
            "/collections/test_collection/documents/doc_123",
            params={"backend": "milvus"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_get_collection_count(self, app_with_manager):
        """Test GET /collections/{name}/count"""
        client, mock_manager = app_with_manager

        response = client.get(
            "/collections/test_collection/count",
            params={"backend": "milvus"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 100

    def test_get_stats(self, app_with_manager):
        """Test GET /stats"""
        client, mock_manager = app_with_manager
        mock_manager.get_stats = AsyncMock(return_value={"backends": {}})

        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling"""

    def test_service_not_initialized(self, test_client):
        """Test error when service not initialized"""
        with patch("main.vector_store_manager", None):
            response = test_client.post(
                "/collections/test/insert",
                json={
                    "backend": "milvus",
                    "data": {"chunk_id": "1", "document_id": "1", "content": "test", "embedding": [0.1]},
                }
            )
            # Should handle gracefully
            assert response.status_code in [500, 503]

    def test_invalid_backend(self, app_with_manager):
        """Test with invalid backend name"""
        client, mock_manager = app_with_manager

        response = client.post(
            "/collections/test/insert",
            json={
                "backend": "invalid_backend",  # Not matching pattern
                "data": {"chunk_id": "1", "document_id": "1", "content": "test", "embedding": [0.1]},
            }
        )

        assert response.status_code == 422  # Validation error
