"""
Chat Service for orchestrating the full chat flow
"""

from typing import Dict, Any
from loguru import logger

from app.models.schemas import ParsedIntent
from app.services.ai_service import AIService
from app.services.blockchain_service import BlockchainService
from app.db.session import get_db_connection
from app.db.models import AgentCacheModel


class ChatService:
    """Service for handling chat interactions"""

    def __init__(self, ai_service: AIService, blockchain_service: BlockchainService):
        self.ai = ai_service
        self.blockchain = blockchain_service

    async def parse_message(self, message: str, user_address: str) -> ParsedIntent:
        """
        Parse user message into intent

        Steps:
        1. Get available agents from blockchain
        2. Pass to AI for parsing
        3. Return parsed intent
        """
        try:
            # Get available agents (cached or from blockchain)
            available_agents = await self._get_available_agents()

            # Parse with AI
            intent = await self.ai.parse_user_intent(
                message=message,
                available_agents=available_agents,
                user_context={"address": user_address},
            )

            logger.info(
                f"Parsed intent from user {user_address}: {intent.action} on {intent.protocol}"
            )

            return intent

        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            raise

    async def _get_available_agents(self) -> list:
        """
        Get list of available agents/protocols from database cache
        """
        try:
            # Query from database cache
            with get_db_connection() as conn:
                agents_data = AgentCacheModel.get_all_active(conn, limit=100)

            # Format for AI service
            available_agents = []
            for agent in agents_data:
                available_agents.append(
                    {
                        "name": agent["name"],
                        "description": agent["description"] or "",
                        "target_address": agent["target_address"],
                    }
                )

            logger.info(f"Retrieved {len(available_agents)} available agents for AI context")
            return available_agents

        except Exception as e:
            logger.error(f"Error getting available agents: {e}")
            # Return empty list as fallback
            return []
