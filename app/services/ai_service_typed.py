"""
AI Service for parsing user intent using LLMs with static typing
"""

from typing import Dict, Any, List, Optional
import re
import json
from loguru import logger

from app.models.schemas import ParsedIntent
from app.llm.factory import LLMFactory
from app.llm.base import BaseLLMClient, LLMMessage, LLMProvider
from app.config import settings


class AIService:
    """Service for AI-powered intent parsing with multi-LLM support"""

    def __init__(
        self, llm_provider: Optional[LLMProvider] = None, llm_client: Optional[BaseLLMClient] = None
    ) -> None:
        """
        Initialize AI service

        Args:
            llm_provider: LLM provider to use (defaults to settings)
            llm_client: Pre-configured LLM client (optional)
        """
        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LLMFactory.create_client(provider=llm_provider)

        logger.info(f"AIService initialized with {self.llm.__class__.__name__}")

    async def parse_user_intent(
        self,
        message: str,
        available_agents: Optional[List[Dict[str, Any]]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ParsedIntent:
        """
        Parse user message into structured intent using LLM

        Args:
            message: User's natural language message
            available_agents: List of available agents/protocols
            user_context: Additional context about the user

        Returns:
            ParsedIntent with action, protocol, and parameters
        """
        try:
            # Build context for LLM
            agents_context: str = ""
            if available_agents:
                agent_names: List[str] = [agent.get("name", "") for agent in available_agents]
                agents_context = f"Available protocols: {', '.join(agent_names)}"

            # Build system prompt
            system_prompt: str = f"""You are a blockchain transaction intent parser for ContractMind.
Your job is to extract structured information from user messages about blockchain interactions.

{agents_context}

Extract the following information:
- action: The type of action (stake, unstake, swap, lend, borrow, withdraw, claim, etc.)
- protocol: The protocol/agent name mentioned
- amount: Numeric amount if mentioned
- token: Token symbol if mentioned (e.g., USDC, ETH, etc.)
- params: Any additional parameters as a JSON object
- confidence: Your confidence score (0.0 to 1.0)

Return a valid JSON object with these fields. If information is missing, use null."""

            # Build user prompt
            user_prompt: str = f"""Parse this user message: "{message}"

User context: {json.dumps(user_context or {})}

Return JSON only."""

            # Create messages
            messages: List[LLMMessage] = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]

            # Get LLM response
            response_json: Dict[str, Any] = await self.llm.generate_json(
                messages=messages,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )

            # Parse response
            logger.info(f"LLM parsed intent: {response_json}")

            return ParsedIntent(
                action=response_json.get("action", "unknown"),
                protocol=response_json.get("protocol", ""),
                amount=response_json.get("amount"),
                token=response_json.get("token"),
                params=response_json.get("params", {}),
                confidence=float(response_json.get("confidence", 0.5)),
            )

        except Exception as e:
            logger.error(f"Error parsing intent with LLM: {e}")
            # Fallback to keyword parsing
            return self._fallback_parse(message)

    def _fallback_parse(self, message: str) -> ParsedIntent:
        """
        Fallback parser using keyword matching when LLM fails

        Args:
            message: User message to parse

        Returns:
            ParsedIntent with basic extraction
        """
        message_lower: str = message.lower()

        # Detect action
        action: str = "unknown"
        action_keywords: Dict[str, List[str]] = {
            "stake": ["stake", "staking", "deposit"],
            "unstake": ["unstake", "unstaking", "withdraw"],
            "swap": ["swap", "trade", "exchange"],
            "claim": ["claim", "harvest"],
            "lend": ["lend", "supply"],
            "borrow": ["borrow"],
        }

        for act, keywords in action_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                action = act
                break

        # Extract amount and token
        amount: Optional[str] = None
        token: Optional[str] = None

        # Look for patterns like "100 USDC" or "1.5 ETH"
        amount_pattern = r"(\d+(?:\.\d+)?)\s*([A-Z]{3,})"
        amount_match = re.search(amount_pattern, message)

        if amount_match:
            amount = amount_match.group(1)
            token = amount_match.group(2)

        # Detect protocol (enhanced keyword matching with agent names)
        protocol: str = ""

        # Common protocol keywords mapped to agent names
        protocol_map = {
            "stake": "DeFi Staking",
            "staking": "DeFi Staking",
            "defi": "DeFi Staking",
            "swap": "Uniswap",
            "uniswap": "Uniswap",
            "trade": "Uniswap",
            "exchange": "Uniswap",
            "lend": "Lending Protocol",
            "borrow": "Lending Protocol",
            "lending": "Lending Protocol",
            "aave": "Lending Protocol",
            "compound": "Lending Protocol",
            "farm": "Yield Farming",
            "farming": "Yield Farming",
            "yield": "Yield Farming",
            "nft": "NFT Marketplace",
            "marketplace": "NFT Marketplace",
        }

        for keyword, agent_name in protocol_map.items():
            if keyword in message_lower:
                protocol = agent_name
                break

        # If still no protocol found, default to DeFi Staking for basic actions
        if not protocol and action in ["stake", "unstake", "withdraw", "claim"]:
            protocol = "DeFi Staking"

        logger.warning(f"Using fallback parser: action={action}, protocol={protocol}")

        return ParsedIntent(
            action=action,
            protocol=protocol,
            amount=amount,
            token=token,
            params={},
            confidence=0.3,  # Low confidence for fallback
        )

    async def generate_transaction_description(
        self, intent: ParsedIntent, execution_mode: str
    ) -> str:
        """
        Generate human-readable description of transaction

        Args:
            intent: Parsed intent
            execution_mode: "hub" or "direct"

        Returns:
            Human-readable description
        """
        try:
            prompt: str = f"""Generate a clear, user-friendly description of this blockchain transaction:

Action: {intent.action}
Protocol: {intent.protocol}
Amount: {intent.amount} {intent.token if intent.token else ''}
Execution Mode: {execution_mode}

Write a single sentence that explains what will happen. Be concise and clear."""

            messages: List[LLMMessage] = [LLMMessage(role="user", content=prompt)]

            response = await self.llm.generate(messages=messages, temperature=0.7, max_tokens=100)

            return response.content.strip()

        except Exception as e:
            logger.error(f"Error generating description: {e}")
            # Fallback to template
            return self._generate_template_description(intent, execution_mode)

    def _generate_template_description(self, intent: ParsedIntent, execution_mode: str) -> str:
        """
        Generate description using templates

        Args:
            intent: Parsed intent
            execution_mode: "hub" or "direct"

        Returns:
            Template-based description
        """
        amount_str: str = (
            f"{intent.amount} {intent.token}" if intent.amount and intent.token else ""
        )
        route_str: str = "via ContractMind Hub" if execution_mode == "hub" else "directly"

        return f"{intent.action.capitalize()} {amount_str} on {intent.protocol} {route_str}".strip()
