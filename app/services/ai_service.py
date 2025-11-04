"""
AI Service for intent parsing using Claude
"""

from typing import Dict, Any, Optional
from anthropic import Anthropic
from loguru import logger
import json

from app.config import settings
from app.models.schemas import ParsedIntent


class AIService:
    """Service for AI-powered intent parsing using Claude"""

    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-3-5-sonnet-20241022"

    async def parse_user_intent(
        self,
        message: str,
        available_agents: Optional[list] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ParsedIntent:
        """
        Parse user message into structured intent using Claude

        Args:
            message: User's natural language message
            available_agents: List of available agents/protocols
            user_context: Additional context about the user

        Returns:
            ParsedIntent with action, protocol, and parameters
        """
        try:
            # Build context for Claude
            agents_context = ""
            if available_agents:
                agents_context = "\n".join(
                    [
                        f"- {agent['name']}: {agent.get('description', '')}"
                        for agent in available_agents
                    ]
                )
            else:
                # Default protocols if none provided
                agents_context = """
- DeFi Staking: Stake tokens to earn rewards
- Uniswap: Swap tokens
- Lending Protocol: Lend or borrow tokens
"""

            # Create system prompt
            system_prompt = f"""You are a blockchain transaction assistant for ContractMind.
Your job is to parse user intents into structured actions for smart contract interactions.

Available protocols:
{agents_context}

Parse the user's message and return a JSON object with:
- action: The action to perform (stake, unstake, swap, lend, borrow, withdraw, etc.)
- protocol: The protocol name to use
- amount: The amount (if applicable, as a string with decimals)
- token: The token symbol (if applicable)
- params: Any additional parameters as a dictionary
- confidence: Your confidence in this parsing (0.0 to 1.0)

Be precise and only extract information explicitly stated by the user.
If the user's intent is unclear, set confidence lower."""

            # Create user message
            user_prompt = f"""User message: "{message}"

Parse this into a structured intent. Return ONLY valid JSON, no other text."""

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Extract response text
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            # Parse JSON response
            parsed_data = json.loads(response_text)

            # Validate and create ParsedIntent
            intent = ParsedIntent(
                action=parsed_data.get("action", "unknown"),
                protocol=parsed_data.get("protocol", "unknown"),
                amount=parsed_data.get("amount"),
                token=parsed_data.get("token"),
                params=parsed_data.get("params", {}),
                confidence=parsed_data.get("confidence", 1.0),
            )

            logger.info(f"Parsed intent: {intent.action} on {intent.protocol}")
            return intent

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response was: {response_text}")

            # Return a low-confidence unknown intent
            return ParsedIntent(
                action="unknown",
                protocol="unknown",
                confidence=0.0,
                params={"error": "Failed to parse AI response", "raw_message": message},
            )

        except Exception as e:
            logger.error(f"Error in AI parsing: {e}")

            # Fallback: try simple keyword matching
            return self._fallback_parse(message)

    def _fallback_parse(self, message: str) -> ParsedIntent:
        """Simple keyword-based parsing as fallback"""
        message_lower = message.lower()

        # Detect action
        action = "unknown"
        if "stake" in message_lower and "unstake" not in message_lower:
            action = "stake"
        elif "unstake" in message_lower or "withdraw" in message_lower:
            action = "withdraw"
        elif "swap" in message_lower or "trade" in message_lower:
            action = "swap"
        elif "lend" in message_lower:
            action = "lend"
        elif "borrow" in message_lower:
            action = "borrow"
        elif "claim" in message_lower:
            action = "claim"

        # Try to extract amount
        import re

        amount_match = re.search(r"\b(\d+(?:\.\d+)?)\b", message)
        amount = amount_match.group(1) if amount_match else None

        # Try to extract token
        token = None
        common_tokens = ["ETH", "SOMI", "USDC", "USDT", "DAI", "WETH"]
        for token_symbol in common_tokens:
            if token_symbol.lower() in message_lower:
                token = token_symbol
                break

        logger.warning(f"Using fallback parser: {action}")

        return ParsedIntent(
            action=action,
            protocol="unknown",
            amount=amount,
            token=token,
            confidence=0.3,  # Low confidence for fallback
            params={"fallback": True, "original_message": message},
        )

    async def generate_transaction_description(
        self, intent: ParsedIntent, target_contract: str
    ) -> str:
        """Generate human-readable transaction description"""
        try:
            if intent.action == "stake" and intent.amount and intent.token:
                return f"Stake {intent.amount} {intent.token} on {intent.protocol}"
            elif intent.action == "withdraw" and intent.amount and intent.token:
                return f"Withdraw {intent.amount} {intent.token} from {intent.protocol}"
            elif intent.action == "swap":
                return f"Swap tokens on {intent.protocol}"
            else:
                return f"{intent.action.capitalize()} on {intent.protocol}"
        except:
            return f"Execute {intent.action}"
