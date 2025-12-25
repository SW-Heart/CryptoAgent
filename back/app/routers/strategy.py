"""
Strategy API router.
Handles virtual trading, positions, and strategy logs.
"""
from fastapi import APIRouter, HTTPException
import sqlite3
import os
from datetime import datetime

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

DB_PATH = "tmp/test.db"

# Binance API base URL (configurable via environment variable)
BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_strategy_tables():
    """Initialize strategy tables"""
    conn = get_db_connection()
    
    # Virtual wallet - system-wide (single wallet for demo)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS virtual_wallet (
            id INTEGER PRIMARY KEY,
            initial_balance REAL DEFAULT 10000,
            current_balance REAL DEFAULT 10000,
            total_pnl REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            win_trades INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Positions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    # Orders history
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            margin REAL,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            fee REAL DEFAULT 0,
            status TEXT DEFAULT 'FILLED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Strategy logs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    # Initialize wallet if not exists
    conn.execute("""
        INSERT OR IGNORE INTO virtual_wallet (id, initial_balance, current_balance)
        VALUES (1, 10000, 10000)
    """)
    
    conn.commit()
    conn.close()

# GET endpoints for UI

@router.get("/wallet")
async def get_wallet():
    """Get virtual wallet status with real-time equity"""
    import requests
    
    try:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM virtual_wallet WHERE id = 1").fetchone()
        
        # Get open positions for equity calculation
        positions = conn.execute("SELECT * FROM positions WHERE status = 'OPEN'").fetchall()
        conn.close()
        
        if not row:
            return {"error": "Wallet not initialized"}
        
        # Calculate real-time unrealized PnL
        total_unrealized_pnl = 0
        total_margin_in_use = 0
        
        for pos in positions:
            total_margin_in_use += pos["margin"]
            try:
                resp = requests.get(
                    f"{BINANCE_API_BASE}/api/v3/ticker/price?symbol={pos['symbol']}USDT",

                    timeout=3
                )
                if resp.status_code == 200:
                    current_price = float(resp.json().get("price", 0))
                    if pos["direction"] == "LONG":
                        total_unrealized_pnl += pos["quantity"] * (current_price - pos["entry_price"])
                    else:
                        total_unrealized_pnl += pos["quantity"] * (pos["entry_price"] - current_price)
            except:
                total_unrealized_pnl += pos["unrealized_pnl"] or 0
        
        # Equity = current_balance + margin_in_use + unrealized_pnl
        equity = row["current_balance"] + total_margin_in_use + total_unrealized_pnl
        
        return {
            "initial_balance": row["initial_balance"],
            "current_balance": row["current_balance"],
            "margin_in_use": round(total_margin_in_use, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "equity": round(equity, 2),
            "total_pnl": row["total_pnl"],
            "total_trades": row["total_trades"],
            "win_trades": row["win_trades"],
            "win_rate": round(row["win_trades"] / row["total_trades"] * 100, 1) if row["total_trades"] > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(status: str = "OPEN"):
    """Get positions (OPEN / CLOSED / ALL) with real-time PnL for open positions"""
    import requests
    
    try:
        conn = get_db_connection()
        
        if status == "ALL":
            rows = conn.execute("SELECT * FROM positions ORDER BY opened_at DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status = ? ORDER BY opened_at DESC",
                (status,)
            ).fetchall()
        
        conn.close()
        
        positions = []
        for row in rows:
            # Safely get leverage and notional_value (may not exist in old records)
            leverage = row["leverage"] if "leverage" in row.keys() else 10
            notional_value = row["notional_value"] if "notional_value" in row.keys() else row["margin"] * leverage
            
            pos_data = {
                "id": row["id"],
                "symbol": row["symbol"],
                "direction": row["direction"],
                "leverage": leverage,
                "margin": row["margin"],
                "notional_value": notional_value,
                "entry_price": row["entry_price"],
                "quantity": row["quantity"],
                "stop_loss": row["stop_loss"],
                "take_profit": row["take_profit"],
                "current_price": row["current_price"],
                "unrealized_pnl": row["unrealized_pnl"],
                "status": row["status"],
                "opened_at": row["opened_at"],
                "closed_at": row["closed_at"],
                "close_price": row["close_price"],
                "realized_pnl": row["realized_pnl"]
            }
            
            # For OPEN positions, get real-time price and calculate PnL
            if row["status"] == "OPEN":
                try:
                    resp = requests.get(
                        f"{BINANCE_API_BASE}/api/v3/ticker/price?symbol={row['symbol']}USDT",

                        timeout=3
                    )
                    if resp.status_code == 200:
                        current_price = float(resp.json().get("price", 0))
                        pos_data["current_price"] = current_price
                        
                        # Calculate unrealized PnL
                        if row["direction"] == "LONG":
                            unrealized_pnl = row["quantity"] * (current_price - row["entry_price"])
                        else:
                            unrealized_pnl = row["quantity"] * (row["entry_price"] - current_price)
                        
                        pos_data["unrealized_pnl"] = round(unrealized_pnl, 2)
                except:
                    pass  # Keep database values if API fails
            
            positions.append(pos_data)
        
        return {"positions": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_orders(limit: int = 20):
    """Get order history"""
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        
        orders = [dict(row) for row in rows]
        return {"orders": orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_strategy_logs(limit: int = 10):
    """Get strategy logs"""
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT * FROM strategy_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        
        logs = [dict(row) for row in rows]
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/equity-curve")
async def get_equity_curve():
    """Get equity curve data from closed positions"""
    try:
        conn = get_db_connection()
        
        # Get initial balance
        wallet = conn.execute("SELECT initial_balance FROM virtual_wallet WHERE id = 1").fetchone()
        initial = wallet["initial_balance"] if wallet else 10000
        
        # Get all closed positions ordered by close time
        rows = conn.execute("""
            SELECT closed_at, realized_pnl 
            FROM positions 
            WHERE status IN ('CLOSED', 'LIQUIDATED') AND closed_at IS NOT NULL
            ORDER BY closed_at ASC
        """).fetchall()
        conn.close()
        
        # Build equity curve
        curve = [{"time": None, "equity": initial}]
        running_equity = initial
        
        for row in rows:
            running_equity += row["realized_pnl"] or 0
            curve.append({
                "time": row["closed_at"],
                "equity": round(running_equity, 2)
            })
        
        return {"curve": curve}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger")
async def trigger_strategy_manually():
    """Manually trigger a test trade (for testing)"""
    from datetime import datetime
    
    round_id = datetime.now().strftime("%Y-%m-%d_%H:%M")
    
    try:
        # Import trading tools directly (avoid proxy issues with requests)
        from trading_tools import open_position, get_positions_summary
        
        # Get current positions
        summary = get_positions_summary()
        
        # Log to strategy_logs
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO strategy_logs (round_id, symbols, market_analysis, position_check, strategy_decision, actions_taken, raw_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            round_id, 
            "BTC,ETH,SOL", 
            f"Manual trigger test at {round_id}",
            f"Current positions: {summary['position_count']}, Balance: ${summary['wallet']['current_balance']}",
            "Test trigger completed",
            "[]",
            f"Manual test - Wallet: {summary['wallet']}"
        ))
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "round_id": round_id,
            "wallet": summary["wallet"],
            "positions": summary["open_positions"],
            "message": "Strategy log created. To test trading, use /api/strategy/test-trade"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-trade")
async def test_trade(symbol: str = "BTC", direction: str = "LONG", margin: float = 500):
    """Create a test trade position"""
    try:
        from trading_tools import open_position
        
        result = open_position(
            symbol=symbol,
            direction=direction,
            margin=margin,
            stop_loss=None,
            take_profit=None
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
