"""
Credits API router.
Handles user credits system for tool usage.
"""
from fastapi import APIRouter, Request, HTTPException
import sqlite3
from datetime import datetime

router = APIRouter(prefix="/api/credits", tags=["credits"])

DEFAULT_CREDITS = 100  # New user default credits
CREDITS_PER_TOOL = 5   # Credits deducted per tool call

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect("tmp/test.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_credits_table():
    """Initialize credits table if not exists"""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id TEXT PRIMARY KEY,
            credits INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Credits history table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credits_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            details TEXT NOT NULL,
            credits_change INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Daily check-in table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            checkin_date TEXT NOT NULL,
            credits_earned INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, checkin_date)
        )
    """)
    conn.commit()
    conn.close()

def get_user_credits(user_id: str) -> int:
    """Get user credits, initialize if new user"""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT credits FROM user_credits WHERE user_id = ?", 
        (user_id,)
    ).fetchone()
    
    if row is None:
        conn.execute(
            "INSERT INTO user_credits (user_id, credits) VALUES (?, ?)",
            (user_id, DEFAULT_CREDITS)
        )
        conn.commit()
        conn.close()
        return DEFAULT_CREDITS
    
    conn.close()
    return row["credits"]

def update_user_credits(user_id: str, credits: int) -> int:
    """Update user credits (direct set - use with caution, prefer atomic functions)"""
    conn = get_db_connection()
    conn.execute(
        "UPDATE user_credits SET credits = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (credits, user_id)
    )
    conn.commit()
    conn.close()
    return credits

def add_credits_atomic(user_id: str, amount: int) -> int:
    """Atomically add credits to user (thread-safe)"""
    # Ensure user exists first
    get_user_credits(user_id)
    
    conn = get_db_connection()
    conn.execute(
        "UPDATE user_credits SET credits = credits + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
    
    # Get updated value
    row = conn.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["credits"] if row else 0

def deduct_credits_atomic(user_id: str, amount: int) -> int:
    """Atomically deduct credits from user (thread-safe, allows negative)"""
    # Ensure user exists first
    get_user_credits(user_id)
    
    conn = get_db_connection()
    conn.execute(
        "UPDATE user_credits SET credits = credits - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
    
    # Get updated value
    row = conn.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["credits"] if row else 0

def log_credits_history(user_id: str, details: str, credits_change: int):
    """Log a credits change to history"""
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO credits_history (user_id, details, credits_change) VALUES (?, ?, ?)",
        (user_id, details, credits_change)
    )
    conn.commit()
    conn.close()

@router.get("/{user_id}")
async def api_get_credits(user_id: str):
    """Get user's current credits"""
    try:
        credits = get_user_credits(user_id)
        return {"user_id": user_id, "credits": credits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/history")
async def api_get_credits_history(user_id: str, page: int = 1, limit: int = 10):
    """Get user's credits usage history"""
    try:
        conn = get_db_connection()
        offset = (page - 1) * limit
        
        rows = conn.execute(
            """SELECT details, credits_change, created_at 
               FROM credits_history 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset)
        ).fetchall()
        
        # Get total count
        total = conn.execute(
            "SELECT COUNT(*) FROM credits_history WHERE user_id = ?",
            (user_id,)
        ).fetchone()[0]
        
        conn.close()
        
        history = [
            {
                "details": row["details"],
                "credits_change": row["credits_change"],
                "date": row["created_at"]
            }
            for row in rows
        ]
        
        return {
            "history": history,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/add")
async def api_add_credits(user_id: str, request: Request):
    """Add credits to user (admin function)"""
    try:
        data = await request.json()
        amount = data.get("amount", 0)
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        # Use atomic function to prevent race conditions
        previous = get_user_credits(user_id)
        new_credits = add_credits_atomic(user_id, amount)
        
        # Log to history
        log_credits_history(user_id, "Credits added", amount)
        
        return {
            "user_id": user_id, 
            "previous_credits": previous,
            "added": amount,
            "current_credits": new_credits
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/deduct")
async def api_deduct_credits(user_id: str, request: Request):
    """Deduct credits from user. Allows negative balance during conversation."""
    try:
        data = await request.json()
        tool_count = data.get("tool_count", 0)
        details = data.get("details", "Tool usage")  # Question/context
        amount = tool_count * CREDITS_PER_TOOL
        
        # Use atomic function to prevent race conditions
        previous = get_user_credits(user_id)
        new_credits = deduct_credits_atomic(user_id, amount)
        
        # Log to history with negative value
        log_credits_history(user_id, details, -amount)
        
        return {
            "user_id": user_id,
            "previous_credits": current,
            "deducted": amount,
            "current_credits": new_credits
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/can-chat")
async def api_can_chat(user_id: str):
    """Check if user has enough credits to start a new conversation (minimum 5)"""
    try:
        credits = get_user_credits(user_id)
        can_chat = credits >= 5
        return {
            "user_id": user_id,
            "credits": credits,
            "can_chat": can_chat,
            "message": "OK" if can_chat else "Insufficient credits. You need at least 5 credits to start a conversation."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/checkin-status")
async def api_checkin_status(user_id: str):
    """Check if user has checked in today"""
    try:
        conn = get_db_connection()
        today = datetime.now().strftime("%Y-%m-%d")
        
        row = conn.execute(
            "SELECT * FROM daily_checkins WHERE user_id = ? AND checkin_date = ?",
            (user_id, today)
        ).fetchone()
        conn.close()
        
        return {
            "user_id": user_id,
            "checked_in_today": row is not None,
            "date": today
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/checkin")
async def api_checkin(user_id: str):
    """Daily check-in to earn 10 credits"""
    CHECKIN_CREDITS = 10
    
    try:
        conn = get_db_connection()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check if already checked in today
        existing = conn.execute(
            "SELECT * FROM daily_checkins WHERE user_id = ? AND checkin_date = ?",
            (user_id, today)
        ).fetchone()
        
        if existing:
            conn.close()
            return {
                "success": False,
                "message": "You've already checked in today!",
                "credits_earned": 0
            }
        
        # All operations in a single transaction for consistency
        try:
            # Record check-in
            conn.execute(
                "INSERT INTO daily_checkins (user_id, checkin_date, credits_earned) VALUES (?, ?, ?)",
                (user_id, today, CHECKIN_CREDITS)
            )
            
            # Ensure user exists in credits table
            existing_credits = conn.execute(
                "SELECT credits FROM user_credits WHERE user_id = ?", (user_id,)
            ).fetchone()
            
            if existing_credits is None:
                conn.execute(
                    "INSERT INTO user_credits (user_id, credits) VALUES (?, ?)",
                    (user_id, DEFAULT_CREDITS + CHECKIN_CREDITS)
                )
                new_credits = DEFAULT_CREDITS + CHECKIN_CREDITS
            else:
                # Atomic update within same transaction
                conn.execute(
                    "UPDATE user_credits SET credits = credits + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (CHECKIN_CREDITS, user_id)
                )
                row = conn.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,)).fetchone()
                new_credits = row["credits"]
            
            # Log to history
            conn.execute(
                "INSERT INTO credits_history (user_id, details, credits_change) VALUES (?, ?, ?)",
                (user_id, "Daily check-in", CHECKIN_CREDITS)
            )
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            raise HTTPException(status_code=500, detail=f"Check-in failed: {str(e)}")
        
        conn.close()
        
        return {
            "success": True,
            "message": f"🎉 Check-in successful! +{CHECKIN_CREDITS} credits",
            "credits_earned": CHECKIN_CREDITS,
            "current_credits": new_credits
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
