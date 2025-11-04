"""
Script to update an agent's target contract address
"""

from app.db.session import get_db_connection
from app.config import settings


def update_agent_address(agent_id: str, new_address: str):
    """Update agent's target contract address"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if agent exists
            cur.execute(
                "SELECT agent_id, name, target_address FROM agents_cache WHERE agent_id = %s",
                (agent_id,),
            )
            agent = cur.fetchone()

            if not agent:
                print(f"❌ Agent '{agent_id}' not found")
                return

            print(f"✅ Found agent: {agent[1]}")
            print(f"   Old target: {agent[2]}")
            print(f"   New target: {new_address}")

            # Update the target address
            cur.execute(
                """
                UPDATE agents_cache 
                SET target_address = %s, updated_at = NOW()
                WHERE agent_id = %s
                """,
                (new_address, agent_id),
            )
            conn.commit()

            print(f"✅ Updated agent '{agent_id}' target address")

            # Verify update
            cur.execute("SELECT target_address FROM agents_cache WHERE agent_id = %s", (agent_id,))
            updated = cur.fetchone()
            print(f"✅ Verified: {updated[0]}")


if __name__ == "__main__":
    # Update erc20-2 agent to new TestToken address
    update_agent_address(
        agent_id="erc20-2", new_address="0x0dDF803Cfb6a1ABf0c84F7fED62746A3Ba6365e3"
    )
