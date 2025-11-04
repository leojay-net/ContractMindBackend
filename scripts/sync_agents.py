"""
Sync agents from blockchain to database cache

This script:
1. Connects to blockchain and database
2. Seeds initial demo agents for testing
3. Can be extended to listen for AgentRegistered events
"""

from app.config import settings
from app.db.session import init_db_pool, get_db_connection, close_db_pool
from app.db.models import AgentCacheModel
from loguru import logger


def seed_demo_agents():
    """Seed demo agents for testing"""

    demo_agents = [
        {
            "agent_id": "0x" + "1" * 64,
            "target_address": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "name": "DeFi Staking",
            "description": "Stake tokens to earn rewards. Supports stake, unstake, and claim operations.",
            "config_ipfs": "ipfs://Qm...",
            "active": True,
        },
        {
            "agent_id": "0x" + "2" * 64,
            "target_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 Router
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "name": "Uniswap",
            "description": "Decentralized exchange for token swaps. Swap any ERC20 tokens.",
            "config_ipfs": "ipfs://Qm...",
            "active": True,
        },
        {
            "agent_id": "0x" + "3" * 64,
            "target_address": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "name": "Lending Protocol",
            "description": "Lend and borrow tokens. Supports lend, borrow, repay, and withdraw operations.",
            "config_ipfs": "ipfs://Qm...",
            "active": True,
        },
        {
            "agent_id": "0x" + "4" * 64,
            "target_address": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "name": "Yield Farming",
            "description": "Earn rewards by providing liquidity. Supports deposit and harvest operations.",
            "config_ipfs": "ipfs://Qm...",
            "active": True,
        },
        {
            "agent_id": "0x" + "5" * 64,
            "target_address": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "name": "NFT Marketplace",
            "description": "Buy, sell, and trade NFTs. Supports list, buy, and cancel operations.",
            "config_ipfs": "ipfs://Qm...",
            "active": True,
        },
    ]

    logger.info(f"Seeding {len(demo_agents)} demo agents...")

    with get_db_connection() as conn:
        for agent in demo_agents:
            try:
                AgentCacheModel.upsert(conn, agent)
                logger.info(f"✅ Seeded agent: {agent['name']}")
            except Exception as e:
                logger.error(f"❌ Failed to seed {agent['name']}: {e}")

    logger.info("✅ Demo agents seeded successfully!")


def sync_from_blockchain():
    """
    Sync agents from blockchain by listening to events

    This would:
    1. Query past AgentRegistered events
    2. Insert/update agents in cache
    3. Set up event listener for new registrations
    """
    # TODO: Implement blockchain event listening
    # For now, we use seed_demo_agents()
    logger.warning("Blockchain sync not yet implemented, using demo agents")
    seed_demo_agents()


def list_cached_agents():
    """List all cached agents"""
    with get_db_connection() as conn:
        agents = AgentCacheModel.get_all_active(conn)
        count = AgentCacheModel.get_count(conn)

        print(f"\n📋 Found {count} active agents in cache:")
        print("=" * 80)

        for agent in agents:
            print(f"\n🤖 {agent['name']}")
            print(f"   ID: {agent['agent_id'][:20]}...")
            print(f"   Target: {agent['target_address']}")
            print(f"   Description: {agent['description']}")
            print(f"   Owner: {agent['owner']}")
            print(f"   Active: {agent['active']}")

        print("\n" + "=" * 80)


def main():
    """Main sync script"""
    print("\n" + "=" * 80)
    print("Agent Sync Script")
    print("=" * 80 + "\n")

    try:
        # Initialize database
        init_db_pool()

        # Sync agents
        sync_from_blockchain()

        # List cached agents
        list_cached_agents()

        print("\n✅ Sync complete!\n")

    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        close_db_pool()


if __name__ == "__main__":
    main()
