"""
Test database connection and setup
"""

from app.config import settings
from app.db.session import init_db_pool, get_db_connection, close_db_pool
from app.db.models import init_database
from loguru import logger


def test_connection():
    """Test basic database connection"""
    print("\n" + "=" * 60)
    print("Testing Database Connection")
    print("=" * 60)

    print(f"\n📊 Database Configuration:")
    print(f"   Host: {settings.host}")
    print(f"   Port: {settings.port}")
    print(f"   Database: {settings.dbname}")
    print(f"   User: {settings.user}")
    print()

    try:
        # Initialize connection pool
        print("1️⃣  Initializing connection pool...")
        init_db_pool()
        print("   ✅ Connection pool created")

        # Test connection
        print("\n2️⃣  Testing database connection...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT NOW(), version();")
            timestamp, version = cursor.fetchone()
            cursor.close()

            print(f"   ✅ Connection successful!")
            print(f"   📅 Server time: {timestamp}")
            print(f"   🗄️  PostgreSQL version: {version}")

        # Initialize tables
        print("\n3️⃣  Creating/updating database tables...")
        with get_db_connection() as conn:
            init_database(conn)
        print("   ✅ Tables created successfully")

        # List tables
        print("\n4️⃣  Listing database tables...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """
            )
            tables = cursor.fetchall()
            cursor.close()

            if tables:
                print("   📋 Found tables:")
                for table in tables:
                    print(f"      - {table[0]}")
            else:
                print("   ⚠️  No tables found")

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Database test failed")
        return False

    finally:
        # Cleanup
        close_db_pool()
        print("🔒 Connection pool closed")


if __name__ == "__main__":
    test_connection()
