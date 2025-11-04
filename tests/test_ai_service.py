"""
Tests for AIService with multi-LLM support
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.ai_service_typed import AIService
from app.models.schemas import ParsedIntent
from app.llm.base import LLMProvider, LLMMessage


class TestAIService:
    """Test cases for AIService"""

    @pytest.mark.asyncio
    async def test_init_with_default_provider(self):
        """Test AIService initialization with default provider"""
        with patch("app.llm.factory.LLMFactory.create_client") as mock_create:
            mock_create.return_value = Mock()
            service = AIService()
            assert service.llm is not None
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_with_custom_client(self, mock_llm_client):
        """Test AIService initialization with custom client"""
        service = AIService(llm_client=mock_llm_client)
        assert service.llm == mock_llm_client

    @pytest.mark.asyncio
    async def test_parse_user_intent_success(self, mock_llm_client):
        """Test successful intent parsing"""
        service = AIService(llm_client=mock_llm_client)

        result = await service.parse_user_intent(
            message="Stake 1000 USDC on DeFi Staking",
            available_agents=[{"name": "DeFi Staking"}],
            user_context={"address": "0x123"},
        )

        assert isinstance(result, ParsedIntent)
        assert result.action == "stake"
        assert result.protocol == "DeFi Staking"
        assert result.amount == "1000"
        assert result.token == "USDC"
        assert result.confidence == 0.95
        assert mock_llm_client.call_count == 1

    @pytest.mark.asyncio
    async def test_parse_user_intent_with_agents_context(self, mock_llm_client):
        """Test intent parsing with available agents context"""
        service = AIService(llm_client=mock_llm_client)

        available_agents = [
            {"name": "DeFi Staking"},
            {"name": "Uniswap"},
            {"name": "Lending Protocol"},
        ]

        await service.parse_user_intent(
            message="Swap ETH for USDC", available_agents=available_agents
        )

        # Check that agents were included in the prompt
        messages = mock_llm_client.last_messages
        assert len(messages) > 0
        system_message = messages[0]
        assert "DeFi Staking" in system_message.content
        assert "Uniswap" in system_message.content

    @pytest.mark.asyncio
    async def test_parse_user_intent_fallback(self, mock_llm_client):
        """Test fallback parsing when LLM fails"""
        # Mock LLM to raise exception
        mock_llm_client.generate_json = AsyncMock(side_effect=Exception("LLM Error"))

        service = AIService(llm_client=mock_llm_client)

        result = await service.parse_user_intent(message="Stake 100 USDC")

        assert isinstance(result, ParsedIntent)
        assert result.action == "stake"
        assert result.confidence < 0.5  # Low confidence for fallback

    @pytest.mark.asyncio
    async def test_fallback_parse_stake_action(self):
        """Test fallback parser detects stake action"""
        service = AIService(llm_client=Mock())

        result = service._fallback_parse("I want to stake 100 USDC")

        assert result.action == "stake"
        assert result.amount == "100"
        assert result.token == "USDC"

    @pytest.mark.asyncio
    async def test_fallback_parse_swap_action(self):
        """Test fallback parser detects swap action"""
        service = AIService(llm_client=Mock())

        result = service._fallback_parse("Swap 50 ETH for USDC")

        assert result.action == "swap"
        assert result.amount == "50"
        assert result.token == "ETH"

    @pytest.mark.asyncio
    async def test_fallback_parse_no_amount(self):
        """Test fallback parser without amount"""
        service = AIService(llm_client=Mock())

        result = service._fallback_parse("Claim my rewards")

        assert result.action == "claim"
        assert result.amount is None
        assert result.token is None

    @pytest.mark.asyncio
    async def test_generate_transaction_description(self, mock_llm_client):
        """Test transaction description generation"""
        service = AIService(llm_client=mock_llm_client)

        intent = ParsedIntent(
            action="stake",
            protocol="DeFi Staking",
            amount="1000",
            token="USDC",
            params={},
            confidence=0.95,
        )

        description = await service.generate_transaction_description(
            intent=intent, execution_mode="hub"
        )

        assert isinstance(description, str)
        assert len(description) > 0

    @pytest.mark.asyncio
    async def test_generate_template_description(self):
        """Test template-based description generation"""
        service = AIService(llm_client=Mock())

        intent = ParsedIntent(
            action="stake",
            protocol="DeFi Staking",
            amount="1000",
            token="USDC",
            params={},
            confidence=0.95,
        )

        description = service._generate_template_description(intent=intent, execution_mode="hub")

        assert "stake" in description.lower() or "Stake" in description
        assert "1000" in description
        assert "USDC" in description
        assert "DeFi Staking" in description


class TestAIServiceTypes:
    """Test static typing in AIService"""

    def test_parse_user_intent_type_hints(self):
        """Test that parse_user_intent has proper type hints"""
        from inspect import signature

        sig = signature(AIService.parse_user_intent)

        # Check return type
        assert sig.return_annotation.__name__ == "ParsedIntent"

        # Check parameter types
        assert "message" in sig.parameters
        assert "available_agents" in sig.parameters
        assert "user_context" in sig.parameters

    def test_init_type_hints(self):
        """Test that __init__ has proper type hints"""
        from inspect import signature

        sig = signature(AIService.__init__)

        assert "llm_provider" in sig.parameters
        assert "llm_client" in sig.parameters
        assert sig.return_annotation == None or sig.return_annotation.__name__ == "None"
