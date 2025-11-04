"""
Intent Service for mapping user intents to blockchain transactions
"""

from typing import Dict, Any, Optional
from eth_abi import encode
from web3 import Web3
from loguru import logger

from app.models.schemas import ParsedIntent, TransactionRequest
from app.services.blockchain_service import BlockchainService
from app.db.session import get_db_connection
from app.db.models import AgentCacheModel


class IntentService:
    """Service for processing intents and mapping to transactions"""

    def __init__(self, blockchain_service: BlockchainService):
        self.blockchain = blockchain_service

        # Function mappings for common actions
        self.function_mappings = {
            "stake": {
                "name": "stake",
                "selector": "0xa694fc3a",  # stake(uint256)
                "params": ["uint256"],
            },
            "withdraw": {
                "name": "withdraw",
                "selector": "0x2e1a7d4d",  # withdraw(uint256)
                "params": ["uint256"],
            },
            "claim": {
                "name": "claimRewards",
                "selector": "0x372500ab",  # claimRewards()
                "params": [],
            },
            "swap": {
                "name": "swapExactTokensForTokens",
                "selector": "0x38ed1739",  # Common Uniswap function
                "params": ["uint256", "uint256", "address[]", "address", "uint256"],
            },
        }

    async def process_intent(self, intent: ParsedIntent, user_address: str) -> TransactionRequest:
        """
        Process parsed intent and create transaction request

        Steps:
        1. Look up agent/protocol
        2. Detect contract type (hub-aware vs regular)
        3. Map action to function
        4. Encode calldata
        5. Return transaction request with execution mode
        """
        try:
            # 1. Find agent by protocol name
            # For demo, we'll use a simplified lookup
            # In production, this should query the blockchain or cache
            agent = await self._find_agent_by_name(intent.protocol)

            if not agent:
                raise ValueError(f"Protocol '{intent.protocol}' not found")

            # 2. Detect contract type
            contract_type = await self.blockchain.detect_contract_type(agent["target_address"])

            logger.info(f"Contract type: {contract_type}")

            # 3. Map action to function
            function_info = self._map_action_to_function(intent.action, agent)

            # 4. Encode calldata
            calldata = self._encode_calldata(intent, function_info, user_address)

            # 5. Determine execution mode
            execution_mode = "hub" if contract_type == "hub-aware" else "direct"

            return TransactionRequest(
                agent_id=agent["id"],
                target_address=agent["target_address"],
                function_name=function_info["name"],
                function_selector=function_info["selector"],
                calldata=calldata,
                execution_mode=execution_mode,
            )

        except Exception as e:
            logger.error(f"Error processing intent: {e}")
            raise

    async def _find_agent_by_name(self, protocol_name: str) -> Optional[Dict[str, Any]]:
        """
        Find agent by protocol name from database cache
        """
        try:
            # Query from database cache
            with get_db_connection() as conn:
                agent_data = AgentCacheModel.get_by_name(conn, protocol_name)

            if agent_data:
                logger.info(
                    f"Found agent '{protocol_name}' in cache: {agent_data['agent_id'][:20]}..."
                )
                return {
                    "id": agent_data["agent_id"],
                    "name": agent_data["name"],
                    "target_address": agent_data["target_address"],
                    "owner": agent_data["owner"],
                    "description": agent_data["description"],
                }
            else:
                logger.warning(f"Agent '{protocol_name}' not found in cache")
                return None

        except Exception as e:
            logger.error(f"Error finding agent by name: {e}")
            return None

    def _map_action_to_function(self, action: str, agent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map user action to contract function

        Returns function info: name, selector, params
        """
        # Get function info from mappings
        if action in self.function_mappings:
            return self.function_mappings[action]

        # Default: try to use action as function name
        logger.warning(f"No mapping for action '{action}', using default")
        return {"name": action, "selector": Web3.keccak(text=f"{action}()")[:4].hex(), "params": []}

    def _encode_calldata(
        self, intent: ParsedIntent, function_info: Dict[str, Any], user_address: str
    ) -> str:
        """
        Encode function calldata from intent

        Handles common patterns:
        - stake(uint256 amount)
        - withdraw(uint256 amount)
        - swap(uint256 amountIn, uint256 amountOutMin, address[] path, address to, uint256 deadline)
        """
        try:
            function_name = function_info["name"]
            params = function_info["params"]

            # Build arguments based on function
            args = []

            if function_name in ["stake", "withdraw"]:
                # Parse amount to wei (assuming 18 decimals)
                if intent.amount:
                    amount_wei = int(float(intent.amount) * 10**18)
                    args = [amount_wei]
                else:
                    raise ValueError("Amount required for stake/withdraw")

            elif function_name == "claimRewards":
                # No arguments
                args = []

            elif function_name == "swapExactTokensForTokens":
                # Parse swap parameters from intent
                import time

                if intent.amount and intent.params:
                    # Parse amount in
                    amount_in = int(float(intent.amount) * 10**18)

                    # Calculate minimum output with 0.5% slippage
                    slippage = 0.005
                    amount_out_min = int(amount_in * (1 - slippage))

                    # Get token path from params
                    token_in = intent.params.get(
                        "token_in", "0x0000000000000000000000000000000000000000"
                    )
                    token_out = intent.params.get(
                        "token_out", "0x0000000000000000000000000000000000000000"
                    )
                    path = [token_in, token_out]

                    # Set deadline to 5 minutes from now
                    deadline = int(time.time()) + 300

                    args = [
                        amount_in,
                        amount_out_min,
                        path,
                        user_address,
                        deadline,
                    ]

                    logger.info(f"Swap params: {amount_in} -> {amount_out_min}, path: {path}")
                else:
                    raise ValueError("Amount and token parameters required for swap")

            # Encode function call
            if args:
                # Encode function selector + arguments
                encoded_args = encode(params, args)
                calldata = function_info["selector"] + encoded_args.hex()
            else:
                # Just function selector
                calldata = function_info["selector"]

            return calldata

        except Exception as e:
            logger.error(f"Error encoding calldata: {e}")
            raise

    def get_function_selector(self, function_signature: str) -> str:
        """Get function selector from signature"""
        return Web3.keccak(text=function_signature)[:4].hex()
