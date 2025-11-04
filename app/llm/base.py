"""
LLM Provider abstraction for multi-model support
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum

from pydantic import BaseModel


class LLMProvider(str, Enum):
    """Supported LLM providers"""

    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENAI = "openai"


class LLMMessage(BaseModel):
    """Standard message format across providers"""

    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """Standard response format"""

    content: str
    provider: LLMProvider
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def generate(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate completion from messages"""
        pass

    @abstractmethod
    async def generate_json(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        pass
