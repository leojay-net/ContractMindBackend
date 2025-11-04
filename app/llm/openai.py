"""
OpenAI LLM client implementation
"""

from typing import Dict, Any, List, Optional
import json
from openai import AsyncOpenAI
from loguru import logger

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse, LLMProvider


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client"""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        super().__init__(api_key, model)
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate completion from messages"""
        try:
            # Convert messages to OpenAI format
            openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

            # Generate response
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                provider=LLMProvider.OPENAI,
                model=self.model,
                tokens_used=response.usage.total_tokens,
                finish_reason=response.choices[0].finish_reason,
            )

        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    async def generate_json(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        try:
            # Convert messages to OpenAI format
            openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

            # Add JSON instruction to last message
            if openai_messages:
                openai_messages[-1]["content"] += "\n\nRespond with valid JSON only."

            # Generate response with JSON mode
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            return json.loads(response.choices[0].message.content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI response: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI JSON generation error: {e}")
            raise
