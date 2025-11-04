"""
Example database operations using psycopg2
"""

from app.db.session import get_db_connection
from app.db.models import TransactionModel
from datetime import datetime


def example_insert_transaction():
    """Example: Insert a new transaction"""
    print("\n📝 Example: Inserting a transaction")

    with get_db_connection() as conn:
        tx_data = {
            "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "user_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "agent_id": "0xagent123",
            "target_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
            "function_name": "stake",
            "calldata": "0xabcd...",
            "execution_mode": "hub",
            "status": "pending",
            "intent_action": "stake",
            "intent_protocol": "DeFi Staking",
            "intent_amount": "1000",
            "intent_confidence": 0.95,
        }

        tx_id = TransactionModel.insert(conn, tx_data)
        print(f"✅ Transaction inserted with ID: {tx_id}")
        return tx_id


def example_get_transaction(tx_hash: str):
    """Example: Get a transaction by hash"""
    print(f"\n🔍 Example: Getting transaction {tx_hash}")

    with get_db_connection() as conn:
        tx = TransactionModel.get_by_hash(conn, tx_hash)

        if tx:
            print(f"✅ Found transaction:")
            print(f"   ID: {tx['id']}")
            print(f"   User: {tx['user_address']}")
            print(f"   Status: {tx['status']}")
            print(f"   Action: {tx['intent_action']}")
            print(f"   Created: {tx['created_at']}")
        else:
            print("❌ Transaction not found")

        return tx


def example_update_transaction(tx_hash: str):
    """Example: Update transaction status"""
    print(f"\n✏️  Example: Updating transaction {tx_hash}")

    with get_db_connection() as conn:
        TransactionModel.update_status(
            conn, tx_hash=tx_hash, status="confirmed", block_number=12345678, gas_used=150000
        )
        print("✅ Transaction updated to confirmed")


def example_get_user_transactions(user_address: str):
    """Example: Get user's recent transactions"""
    print(f"\n👤 Example: Getting transactions for {user_address}")

    with get_db_connection() as conn:
        txs = TransactionModel.get_user_transactions(conn, user_address, limit=10)

        print(f"✅ Found {len(txs)} transactions:")
        for tx in txs:
            print(f"   - {tx['tx_hash'][:10]}... | {tx['status']} | {tx['intent_action']}")

        return txs


def example_custom_query():
    """Example: Custom SQL query"""
    print("\n🔧 Example: Custom query - Count transactions by status")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM transactions
            GROUP BY status
            ORDER BY count DESC
        """
        )

        results = cursor.fetchall()
        cursor.close()

        print("✅ Transaction counts by status:")
        for status, count in results:
            print(f"   - {status}: {count}")

        return results


def example_transaction_rollback():
    """Example: Transaction with rollback on error"""
    print("\n🔄 Example: Transaction with rollback")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            # Start transaction
            cursor.execute("BEGIN")

            # Do some operations
            cursor.execute(
                """
                INSERT INTO transactions (tx_hash, user_address, target_address, execution_mode, status)
                VALUES (%s, %s, %s, %s, %s)
            """,
                ("0xtest1", "0xuser1", "0xtarget1", "direct", "pending"),
            )

            cursor.execute(
                """
                INSERT INTO transactions (tx_hash, user_address, target_address, execution_mode, status)
                VALUES (%s, %s, %s, %s, %s)
            """,
                ("0xtest2", "0xuser1", "0xtarget1", "direct", "pending"),
            )

            # Commit transaction
            conn.commit()
            print("✅ Transaction committed successfully")

        except Exception as e:
            # Rollback on error
            conn.rollback()
            print(f"❌ Error occurred, rolling back: {e}")

        finally:
            cursor.close()


def run_examples():
    """Run all examples"""
    print("=" * 60)
    print("Database Operations Examples")
    print("=" * 60)

    try:
        # Insert a transaction
        tx_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        example_insert_transaction()

        # Get the transaction
        example_get_transaction(tx_hash)

        # Update the transaction
        example_update_transaction(tx_hash)

        # Get updated transaction
        example_get_transaction(tx_hash)

        # Get user transactions
        example_get_user_transactions("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")

        # Custom query
        example_custom_query()

        # Transaction with rollback
        example_transaction_rollback()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    from app.db.session import init_db_pool, close_db_pool

    # Initialize connection pool
    init_db_pool()

    try:
        run_examples()
    finally:
        # Cleanup
        close_db_pool()
