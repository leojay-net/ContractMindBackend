"""
Optional on-chain smoke test for Somnia testnet.

Run only when RUN_ONCHAIN_TESTS is set, e.g.:

  RUN_ONCHAIN_TESTS=1 poetry run pytest -m onchain -q
"""

from __future__ import annotations

import os
import pytest
from web3 import Web3

from app.config import settings


pytestmark = pytest.mark.onchain


def _truthy(env: str | None) -> bool:
    return (env or "").lower() in {"1", "true", "yes", "on"}


@pytest.mark.skipif(not _truthy(os.getenv("RUN_ONCHAIN_TESTS")), reason="RUN_ONCHAIN_TESTS not set")
def test_somnia_contracts_have_code():
    w3 = Web3(Web3.HTTPProvider(settings.SOMNIA_RPC_URL))
    assert w3.is_connected(), "Cannot connect to Somnia RPC"

    assert w3.eth.chain_id == settings.CHAIN_ID, "Chain ID mismatch"

    hub = Web3.to_checksum_address(settings.CONTRACT_MIND_HUB_ADDRESS)
    reg = Web3.to_checksum_address(settings.AGENT_REGISTRY_ADDRESS)

    hub_code = w3.eth.get_code(hub)
    reg_code = w3.eth.get_code(reg)

    assert len(hub_code) > 2, "Hub address has no code"
    assert len(reg_code) > 2, "Registry address has no code"
