"""
Database connection management using psycopg2
"""

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Generator
from loguru import logger

from app.config import settings


# Global connection pool
_connection_pool = None


def init_db_pool():
    """Initialize the database connection pool"""
    global _connection_pool

    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=settings.DATABASE_POOL_SIZE,
                user=settings.user,
                password=settings.password,
                host=settings.host,
                port=settings.port,
                dbname=settings.dbname,
                sslmode="prefer",  # Supabase requires SSL
                connect_timeout=10,
            )
            logger.info(
                f"✅ Database connection pool initialized: {settings.host}:{settings.port}/{settings.dbname}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to create database pool: {e}")
            raise


def close_db_pool():
    """Close all database connections"""
    global _connection_pool

    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_db_connection():
    """
    Get a database connection from the pool

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM table")
            results = cursor.fetchall()
    """
    if _connection_pool is None:
        init_db_pool()

    conn = None
    try:
        conn = _connection_pool.getconn()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            _connection_pool.putconn(conn)


def get_db() -> Generator:
    """
    FastAPI dependency for database connection

    Usage in FastAPI:
    @app.get("/example")
    def example(db=Depends(get_db)):
        cursor = db.cursor()
        ...
    """
    with get_db_connection() as conn:
        yield conn


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection"""
    await engine.dispose()
