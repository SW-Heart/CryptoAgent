"""
Strategy API Router - 主入口

路由已按功能拆分至子模块:
- data_routes: 钱包/持仓/订单/交易历史等数据查询
- config_routes: 日志/调度器/策略配置/Beta/LLM

此文件保留: DB 初始化 + 子路由注册
"""
from fastapi import APIRouter
from app.database import get_db_connection
import os

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

STRATEGY_ADMIN_USER_ID = "ee20fa53-5ac2-44bc-9237-41b308e291d8"


def init_strategy_tables():
    """Initialize strategy tables"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Virtual wallet
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_wallet (
                id SERIAL PRIMARY KEY,
                user_id TEXT UNIQUE,
                initial_balance DOUBLE PRECISION DEFAULT 10000,
                current_balance DOUBLE PRECISION DEFAULT 10000,
                total_pnl DOUBLE PRECISION DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                win_trades INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                symbol TEXT NOT NULL,

            direction TEXT NOT NULL,
            leverage INTEGER DEFAULT 10,
            margin REAL NOT NULL,
            notional_value REAL NOT NULL,
            entry_price REAL NOT NULL,
            quantity REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            current_price REAL,
            unrealized_pnl REAL DEFAULT 0,
            status TEXT DEFAULT 'OPEN',
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            close_price REAL,
            realized_pnl REAL
        )
    """)
    
    with conn.cursor() as cursor:
        # Orders history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                position_id INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                direction TEXT,
                quantity DOUBLE PRECISION,
                margin DOUBLE PRECISION,
                entry_price DOUBLE PRECISION,
                stop_loss DOUBLE PRECISION,
                take_profit DOUBLE PRECISION,
                realized_pnl DOUBLE PRECISION,
                tp_level INTEGER,
                close_reason TEXT,
                fee DOUBLE PRECISION DEFAULT 0,
                status TEXT DEFAULT 'FILLED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Strategy logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_logs (
                id SERIAL PRIMARY KEY,
                round_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbols TEXT,
                market_analysis TEXT,
                position_check TEXT,
                strategy_decision TEXT,
                actions_taken TEXT,
                raw_response TEXT
            )
        """)
        
        # Binance sync state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS binance_sync_state (
                user_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                last_trade_id BIGINT DEFAULT 0,
                total_pnl DOUBLE PRECISION DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                win_trades INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, symbol)
            )
        """)
        conn.commit()
    
    # Initialize wallet if not exists
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO virtual_wallet (id, user_id, initial_balance, current_balance)
            VALUES (1, %s, 10000, 10000)
            ON CONFLICT (id) DO NOTHING
        """, (STRATEGY_ADMIN_USER_ID,))
        conn.commit()
    conn.close()
    
    # Run migrations
    migrate_tables()

def migrate_tables():
    """Migrate tables to add missing columns"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            print("[Strategy] Checking migrations...")
            
            # Virtual wallet user_id
            try:
                cursor.execute("ALTER TABLE virtual_wallet ADD COLUMN IF NOT EXISTS user_id TEXT UNIQUE")
            except Exception as e:
                print(f"[Strategy] virtual_wallet migration note: {e}")
            
            # Fix data: ensure ID 1 has user_id
            cursor.execute("UPDATE virtual_wallet SET user_id = %s WHERE id = 1 AND user_id IS NULL", (STRATEGY_ADMIN_USER_ID,))
            
            # Positions user_id
            try:
                cursor.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS user_id TEXT")
            except Exception as e:
                 print(f"[Strategy] positions migration note: {e}")

            # Fix data: populate missing user_ids
            # strategy_logs extensions
            try:
                cursor.execute("ALTER TABLE strategy_logs ADD COLUMN IF NOT EXISTS user_id TEXT")
                cursor.execute("ALTER TABLE strategy_logs ADD COLUMN IF NOT EXISTS trader_instance_id TEXT")
            except Exception as e:
                print(f"[Strategy] strategy_logs migration note: {e}")
                
        conn.commit()
    except Exception as e:
        print(f"[Strategy] Migration error: {e}")
    finally:
        conn.close()


# ============= Register sub-routers =============
from app.routers.data_routes import router as data_router
from app.routers.config_routes import router as config_router

router.include_router(data_router)
router.include_router(config_router)
