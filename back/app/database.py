"""
Database connection and utilities with connection pooling.
"""
import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2 import pool
from dotenv import load_dotenv
from contextlib import contextmanager

import os
from pathlib import Path

# Load .env from parent directory (back/.env) if not found in current dir
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

DB_URL = os.getenv("DB_URL")

# ============= Connection Pool Setup =============
# 连接池配置:
# - minconn: 最小保持连接数 (2)
# - maxconn: 最大连接数 (20)
# - 使用 ThreadedConnectionPool 支持多线程

_connection_pool = None

def _init_pool():
    """Initialize the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=DB_URL,
                cursor_factory=DictCursor
            )
            print("[DB] Connection pool initialized (min=2, max=20)")
        except Exception as e:
            print(f"[DB] Failed to create connection pool: {e}")
            raise

def get_db_connection():
    """
    Get a database connection from the pool.
    
    返回的连接已包装，调用 close() 会将连接归还池子。
    """
    global _connection_pool
    if _connection_pool is None:
        _init_pool()
    
    try:
        conn = _connection_pool.getconn()
        # 包装连接，让 close() 归还到池子而非真正关闭
        return PooledConnection(conn, _connection_pool)
    except Exception as e:
        print(f"[DB] Error getting connection from pool: {e}")
        # Fallback to direct connection (不使用池子)
        return psycopg2.connect(DB_URL, cursor_factory=DictCursor)


class PooledConnection:
    """
    连接池包装器，让 close() 归还连接而非关闭。
    
    这样现有代码调用 conn.close() 时会正确归还连接到池子。
    """
    
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._closed = False
    
    def close(self):
        """归还连接到池子"""
        if not self._closed and self._pool:
            try:
                self._pool.putconn(self._conn)
                self._closed = True
            except Exception as e:
                print(f"[DB] Error returning connection: {e}")
                try:
                    self._conn.close()
                except:
                    pass
    
    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)
    
    def commit(self):
        return self._conn.commit()
    
    def rollback(self):
        return self._conn.rollback()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def release_db_connection(conn):
    """Release a connection back to the pool."""
    global _connection_pool
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            print(f"[DB] Error releasing connection: {e}")
            try:
                conn.close()
            except:
                pass

@contextmanager
def get_db():
    """
    Context manager for database connections.
    
    Usage:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ...")
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        release_db_connection(conn)

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
    release_db_connection(conn)
