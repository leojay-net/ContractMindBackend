#!/usr/bin/env python3
"""
Test script for transaction history endpoint
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"


def test_transaction_endpoint():
    """Test the transaction history endpoint"""

    print("🧪 Testing Transaction History Endpoint")
    print("=" * 60)

    # Test 1: Get all transactions
    print("\n1️⃣  Test: GET /api/v1/transactions")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/transactions")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success! Found {data.get('total', 0)} total transactions")
            print(f"   ✅ Returned {len(data.get('transactions', []))} transactions")
            print(f"   ✅ Limit: {data.get('limit')}, Offset: {data.get('offset')}")
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Get with limit
    print("\n2️⃣  Test: GET /api/v1/transactions?limit=5")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/transactions?limit=5")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(
                f"   ✅ Success! Returned {len(data.get('transactions', []))} transactions (max 5)"
            )
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: Get with filters
    print("\n3️⃣  Test: GET /api/v1/transactions?status=confirmed")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/transactions?status=confirmed")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success! Found {data.get('total', 0)} confirmed transactions")
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 4: Pagination
    print("\n4️⃣  Test: GET /api/v1/transactions?limit=10&offset=0")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/transactions?limit=10&offset=0")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success! Page 1 - {len(data.get('transactions', []))} transactions")

            # Display sample transaction if available
            if data.get("transactions"):
                tx = data["transactions"][0]
                print(f"\n   📄 Sample Transaction:")
                print(f"      Hash: {tx.get('tx_hash')}")
                print(f"      Status: {tx.get('status')}")
                print(f"      Function: {tx.get('function_name')}")
                print(f"      Created: {tx.get('created_at')}")
        else:
            print(f"   ❌ Failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 5: OpenAPI docs
    print("\n5️⃣  Test: Check OpenAPI Documentation")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/openapi.json")
        if response.status_code == 200:
            openapi = response.json()
            paths = openapi.get("paths", {})

            # Check if our endpoint is documented
            if "/api/v1/transactions" in paths:
                endpoint = paths["/api/v1/transactions"]
                print(f"   ✅ Endpoint documented in OpenAPI spec")

                # Check GET method
                if "get" in endpoint:
                    get_method = endpoint["get"]
                    print(f"   ✅ GET method documented")
                    print(f"      Summary: {get_method.get('summary', 'N/A')}")

                    # Check parameters
                    params = get_method.get("parameters", [])
                    if params:
                        print(f"      Parameters: {len(params)} defined")
                        for param in params:
                            print(
                                f"        • {param.get('name')}: {param.get('description', 'N/A')}"
                            )
                else:
                    print(f"   ⚠️  GET method not documented")
            else:
                print(f"   ⚠️  Endpoint not found in OpenAPI spec")
                print(f"   Available endpoints: {list(paths.keys())[:5]}...")
        else:
            print(f"   ❌ Failed to fetch OpenAPI spec: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print("\n" + "=" * 60)
    print("✅ Testing complete! Visit http://localhost:8000/docs to see the endpoint.")


if __name__ == "__main__":
    test_transaction_endpoint()
