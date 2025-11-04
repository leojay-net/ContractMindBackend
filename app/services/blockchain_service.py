"""
Blockchain service for contract interactions
"""

from typing import List, Optional, Dict, Any
from web3 import Web3
from eth_abi import encode
from loguru import logger

from app.blockchain.client import blockchain_client
from app.models.schemas import AgentResponse, TransactionEvent
from app.db.session import get_db_connection
from app.db.models import AgentCacheModel


class BlockchainService:
    """Service for blockchain interactions"""

    def __init__(self):
        self.client = blockchain_client

    async def get_all_agents(self, skip: int = 0, limit: int = 100) -> List[AgentResponse]:
        """Get all registered agents from database cache"""
        try:
            # Query from database cache
            with get_db_connection() as conn:
                agents_data = AgentCacheModel.get_all_active(conn, limit=limit)

            # Convert to AgentResponse objects
            agents = []
            for agent_data in agents_data:
                agents.append(
                    AgentResponse(
                        id=agent_data["agent_id"],
                        target_address=agent_data["target_address"],
                        owner=agent_data["owner"],
                        name=agent_data["name"],
                        config_ipfs=agent_data["config_ipfs"],
                        active=agent_data["active"],
                        created_at=agent_data["created_at"],
                    )
                )

            logger.info(f"Retrieved {len(agents)} agents from cache")
            return agents

        except Exception as e:
            logger.error(f"Error fetching agents: {e}")
            return []

    async def get_agent(self, agent_id: str) -> Optional[AgentResponse]:
        """Get agent by ID"""
        try:
            registry = self.client.get_contract("AgentRegistry")

            # Convert agent_id to bytes32 if it's a hex string
            if isinstance(agent_id, str) and agent_id.startswith("0x"):
                agent_id_bytes = bytes.fromhex(agent_id[2:])
            else:
                agent_id_bytes = agent_id.encode()
                agent_id_bytes = agent_id_bytes.ljust(32, b"\x00")[:32]

            # Get agent data
            agent_data = await registry.functions.getAgent(agent_id_bytes).call()

            # Agent struct in contract is:
            # struct Agent { address owner; address targetContract; string name; string configIPFS; bool active; uint256 createdAt; uint256 updatedAt; }
            owner = agent_data[0]
            target_contract = agent_data[1]
            name = agent_data[2]
            config_ipfs = agent_data[3]
            active = agent_data[4]
            created_at = None
            try:
                # createdAt is index 5 if returned
                if len(agent_data) > 5 and agent_data[5]:
                    from datetime import datetime

                    created_at = datetime.utcfromtimestamp(int(agent_data[5]))
            except Exception:
                # Keep created_at as None if parsing fails
                created_at = None

            # Parse response
            return AgentResponse(
                id=agent_id,
                target_address=target_contract,
                owner=owner,
                name=name,
                config_ipfs=config_ipfs,
                active=active,
                created_at=created_at,
            )

        except Exception as e:
            logger.error(f"Error fetching agent {agent_id}: {e}")
            return None

    async def get_agent_by_name(self, name: str) -> Optional[AgentResponse]:
        """Get agent by name (requires iteration or mapping)"""
        try:
            registry = self.client.get_contract("AgentRegistry")

            # Get agent by name (if contract supports it)
            # This is a simplified version - in production, you'd want an indexed mapping
            # For now, we'll try to find by checking events or implement a backend cache

            logger.warning("get_agent_by_name not fully implemented - needs backend cache")
            return None

        except Exception as e:
            logger.error(f"Error fetching agent by name {name}: {e}")
            return None

    async def is_agent_active(self, agent_id: str) -> bool:
        """Check if agent is active"""
        try:
            registry = self.client.get_contract("AgentRegistry")

            if isinstance(agent_id, str) and agent_id.startswith("0x"):
                agent_id_bytes = bytes.fromhex(agent_id[2:])
            else:
                agent_id_bytes = agent_id.encode().ljust(32, b"\x00")[:32]

            return await registry.functions.isAgentActive(agent_id_bytes).call()

        except Exception as e:
            logger.error(f"Error checking agent active status: {e}")
            return False

    async def validate_transaction(
        self, agent_id: str, target: str, function_selector: str, user_address: str
    ) -> bool:
        """Validate if transaction is authorized via hub"""
        try:
            hub = self.client.get_contract("ContractMindHubV2")

            # Convert inputs
            if isinstance(agent_id, str) and agent_id.startswith("0x"):
                agent_id_bytes = bytes.fromhex(agent_id[2:])
            else:
                agent_id_bytes = agent_id.encode().ljust(32, b"\x00")[:32]

            if isinstance(function_selector, str) and function_selector.startswith("0x"):
                selector_bytes = bytes.fromhex(function_selector[2:])
            else:
                selector_bytes = function_selector[:4].encode()

            # Call validateTransaction on hub
            is_valid = await hub.functions.validateTransaction(
                agent_id_bytes, target, selector_bytes
            ).call({"from": user_address})

            return is_valid

        except Exception as e:
            logger.error(f"Error validating transaction: {e}")
            return False

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get transaction receipt"""
        try:
            receipt = await self.client.get_transaction_receipt(tx_hash)
            if receipt:
                return dict(receipt)
            return None
        except Exception as e:
            logger.error(f"Error getting receipt: {e}")
            return None

    async def parse_transaction_events(self, tx_hash: str) -> List[TransactionEvent]:
        """Parse events from transaction receipt"""
        try:
            receipt = await self.get_transaction_receipt(tx_hash)
            if not receipt:
                return []

            events = []
            hub = self.client.get_contract("ContractMindHubV2")

            # Parse FunctionExecuted events
            for log in receipt.get("logs", []):
                try:
                    # Try to parse with hub contract
                    event = hub.events.FunctionExecuted().process_log(log)

                    events.append(
                        TransactionEvent(
                            name="FunctionExecuted",
                            args=dict(event["args"]),
                            log_index=log["logIndex"],
                            transaction_hash=log["transactionHash"].hex(),
                        )
                    )
                except:
                    # Not a FunctionExecuted event, skip
                    pass

            return events

        except Exception as e:
            logger.error(f"Error parsing events: {e}")
            return []

    async def detect_contract_type(self, address: str) -> str:
        """
        Detect if contract is hub-aware or regular

        Returns:
            "hub-aware" if contract has trustedHub
            "regular" otherwise
        """
        try:
            # Try to call trustedHub() function
            # This is a simple ABI with just the function we need
            hub_aware_abi = [
                {
                    "inputs": [],
                    "name": "trustedHub",
                    "outputs": [{"type": "address"}],
                    "stateMutability": "view",
                    "type": "function",
                }
            ]

            contract = self.client.w3.eth.contract(address=address, abi=hub_aware_abi)

            hub_address = await contract.functions.trustedHub().call()

            # Check if it's a valid hub address (not zero address)
            if hub_address and hub_address != "0x0000000000000000000000000000000000000000":
                logger.info(f"Contract {address} is hub-aware (hub: {hub_address})")
                return "hub-aware"

        except Exception as e:
            # Contract doesn't have trustedHub function
            logger.debug(f"Contract {address} detection failed: {e}")

        logger.info(f"Contract {address} is regular (not hub-aware)")
        return "regular"
