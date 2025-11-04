"""
WebSocket endpoints for real-time chat
"""

from typing import Annotated, Dict, Set, List
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from loguru import logger

from app.api.dependencies import get_chat_service, get_intent_service, get_execution_service
from app.services.chat_service import ChatService
from app.services.intent_service import IntentService
from app.services.execution_service import ExecutionService

router = APIRouter()


# Models for documentation
class WebSocketInfo(BaseModel):
    """WebSocket connection information"""

    endpoint: str
    description: str
    protocol: str
    example_url: str


class WebSocketMessage(BaseModel):
    """WebSocket message format"""

    type: str
    description: str
    example: dict


class WebSocketDocumentation(BaseModel):
    """Complete WebSocket API documentation"""

    connection: WebSocketInfo
    client_messages: List[WebSocketMessage]
    server_messages: List[WebSocketMessage]


# Connection manager
class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        # user_address -> Set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_address: str):
        """Accept new connection"""
        await websocket.accept()

        if user_address not in self.active_connections:
            self.active_connections[user_address] = set()

        self.active_connections[user_address].add(websocket)
        logger.info(f"WebSocket connected: {user_address}")

    def disconnect(self, websocket: WebSocket, user_address: str):
        """Remove connection"""
        if user_address in self.active_connections:
            self.active_connections[user_address].discard(websocket)

            if not self.active_connections[user_address]:
                del self.active_connections[user_address]

        logger.info(f"WebSocket disconnected: {user_address}")

    async def send_personal_message(self, message: dict, user_address: str):
        """Send message to specific user's connections"""
        if user_address in self.active_connections:
            for connection in self.active_connections[user_address]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")


manager = ConnectionManager()


@router.get("/docs", response_model=WebSocketDocumentation, summary="WebSocket API Documentation")
async def websocket_documentation():
    """
    Get complete documentation for WebSocket endpoints

    This endpoint provides information about:
    - How to connect to the WebSocket
    - Available message types from client
    - Expected message types from server
    - Example messages
    """
    return WebSocketDocumentation(
        connection=WebSocketInfo(
            endpoint="/ws/chat/{user_address}",
            description="Real-time chat endpoint for AI-powered blockchain interactions",
            protocol="WebSocket (ws:// or wss://)",
            example_url="ws://localhost:8000/api/v1/ws/chat/0x1234567890abcdef1234567890abcdef12345678",
        ),
        client_messages=[
            WebSocketMessage(
                type="chat",
                description="Send a chat message to be processed by AI",
                example={"type": "chat", "message": "Stake 1000 tokens in the DeFi protocol"},
            ),
            WebSocketMessage(
                type="transaction_sent",
                description="Notify server that user has signed and sent a transaction",
                example={"type": "transaction_sent", "tx_hash": "0xabcdef..."},
            ),
            WebSocketMessage(
                type="ping",
                description="Heartbeat to keep connection alive",
                example={"type": "ping"},
            ),
        ],
        server_messages=[
            WebSocketMessage(
                type="thinking",
                description="Server is processing the request",
                example={"type": "thinking", "message": "Processing your request..."},
            ),
            WebSocketMessage(
                type="intent_parsed",
                description="AI has parsed the user's intent",
                example={
                    "type": "intent_parsed",
                    "intent": {
                        "action": "stake",
                        "protocol": "DeFi Staking",
                        "amount": "1000",
                        "confidence": 0.95,
                    },
                },
            ),
            WebSocketMessage(
                type="transaction_ready",
                description="Transaction is prepared and ready to sign",
                example={
                    "type": "transaction_ready",
                    "transaction": {
                        "to": "0x...",
                        "data": "0x...",
                        "value": "0",
                        "description": "Stake 1000 tokens",
                    },
                    "message": "Transaction prepared: Stake 1000 tokens",
                },
            ),
            WebSocketMessage(
                type="transaction_monitoring",
                description="Server is monitoring the submitted transaction",
                example={
                    "type": "transaction_monitoring",
                    "tx_hash": "0xabcdef...",
                    "message": "Monitoring transaction...",
                },
            ),
            WebSocketMessage(
                type="transaction_confirmed",
                description="Transaction has been confirmed on-chain",
                example={
                    "type": "transaction_confirmed",
                    "tx_hash": "0xabcdef...",
                    "block_number": 12345,
                    "message": "Transaction confirmed!",
                },
            ),
            WebSocketMessage(
                type="error",
                description="An error occurred during processing",
                example={"type": "error", "message": "Error: Unable to parse intent"},
            ),
            WebSocketMessage(
                type="pong", description="Response to ping heartbeat", example={"type": "pong"}
            ),
        ],
    )


@router.get("/status", summary="WebSocket Connection Status")
async def websocket_status():
    """
    Get current WebSocket connection statistics

    Returns:
    - Number of active connections
    - Number of connected users
    """
    total_connections = sum(len(connections) for connections in manager.active_connections.values())
    return {
        "active_users": len(manager.active_connections),
        "total_connections": total_connections,
        "max_connections_per_user": 3,
        "users": list(manager.active_connections.keys()) if manager.active_connections else [],
    }


@router.websocket("/chat/{user_address}")
async def websocket_chat(
    websocket: WebSocket,
    user_address: str,
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,
    intent_service: Annotated[IntentService, Depends(get_intent_service)] = None,
    execution_service: Annotated[ExecutionService, Depends(get_execution_service)] = None,
):
    """
    WebSocket endpoint for real-time chat

    Flow:
    1. User sends message: "Stake 1000 tokens"
    2. Backend parses intent with AI
    3. Backend prepares transaction
    4. Send transaction to user for signing
    5. Monitor transaction after user signs
    """
    await manager.connect(websocket, user_address)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            logger.info(f"Received message from {user_address}: {message_data}")

            message_type = message_data.get("type")

            if message_type == "chat":
                # Process chat message
                user_message = message_data.get("message")

                # Send thinking indicator
                await websocket.send_json(
                    {"type": "thinking", "message": "Processing your request..."}
                )

                try:
                    # Parse intent using AI
                    parsed_intent = await chat_service.parse_message(user_message, user_address)

                    # Send parsed intent
                    await websocket.send_json({"type": "intent_parsed", "intent": parsed_intent})

                    # Process intent and prepare transaction
                    tx_request = await intent_service.process_intent(parsed_intent, user_address)

                    # Prepare transaction
                    prepared_tx = await execution_service.prepare_transaction(
                        tx_request, user_address
                    )

                    # Send transaction to user
                    await websocket.send_json(
                        {
                            "type": "transaction_ready",
                            "transaction": prepared_tx.dict(),
                            "message": f"Transaction prepared: {prepared_tx.description}",
                        }
                    )

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send_json({"type": "error", "message": f"Error: {str(e)}"})

            elif message_type == "transaction_sent":
                # User has signed and sent transaction
                tx_hash = message_data.get("tx_hash")

                await websocket.send_json(
                    {
                        "type": "transaction_monitoring",
                        "tx_hash": tx_hash,
                        "message": "Monitoring transaction...",
                    }
                )

                # Monitor transaction (this will be handled by event listeners)
                # Event listeners will send updates via manager.send_personal_message

            elif message_type == "ping":
                # Heartbeat
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_address)
        logger.info(f"Client {user_address} disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_address)


# Export manager for use in event listeners
__all__ = ["router", "manager"]
