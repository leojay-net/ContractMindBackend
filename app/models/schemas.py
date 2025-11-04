"""
Pydantic schemas for API requests and responses
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# Function Schemas
class FunctionInput(BaseModel):
    """Function input parameter"""

    name: str
    type: str


class FunctionOutput(BaseModel):
    """Function output parameter"""

    name: str
    type: str


class AgentFunction(BaseModel):
    """Agent function from ABI"""

    name: str
    inputs: List[FunctionInput] = []
    outputs: List[FunctionOutput] = []
    stateMutability: str = Field(serialization_alias="stateMutability")
    authorized: bool = False  # Default to false, can be updated later


# Agent Schemas
class AgentBase(BaseModel):
    """Base agent model"""

    target_address: str
    name: str
    config_ipfs: str


class AgentResponse(BaseModel):
    """Agent response model"""

    id: str
    target_address: str = Field(serialization_alias="targetContract")
    owner: str
    name: str
    config_ipfs: str = Field(serialization_alias="configIPFS")
    active: bool
    created_at: Optional[datetime] = Field(None, serialization_alias="createdAt")
    functions: Optional[List[AgentFunction]] = None
    abi: Optional[List[dict]] = None  # Full ABI for encoding transactions
    analytics: Optional["AgentStats"] = None  # Analytics data

    model_config = ConfigDict(populate_by_name=True, by_alias=True)


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


class TransactionHistoryItem(BaseModel):
    """Transaction history item"""

    id: int
    tx_hash: str
    user_address: str
    agent_id: Optional[str] = None
    target_address: str
    function_name: Optional[str] = None
    execution_mode: str
    status: str
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    intent_action: Optional[str] = None
    intent_protocol: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None


class TransactionHistoryResponse(BaseModel):
    """Transaction history response"""

    transactions: List[TransactionHistoryItem]
    total: int
    limit: int
    offset: int


# Analytics Schemas
class UserStats(BaseModel):
    """User analytics"""

    model_config = ConfigDict(populate_by_name=True, alias_generator=None, by_alias=True)

    user_address: str = Field(alias="userAddress")
    total_transactions: int = Field(alias="totalTransactions")
    total_gas_used: int = Field(alias="totalGasUsed")
    success_rate: float = Field(alias="successRate")
    favorite_agents: List[Dict[str, Any]] = Field(default_factory=list, alias="favoriteAgents")
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list, alias="recentActivity")


class AgentStats(BaseModel):
    """Agent analytics"""

    model_config = ConfigDict(populate_by_name=True, alias_generator=None, by_alias=True)

    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    total_calls: int = Field(alias="totalCalls")
    unique_users: int = Field(alias="uniqueUsers")
    total_gas_used: int = Field(alias="totalGasUsed")
    success_rate: float = Field(alias="successRate")
    average_gas_per_call: int = Field(alias="averageGasPerCall")


class GlobalStats(BaseModel):
    """Global platform analytics"""

    model_config = ConfigDict(populate_by_name=True, alias_generator=None, by_alias=True)

    total_transactions: int = Field(alias="totalTransactions")
    total_users: int = Field(alias="totalUsers")
    total_agents: int = Field(alias="totalAgents")
    total_gas_used: int = Field(alias="totalGasUsed")
    success_rate: float = Field(alias="successRate")
    transactions_last_24h: int = Field(alias="transactionsLast24h")
    top_agents: List[Dict[str, Any]] = Field(default_factory=list, alias="topAgents")
