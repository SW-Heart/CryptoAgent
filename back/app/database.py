"""
Database connection and utilities.
"""
import sqlite3
from .config import DB_PATH

def get_db_connection():
    """Get a database connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提高并发性能
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
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
