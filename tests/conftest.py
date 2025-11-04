"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from web3 import Web3

from app.main import app
from app.db.session import Base, get_db
from app.config import settings
from app.llm.base import BaseLLMClient, LLMMessage, LLMResponse, LLMProvider


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def client() -> TestClient:
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_web3() -> Web3:
    """Create mock Web3 instance"""
    return Web3(Web3.HTTPProvider("http://localhost:8545"))


@pytest.fixture
def sample_user_address() -> str:
    """Sample Ethereum address for testing"""
    return "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"


@pytest.fixture
def sample_agent_id() -> str:
    """Sample agent ID for testing"""
    return "0x" + "defi".encode().hex().ljust(64, "0")


@pytest.fixture
def sample_contract_address() -> str:
    """Sample contract address for testing"""
    return "0x1234567890123456789012345678901234567890"


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing"""

    def __init__(self, api_key: str = "test", model: str = "test-model"):
        super().__init__(api_key, model)
        self.call_count = 0
        self.last_messages = []

    async def generate(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> LLMResponse:
        """Mock generate method"""
        self.call_count += 1
        self.last_messages = messages

        return LLMResponse(
            content="This is a mock response",
            provider=LLMProvider.GEMINI,
            model=self.model,
            tokens_used=50,
            finish_reason="stop",
        )

    async def generate_json(
        self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 1000
    ) -> dict:
        """Mock generate_json method"""
        self.call_count += 1
        self.last_messages = messages

        # Return mock parsed intent
        return {
            "action": "stake",
            "protocol": "DeFi Staking",
            "amount": "1000",
            "token": "USDC",
            "params": {},
            "confidence": 0.95,
        }


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Create mock LLM client"""
    return MockLLMClient()


@pytest.fixture
def sample_parsed_intent() -> dict:
    """Sample parsed intent data"""
    return {
        "action": "stake",
        "protocol": "DeFi Staking",
        "amount": "1000",
        "token": "USDC",
        "params": {},
        "confidence": 0.95,
    }


@pytest.fixture
def sample_transaction_request() -> dict:
    """Sample transaction request data"""
    return {
        "agent_id": "0x" + "defi".encode().hex().ljust(64, "0"),
        "target_address": "0x1234567890123456789012345678901234567890",
        "function_name": "stake",
        "calldata": "0xa694fc3a" + "1000".encode().hex(),
        "execution_mode": "hub",
    }
