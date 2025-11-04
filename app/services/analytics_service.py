"""
Analytics Service for querying transaction analytics
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

from app.models.schemas import UserStats, AgentStats, GlobalStats
from app.db.session import get_db_connection
from app.db.models import AgentCacheModel


class AnalyticsService:
    """Service for analytics and statistics"""

    def __init__(self):
        pass

    async def get_user_stats(self, user_address: str, start_date: datetime = None) -> UserStats:
        """Get user analytics from real database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get user transaction stats
                query = """
                    SELECT 
                        COUNT(*) as total_tx,
                        SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as successful_tx,
                        COALESCE(SUM(gas_used), 0) as total_gas,
                        AVG(CASE WHEN status = 'confirmed' THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM transactions
                    WHERE user_address = %s
                """
                params = [user_address]

                if start_date:
                    query += " AND created_at >= %s"
                    params.append(start_date)

                cursor.execute(query, params)
                row = cursor.fetchone()

                total_tx = row[0] if row[0] else 0
                successful_tx = row[1] if row[1] else 0
                total_gas = row[2] if row[2] else 0
                success_rate = float(row[3]) if row[3] else 0.0

                # Get favorite agents
                cursor.execute(
                    """
                    SELECT intent_protocol, COUNT(*) as count
                    FROM transactions
                    WHERE user_address = %s AND intent_protocol IS NOT NULL
                    GROUP BY intent_protocol
                    ORDER BY count DESC
                    LIMIT 5
                """,
                    (user_address,),
                )

                favorite_agents = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

                # Get recent activity
                cursor.execute(
                    """
                    SELECT intent_action, intent_protocol, created_at, status
                    FROM transactions
                    WHERE user_address = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """,
                    (user_address,),
                )

                recent_activity = [
                    {
                        "action": row[0] or "unknown",
                        "protocol": row[1] or "unknown",
                        "timestamp": row[2].isoformat() if row[2] else "",
                        "success": row[3] == "confirmed",
                    }
                    for row in cursor.fetchall()
                ]

                cursor.close()

                return UserStats(
                    user_address=user_address,
                    total_transactions=total_tx,
                    total_gas_used=total_gas,
                    success_rate=success_rate,
                    favorite_agents=favorite_agents,
                    recent_activity=recent_activity,
                )

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            raise

    async def get_agent_stats(self, agent_id: str, start_date: datetime = None) -> AgentStats:
        """Get agent analytics from real database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get agent info
                agent_data = AgentCacheModel.get_by_id(conn, agent_id)
                agent_name = agent_data["name"] if agent_data else "Unknown Agent"

                # Get agent transaction stats
                query = """
                    SELECT 
                        COUNT(*) as total_calls,
                        COUNT(DISTINCT user_address) as unique_users,
                        COALESCE(SUM(gas_used), 0) as total_gas,
                        AVG(CASE WHEN status = 'confirmed' THEN 1.0 ELSE 0.0 END) as success_rate,
                        AVG(gas_used) as avg_gas
                    FROM transactions
                    WHERE agent_id = %s
                """
                params = [agent_id]

                if start_date:
                    query += " AND created_at >= %s"
                    params.append(start_date)

                cursor.execute(query, params)
                row = cursor.fetchone()

                total_calls = row[0] if row[0] else 0
                unique_users = row[1] if row[1] else 0
                total_gas = row[2] if row[2] else 0
                success_rate = float(row[3]) if row[3] else 0.0
                avg_gas = int(row[4]) if row[4] else 0

                cursor.close()

                return AgentStats(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    total_calls=total_calls,
                    unique_users=unique_users,
                    total_gas_used=total_gas,
                    success_rate=success_rate,
                    average_gas_per_call=avg_gas,
                )

        except Exception as e:
            logger.error(f"Error getting agent stats: {e}")
            raise

    async def get_global_stats(self, start_date: datetime = None) -> GlobalStats:
        """Get global platform analytics from real database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get global transaction stats
                query = """
                    SELECT 
                        COUNT(*) as total_tx,
                        COUNT(DISTINCT user_address) as total_users,
                        COALESCE(SUM(gas_used), 0) as total_gas,
                        AVG(CASE WHEN status = 'confirmed' THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM transactions
                """
                params = []

                if start_date:
                    query += " WHERE created_at >= %s"
                    params.append(start_date)

                cursor.execute(query, params)
                row = cursor.fetchone()

                total_tx = row[0] if row[0] else 0
                total_users = row[1] if row[1] else 0
                total_gas = row[2] if row[2] else 0
                success_rate = float(row[3]) if row[3] else 0.0

                # Get total active agents
                total_agents = AgentCacheModel.get_count(conn)

                # Get last 24h transactions
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM transactions
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """
                )
                tx_last_24h = cursor.fetchone()[0] or 0

                # Get top agents
                cursor.execute(
                    """
                    SELECT intent_protocol, COUNT(*) as count
                    FROM transactions
                    WHERE intent_protocol IS NOT NULL
                    GROUP BY intent_protocol
                    ORDER BY count DESC
                    LIMIT 10
                """
                )

                top_agents = [{"name": row[0], "calls": row[1]} for row in cursor.fetchall()]

                cursor.close()

                return GlobalStats(
                    total_transactions=total_tx,
                    total_users=total_users,
                    total_agents=total_agents,
                    total_gas_used=total_gas,
                    success_rate=success_rate,
                    transactions_last_24h=tx_last_24h,
                    top_agents=top_agents,
                )

        except Exception as e:
            logger.error(f"Error getting global stats: {e}")
            raise
