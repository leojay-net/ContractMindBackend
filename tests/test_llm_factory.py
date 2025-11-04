"""
Tests for LLM Factory and providers
"""

import pytest
from unittest.mock import patch, Mock

from app.llm.factory import LLMFactory
from app.llm.base import LLMProvider, BaseLLMClient
from app.llm.gemini import GeminiClient
from app.llm.claude import ClaudeClient
from app.llm.openai import OpenAIClient


class TestLLMFactory:
    """Test cases for LLM Factory"""

    def test_create_gemini_client(self):
        """Test creating Gemini client"""
        with patch("app.config.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-key"
            mock_settings.GEMINI_MODEL = "gemini-1.5-pro"

            with patch("google.generativeai.configure"):
                with patch("google.generativeai.GenerativeModel"):
                    client = LLMFactory.create_client(
                        provider=LLMProvider.GEMINI, api_key="test-key"
                    )

                    assert isinstance(client, GeminiClient)
                    assert client.api_key == "test-key"

    def test_create_claude_client(self):
        """Test creating Claude client"""
        with patch("anthropic.AsyncAnthropic"):
            client = LLMFactory.create_client(provider=LLMProvider.CLAUDE, api_key="test-key")

            assert isinstance(client, ClaudeClient)
            assert client.api_key == "test-key"

    def test_create_openai_client(self):
        """Test creating OpenAI client"""
        with patch("openai.AsyncOpenAI"):
            client = LLMFactory.create_client(provider=LLMProvider.OPENAI, api_key="test-key")

            assert isinstance(client, OpenAIClient)
            assert client.api_key == "test-key"

    def test_create_with_invalid_provider(self):
        """Test creating client with invalid provider"""
        with pytest.raises(ValueError):
            LLMFactory.create_client(provider="invalid")

    def test_get_default_client(self):
        """Test getting default client from settings"""
        with patch("app.config.settings") as mock_settings:
            mock_settings.DEFAULT_LLM_PROVIDER = "gemini"
            mock_settings.GEMINI_API_KEY = "test-key"
            mock_settings.GEMINI_MODEL = "gemini-1.5-pro"

            with patch("google.generativeai.configure"):
                with patch("google.generativeai.GenerativeModel"):
                    client = LLMFactory.get_default_client()

                    assert isinstance(client, GeminiClient)
