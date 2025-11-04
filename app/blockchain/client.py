"""
Web3 blockchain client wrapper
"""

from web3 import AsyncWeb3
from web3.eth import AsyncEth
from web3.providers import AsyncHTTPProvider
from eth_account import Account
from loguru import logger
import json
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import settings


class BlockchainClient:
    """Async Web3 client for Somnia blockchain"""

    def __init__(self):
        self.w3: Optional[AsyncWeb3] = None
        self.contracts: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize Web3 connection and load contracts"""
        if self._initialized:
            return

        try:
            # Create async Web3 instance
            self.w3 = AsyncWeb3(
                AsyncHTTPProvider(settings.SOMNIA_RPC_URL), modules={"eth": (AsyncEth,)}
            )

            # Test connection
            is_connected = await self.w3.is_connected()
            if not is_connected:
                raise ConnectionError(f"Cannot connect to {settings.SOMNIA_RPC_URL}")

            # Get chain ID
            chain_id = await self.w3.eth.chain_id
            logger.info(f"Connected to Somnia (Chain ID: {chain_id})")

            if chain_id != settings.CHAIN_ID:
                logger.warning(f"Chain ID mismatch: expected {settings.CHAIN_ID}, got {chain_id}")

            # Load contract ABIs
            await self._load_contracts()

            self._initialized = True
            logger.info("✅ Blockchain client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize blockchain client: {e}")
            raise

    async def _load_contracts(self):
        """Load contract ABIs and create contract instances"""
        contracts_dir = Path("contracts/abis")

        if not contracts_dir.exists():
            logger.warning("Contracts directory not found, creating...")
            contracts_dir.mkdir(parents=True, exist_ok=True)
            return

        # Load AgentRegistry
        registry_abi_file = contracts_dir / "AgentRegistry.json"
        if registry_abi_file.exists():
            with open(registry_abi_file) as f:
                abi_json = json.load(f)
                registry_abi = abi_json.get("abi", abi_json)

            self.contracts["AgentRegistry"] = self.w3.eth.contract(
                address=settings.AGENT_REGISTRY_ADDRESS, abi=registry_abi
            )
            logger.info(f"Loaded AgentRegistry at {settings.AGENT_REGISTRY_ADDRESS}")
        else:
            logger.warning("AgentRegistry ABI not found")

        # Load ContractMindHubV2
        hub_abi_file = contracts_dir / "ContractMindHubV2.json"
        if hub_abi_file.exists():
            with open(hub_abi_file) as f:
                abi_json = json.load(f)
                hub_abi = abi_json.get("abi", abi_json)

            self.contracts["ContractMindHubV2"] = self.w3.eth.contract(
                address=settings.CONTRACT_MIND_HUB_ADDRESS, abi=hub_abi
            )
            logger.info(f"Loaded ContractMindHubV2 at {settings.CONTRACT_MIND_HUB_ADDRESS}")
        else:
            logger.warning("ContractMindHubV2 ABI not found")

    async def get_block_number(self) -> int:
        """Get current block number"""
        return await self.w3.eth.block_number

    async def get_gas_price(self) -> int:
        """Get current gas price"""
        return await self.w3.eth.gas_price

    async def estimate_gas(self, transaction: Dict[str, Any]) -> int:
        """Estimate gas for transaction"""
        try:
            return await self.w3.eth.estimate_gas(transaction)
        except Exception as e:
            logger.error(f"Gas estimation failed: {e}")
            # Return a default high estimate
            return 500000

    async def get_transaction_receipt(self, tx_hash: str):
        """Get transaction receipt"""
        try:
            return await self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception as e:
            logger.error(f"Failed to get receipt for {tx_hash}: {e}")
            return None

    async def wait_for_transaction(self, tx_hash: str, timeout: int = 120):
        """Wait for transaction confirmation"""
        try:
            return await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        except Exception as e:
            logger.error(f"Transaction wait failed for {tx_hash}: {e}")
            return None

    def get_contract(self, name: str):
        """Get loaded contract instance"""
        if name not in self.contracts:
            raise ValueError(f"Contract {name} not loaded")
        return self.contracts[name]


# Global blockchain client instance
blockchain_client = BlockchainClient()
