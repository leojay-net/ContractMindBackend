"""
LLM Factory for creating LLM clients
"""

from typing import Optional
from loguru import logger

from app.llm.base import BaseLLMClient, LLMProvider
from app.llm.gemini import GeminiClient
from app.llm.claude import ClaudeClient
from app.llm.openai import OpenAIClient
from app.config import settings


class LLMFactory:
    """Factory for creating LLM clients"""

    @staticmethod
    def create_client(
        provider: Optional[LLMProvider] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseLLMClient:
        """
        Create LLM client based on provider

        Args:
            provider: LLM provider (defaults to settings.DEFAULT_LLM_PROVIDER)
            api_key: API key for the provider (defaults to settings)
            model: Model name (defaults to provider default)

        Returns:
            BaseLLMClient instance
        """
        # Use defaults from settings if not provided
        if provider is None:
            provider = LLMProvider(settings.DEFAULT_LLM_PROVIDER)

        # Get API key and model from settings if not provided
        if provider == LLMProvider.GEMINI:
            api_key = api_key or settings.GEMINI_API_KEY
            model = model or settings.GEMINI_MODEL
            logger.info(f"Creating Gemini client with model: {model}")
            return GeminiClient(api_key=api_key, model=model)

        elif provider == LLMProvider.CLAUDE:
            api_key = api_key or settings.ANTHROPIC_API_KEY
            model = model or settings.CLAUDE_MODEL
            logger.info(f"Creating Claude client with model: {model}")
            return ClaudeClient(api_key=api_key, model=model)

        elif provider == LLMProvider.OPENAI:
            api_key = api_key or settings.OPENAI_API_KEY
            model = model or settings.OPENAI_MODEL
            logger.info(f"Creating OpenAI client with model: {model}")
            return OpenAIClient(api_key=api_key, model=model)

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    @staticmethod
    def get_default_client() -> BaseLLMClient:
        """Get default LLM client from settings"""
        return LLMFactory.create_client()
