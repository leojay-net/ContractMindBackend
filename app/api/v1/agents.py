"""
Agent management endpoints
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_blockchain_service
from app.models.schemas import AgentResponse, AgentListResponse
from app.services.blockchain_service import BlockchainService
from app.blockchain.client import blockchain_client
from app.config import settings

router = APIRouter()


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)] = None,
):
    """List all registered agents"""
    try:
        agents = await blockchain.get_all_agents(skip=skip, limit=limit)
        return AgentListResponse(agents=agents, total=len(agents))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str, blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)] = None
):
    """Get agent by ID"""
    try:
        agent = await blockchain.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegisterAgentRequest(BaseModel):
    """Request to register a new agent (doc-aligned minimal fields)."""

    ownerAddress: str
    targetContract: str
    name: str
    configIPFS: str


@router.post("/register", response_model=dict)
async def register_agent(
    request: RegisterAgentRequest,
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)] = None,
):
    """
    Prepare a registerAgent transaction for signing by the user's wallet.

    Returns a documentation-like payload with a transaction preview.
    """
    try:
        # Ensure blockchain client is initialized and contracts loaded
        await blockchain.client.initialize()

        try:
            registry = blockchain.client.get_contract("AgentRegistry")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"AgentRegistry ABI or address not loaded: {e}"
            )

        # Build transaction
        tx = registry.functions.registerAgent(
            request.targetContract,
            request.name,
            request.configIPFS,
        ).build_transaction(
            {
                "from": request.ownerAddress,
                "value": 0,
                "gas": 0,
                "gasPrice": 0,
                "nonce": await blockchain.client.w3.eth.get_transaction_count(request.ownerAddress),
            }
        )

        # Estimate gas and gas price
        try:
            gas_estimate = await blockchain.client.estimate_gas(tx)
        except Exception:
            gas_estimate = 500000

        try:
            gas_price = await blockchain.client.get_gas_price()
        except Exception:
            gas_price = None

        transaction = {
            "to": settings.AGENT_REGISTRY_ADDRESS,
            "data": tx.get("data"),
            "value": "0",
            "gasEstimate": str(gas_estimate),
            "explanation": f"Register agent '{request.name}'",
            "functionName": "registerAgent",
            "warnings": [
                "Gas fees will apply",
                "You will grant your agent configuration on-chain",
            ],
        }

        return {
            "success": True,
            "requiresTransaction": True,
            "transaction": transaction,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConfirmAgentRegistrationRequest(BaseModel):
    """Confirm registration by parsing the transaction receipt for AgentRegistered."""

    txHash: str


@router.post("/confirm", response_model=dict)
async def confirm_agent_registration(
    request: ConfirmAgentRegistrationRequest,
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)] = None,
):
    """
    Parse AgentRegistered event from the tx receipt and return agentId and agent details.
    """
    try:
        await blockchain.client.initialize()

        registry = blockchain.client.get_contract("AgentRegistry")

        receipt = await blockchain.client.get_transaction_receipt(request.txHash)
        if not receipt:
            return {
                "success": False,
                "error": "Transaction not found or pending",
                "txHash": request.txHash,
            }

        agent_id_hex = None
        # Parse logs for AgentRegistered
        for log in receipt.get("logs", []):
            try:
                ev = registry.events.AgentRegistered().process_log(log)
                agent_id_bytes = ev["args"]["agentId"] if "agentId" in ev["args"] else ev["args"][0]
                if isinstance(agent_id_bytes, (bytes, bytearray)):
                    agent_id_hex = "0x" + agent_id_bytes.hex()
                else:
                    # web3.py may return HexBytes
                    agent_id_hex = str(agent_id_bytes)
                break
            except Exception:
                continue

        if not agent_id_hex:
            return {
                "success": False,
                "error": "AgentRegistered event not found",
                "txHash": request.txHash,
            }

        # Fetch agent details
        try:
            # Convert hex to bytes32 for the contract call
            agent_id_bytes = bytes.fromhex(agent_id_hex[2:])
            agent_tuple = await registry.functions.getAgent(agent_id_bytes).call()

            owner = agent_tuple[0]
            target = agent_tuple[1]
            name = agent_tuple[2]
            config_ipfs = agent_tuple[3]
            active = agent_tuple[4]

            agent_obj = {
                "id": agent_id_hex,
                "owner": owner,
                "targetContract": target,
                "name": name,
                "active": bool(active),
            }
        except Exception:
            agent_obj = None

        return {
            "success": True,
            "agentId": agent_id_hex,
            "txHash": request.txHash,
            "agent": agent_obj,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/name/{agent_name}", response_model=AgentResponse)
async def get_agent_by_name(agent_name: str, blockchain: BlockchainService = Depends()):
    """Get agent by name"""
    try:
        agent = await blockchain.get_agent_by_name(agent_name)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
