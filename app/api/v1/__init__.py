"""
API v1 router
"""

from fastapi import APIRouter

from app.api.v1 import agents, chat, transactions, analytics, websocket

router = APIRouter()

# Include sub-routers
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
