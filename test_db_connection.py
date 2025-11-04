import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Connection details from Supabase
USER = "postgres.pzfmtujykgkrkdddxxdi"
PASSWORD = os.getenv("password")  # Keep password in .env for security
HOST = "aws-1-eu-west-1.pooler.supabase.com"
PORT = "5432"  # Session pooler typically uses port 6543
DBNAME = "postgres"

print(f"Attempting connection with:")
print(f"USER: {USER}")
print(f"HOST: {HOST}")
print(f"PORT: {PORT}")
print(f"DBNAME: {DBNAME}")
print()

# Connect to the database
try:
    connection = psycopg2.connect(user=USER, password=PASSWORD, host=HOST, port=PORT, dbname=DBNAME)
    print("✅ Connection successful!")

    # Create a cursor to execute SQL queries
    cursor = connection.cursor()

    # Example query
    cursor.execute("SELECT NOW();")
    result = cursor.fetchone()
    print(f"Current Time: {result}")

    # Close the cursor and connection
    cursor.close()
    connection.close()
    print("Connection closed.")

except Exception as e:
    print(f"❌ Failed to connect: {e}")
