"""
Database connection and utilities.
"""
import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

import os
from pathlib import Path

# Load .env from parent directory (back/.env) if not found in current dir
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

DB_URL = os.getenv("DB_URL")

def get_db_connection():
    """Get a database connection."""
    conn = psycopg2.connect(DB_URL, cursor_factory=DictCursor)
    # No WAL or busy_timeout needed for Postgres
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create sessions table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_titles (
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create credits table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id TEXT PRIMARY KEY,
            credits INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
