"""
Integration tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app


class TestAgentsAPI:
    """Test agents API endpoints"""

    def test_health_check(self):
        """Test health check endpoint"""
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_root_endpoint(self):
        """Test root endpoint"""
        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == "1.0.0"


class TestWebSocketAPI:
    """Test WebSocket endpoints"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection establishment"""
        # Note: WebSocket testing requires special handling
        # This is a placeholder for the structure
        pass


class TestAnalyticsAPI:
    """Test analytics endpoints"""

    def test_get_global_analytics(self):
        """Test global analytics endpoint"""

        from app.models.schemas import GlobalStats
        from app.api.dependencies import get_analytics_service

        # Create a proper mock that returns a GlobalStats instance
        mock_stats = GlobalStats(
            total_transactions=1000,
            total_users=500,
            total_agents=10,
            total_gas_used=5000000,
            success_rate=0.95,
            transactions_last_24h=100,
            top_agents=[{"name": "DeFi Staking", "calls": 500}, {"name": "Uniswap", "calls": 300}],
        )

        # Create mock service
        mock_service = MagicMock()
        mock_service.get_global_stats = AsyncMock(return_value=mock_stats)

        # Override the dependency
        app.dependency_overrides[get_analytics_service] = lambda: mock_service

        try:
            client = TestClient(app)
            response = client.get("/api/v1/analytics/global")

            assert response.status_code == 200
            data = response.json()
            assert data["total_transactions"] == 1000
            assert data["total_users"] == 500
        finally:
            # Clean up the override
            app.dependency_overrides.clear()
