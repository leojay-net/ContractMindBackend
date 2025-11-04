"""
Database models and table creation SQL
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from loguru import logger


# SQL for creating tables
CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    tx_hash VARCHAR(66) UNIQUE NOT NULL,
    user_address VARCHAR(42) NOT NULL,
    agent_id VARCHAR(66),
    target_address VARCHAR(42) NOT NULL,
    
    -- Transaction details
    function_name VARCHAR(255),
    calldata TEXT,
    execution_mode VARCHAR(20) NOT NULL,
    
    -- Status
    status VARCHAR(20) NOT NULL,
    block_number BIGINT,
    
    -- Gas and fees
    gas_used BIGINT,
    gas_price BIGINT,
    protocol_fee BIGINT DEFAULT 0,
    
    -- Intent data
    intent_action VARCHAR(50),
    intent_protocol VARCHAR(100),
    intent_amount VARCHAR(100),
    intent_confidence FLOAT,
    
    -- Events
    events JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    confirmed_at TIMESTAMP,
    
    -- Error info
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_tx_hash ON transactions(tx_hash);
CREATE INDEX IF NOT EXISTS idx_user_address ON transactions(user_address);
CREATE INDEX IF NOT EXISTS idx_agent_id ON transactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_block_number ON transactions(block_number);
CREATE INDEX IF NOT EXISTS idx_created_at ON transactions(created_at);
"""

CREATE_AGENT_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_metrics (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(66) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    
    -- Daily metrics
    date TIMESTAMP NOT NULL,
    total_calls INTEGER DEFAULT 0,
    successful_calls INTEGER DEFAULT 0,
    failed_calls INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    
    -- Gas metrics
    total_gas_used BIGINT DEFAULT 0,
    average_gas BIGINT DEFAULT 0,
    
    -- Revenue
    total_fees BIGINT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_agent_id ON agent_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_date ON agent_metrics(date);
"""

CREATE_USER_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS user_metrics (
    id SERIAL PRIMARY KEY,
    user_address VARCHAR(42) NOT NULL,
    
    -- Daily metrics
    date TIMESTAMP NOT NULL,
    total_transactions INTEGER DEFAULT 0,
    successful_transactions INTEGER DEFAULT 0,
    failed_transactions INTEGER DEFAULT 0,
    
    -- Gas metrics
    total_gas_used BIGINT DEFAULT 0,
    total_fees_paid BIGINT DEFAULT 0,
    
    -- Activity
    unique_agents_used INTEGER DEFAULT 0,
    most_used_agent VARCHAR(66),
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_metrics_address ON user_metrics(user_address);
CREATE INDEX IF NOT EXISTS idx_user_metrics_date ON user_metrics(date);
"""

CREATE_AGENTS_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS agents_cache (
    agent_id VARCHAR(66) PRIMARY KEY,
    target_address VARCHAR(42) NOT NULL,
    owner VARCHAR(42) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config_ipfs TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_name ON agents_cache(LOWER(name));
CREATE INDEX IF NOT EXISTS idx_agents_target ON agents_cache(target_address);
CREATE INDEX IF NOT EXISTS idx_agents_active ON agents_cache(active);
"""


def init_database(conn):
    """
    Initialize database tables

    Args:
        conn: psycopg2 connection
    """
    try:
        cursor = conn.cursor()

        # Create tables
        cursor.execute(CREATE_TRANSACTIONS_TABLE)
        cursor.execute(CREATE_AGENT_METRICS_TABLE)
        cursor.execute(CREATE_USER_METRICS_TABLE)
        cursor.execute(CREATE_AGENTS_CACHE_TABLE)

        conn.commit()
        cursor.close()

        logger.info("✅ Database tables initialized successfully")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to initialize database: {e}")
        raise


class TransactionModel:
    """Helper class for transaction operations"""

    @staticmethod
    def insert(conn, tx_data: Dict[str, Any]) -> int:
        """Insert a new transaction"""
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO transactions (
                tx_hash, user_address, agent_id, target_address,
                function_name, calldata, execution_mode, status,
                intent_action, intent_protocol, intent_amount, intent_confidence
            ) VALUES (
                %(tx_hash)s, %(user_address)s, %(agent_id)s, %(target_address)s,
                %(function_name)s, %(calldata)s, %(execution_mode)s, %(status)s,
                %(intent_action)s, %(intent_protocol)s, %(intent_amount)s, %(intent_confidence)s
            ) RETURNING id
        """,
            tx_data,
        )

        tx_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()

        return tx_id

    @staticmethod
    def update_status(
        conn,
        tx_hash: str,
        status: str,
        block_number: Optional[int] = None,
        gas_used: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Update transaction status"""
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE transactions 
            SET status = %s, 
                block_number = %s, 
                gas_used = %s,
                error_message = %s,
                confirmed_at = CASE WHEN %s = 'confirmed' THEN NOW() ELSE confirmed_at END
            WHERE tx_hash = %s
        """,
            (status, block_number, gas_used, error_message, status, tx_hash),
        )

        conn.commit()
        cursor.close()

    @staticmethod
    def get_by_hash(conn, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get transaction by hash"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, tx_hash, user_address, agent_id, target_address,
                   function_name, calldata, execution_mode, status, block_number,
                   gas_used, gas_price, protocol_fee,
                   intent_action, intent_protocol, intent_amount, intent_confidence,
                   events, created_at, confirmed_at, error_message
            FROM transactions
            WHERE tx_hash = %s
        """,
            (tx_hash,),
        )

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            "id": row[0],
            "tx_hash": row[1],
            "user_address": row[2],
            "agent_id": row[3],
            "target_address": row[4],
            "function_name": row[5],
            "calldata": row[6],
            "execution_mode": row[7],
            "status": row[8],
            "block_number": row[9],
            "gas_used": row[10],
            "gas_price": row[11],
            "protocol_fee": row[12],
            "intent_action": row[13],
            "intent_protocol": row[14],
            "intent_amount": row[15],
            "intent_confidence": row[16],
            "events": row[17],
            "created_at": row[18],
            "confirmed_at": row[19],
            "error_message": row[20],
        }

    @staticmethod
    def get_user_transactions(conn, user_address: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's recent transactions"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, tx_hash, user_address, agent_id, target_address,
                   function_name, execution_mode, status, block_number,
                   intent_action, intent_protocol, created_at
            FROM transactions
            WHERE user_address = %s
            ORDER BY created_at DESC
            LIMIT %s
        """,
            (user_address, limit),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "id": row[0],
                "tx_hash": row[1],
                "user_address": row[2],
                "agent_id": row[3],
                "target_address": row[4],
                "function_name": row[5],
                "execution_mode": row[6],
                "status": row[7],
                "block_number": row[8],
                "intent_action": row[9],
                "intent_protocol": row[10],
                "created_at": row[11],
            }
            for row in rows
        ]

    @staticmethod
    def get_transactions(
        conn,
        agent_id: Optional[str] = None,
        user_address: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get transactions with optional filters
        Returns tuple of (transactions, total_count)
        """
        cursor = conn.cursor()

        # Build WHERE clause dynamically
        where_clauses = []
        params = []

        if agent_id:
            where_clauses.append("agent_id = %s")
            params.append(agent_id)

        if user_address:
            where_clauses.append("user_address = %s")
            params.append(user_address)

        if status:
            where_clauses.append("status = %s")
            params.append(status)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Get total count
        count_query = f"SELECT COUNT(*) FROM transactions {where_sql}"
        cursor.execute(count_query, tuple(params))
        total = cursor.fetchone()[0]

        # Get transactions
        query = f"""
            SELECT id, tx_hash, user_address, agent_id, target_address,
                   function_name, execution_mode, status, block_number,
                   gas_used, intent_action, intent_protocol, created_at, confirmed_at
            FROM transactions
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cursor.execute(query, tuple(params))

        rows = cursor.fetchall()
        cursor.close()

        transactions = [
            {
                "id": row[0],
                "tx_hash": row[1],
                "user_address": row[2],
                "agent_id": row[3],
                "target_address": row[4],
                "function_name": row[5],
                "execution_mode": row[6],
                "status": row[7],
                "block_number": row[8],
                "gas_used": row[9],
                "intent_action": row[10],
                "intent_protocol": row[11],
                "created_at": row[12],
                "confirmed_at": row[13],
            }
            for row in rows
        ]

        return transactions, total


class AgentCacheModel:
    """Helper class for agents_cache operations"""

    @staticmethod
    def upsert(conn, agent_data: Dict[str, Any]):
        """Insert or update an agent in cache"""
        cursor = conn.cursor()

        # Convert abi to JSON string if it's a list/dict
        import json

        if "abi" in agent_data and isinstance(agent_data["abi"], (list, dict)):
            agent_data = agent_data.copy()
            agent_data["abi"] = json.dumps(agent_data["abi"])

        cursor.execute(
            """
            INSERT INTO agents_cache (
                agent_id, target_address, owner, name, description, config_ipfs, active, abi
            ) VALUES (
                %(agent_id)s, %(target_address)s, %(owner)s, %(name)s, 
                %(description)s, %(config_ipfs)s, %(active)s, %(abi)s
            )
            ON CONFLICT (agent_id) DO UPDATE SET
                target_address = EXCLUDED.target_address,
                owner = EXCLUDED.owner,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                config_ipfs = EXCLUDED.config_ipfs,
                active = EXCLUDED.active,
                abi = EXCLUDED.abi,
                updated_at = NOW()
        """,
            agent_data,
        )

        conn.commit()
        cursor.close()

    @staticmethod
    def get_by_id(conn, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT agent_id, target_address, owner, name, description, 
                   config_ipfs, active, created_at, updated_at, abi
            FROM agents_cache
            WHERE agent_id = %s
        """,
            (agent_id,),
        )

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            "agent_id": row[0],
            "target_address": row[1],
            "owner": row[2],
            "name": row[3],
            "description": row[4],
            "config_ipfs": row[5],
            "active": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "abi": row[9],  # JSONB field, already parsed as dict/list
        }

    @staticmethod
    def get_by_name(conn, name: str) -> Optional[Dict[str, Any]]:
        """Get agent by name (case-insensitive)"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT agent_id, target_address, owner, name, description, 
                   config_ipfs, active, created_at, updated_at
            FROM agents_cache
            WHERE LOWER(name) = LOWER(%s) AND active = true
        """,
            (name,),
        )

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            "agent_id": row[0],
            "target_address": row[1],
            "owner": row[2],
            "name": row[3],
            "description": row[4],
            "config_ipfs": row[5],
            "active": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }

    @staticmethod
    def get_all_active(conn, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all active agents"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT agent_id, target_address, owner, name, description, 
                   config_ipfs, active, created_at, updated_at, abi
            FROM agents_cache
            WHERE active = true
            ORDER BY created_at DESC
            LIMIT %s
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "agent_id": row[0],
                "target_address": row[1],
                "owner": row[2],
                "name": row[3],
                "description": row[4],
                "config_ipfs": row[5],
                "active": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "abi": row[9],  # JSONB field
            }
            for row in rows
        ]

    @staticmethod
    def get_count(conn) -> int:
        """Get total count of active agents"""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM agents_cache WHERE active = true")
        count = cursor.fetchone()[0]
        cursor.close()
        return count


class AgentFunctionAuthorizationModel:
    """Helper class for agent function authorization operations"""

    @staticmethod
    def authorize_functions(conn, agent_id: str, function_names: List[str]):
        """Authorize functions for an agent"""
        cursor = conn.cursor()

        for function_name in function_names:
            cursor.execute(
                """
                INSERT INTO agent_function_authorizations (agent_id, function_name, authorized)
                VALUES (%s, %s, true)
                ON CONFLICT (agent_id, function_name) 
                DO UPDATE SET authorized = true, updated_at = NOW()
                """,
                (agent_id, function_name),
            )

        conn.commit()
        cursor.close()

    @staticmethod
    def revoke_functions(conn, agent_id: str, function_names: List[str]):
        """Revoke functions for an agent"""
        cursor = conn.cursor()

        for function_name in function_names:
            cursor.execute(
                """
                INSERT INTO agent_function_authorizations (agent_id, function_name, authorized)
                VALUES (%s, %s, false)
                ON CONFLICT (agent_id, function_name) 
                DO UPDATE SET authorized = false, updated_at = NOW()
                """,
                (agent_id, function_name),
            )

        conn.commit()
        cursor.close()

    @staticmethod
    def get_authorizations(conn, agent_id: str) -> Dict[str, bool]:
        """Get function authorization status for an agent"""
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT function_name, authorized
            FROM agent_function_authorizations
            WHERE agent_id = %s
            """,
            (agent_id,),
        )

        rows = cursor.fetchall()
        cursor.close()

        return {row[0]: row[1] for row in rows}
