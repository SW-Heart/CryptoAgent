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
                minconn=5,
                maxconn=50,
                dsn=DB_URL,
                cursor_factory=DictCursor
            )
            print("[DB] Connection pool initialized (min=5, max=50)")
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
        return PooledConnection(conn, _connection_pool)
    except Exception as e:
        print(f"[DB] CRITICAL: Connection pool exhausted or failed: {e}")
        raise # 不要使用静默的 psycopg2.connect，防止连接泄露


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
            # If it's the wrapper, call its close() which safely returns the raw connection
            if hasattr(conn, 'close'):
                conn.close()
            else:
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
    
    # Create notification_configs table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_configs (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            config JSONB NOT NULL DEFAULT '{}',
            enabled_events JSONB NOT NULL DEFAULT '["TRADE_OPEN", "TRADE_CLOSE", "SL_TRIGGERED", "SYSTEM_ALERT", "DAILY_REPORT"]',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, channel)
        )
    """)
    
    # Create news_intelligence table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_intelligence (
            id SERIAL PRIMARY KEY,
            news_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            source TEXT NOT NULL,
            published_at TIMESTAMP NOT NULL,
            impact_score INTEGER DEFAULT 0,
            impact_reason TEXT,
            alert_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create kline_cache table (historical kline local cache for backtesting)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_cache (
            id SERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            open_time BIGINT NOT NULL,
            open DOUBLE PRECISION NOT NULL,
            high DOUBLE PRECISION NOT NULL,
            low DOUBLE PRECISION NOT NULL,
            close DOUBLE PRECISION NOT NULL,
            volume DOUBLE PRECISION NOT NULL,
            close_time BIGINT NOT NULL,
            quote_volume DOUBLE PRECISION NOT NULL,
            trades INTEGER DEFAULT 0,
            UNIQUE(symbol, interval, open_time)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_kline_cache_lookup
        ON kline_cache(symbol, interval, open_time)
    """)
    
    # Create backtest_jobs table (persist backtest tasks and results)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backtest_jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            initial_capital DOUBLE PRECISION DEFAULT 10000,
            leverage INTEGER DEFAULT 10,
            strategy_type TEXT DEFAULT '',
            strategy_params JSONB DEFAULT '{}',
            progress INTEGER DEFAULT 0,
            total_rounds INTEGER DEFAULT 0,
            result JSONB,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    # Create price_alerts table (Agent 自主设置的价格警报)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            trader_instance_id INTEGER,
            symbol TEXT NOT NULL,
            target_price DOUBLE PRECISION NOT NULL,
            direction TEXT NOT NULL,
            price_source TEXT DEFAULT 'binance',
            reason TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            triggered_at TIMESTAMP,
            cooldown_until TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_alerts_active
        ON price_alerts(status, user_id)
    """)
    
    # Create agent_execution_memory table (Agent 跨心跳分析记忆)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_execution_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            trader_instance_id INTEGER NOT NULL,
            last_analysis_summary JSONB DEFAULT '{}',
            active_trade_plan TEXT,
            observations JSONB DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, trader_instance_id)
        )
    """)
    
    conn.commit()
    release_db_connection(conn)
