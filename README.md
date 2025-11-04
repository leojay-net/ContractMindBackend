# ContractMind Backend

Python-based backend for ContractMind AI-powered blockchain infrastructure.

## 🎯 Technology Stack

- **FastAPI** - High-performance async web framework
- **FastMCP** - Model Context Protocol for AI agent integration
- **Web3.py** - Blockchain interaction with Somnia
- **PostgreSQL** - Analytics and agent configuration storage
- **Redis** - Session management and caching
- **Anthropic Claude** - AI intent parsing
- **WebSockets** - Real-time chat communication

## 🏗️ Architecture

```
Frontend (React) 
    ↓ WebSocket
Backend (FastAPI + FastMCP)
    ├─► AI Service (Claude) → Parse intent
    ├─► Intent Service → Detect contract type
    ├─► Execution Service → Prepare transaction
    └─► Blockchain Service → Web3 interaction
        ↓
Somnia Blockchain
    ├─► AgentRegistry
    ├─► ContractMindHubV2
    └─► Protocol Contracts
```

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Poetry (Python package manager)
- Access to Somnia RPC
- Anthropic API key

## 🚀 Quick Start

### 1. Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Install Dependencies

```bash
cd backend
poetry install
```

### 3. Setup Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```env
# Blockchain
SOMNIA_RPC_URL=https://dream-rpc.somnia.network
AGENT_REGISTRY_ADDRESS=0x...  # From deployment
CONTRACT_MIND_HUB_ADDRESS=0x...  # From deployment

# AI
ANTHROPIC_API_KEY=your-api-key-here

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/contractmind

# Redis
REDIS_URL=redis://localhost:6379/0
```

### 4. Setup Database

```bash
# Start PostgreSQL and Redis (using Docker)
docker-compose up -d postgres redis

# Run migrations
poetry run alembic upgrade head
```

### 5. Sync Contract ABIs

```bash
# Copy ABIs from contracts deployment
poetry run python scripts/sync_contracts.py
```

### 6. Run Development Server

```bash
poetry run uvicorn app.main:app --reload
```

Server will start at: http://localhost:8000

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/v1/          # API endpoints
│   │   ├── agents.py    # Agent management
│   │   ├── chat.py      # Chat (REST)
│   │   ├── transactions.py
│   │   ├── analytics.py
│   │   └── websocket.py # WebSocket chat
│   │
│   ├── services/        # Business logic
│   │   ├── ai_service.py
│   │   ├── intent_service.py
│   │   ├── execution_service.py
│   │   ├── blockchain_service.py
│   │   └── analytics_service.py
│   │
│   ├── blockchain/      # Web3 layer
│   │   ├── client.py
│   │   ├── contracts/
│   │   └── events.py
│   │
│   ├── mcp/            # FastMCP integration
│   │   ├── server.py
│   │   ├── tools.py
│   │   └── prompts.py
│   │
│   ├── models/         # Data models
│   │   ├── database.py
│   │   └── schemas.py
│   │
│   └── db/            # Database
│       └── session.py
│
├── tests/             # Tests
├── scripts/           # Utility scripts
└── contracts/         # Contract ABIs
```

## 🔄 Data Flow

### Hub-Aware Contract Flow

```
1. User WebSocket: "Stake 1000 tokens"
   ↓
2. AI Service (Claude): Parse → {action: "stake", amount: 1000}
   ↓
3. Intent Service: 
   - Query AgentRegistry
   - Detect: hub-aware contract
   - Map: stake → stake(uint256)
   ↓
4. Execution Service:
   - Prepare: hub.executeOnTarget(...)
   - Estimate gas: ~370k
   ↓
5. WebSocket: Send transaction to frontend
   ↓
6. User signs & broadcasts
   ↓
7. Event Listener: 
   - Monitor transaction
   - Parse events
   - Store analytics
   ↓
8. WebSocket: Send success notification
```

### Regular Contract Flow

```
1. User: "Swap 100 SOMI for USDC"
   ↓
2. AI Service: Parse → {action: "swap", ...}
   ↓
3. Intent Service:
   - Detect: regular contract (Uniswap)
   - Map: swap → swapExactTokensForTokens
   ↓
4. Execution Service:
   - Prepare: DIRECT to Uniswap
   - Estimate gas: ~150k
   ↓
5. WebSocket: Send direct transaction
   ↓
6. User signs & broadcasts (bypasses hub)
   ↓
7. Analytics: Track off-chain
```

## 🧪 API Endpoints

### WebSocket

```
WS /api/v1/ws/chat/{user_address}
```

Message types:
```json
// Send
{
  "type": "chat",
  "message": "Stake 1000 tokens"
}

// Receive
{
  "type": "transaction_ready",
  "transaction": {
    "to": "0x...",
    "data": "0x...",
    "gas": 370000,
    "description": "Stake 1000 SOMI"
  }
}
```

### REST API

```
GET  /api/v1/agents              # List agents
GET  /api/v1/agents/{id}         # Get agent
POST /api/v1/chat/message        # Process message (REST)
POST /api/v1/transactions/status # Get tx status
POST /api/v1/transactions/validate
GET  /api/v1/analytics/user/{address}
GET  /api/v1/analytics/agent/{id}
GET  /api/v1/analytics/global
```

## 🔧 Configuration

### Key Settings

```python
# app/config.py
class Settings:
   # Blockchain
   SOMNIA_RPC_URL: str
   CHAIN_ID: int = 50312
    
   # Contracts
   AGENT_REGISTRY_ADDRESS: str
   CONTRACT_MIND_HUB_ADDRESS: str
    
   # AI
   ANTHROPIC_API_KEY: str
    
   # Database
   DATABASE_URL: str
    
   # Redis
   REDIS_URL: str
    
   # Rate Limiting
   RATE_LIMIT_PER_MINUTE: int = 60
```

## 🧠 AI Integration (FastMCP)

FastMCP provides structured AI agent context:

```python
from fastmcp import FastMCP

mcp = FastMCP("ContractMind")

@mcp.tool()
async def parse_intent(message: str) -> dict:
    """Parse user intent using Claude"""
    # AI parsing logic
    pass

@mcp.tool()
async def validate_transaction(...) -> bool:
    """Validate transaction authorization"""
    # Blockchain validation
    pass

@mcp.resource("contract://agents")
async def list_agents() -> str:
    """Get available agents for AI context"""
    pass
```

## 📊 Database Models

```python
# app/models/database.py

class Transaction(Base):
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String, unique=True)
    user_address = Column(String, index=True)
    agent_id = Column(String, index=True)
    target_contract = Column(String)
    function_selector = Column(String)
    success = Column(Boolean)
    gas_used = Column(Integer)
    created_at = Column(DateTime)

class AgentAnalytics(Base):
    id = Column(Integer, primary_key=True)
    agent_id = Column(String, index=True)
    total_calls = Column(Integer)
    total_gas_used = Column(BigInteger)
    success_rate = Column(Float)
    updated_at = Column(DateTime)
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app tests/

# Run specific test
poetry run pytest tests/test_services/test_intent_service.py
```

### On-chain (Somnia) checks

We keep unit tests fast and offline by default. For a quick live-network sanity check:

```bash
# Smoke script: verifies RPC connectivity and that deployed addresses have bytecode
poetry run python scripts/smoke_onchain.py

# Optional pytest on-chain test (opt-in)
RUN_ONCHAIN_TESTS=1 poetry run pytest -m onchain -q
```

Current Somnia Testnet deployments:

- AgentRegistry: `0x318FFd8Fc398a3639Faa837307Ffdd0b9E1017c9`
- ContractMindHubV2: `0x8244777FAe8F2f4AE50875405AFb34E10164C027`
- Chain ID: `50312`
- RPC: `https://dream-rpc.somnia.network`

## 🐳 Docker Deployment

```bash
# Build image
docker build -t contractmind-backend .

# Run with docker-compose
docker-compose up -d
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: contractmind
      POSTGRES_USER: contractmind
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## 📈 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Metrics

```bash
# View logs
poetry run python -m app.utils.logger

# Database connection pool stats
curl http://localhost:8000/api/v1/analytics/global
```

## 🔐 Security

- WebSocket connection validation
- Rate limiting (Redis-based)
- Transaction validation before execution
- Signature verification (future)
- API key authentication (future)

## 🚧 Development

### Add New Endpoint

1. Create route in `app/api/v1/`
2. Add service logic in `app/services/`
3. Update schema in `app/models/schemas.py`
4. Add tests in `tests/`

### Add New Contract

1. Copy ABI to `contracts/abis/`
2. Create interface in `app/blockchain/contracts/`
3. Register in blockchain service
4. Update AI prompts for intent parsing

## 📝 Environment Variables

See `.env.example` for all configuration options.

Critical variables:
- `SOMNIA_RPC_URL` - Blockchain RPC endpoint
- `AGENT_REGISTRY_ADDRESS` - Deployed registry
- `CONTRACT_MIND_HUB_ADDRESS` - Deployed hub
- `ANTHROPIC_API_KEY` - Claude API key
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests
4. Run linting: `poetry run black . && poetry run isort .`
5. Submit pull request

## 📄 License

MIT License

## 🔗 Links

- Frontend: `../frontend`
- Contracts: `../contracts`
- Documentation: `../docs`
- API Docs: http://localhost:8000/docs
