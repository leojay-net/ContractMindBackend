"""
Transaction endpoints
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_blockchain_service
from app.services.blockchain_service import BlockchainService

router = APIRouter()


class TransactionStatusRequest(BaseModel):
    """Transaction status request"""

    tx_hash: str


class TransactionStatusResponse(BaseModel):
    """Transaction status response"""

    tx_hash: str
    status: str
    block_number: int | None = None
    gas_used: int | None = None
    events: list[dict] | None = None


@router.post("/status", response_model=TransactionStatusResponse)
async def get_transaction_status(
    request: TransactionStatusRequest,
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)] = None,
):
    """Get transaction status and events"""
    try:
        receipt = await blockchain.get_transaction_receipt(request.tx_hash)

        if not receipt:
            return TransactionStatusResponse(tx_hash=request.tx_hash, status="pending")

        # Parse events
        events = await blockchain.parse_transaction_events(request.tx_hash)

        return TransactionStatusResponse(
            tx_hash=request.tx_hash,
            status="success" if receipt["status"] == 1 else "failed",
            block_number=receipt["blockNumber"],
            gas_used=receipt["gasUsed"],
            events=events,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_transaction(
    agent_id: str,
    target: str,
    function_selector: str,
    user_address: str,
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)] = None,
):
    """Validate if transaction is authorized"""
    try:
        is_valid = await blockchain.validate_transaction(
            agent_id, target, function_selector, user_address
        )

        return {
            "valid": is_valid,
            "agent_id": agent_id,
            "target": target,
            "function": function_selector,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
