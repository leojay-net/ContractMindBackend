"""
Tests for IntentService
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.intent_service import IntentService
from app.services.blockchain_service import BlockchainService
from app.models.schemas import ParsedIntent, TransactionRequest


class TestIntentService:
    """Test cases for IntentService"""

    @pytest.fixture
    def mock_blockchain_service(self):
        """Create mock blockchain service"""
        service = Mock(spec=BlockchainService)
        service.get_all_agents = AsyncMock(
            return_value=[
                {
                    "id": "0x" + "defi".encode().hex().ljust(64, "0"),
                    "name": "DeFi Staking",
                    "target_address": "0x1234567890123456789012345678901234567890",
                }
            ]
        )
        service.detect_contract_type = AsyncMock(return_value="hub-aware")
        return service

    @pytest.mark.asyncio
    async def test_process_intent_hub_aware(self, mock_blockchain_service):
        """Test processing intent for hub-aware contract"""
        service = IntentService(mock_blockchain_service)

        intent = ParsedIntent(
            action="stake",
            protocol="DeFi Staking",
            amount="1000",
            token="USDC",
            params={},
            confidence=0.95,
        )

        result = await service.process_intent(intent, "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")

        assert isinstance(result, TransactionRequest)
        assert result.execution_mode == "hub"
        assert result.function_name == "stake"
        assert "0xa694fc3a" in result.calldata  # stake function selector

    @pytest.mark.asyncio
    async def test_process_intent_regular_contract(self, mock_blockchain_service):
        """Test processing intent for regular contract"""
        mock_blockchain_service.detect_contract_type = AsyncMock(return_value="regular")

        service = IntentService(mock_blockchain_service)

        intent = ParsedIntent(
            action="stake",
            protocol="DeFi Staking",
            amount="1000",
            token="USDC",
            params={},
            confidence=0.95,
        )

        result = await service.process_intent(intent, "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")

        assert isinstance(result, TransactionRequest)
        assert result.execution_mode == "direct"

    @pytest.mark.asyncio
    async def test_encode_calldata_with_amount(self, mock_blockchain_service):
        """Test calldata encoding with amount"""
        service = IntentService(mock_blockchain_service)

        intent = ParsedIntent(
            action="stake",
            protocol="DeFi Staking",
            amount="1000",
            token="USDC",
            params={},
            confidence=0.95,
        )

        function_info = {"name": "stake", "selector": "0xa694fc3a", "params": ["uint256"]}

        calldata = service._encode_calldata(
            intent, function_info, "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        )

        assert calldata.startswith("0xa694fc3a")
        assert len(calldata) > 10  # Has encoded parameters
