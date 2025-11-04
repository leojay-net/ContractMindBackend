"""
Google Gemini LLM client implementation
"""

from typing import Dict, Any, List, Optional
import json
import google.generativeai as genai
from loguru import logger

from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse, LLMProvider


class GeminiClient(BaseLLMClient):
    """Google Gemini LLM client"""

    def __init__(self, api_key: str, model: str = "gemini-pro"):
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)
        # Use gemini-pro which is the stable model name
        self.client = genai.GenerativeModel(
            model if model != "gemini-1.5-pro-latest" else "gemini-pro"
        )

    async def generate(
        self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate completion from messages"""
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages(messages)

            # Configure generation
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            # Generate response
            response = await self.client.generate_content_async(
                gemini_messages, generation_config=generation_config
            )

            return LLMResponse(
                content=response.text,
                provider=LLMProvider.GEMINI,
                model=self.model,
                tokens_used=(
                    response.usage_metadata.total_token_count
                    if hasattr(response, "usage_metadata")
                    else None
                ),
                finish_reason=(
                    response.candidates[0].finish_reason.name if response.candidates else None
                ),
            )

        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
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
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.error(f"Response content: {response.content}")
            raise
        except Exception as e:
            logger.error(f"Gemini JSON generation error: {e}")
            raise

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, str]]:
        """Convert standard messages to Gemini format"""
        gemini_messages = []

        for msg in messages:
            if msg.role == "system":
                # Gemini doesn't have system role, prepend to first user message
                if not gemini_messages:
                    gemini_messages.append({"role": "user", "parts": [msg.content]})
                else:
                    gemini_messages[0]["parts"][0] = (
                        msg.content + "\n\n" + gemini_messages[0]["parts"][0]
                    )
            elif msg.role == "user":
                gemini_messages.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                gemini_messages.append({"role": "model", "parts": [msg.content]})

        return gemini_messages
