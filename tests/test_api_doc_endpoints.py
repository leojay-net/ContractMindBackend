"""
Tests for documentation-compatible endpoints and on-chain read flow
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.models.schemas import ParsedIntent, TransactionRequest, AgentResponse
from app.api.dependencies import (
    get_chat_service,
    get_intent_service,
    get_execution_service,
    get_blockchain_service,
)


class DummyChatService:
    async def parse_message(self, message: str, user_address: str):
        # Force a read intent: APY
        return ParsedIntent(
            action="apy",
            protocol="DeFi Staking",
            amount=None,
            token=None,
            params={},
            confidence=0.95,
        )


class DummyIntentService:
    async def process_intent(self, parsed_intent: ParsedIntent, user_address: str):
        # Return a minimal TransactionRequest (not used for read path beyond agent_id override)
        return TransactionRequest(
            agent_id="0x" + "aa" * 32,
            target_address="0x" + "bb" * 20,
            function_name="getCurrentAPY",
            function_selector="0x00000000",
            calldata="0x",
            execution_mode="hub",
        )


class DummyExecutionService:
    async def prepare_transaction(self, tx_request, user_address: str, intent=None):
        class PT:
            to = "0x" + "cc" * 20
            data = "0xdeadbeef"
            value = "0x0"
            gas = 123456
            gas_price = 1
            route = "hub"
            description = "Prepared Tx"
            preview = {"route": "hub"}

            def dict(self):
                return {
                    "to": self.to,
                    "data": self.data,
                    "value": self.value,
                    "gas": self.gas,
                    "gas_price": self.gas_price,
                    "route": self.route,
                    "description": self.description,
                    "preview": self.preview,
                }

        return PT()


class DummyBlockchainClient:
    def __init__(self):
        self.w3 = MagicMock()
        self.w3.eth.get_transaction_count = AsyncMock(return_value=0)

    async def initialize(self):
        return None

    def get_contract(self, name: str):
        if name == "ContractMindHubV2":
            # Return a dummy hub contract with functions.queryTarget().call returning encoded APY=1250
            class _F:
                def queryTarget(self, agent_id_bytes, target, call_data):
                    class _C:
                        async def call(self, *_args, **_kwargs):
                            # eth_abi encoding for uint256 value 1250
                            from eth_abi import encode

                            return encode(["uint256"], [1250])

                    return _C()

            class _Hub:
                functions = _F()

            return _Hub()
        elif name == "AgentRegistry":
            # Provide events.AgentRegistered().process_log and functions.getAgent().call
            class _Events:
                class _AgentRegistered:
                    def process_log(self, log):
                        return {"args": {"agentId": bytes.fromhex("11" * 32)}}

                def AgentRegistered(self):
                    return self._AgentRegistered()

            class _Functions:
                async def getAgent(self, agent_id_bytes):
                    # Return tuple matching contract struct (owner, target, name, config, active)
                    return (
                        "0x" + "22" * 20,
                        "0x" + "33" * 20,
                        "Test Agent",
                        "ipfs://QmTest",
                        True,
                    )

            class _Registry:
                events = _Events()

                class functions:  # noqa: N801 - mimic web3 style
                    @staticmethod
                    def getAgent(agent_id_bytes):
                        class _C:
                            async def call(self):
                                return (
                                    "0x" + "22" * 20,
                                    "0x" + "33" * 20,
                                    "Test Agent",
                                    "ipfs://QmTest",
                                    True,
                                )

                        return _C()

            return _Registry()
        raise ValueError("Unknown contract name")

    async def estimate_gas(self, tx):
        return 210000

    async def get_gas_price(self):
        return 1

    async def get_transaction_receipt(self, tx_hash: str):
        # Return a fake receipt with a single log; details are irrelevant since we mock process_log
        return {"logs": [{}], "status": 1, "blockNumber": 100, "gasUsed": 42000}


class DummyBlockchainService:
    def __init__(self):
        self.client = DummyBlockchainClient()

    async def get_agent(self, agent_id: str):
        return AgentResponse(
            id=agent_id,
            target_address="0x" + "44" * 20,
            owner="0x" + "55" * 20,
            name="DeFi Staking",
            config_ipfs="ipfs://QmConfig",
            active=True,
        )


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    # Ensure we start from a clean slate per test
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_chat_read_flow_via_hub_query_target():
    # Override dependencies
    app.dependency_overrides[get_chat_service] = lambda: DummyChatService()
    app.dependency_overrides[get_intent_service] = lambda: DummyIntentService()
    app.dependency_overrides[get_execution_service] = lambda: DummyExecutionService()
    app.dependency_overrides[get_blockchain_service] = lambda: DummyBlockchainService()

    client = TestClient(app)

    agent_id = "0x" + "aa" * 32
    payload = {"message": "What's the APY?", "userAddress": "0x" + "66" * 20}
    resp = client.post(f"/api/v1/chat/{agent_id}/message", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert body.get("requiresTransaction") is False
    assert body.get("data", {}).get("apy") == "1250"


def test_agents_register_prepare_transaction():
    svc = DummyBlockchainService()
    app.dependency_overrides[get_blockchain_service] = lambda: svc

    # Patch get_contract to include AgentRegistry with build_transaction
    hub = svc.client.get_contract("AgentRegistry")

    # Monkeypatch build_transaction path by wrapping a minimal contract interface
    class _RegWithBuild:
        class functions:
            @staticmethod
            def registerAgent(target, name, config):
                class _B:
                    def build_transaction(self, tx):
                        return {"data": "0xdeadbeef", **tx}

                return _B()

    svc.client.get_contract = lambda name: _RegWithBuild() if name == "AgentRegistry" else hub

    client = TestClient(app)
    payload = {
        "ownerAddress": "0x" + "77" * 20,
        "targetContract": "0x" + "88" * 20,
        "name": "My DeFi Agent",
        "configIPFS": "ipfs://QmTest",
    }
    resp = client.post("/api/v1/agents/register", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["requiresTransaction"] is True
    assert "transaction" in data
    assert data["transaction"]["to"].startswith("0x")
    assert data["transaction"]["data"].startswith("0x")


def test_agents_confirm_returns_agent_id():
    app.dependency_overrides[get_blockchain_service] = lambda: DummyBlockchainService()

    client = TestClient(app)
    resp = client.post("/api/v1/agents/confirm", json={"txHash": "0x" + "99" * 32})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert body.get("agentId", "").startswith("0x11")  # from our DummyBlockchainClient
