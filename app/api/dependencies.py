"""
FastAPI dependency injection functions
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.services.ai_service_typed import AIService
from app.services.blockchain_service import BlockchainService
from app.services.chat_service import ChatService
from app.services.intent_service import IntentService
from app.services.execution_service import ExecutionService
from app.services.analytics_service import AnalyticsService


# Singleton instances - cached for reuse across requests
@lru_cache()
def get_blockchain_service() -> BlockchainService:
    """Get blockchain service instance"""
    return BlockchainService()


@lru_cache()
def get_ai_service() -> AIService:
    """Get AI service instance (uses default Gemini LLM)"""
    return AIService()


@lru_cache()
def get_analytics_service() -> AnalyticsService:
    """Get analytics service instance"""
    return AnalyticsService()


# Services that depend on other services
def get_chat_service(
    ai_service: Annotated[AIService, Depends(get_ai_service)],
    blockchain_service: Annotated[BlockchainService, Depends(get_blockchain_service)],
) -> ChatService:
    """Get chat service instance"""
    return ChatService(ai_service, blockchain_service)


def get_intent_service(
    blockchain_service: Annotated[BlockchainService, Depends(get_blockchain_service)],
) -> IntentService:
    """Get intent service instance"""
    return IntentService(blockchain_service)


def get_execution_service(
    blockchain_service: Annotated[BlockchainService, Depends(get_blockchain_service)],
) -> ExecutionService:
    """Get execution service instance"""
    return ExecutionService(blockchain_service)
