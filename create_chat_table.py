"""
Create chat_messages table
"""

from app.db.session import get_db_connection
from app.db.models import CREATE_CHAT_MESSAGES_TABLE


def run_migration():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print("Creating chat_messages table...")
            cur.execute(CREATE_CHAT_MESSAGES_TABLE)
            conn.commit()
            print("✅ chat_messages table created successfully")


if __name__ == "__main__":
    run_migration()
