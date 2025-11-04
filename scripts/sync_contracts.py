#!/usr/bin/env python3
"""
Sync compiled contract ABIs from the Solidity project into the backend.

- Reads from: ../../contracts/out/*/*.json (Foundry default output)
- Writes to:  contracts/abis/*.json (relative to backend directory)

Usage:
  poetry run python scripts/sync_contracts.py

This looks for the core contracts and copies their ABIs:
- AgentRegistry
- ContractMindHubV2
- HubAwareStaking
- TestToken (useful for local testing)
"""

from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Dict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_OUT = (BACKEND_ROOT.parent / "contracts" / "out").resolve()
DEST_DIR = (BACKEND_ROOT / "contracts" / "abis").resolve()

TARGETS = {
    "AgentRegistry": "AgentRegistry.sol/AgentRegistry.json",
    "ContractMindHubV2": "ContractMindHubV2.sol/ContractMindHubV2.json",
    "HubAwareStaking": "HubAwareStaking.sol/HubAwareStaking.json",
    "TestToken": "TestToken.sol/TestToken.json",
}


def ensure_dirs() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)


def extract_abi(source_file: Path) -> Dict:
    """Load JSON and return the full json. Supports both raw ABI and foundry standard artifact."""
    with source_file.open() as f:
        data = json.load(f)
    # Foundry artifact has keys {abi, bytecode, deployedBytecode, ...}
    # Some tools may export pure ABI array. The backend loader can handle both.
    return data


def copy_one(name: str, rel_path: str) -> None:
    src = CONTRACTS_OUT / rel_path
    if not src.exists():
        print(f"[WARN] Missing artifact for {name}: {src}")
        return
    data = extract_abi(src)
    dest = DEST_DIR / f"{name}.json"
    with dest.open("w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] {name} → {dest}")


def main() -> int:
    if not CONTRACTS_OUT.exists():
        print(f"[ERROR] Contracts out directory not found: {CONTRACTS_OUT}")
        print("Run `forge build` inside the contracts/ project first.")
        return 1
    ensure_dirs()
    for name, rel in TARGETS.items():
        copy_one(name, rel)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
