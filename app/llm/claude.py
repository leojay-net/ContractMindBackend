"""
Anthropic Claude LLM client implementation
"""

from typing import Dict, Any, List, Optional
import json
from anthropic import AsyncAnthropic
from loguru import logger

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse, LLMProvider


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude LLM client"""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key, model)
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate completion from messages"""
        try:
            # Separate system message from others
            system_message = ""
            conversation_messages = []

            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    conversation_messages.append({"role": msg.role, "content": msg.content})

            # Generate response
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message if system_message else None,
                messages=conversation_messages,
            )

            return LLMResponse(
                content=response.content[0].text,
                provider=LLMProvider.CLAUDE,
                model=self.model,
                tokens_used=response.usage.total_tokens,
                finish_reason=response.stop_reason,
            )

        except Exception as e:
            logger.error(f"Claude generation error: {e}")
            raise

    async def generate_json(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        try:
            # Add JSON instruction to last message
            if messages:
                messages[-1].content += "\n\nRespond with valid JSON only."

            response = await self.generate(messages, temperature, max_tokens)

            # Extract JSON from response
            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            return json.loads(content.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Claude response: {e}")
            logger.error(f"Response content: {response.content}")
            raise
        except Exception as e:
            logger.error(f"Claude JSON generation error: {e}")
            raise
