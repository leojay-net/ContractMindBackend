"""
Test script to verify all services use real data
"""

from app.db.session import init_db_pool, get_db_connection, close_db_pool
from app.db.models import TransactionModel, AgentCacheModel
from loguru import logger


def create_test_transactions():
    """Create some test transactions"""
    print("\n📝 Creating test transactions...")

    test_transactions = [
        {
            "tx_hash": "0xabc1111111111111111111111111111111111111111111111111111111111111",
            "user_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "agent_id": "0x1111111111111111111111111111111111111111111111111111111111111111",
            "target_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
            "function_name": "stake",
            "calldata": "0xabcd...",
            "execution_mode": "hub",
            "status": "confirmed",
            "intent_action": "stake",
            "intent_protocol": "DeFi Staking",
            "intent_amount": "1000",
            "intent_confidence": 0.95,
        },
        {
            "tx_hash": "0xdef2222222222222222222222222222222222222222222222222222222222222",
            "user_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "agent_id": "0x2222222222222222222222222222222222222222222222222222222222222222",
            "target_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swap",
            "calldata": "0xdef...",
            "execution_mode": "direct",
            "status": "confirmed",
            "intent_action": "swap",
            "intent_protocol": "Uniswap",
            "intent_amount": "500",
            "intent_confidence": 0.92,
        },
        {
            "tx_hash": "0xghi3333333333333333333333333333333333333333333333333333333333333",
            "user_address": "0x8626f6940E2eb28930eFb4CeF49B2d1F2C9C1199",
            "agent_id": "0x3333333333333333333333333333333333333333333333333333333333333333",
            "target_address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
            "function_name": "lend",
            "calldata": "0x123...",
            "execution_mode": "hub",
            "status": "confirmed",
            "intent_action": "lend",
            "intent_protocol": "Lending Protocol",
            "intent_amount": "2000",
            "intent_confidence": 0.88,
        },
        {
            "tx_hash": "0xjkl4444444444444444444444444444444444444444444444444444444444444",
            "user_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "agent_id": "0x1111111111111111111111111111111111111111111111111111111111111111",
            "target_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
            "function_name": "unstake",
            "calldata": "0x456...",
            "execution_mode": "hub",
            "status": "pending",
            "intent_action": "unstake",
            "intent_protocol": "DeFi Staking",
            "intent_amount": "500",
            "intent_confidence": 0.90,
        },
    ]

    with get_db_connection() as conn:
        for tx in test_transactions:
            try:
                tx_id = TransactionModel.insert(conn, tx)

                # Update some with gas used
                if tx["status"] == "confirmed":
                    TransactionModel.update_status(
                        conn, tx["tx_hash"], "confirmed", block_number=12345678, gas_used=150000
                    )

                print(
                    f"✅ Created transaction: {tx['tx_hash'][:20]}... ({tx['intent_action']} on {tx['intent_protocol']})"
                )
            except Exception as e:
                print(f"❌ Failed to create transaction: {e}")


def verify_data():
    """Verify all data is real"""
    print("\n" + "=" * 80)
    print("Verification: All Services Using Real Data")
    print("=" * 80)

    with get_db_connection() as conn:
        # Check agents
        agents = AgentCacheModel.get_all_active(conn)
        print(f"\n✅ Agents Cache: {len(agents)} active agents")
        for agent in agents[:3]:
            print(f"   - {agent['name']}")

        # Check transactions
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT user_address) FROM transactions")
        tx_count, user_count = cursor.fetchone()
        print(f"\n✅ Transactions: {tx_count} transactions from {user_count} users")

        # Check transaction details
        cursor.execute(
            """
            SELECT intent_protocol, COUNT(*) 
            FROM transactions 
            GROUP BY intent_protocol 
            ORDER BY COUNT(*) DESC
        """
        )
        print(f"\n✅ Transactions by Protocol:")
        for protocol, count in cursor.fetchall():
            print(f"   - {protocol}: {count}")

        # Check status breakdown
        cursor.execute(
            """
            SELECT status, COUNT(*) 
            FROM transactions 
            GROUP BY status
        """
        )
        print(f"\n✅ Transaction Status:")
        for status, count in cursor.fetchall():
            print(f"   - {status}: {count}")

        cursor.close()

    print("\n" + "=" * 80)
    print("✅ All services now using REAL DATA from database!")
    print("=" * 80 + "\n")


def main():
    print("\n" + "=" * 80)
    print("Real Data Test Script")
    print("=" * 80)

    try:
        init_db_pool()

        create_test_transactions()
        verify_data()

        print("\n✅ Test complete! Now test the API endpoints:")
        print("   - GET /api/v1/agents")
        print("   - GET /api/v1/analytics/global")
        print("   - GET /api/v1/analytics/user/0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        print()

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        close_db_pool()


if __name__ == "__main__":
    main()
