"""
Execution Service for preparing transactions
"""

from typing import Dict, Any
from loguru import logger

from app.models.schemas import TransactionRequest, PreparedTransaction, ParsedIntent
from app.blockchain.client import blockchain_client
from app.config import settings


class ExecutionService:
    """Service for preparing blockchain transactions"""

    def __init__(self, *_args, **_kwargs):
        """
        Accept optional injected dependencies for compatibility with DI layer.
        Currently uses the global blockchain_client.
        """
        self.client = blockchain_client

    async def prepare_transaction(
        self, tx_request: TransactionRequest, user_address: str, intent: ParsedIntent = None
    ) -> PreparedTransaction:
        """
        Prepare transaction for user to sign

        Routes transaction based on execution_mode:
        - "hub": Route through ContractMindHub
        - "direct": Direct to protocol contract
        """
        try:
            if tx_request.execution_mode == "hub":
                return await self._prepare_hub_transaction(tx_request, user_address, intent)
            else:
                return await self._prepare_direct_transaction(tx_request, user_address, intent)

        except Exception as e:
            logger.error(f"Error preparing transaction: {e}")
            raise

    async def _prepare_hub_transaction(
        self, tx_request: TransactionRequest, user_address: str, intent: ParsedIntent = None
    ) -> PreparedTransaction:
        """
        Prepare transaction routed through ContractMindHub

        Creates call to: hub.executeOnTarget(agentId, target, calldata)
        """
        try:
            hub = self.client.get_contract("ContractMindHubV2")

            # Convert agent_id to bytes32
            if isinstance(tx_request.agent_id, str) and tx_request.agent_id.startswith("0x"):
                agent_id_bytes = bytes.fromhex(tx_request.agent_id[2:])
            else:
                agent_id_bytes = tx_request.agent_id.encode().ljust(32, b"\x00")[:32]

            # Build hub transaction
            hub_tx = hub.functions.executeOnTarget(
                agent_id_bytes,
                tx_request.target_address,
                bytes.fromhex(tx_request.calldata.replace("0x", "")),
            ).build_transaction(
                {
                    "from": user_address,
                    "value": 0,
                    "gas": 0,  # Will estimate
                    "gasPrice": 0,  # Will get from network
                    "nonce": await self.client.w3.eth.get_transaction_count(user_address),
                }
            )

            # Estimate gas
            try:
                gas_estimate = await self.client.estimate_gas(hub_tx)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default")
                gas_estimate = 500000

            # Get gas price
            try:
                gas_price = await self.client.get_gas_price()
            except:
                gas_price = None

            # Build description
            description = self._build_description(intent, tx_request)

            # Build preview
            preview = {
                "action": intent.action.capitalize() if intent else tx_request.function_name,
                "protocol": intent.protocol if intent else "Unknown",
                "route": "ContractMind Hub",
                "features": [
                    "Rate limiting protection",
                    "On-chain analytics",
                    "Protocol fee: 0.1%",
                ],
            }

            if intent and intent.amount and intent.token:
                preview["amount"] = f"{intent.amount} {intent.token}"

            return PreparedTransaction(
                to=settings.CONTRACT_MIND_HUB_ADDRESS,
                data=hub_tx["data"],
                value="0x0",
                gas=gas_estimate,
                gas_price=gas_price,
                route="hub",
                description=description,
                preview=preview,
            )

        except Exception as e:
            logger.error(f"Error preparing hub transaction: {e}")
            raise

    async def _prepare_direct_transaction(
        self, tx_request: TransactionRequest, user_address: str, intent: ParsedIntent = None
    ) -> PreparedTransaction:
        """
        Prepare direct transaction to protocol (bypassing hub)

        For regular contracts like Uniswap
        """
        try:
            # Build direct transaction
            tx = {
                "from": user_address,
                "to": tx_request.target_address,
                "data": tx_request.calldata,
                "value": 0,
                "gas": 0,
                "gasPrice": 0,
                "nonce": await self.client.w3.eth.get_transaction_count(user_address),
            }

            # Estimate gas
            try:
                gas_estimate = await self.client.estimate_gas(tx)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default")
                gas_estimate = 300000

            # Get gas price
            try:
                gas_price = await self.client.get_gas_price()
            except:
                gas_price = None

            # Build description
            description = self._build_description(intent, tx_request)

            # Build preview
            preview = {
                "action": intent.action.capitalize() if intent else tx_request.function_name,
                "protocol": intent.protocol if intent else "Unknown",
                "route": "Direct (no intermediary)",
                "features": ["Lower gas cost", "Standard Web3 transaction", "Full compatibility"],
            }

            if intent and intent.amount and intent.token:
                preview["amount"] = f"{intent.amount} {intent.token}"

            return PreparedTransaction(
                to=tx_request.target_address,
                data=tx_request.calldata,
                value="0x0",
                gas=gas_estimate,
                gas_price=gas_price,
                route="direct",
                description=description,
                preview=preview,
            )

        except Exception as e:
            logger.error(f"Error preparing direct transaction: {e}")
            raise

    def _build_description(
        self, intent: ParsedIntent = None, tx_request: TransactionRequest = None
    ) -> str:
        """Build human-readable transaction description"""
        if intent:
            if intent.action == "stake" and intent.amount and intent.token:
                return f"Stake {intent.amount} {intent.token} on {intent.protocol}"
            elif intent.action == "withdraw" and intent.amount and intent.token:
                return f"Withdraw {intent.amount} {intent.token} from {intent.protocol}"
            elif intent.action == "swap":
                return f"Swap tokens on {intent.protocol}"
            elif intent.action == "claim":
                return f"Claim rewards from {intent.protocol}"
            else:
                return f"{intent.action.capitalize()} on {intent.protocol}"
        elif tx_request:
            return f"Execute {tx_request.function_name} on contract"
        else:
            return "Execute blockchain transaction"
