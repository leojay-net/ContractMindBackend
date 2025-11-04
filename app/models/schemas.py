"""
Pydantic schemas for API requests and responses
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# Agent Schemas
class AgentBase(BaseModel):
    """Base agent model"""

    target_address: str
    name: str
    config_ipfs: str


class AgentResponse(BaseModel):
    """Agent response model"""

    id: str
    target_address: str
    owner: str
    name: str
    config_ipfs: str
    active: bool
    created_at: Optional[datetime] = None


class AgentListResponse(BaseModel):
    """Agent list response"""

    agents: List[AgentResponse]
    total: int


# Chat Schemas
class ParsedIntent(BaseModel):
    """Parsed user intent from AI"""

    action: str  # stake, swap, lend, withdraw, etc.
    protocol: str  # Protocol/agent name
    amount: Optional[str] = None
    token: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class TransactionRequest(BaseModel):
    """Internal transaction request"""

    agent_id: str
    target_address: str
    function_name: str
    function_selector: str
    calldata: str
    execution_mode: str  # "hub" or "direct"


class PreparedTransaction(BaseModel):
    """Prepared transaction ready for signing"""

    to: str
    data: str
    value: str = "0x0"
    gas: int
    gas_price: Optional[int] = None
    route: str  # "hub" or "direct"
    description: str
    preview: Dict[str, Any] = Field(default_factory=dict)

    # Pydantic v2 configuration
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "to": "0x1234...",
                "data": "0xabcd...",
                "value": "0x0",
                "gas": 370000,
                "route": "hub",
                "description": "Stake 1000 SOMI tokens",
                "preview": {
                    "action": "Stake",
                    "amount": "1000 SOMI",
                    "protocol": "DeFi Staking",
                },
            }
        }
    )


# Transaction Schemas
class TransactionEvent(BaseModel):
    """Blockchain event"""

    name: str
    args: Dict[str, Any]
    log_index: int
    transaction_hash: str


class TransactionReceipt(BaseModel):
    """Transaction receipt"""

    tx_hash: str
    block_number: int
    gas_used: int
    status: int  # 1 = success, 0 = failed
    events: List[TransactionEvent] = Field(default_factory=list)


# Analytics Schemas
class UserStats(BaseModel):
    """User analytics"""

    user_address: str
    total_transactions: int
    total_gas_used: int
    success_rate: float
    favorite_agents: List[Dict[str, Any]] = Field(default_factory=list)
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list)


class AgentStats(BaseModel):
    """Agent analytics"""

    agent_id: str
    agent_name: str
    total_calls: int
    unique_users: int
    total_gas_used: int
    success_rate: float
    average_gas_per_call: int


class GlobalStats(BaseModel):
    """Global platform analytics"""

    total_transactions: int
    total_users: int
    total_agents: int
    total_gas_used: int
    success_rate: float
    transactions_last_24h: int
    top_agents: List[Dict[str, Any]] = Field(default_factory=list)
