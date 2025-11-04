"""
Chat endpoints (REST API alternative to WebSocket)
"""

from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from web3 import Web3
from eth_abi import encode, decode
from loguru import logger

from app.api.dependencies import get_chat_service, get_intent_service, get_execution_service
from app.services.chat_service import ChatService
from app.services.intent_service import IntentService
from app.services.execution_service import ExecutionService
from app.services.blockchain_service import BlockchainService
from app.api.dependencies import get_blockchain_service
from app.config import settings
from app.llm.factory import LLMFactory
from app.llm.base import LLMMessage
from app.db.session import get_db_connection
from app.db.models import ChatMessageModel

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


class SendMessageRequest(BaseModel):
    """Send message request (frontend format)"""

    agentId: str
    message: str
    userAddress: str


class TransactionResultRequest(BaseModel):
    """Transaction result report from frontend"""

    agentId: str
    txHash: str
    userAddress: str
    functionName: str
    targetAddress: str  # Contract address


@router.post("/transaction-result")
async def report_transaction_result(
    request: TransactionResultRequest,
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)],
):
    """
    Receive transaction hash from frontend after user signs,
    fetch receipt, and generate AI response about success/failure
    """
    try:
        # Ensure blockchain client is initialized
        await blockchain.client.initialize()

        # Get transaction receipt
        receipt = await blockchain.client.get_transaction_receipt(request.txHash)

        if not receipt:
            # Transaction is pending - still save to DB
            with get_db_connection() as conn:
                # Save to transactions table
                from app.db.models import TransactionModel

                # Check if transaction already exists
                existing = TransactionModel.get_by_hash(conn, request.txHash)
                if not existing:
                    TransactionModel.insert(
                        conn,
                        {
                            "tx_hash": request.txHash,
                            "user_address": request.userAddress,
                            "agent_id": request.agentId,
                            "target_address": request.targetAddress,
                            "function_name": request.functionName,
                            "calldata": "",
                            "execution_mode": "wallet",
                            "status": "pending",
                            "intent_action": request.functionName,
                            "intent_protocol": request.agentId,
                            "intent_amount": None,
                            "intent_confidence": 1.0,
                        },
                    )

                # Transaction is pending
                response_msg = f"⏳ Transaction submitted! Hash: `{request.txHash}`\n\nYour transaction is pending confirmation..."

                ChatMessageModel.create_message(
                    conn=conn,
                    agent_id=request.agentId,
                    user_address=request.userAddress,
                    role="assistant",
                    message=response_msg,
                    transaction_hash=request.txHash,
                )

            return {
                "response": response_msg,
                "status": "pending",
                "txHash": request.txHash,
            }

        # Transaction confirmed - check status
        status = receipt.get("status", 0)
        block_number = receipt.get("blockNumber")
        gas_used = receipt.get("gasUsed")

        if status == 1:
            # Success!
            response_msg = f"""✅ **Transaction Successful!**

**Function:** {request.functionName}
**Transaction Hash:** `{request.txHash}`
**Block:** {block_number}
**Gas Used:** {gas_used:,}

Your transaction has been confirmed on the blockchain! 🎉"""
        else:
            # Failed
            response_msg = f"""❌ **Transaction Failed**

**Function:** {request.functionName}
**Transaction Hash:** `{request.txHash}`
**Block:** {block_number}

The transaction was reverted. Please check your parameters and try again."""

        # Save to database
        with get_db_connection() as conn:
            from app.db.models import TransactionModel

            # Check if transaction exists, if not create it
            existing = TransactionModel.get_by_hash(conn, request.txHash)
            if not existing:
                TransactionModel.insert(
                    conn,
                    {
                        "tx_hash": request.txHash,
                        "user_address": request.userAddress,
                        "agent_id": request.agentId,
                        "target_address": request.targetAddress,
                        "function_name": request.functionName,
                        "calldata": "",
                        "execution_mode": "wallet",
                        "status": "confirmed" if status == 1 else "failed",
                        "intent_action": request.functionName,
                        "intent_protocol": request.agentId,
                        "intent_amount": None,
                        "intent_confidence": 1.0,
                    },
                )
                # Update with receipt data
                TransactionModel.update_status(
                    conn,
                    request.txHash,
                    "confirmed" if status == 1 else "failed",
                    block_number,
                    gas_used,
                    None if status == 1 else "Transaction reverted",
                )
            else:
                # Just update status
                TransactionModel.update_status(
                    conn,
                    request.txHash,
                    "confirmed" if status == 1 else "failed",
                    block_number,
                    gas_used,
                    None if status == 1 else "Transaction reverted",
                )

            # Save to chat history
            ChatMessageModel.create_message(
                conn=conn,
                agent_id=request.agentId,
                user_address=request.userAddress,
                role="assistant",
                message=response_msg,
                function_name=request.functionName,
                requires_transaction=True,
                transaction_hash=request.txHash,
            )

        return {
            "response": response_msg,
            "status": "success" if status == 1 else "failed",
            "txHash": request.txHash,
            "blockNumber": block_number,
            "gasUsed": gas_used,
        }

    except Exception as e:
        logger.error(f"Error processing transaction result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=dict)
async def send_chat_message(
    request: SendMessageRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    intent_service: Annotated[IntentService, Depends(get_intent_service)],
    execution_service: Annotated[ExecutionService, Depends(get_execution_service)],
    blockchain: Annotated[BlockchainService, Depends(get_blockchain_service)],
):
    """
    Send a chat message to an agent (frontend-compatible endpoint)

    This endpoint matches the frontend's expected format:
    POST /api/v1/chat
    """
    try:
        # Get agent details with ABI
        agent = await blockchain.get_agent(request.agentId)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get available functions from ABI
        available_functions = []
        if agent.functions:
            available_functions = [
                {
                    "name": f.name,
                    "inputs": [{"name": inp.name, "type": inp.type} for inp in f.inputs],
                    "stateMutability": f.stateMutability,
                    "authorized": f.authorized,
                }
                for f in agent.functions
            ]

        # If no functions available, return helpful message
        if not available_functions:
            return {
                "response": "Sorry, I don't have access to the contract's functions. Please make sure the agent has a valid ABI configured.",
                "isPreparedTransaction": False,
            }

        # Get recent chat history for context
        chat_history = []
        try:
            with get_db_connection() as conn:
                recent_messages = ChatMessageModel.get_history(
                    conn, request.agentId, request.userAddress, limit=5
                )
                chat_history = (
                    recent_messages[-4:] if len(recent_messages) > 0 else []
                )  # Last 2 exchanges (4 messages)
        except Exception as e:
            logger.warning(f"Could not load chat history: {e}")

        # Parse user message with function context
        parsed_intent = await _parse_message_with_context(
            message=request.message,
            user_address=request.userAddress,
            agent_name=agent.name,
            available_functions=available_functions,
            chat_history=chat_history,
        )

        # Check if this requires a transaction
        requires_tx = parsed_intent.get("requiresTransaction", False)
        function_name = parsed_intent.get("functionName")
        needs_more_info = parsed_intent.get("needsMoreInfo", False)

        # Save user message to history
        with get_db_connection() as conn:
            ChatMessageModel.create_message(
                conn=conn,
                agent_id=request.agentId,
                user_address=request.userAddress,
                role="user",
                message=request.message,
                function_name=function_name,
                requires_transaction=requires_tx,
            )

        # If AI needs more info (missing parameters), ask user conversationally
        if needs_more_info:
            response_msg = parsed_intent.get("response", "I need more information to proceed.")
            # Save assistant response
            with get_db_connection() as conn:
                ChatMessageModel.create_message(
                    conn=conn,
                    agent_id=request.agentId,
                    user_address=request.userAddress,
                    role="assistant",
                    message=response_msg,
                )
            return {
                "response": response_msg,
                "isPreparedTransaction": False,
            }

        # Check if function exists and is authorized
        if function_name:
            matching_func = next((f for f in agent.functions if f.name == function_name), None)
            if not matching_func:
                response_msg = (
                    f"Sorry, the function '{function_name}' is not available on this contract."
                )
                # Save assistant response
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                    )
                return {
                    "response": response_msg,
                    "isPreparedTransaction": False,
                }
            if not matching_func.authorized:
                response_msg = f"Sorry, the function '{function_name}' is not authorized for this agent. Please contact the agent owner to authorize it."
                # Save assistant response
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                    )
                return {
                    "response": response_msg,
                    "isPreparedTransaction": False,
                }

        if requires_tx and function_name:
            # Get the function ABI to check required parameters
            func_abi = next(
                (
                    f
                    for f in agent.abi
                    if f.get("name") == function_name and f.get("type") == "function"
                ),
                None,
            )

            if not func_abi:
                response_msg = f"Function {function_name} not found in contract ABI"
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                    )
                return {
                    "response": response_msg,
                    "isPreparedTransaction": False,
                }

            # Check if all required parameters are present
            function_params = parsed_intent.get("params", {})
            required_params = func_abi.get("inputs", [])
            missing_params = []

            for param in required_params:
                param_name = param["name"]
                if param_name not in function_params or function_params[param_name] is None:
                    missing_params.append(f"{param_name} ({param['type']})")

            # If parameters are missing, ask for them
            if missing_params:
                missing_str = ", ".join(missing_params)
                response_msg = f"I need the following parameters to proceed: {missing_str}. Could you provide them?"

                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                    )
                return {
                    "response": response_msg,
                    "isPreparedTransaction": False,
                }

            # Encode the function call
            matching_func = next((f for f in agent.functions if f.name == function_name), None)
            function_params = parsed_intent.get("params", {})

            logger.info(f"Encoding transaction for {function_name} with params: {function_params}")

            # Build transaction data
            try:
                # Get function signature
                func_abi = next(
                    (
                        f
                        for f in agent.abi
                        if f.get("name") == function_name and f.get("type") == "function"
                    ),
                    None,
                )
                if not func_abi:
                    raise ValueError(f"Function {function_name} not found in ABI")

                # Extract parameter values in order
                param_values = []
                for input_param in func_abi.get("inputs", []):
                    param_name = input_param["name"]
                    param_value = function_params.get(param_name)

                    if param_value is None:
                        logger.error(
                            f"Missing required parameter: {param_name} (type: {input_param['type']})"
                        )
                        raise ValueError(f"Missing required parameter: {param_name}")

                    logger.info(
                        f"Parameter {param_name}: {param_value} (type: {type(param_value).__name__})"
                    )
                    param_values.append(param_value)

                logger.info(f"Final param_values for Web3 call: {param_values}")

                # Encode function call
                w3 = Web3()
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(agent.target_address), abi=agent.abi
                )
                function_obj = contract.functions[function_name](*param_values)
                encoded_data = function_obj._encode_transaction_data()

                # Format amounts for display
                display_params = {}
                for k, v in function_params.items():
                    # Check if this is an amount field (uint256 in wei)
                    param_def = next(
                        (p for p in func_abi.get("inputs", []) if p["name"] == k), None
                    )
                    if param_def and param_def["type"] == "uint256" and isinstance(v, int):
                        # Convert wei to tokens (divide by 10^18)
                        display_params[k] = f"{v / (10**18):.2f} tokens"
                    else:
                        display_params[k] = v

                # Build human-readable message
                if function_name == "mint":
                    amount_display = display_params.get("amount", "tokens")
                    to_display = display_params.get("to", "address")
                    response_msg = f"✅ Transaction prepared! Ready to mint {amount_display} to {to_display}. Please review and sign."
                elif function_name == "transfer":
                    amount_display = display_params.get("amount", "tokens")
                    to_display = display_params.get("to", "address")
                    response_msg = f"✅ Transaction prepared! Ready to transfer {amount_display} to {to_display}. Please review and sign."
                else:
                    response_msg = f"✅ Transaction prepared! Ready to call {function_name}. Please review and sign."

                # Save assistant response
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                        function_name=function_name,
                        requires_transaction=True,
                    )

                return {
                    "response": response_msg,
                    "isPreparedTransaction": True,
                    "preparedTransaction": {
                        "to": agent.target_address,
                        "data": encoded_data,
                        "value": "0x0",
                        "functionName": function_name,
                        "description": response_msg,
                        "params": function_params,
                    },
                }
            except Exception as e:
                logger.error(f"Error encoding transaction: {e}")
                response_msg = f"Error preparing transaction: {str(e)}"
                # Save assistant response
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                    )
                return {
                    "response": response_msg,
                    "isPreparedTransaction": False,
                }
        elif function_name and not requires_tx:
            # Execute read-only query
            try:
                result = await _execute_read_query(
                    blockchain=blockchain,
                    agent=agent,
                    function_name=function_name,
                    user_address=request.userAddress,
                    parsed_intent=parsed_intent,
                )
                # Save assistant response
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=result,
                        function_name=function_name,
                    )
                return {
                    "response": result,
                    "isPreparedTransaction": False,
                }
            except Exception as e:
                logger.error(f"Error executing read query: {e}")
                response_msg = f"Error executing query: {str(e)}"
                # Save assistant response
                with get_db_connection() as conn:
                    ChatMessageModel.create_message(
                        conn=conn,
                        agent_id=request.agentId,
                        user_address=request.userAddress,
                        role="assistant",
                        message=response_msg,
                    )
                return {
                    "response": response_msg,
                    "isPreparedTransaction": False,
                }
        else:
            # Just return a text response
            response_msg = parsed_intent.get("response", "Query processed")
            # Save assistant response
            with get_db_connection() as conn:
                ChatMessageModel.create_message(
                    conn=conn,
                    agent_id=request.agentId,
                    user_address=request.userAddress,
                    role="assistant",
                    message=response_msg,
                )
            return {
                "response": response_msg,
                "isPreparedTransaction": False,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_chat_message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _parse_message_with_context(
    message: str,
    user_address: str,
    agent_name: str,
    available_functions: list,
    chat_history: list = None,
) -> dict:
    """
    Parse message with contract context using AI (configurable LLM provider)

    Uses the configured LLM (Gemini by default) to understand natural language
    and map to contract functions. Handles greetings, questions, and function
    requests naturally.
    """
    try:
        # Get LLM client from factory (uses DEFAULT_LLM_PROVIDER from config)
        llm_client = LLMFactory.get_default_client()

        # Build function list for AI
        functions_desc = []
        for func in available_functions:
            inputs_str = ", ".join([f"{inp['name']}: {inp['type']}" for inp in func["inputs"]])
            state = func["stateMutability"]
            auth_status = "✅ authorized" if func["authorized"] else "❌ not authorized"
            functions_desc.append(f"- {func['name']}({inputs_str}) [{state}] {auth_status}")

        functions_text = "\n".join(functions_desc)

        # Build conversation context if available
        context_text = ""
        if chat_history and len(chat_history) > 0:
            context_text = "\n\nRecent conversation:\n"
            for msg in chat_history:
                role = "User" if msg["role"] == "user" else "Assistant"
                context_text += f"{role}: {msg['content']}\n"
            context_text += "\nIMPORTANT: If the user is providing information in response to your previous question, maintain the context and use that information to complete the previous intent."

        # Create system prompt
        system_prompt = f"""You are {agent_name}, a friendly AI assistant for a smart contract.

Your role:
1. Handle greetings and casual conversation naturally
2. Answer questions about the contract
3. Map user requests to contract functions when appropriate
4. Extract function parameters from the user's message
5. Ask for missing required parameters conversationally
6. Maintain conversation context - if you asked for parameters, remember what function you were working with

Available contract functions:
{functions_text}
{context_text}

Rules:
- Be friendly and conversational for greetings (hello, hi, thanks, etc.)
- For contract function requests, identify the function name
- Extract parameter values from the user's message when possible
- If parameters are missing, set needsMoreInfo=true and ask for them naturally
- IMPORTANT: If you just asked for parameters and user provides them, use the SAME function from context
- If ALL required parameters are provided, DO NOT ask for confirmation - just prepare the transaction
- Your response should be brief and indicate the transaction is being prepared
- Only suggest functions that are authorized (✅)
- Explain if a function is not authorized (❌)
- For view/pure functions, no transaction is needed
- For other functions, a transaction will be required

Parameter extraction rules:
- For address parameters: 
  * "me", "my", "I", "myself" → use the user's address from context
  * Otherwise extract the actual address (0x...)
- For amount/uint256 parameters:
  * Extract the numeric value (e.g., "ten" → 10, "100" → 100)
  * Return as a string number without decimals (the backend will handle wei conversion)
- For string parameters: extract as-is

IMPORTANT: If user says "me" or "my address", replace it with the actual address value from User address field.

Respond with JSON:
{{
  "functionName": "function name or null",
  "requiresTransaction": true/false,
  "response": "your natural response message",
  "params": {{"param1": actual_value}},  // ACTUAL VALUES, not placeholders or types
  "needsMoreInfo": false,  // true if missing required parameters
  "missingParams": ["param1", "param2"]  // list of missing parameter names
}}

Example:
User says: "mint 100 tokens to my address"
User address: 0xABC123...
You respond: {{"functionName": "mint", "params": {{"to": "0xABC123...", "amount": "100"}}, ...}}"""

        # Create messages
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(
                role="user", content=f"User message: {message}\nUser address: {user_address}"
            ),
        ]

        # Call LLM
        parsed = await llm_client.generate_json(
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

        # Debug: Log what AI returned
        logger.info(f"AI parsed intent: {parsed}")

        # Validate function exists and is authorized
        if parsed.get("functionName"):
            func = next(
                (f for f in available_functions if f["name"] == parsed["functionName"]), None
            )
            if func and not func["authorized"]:
                parsed["response"] = (
                    f"Sorry, the function '{parsed['functionName']}' is not authorized for this agent. Please contact the agent owner to authorize it."
                )
                parsed["functionName"] = None
            else:
                # Process and validate parameters
                params = parsed.get("params", {})
                if params:
                    # Find function ABI to get parameter types
                    for f in available_functions:
                        if f["name"] == parsed["functionName"]:
                            for input_param in f["inputs"]:
                                param_name = input_param["name"]
                                param_type = input_param["type"]

                                if param_name in params:
                                    param_value = params[param_name]

                                    # Handle address type - replace placeholders with actual user address
                                    if param_type == "address":
                                        if isinstance(param_value, str):
                                            # If AI returned placeholder or descriptive text, use user address
                                            if param_value.lower() in [
                                                "user",
                                                "me",
                                                "my",
                                                "myself",
                                                "sender",
                                            ] or not param_value.startswith("0x"):
                                                params[param_name] = user_address
                                                logger.info(
                                                    f"Replaced address placeholder '{param_value}' with user address {user_address}"
                                                )

                                    # Convert amounts to wei for uint256
                                    elif param_type == "uint256" and isinstance(
                                        param_value, (int, float, str)
                                    ):
                                        try:
                                            # Convert to int if string
                                            amount = (
                                                int(param_value)
                                                if isinstance(param_value, str)
                                                else param_value
                                            )
                                            # Convert to wei (multiply by 10^18) - keep as INT for Web3
                                            params[param_name] = amount * (10**18)
                                            logger.info(
                                                f"Converted amount {param_value} to wei: {params[param_name]}"
                                            )
                                        except (ValueError, TypeError):
                                            logger.warning(
                                                f"Failed to convert amount {param_value} to wei"
                                            )
                                            pass  # Keep original value if conversion fails
                            break

                    # Update params in parsed intent
                    parsed["params"] = params
                    logger.info(f"Final processed params: {params}")

        return parsed

    except Exception as e:
        logger.error(f"Error parsing with AI: {e}")
        # Fallback to keyword matching
        return await _parse_message_with_keywords(
            message, user_address, agent_name, available_functions
        )


async def _parse_message_with_keywords(
    message: str,
    user_address: str,
    agent_name: str,
    available_functions: list,
) -> dict:
    """
    Fallback keyword-based parsing when AI is not available
    """
    message_lower = message.lower()

    # Check for greetings and casual conversation
    greeting_keywords = [
        "hello",
        "hi",
        "hey",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
    ]
    thanks_keywords = ["thank", "thanks", "appreciate"]
    help_keywords = ["help", "what can you do", "capabilities", "features"]

    if any(keyword in message_lower for keyword in greeting_keywords):
        available_func_names = ", ".join([f["name"] for f in available_functions[:8]])
        return {
            "functionName": None,
            "requiresTransaction": False,
            "response": f"Hello! I'm {agent_name}, your AI assistant for interacting with smart contracts. I can help you with: {available_func_names}. Just ask me in natural language!",
        }

    if any(keyword in message_lower for keyword in thanks_keywords):
        return {
            "functionName": None,
            "requiresTransaction": False,
            "response": "You're welcome! Let me know if you need anything else.",
        }

    if any(keyword in message_lower for keyword in help_keywords):
        available_func_names = ", ".join([f["name"] for f in available_functions[:8]])
        return {
            "functionName": None,
            "requiresTransaction": False,
            "response": f"I can help you interact with this smart contract. Available functions: {available_func_names}. Try asking things like 'What is my balance?' or 'Transfer tokens'.",
        }

    # Build function map
    function_map = {f["name"].lower(): f for f in available_functions}

    # View/Query functions
    view_keywords = {
        "balance": "balanceOf",
        "allowance": "allowance",
        "total supply": "totalSupply",
        "decimals": "decimals",
        "name": "name",
        "symbol": "symbol",
        "owner": "owner",
    }

    # State-changing functions
    tx_keywords = {
        "transfer": "transfer",
        "send": "transfer",
        "approve": "approve",
        "mint": "mint",
        "stake": "stake",
        "withdraw": "withdraw",
        "swap": "swap",
    }

    # Check for view functions
    for keyword, func_name in view_keywords.items():
        if keyword in message_lower and func_name.lower() in function_map:
            return {
                "functionName": func_name,
                "requiresTransaction": False,
                "response": f"I'll check the {func_name} for you.",
            }

    # Check for transaction functions
    for keyword, func_name in tx_keywords.items():
        if keyword in message_lower and func_name.lower() in function_map:
            func_info = function_map[func_name.lower()]
            if func_info["stateMutability"] in ["pure", "view"]:
                return {
                    "functionName": func_name,
                    "requiresTransaction": False,
                    "response": f"I'll query the {func_name} function for you.",
                }
            return {
                "functionName": func_name,
                "requiresTransaction": True,
                "response": f"I'll prepare a transaction to call {func_name}.",
            }

    # No match - friendly response
    available_func_names = ", ".join([f["name"] for f in available_functions[:5]])
    return {
        "functionName": None,
        "requiresTransaction": False,
        "response": f"I'm not sure how to help with that. I can assist with: {available_func_names}. What would you like to do?",
    }


async def _execute_read_query(
    blockchain: BlockchainService,
    agent,
    function_name: str,
    user_address: str,
    parsed_intent: dict,
) -> str:
    """
    Execute a read-only contract query and return formatted result
    """
    try:
        # Initialize blockchain client
        await blockchain.client.initialize()

        # Get contract instance (we need to use the target contract, not the registry)
        from app.db.session import get_db_connection
        from app.db.models import AgentCacheModel

        # Get the ABI from the agent
        with get_db_connection() as conn:
            agent_data = AgentCacheModel.get_by_id(conn, agent.id)

        if not agent_data or not agent_data.get("abi"):
            return "Error: Contract ABI not available"

        # Create contract instance with the target contract address
        target_contract = blockchain.client.w3.eth.contract(
            address=Web3.to_checksum_address(agent.target_address), abi=agent_data["abi"]
        )

        # Determine which function to call and with what parameters
        if function_name == "balanceOf":
            # Call balanceOf with user's address
            result = await target_contract.functions.balanceOf(
                Web3.to_checksum_address(user_address)
            ).call()

            # Format the result
            # Try to get decimals for better formatting
            try:
                decimals = await target_contract.functions.decimals().call()
                formatted_balance = result / (10**decimals)
                return f"Your balance is {formatted_balance:.4f} tokens (raw: {result})"
            except:
                return f"Your balance is {result} (raw amount)"

        elif function_name == "totalSupply":
            result = await target_contract.functions.totalSupply().call()
            try:
                decimals = await target_contract.functions.decimals().call()
                formatted_supply = result / (10**decimals)
                return f"Total supply is {formatted_supply:.4f} tokens (raw: {result})"
            except:
                return f"Total supply is {result} (raw amount)"

        elif function_name == "decimals":
            result = await target_contract.functions.decimals().call()
            return f"This token uses {result} decimals"

        elif function_name == "name":
            result = await target_contract.functions.name().call()
            return f"Token name: {result}"

        elif function_name == "symbol":
            result = await target_contract.functions.symbol().call()
            return f"Token symbol: {result}"

        elif function_name == "owner":
            result = await target_contract.functions.owner().call()
            return f"Contract owner: {result}"

        elif function_name == "allowance":
            # This needs two addresses - for now just return a helpful message
            return "To check allowance, please specify: 'Check allowance for [spender address]'"

        else:
            # Generic handler for other view functions
            func = getattr(target_contract.functions, function_name)
            result = await func().call()
            return f"{function_name} returned: {result}"

    except Exception as e:
        logger.error(f"Error executing read query for {function_name}: {e}")
        error_msg = str(e)

        # Check if it's a contract deployment issue
        if "is contract deployed" in error_msg.lower() or "could not transact" in error_msg.lower():
            return f"⚠️ The target contract at {agent.target_address} is not deployed or not accessible on the current network. Please verify the contract address and ensure it's deployed on Somnia Testnet (Chain ID: 50312)."

        return f"Error querying {function_name}: {error_msg}"


@router.get("/history")
async def get_chat_history(agent_id: str, user_address: str, limit: int = 50):
    """
    Get chat history for an agent and user
    """
    try:
        with get_db_connection() as conn:
            messages = ChatMessageModel.get_history(conn, agent_id, user_address, limit)
            return messages
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
