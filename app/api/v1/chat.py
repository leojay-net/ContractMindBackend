"""
Chat endpoints (REST API alternative to WebSocket)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from web3 import Web3
from eth_abi import encode, decode

from app.api.dependencies import get_chat_service, get_intent_service, get_execution_service
from app.services.chat_service import ChatService
from app.services.intent_service import IntentService
from app.services.execution_service import ExecutionService
from app.services.blockchain_service import BlockchainService
from app.api.dependencies import get_blockchain_service

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model"""

    message: str
    user_address: str


class ChatResponse(BaseModel):
    """Chat response model"""

    intent: dict
    transaction: dict | None = None
    message: str


class DocChatRequest(BaseModel):
    """Doc-compatible chat request (includes user message and address)."""

    message: str
    userAddress: str


class DocChatQueryResponse(BaseModel):
    """Documentation-compatible response for read-only queries."""

    success: bool = True
    response: str
    requiresTransaction: bool = False
    data: dict | None = None


class DocChatTxResponse(BaseModel):
    """Documentation-compatible response for transactions."""

    success: bool = True
    requiresTransaction: bool = True
    transaction: dict


@router.post("/message", response_model=ChatResponse)
async def process_message(
    request: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    intent_service: Annotated[IntentService, Depends(get_intent_service)],
    execution_service: Annotated[ExecutionService, Depends(get_execution_service)],
):
    """
    Process chat message and return transaction

    This is a REST alternative to WebSocket for simpler integrations
    """
    try:
        # Parse intent
        parsed_intent = await chat_service.parse_message(request.message, request.user_address)

        # Process intent
        tx_request = await intent_service.process_intent(parsed_intent, request.user_address)

        # Prepare transaction
        prepared_tx = await execution_service.prepare_transaction(tx_request, request.user_address)

        return ChatResponse(
            intent=parsed_intent,
            transaction=prepared_tx.dict(),
            message=f"Transaction prepared: {prepared_tx.description}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/message", response_model=dict)
async def process_message_doc_shape(
    agent_id: str,
    request: DocChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    intent_service: Annotated[IntentService, Depends(get_intent_service)],
    execution_service: Annotated[ExecutionService, Depends(get_execution_service)],
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)],
):
    """
    Documentation-compatible chat endpoint:
    - Path: /api/v1/chat/{agent_id}/message
    - Returns either a query response (no transaction) or a transaction preview
    """
    try:
        user_address = request.userAddress

        # Ensure client initialized
        await blockchain.client.initialize()

        # Parse intent
        parsed_intent = await chat_service.parse_message(request.message, user_address)

        # Map to transaction request
        tx_request = await intent_service.process_intent(parsed_intent, user_address)

        # Prefer the path agent_id (override mock when applicable)
        try:
            tx_request.agent_id = agent_id
        except Exception:
            pass

        # Heuristic: determine if it's a write tx or a read query
        write_actions = {"stake", "withdraw", "claim", "swap", "lend", "borrow"}
        requires_tx = (parsed_intent.action or "").lower() in write_actions

        if not requires_tx:
            # Real on-chain read via hub.queryTarget with minimal ABI encoding/decoding
            # 1) Resolve agent and target
            agent = await blockchain.get_agent(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            target = agent.target_address

            # 2) Detect read function by intent + message keywords
            msg_lower = (request.message or "").lower()
            action_lower = (parsed_intent.action or "").lower()

            def selector(sig: str) -> bytes:
                return Web3.keccak(text=sig)[:4]

            # Prepare function selection
            fn = None
            arg_types = []
            args = []
            out_types = []
            data_keys = []

            if "balance" in msg_lower or action_lower in {"balance", "balanceof"}:
                fn = "balanceOf(address)"
                arg_types = ["address"]
                args = [user_address]
                out_types = ["uint256"]
                data_keys = ["balance"]
            elif (
                "pending" in msg_lower
                or "rewards" in msg_lower
                or action_lower in {"pendingrewards"}
            ):
                fn = "pendingRewards(address)"
                arg_types = ["address"]
                args = [user_address]
                out_types = ["uint256"]
                data_keys = ["rewards"]
            elif "apy" in msg_lower or action_lower in {"getcurrentapy", "apy"}:
                fn = "getCurrentAPY()"
                out_types = ["uint256"]
                data_keys = ["apy"]
            elif "tvl" in msg_lower or action_lower in {"gettvl", "tvl"}:
                fn = "getTVL()"
                out_types = ["uint256"]
                data_keys = ["tvl"]
            elif (
                "stake info" in msg_lower
                or "stakeinfo" in msg_lower
                or action_lower in {"getstakeinfo"}
            ):
                fn = "getStakeInfo(address)"
                arg_types = ["address"]
                args = [user_address]
                out_types = ["uint256", "uint256", "uint256", "uint256"]
                data_keys = ["stakedAmount", "rewards", "stakingDuration", "apy"]

            if not fn:
                # Unknown read; return a helpful message
                human = (
                    f"Interpreted as a query on {parsed_intent.protocol or 'the target'}. "
                    "Specify 'balance', 'rewards', 'APY', 'TVL', or 'stake info'."
                )
                return DocChatQueryResponse(
                    response=human,
                    requiresTransaction=False,
                    data=None,
                ).model_dump()

            # 3) Build calldata
            sig_no_spaces = fn.replace(" ", "")
            sel = selector(sig_no_spaces)
            encoded_args = b""
            if arg_types:
                encoded_args = encode(arg_types, args)
            call_data = sel + encoded_args

            # 4) Call hub.queryTarget
            hub = blockchain.client.get_contract("ContractMindHubV2")

            # Convert agentId
            if agent_id.startswith("0x"):
                agent_id_bytes = bytes.fromhex(agent_id[2:])
            else:
                agent_id_bytes = agent_id.encode().ljust(32, b"\x00")[:32]

            try:
                raw = await hub.functions.queryTarget(agent_id_bytes, target, call_data).call(
                    {"from": user_address}
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Query failed: {e}")

            # 5) Decode
            decoded = ()
            if out_types:
                try:
                    decoded = decode(out_types, raw)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Decode failed: {e}")

            # 6) Build data dict with stringified ints
            data = {}
            if data_keys:
                for i, key in enumerate(data_keys):
                    val = decoded[i] if i < len(decoded) else None
                    # return as decimal strings for safety
                    data[key] = str(val) if val is not None else None

            human = (
                f"Fetched {', '.join(data_keys)} from contract."
                if data_keys
                else "Query completed."
            )
            return DocChatQueryResponse(
                response=human,
                requiresTransaction=False,
                data=data,
            ).model_dump()

        # Prepare transaction preview for write ops
        prepared_tx = await execution_service.prepare_transaction(
            tx_request, user_address, parsed_intent
        )

        # Build doc-shaped transaction object
        tx_obj = {
            "to": prepared_tx.to,
            "data": prepared_tx.data,
            "value": (
                prepared_tx.value if isinstance(prepared_tx.value, str) else str(prepared_tx.value)
            ),
            "gasEstimate": str(prepared_tx.gas),
            "explanation": prepared_tx.description,
            "functionName": tx_request.function_name,
            "warnings": [
                "Gas fees will apply",
                "Ensure you have sufficient balance and allowance",
            ],
        }

        return DocChatTxResponse(
            transaction=tx_obj,
            requiresTransaction=True,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DocConfirmRequest(BaseModel):
    txHash: str
    userAddress: str


@router.post("/{agent_id}/confirm", response_model=dict)
async def confirm_transaction_doc_shape(
    agent_id: str,
    request: DocConfirmRequest,
    execution_service: Annotated[ExecutionService, Depends(get_execution_service)],
):
    """
    Documentation-compatible confirm endpoint.

    Note: We reuse the existing transaction status/wait logic via the blockchain client.
    """
    try:
        # Wait for or fetch the transaction receipt
        # Prefer a short wait; if unavailable, return a pending-shaped payload
        receipt = await execution_service.client.wait_for_transaction(request.txHash, timeout=30)
        if not receipt:
            return {
                "success": False,
                "response": "Transaction pending...",
                "txHash": request.txHash,
            }

        success = int(receipt.get("status", 0)) == 1
        gas_used = receipt.get("gasUsed")
        block_number = receipt.get("blockNumber")

        msg = "✅ Transaction succeeded" if success else "❌ Transaction failed"

        return {
            "success": success,
            "response": msg,
            "txHash": request.txHash,
            "blockNumber": str(block_number) if block_number is not None else None,
            "gasUsed": str(gas_used) if gas_used is not None else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
