#!/usr/bin/env python3
"""
Lightweight on-chain smoke check for Somnia testnet.

Verifies connectivity and that deployed contract addresses have code.

Usage:
  poetry run python backend/scripts/smoke_onchain.py
"""

from __future__ import annotations

import sys
from web3 import Web3

from app.config import settings


def main() -> int:
    rpc = settings.SOMNIA_RPC_URL
    hub = Web3.to_checksum_address(settings.CONTRACT_MIND_HUB_ADDRESS)
    registry = Web3.to_checksum_address(settings.AGENT_REGISTRY_ADDRESS)

    w3 = Web3(Web3.HTTPProvider(rpc))

    try:
        chain_id = w3.eth.chain_id
    except Exception as e:
        print(f"[ERROR] Failed to connect to RPC: {rpc}\n{e}")
        return 1

    print(f"Connected to chain_id={chain_id} at {rpc}")
    if chain_id != settings.CHAIN_ID:
        print(f"[WARN] Chain ID mismatch: expected {settings.CHAIN_ID}, got {chain_id}")

    hub_code = w3.eth.get_code(hub)
    reg_code = w3.eth.get_code(registry)

    print(f"Hub address: {hub}")
    print(f"  Code size: {len(hub_code)} bytes")
    print(f"Registry address: {registry}")
    print(f"  Code size: {len(reg_code)} bytes")

    if len(hub_code) <= 2 or len(reg_code) <= 2:
        print("[FAIL] One or more addresses appear to have no code deployed.")
        return 2

    print("[OK] On-chain contracts detected and RPC responsive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
