"""
Transaction endpoints
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import get_blockchain_service
from app.services.blockchain_service import BlockchainService
from app.models.schemas import TransactionHistoryResponse, TransactionHistoryItem
from app.db.session import get_db_connection
from app.db.models import TransactionModel

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


@router.get("", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    user_address: Optional[str] = Query(None, description="Filter by user address"),
    status: Optional[str] = Query(
        None, description="Filter by status (confirmed, pending, failed)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
):
    """
    Get transaction history with optional filters

    Returns a paginated list of transactions with optional filtering by:
    - agent_id: Filter transactions for a specific agent
    - user_address: Filter transactions for a specific user
    - status: Filter by transaction status
    - limit: Maximum results (1-100, default 50)
    - offset: Pagination offset (default 0)
    """
    try:
        with get_db_connection() as conn:
            transactions, total = TransactionModel.get_transactions(
                conn,
                agent_id=agent_id,
                user_address=user_address,
                status=status,
                limit=limit,
                offset=offset,
            )

            # Convert to response model
            transaction_items = [TransactionHistoryItem(**tx) for tx in transactions]

            return TransactionHistoryResponse(
                transactions=transaction_items,
                total=total,
                limit=limit,
                offset=offset,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")


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
