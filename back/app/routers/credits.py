"""
Credits API router.
Handles user credits system for tool usage.
"""
from fastapi import APIRouter, Request, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db_connection

router = APIRouter(prefix="/api/credits", tags=["credits"])

DEFAULT_CREDITS = 100  # New user default credits
CREDITS_PER_TOOL = 5   # Credits deducted per tool call
TOKENS_PER_CREDIT = 50000  # 5万 token = 1积分

class AddCreditsRequest(BaseModel):
    amount: int

class DeductCreditsRequest(BaseModel):
    tool_count: int
    details: str = "Tool usage"

class DeductTokenCreditsRequest(BaseModel):
    total_tokens: int
    session_id: str = None

def init_credits_table():
    """Initialize credits table if not exists"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_credits (
                user_id TEXT PRIMARY KEY,
                credits INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Credits history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credits_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                details TEXT NOT NULL,
                credits_change INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Daily check-in table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_checkins (
                id SERIAL PRIMARY KEY,
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
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT credits FROM user_credits WHERE user_id = %s", 
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            cursor.execute(
                "INSERT INTO user_credits (user_id, credits) VALUES (%s, %s)",
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
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE user_credits SET credits = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
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
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE user_credits SET credits = credits + %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
            (amount, user_id)
        )
        conn.commit()
        
        # Get updated value
        cursor.execute("SELECT credits FROM user_credits WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
    conn.close()
    return row["credits"] if row else 0

def deduct_credits_atomic(user_id: str, amount: int) -> int:
    """Atomically deduct credits from user (thread-safe, allows negative)"""
    # Ensure user exists first
    get_user_credits(user_id)
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE user_credits SET credits = credits - %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
            (amount, user_id)
        )
        conn.commit()
        
        # Get updated value
        cursor.execute("SELECT credits FROM user_credits WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
    conn.close()
    return row["credits"] if row else 0

def log_credits_history(user_id: str, details: str, credits_change: int):
    """Log a credits change to history"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO credits_history (user_id, details, credits_change) VALUES (%s, %s, %s)",
            (user_id, details, credits_change)
        )
        conn.commit()
    conn.close()

def calculate_token_credits(total_tokens: int) -> int:
    """计算 token 消耗对应的积分数
    
    规则：5万 token = 1积分，不足1积分按1积分算（向上取整）
    """
    if total_tokens <= 0:
        return 0
    # 向上取整：任何 >0 的 token 消耗至少扣 1 积分
    return max(1, (total_tokens + TOKENS_PER_CREDIT - 1) // TOKENS_PER_CREDIT)

def deduct_token_credits(user_id: str, total_tokens: int, session_id: str = None) -> dict:
    """根据 token 消耗扣除积分并记录历史
    
    Args:
        user_id: 用户 ID
        total_tokens: 本次 run 消耗的总 token 数
        session_id: 可选，会话 ID（用于记录）
        
    Returns:
        dict: 包含 previous_credits, deducted, current_credits, tokens
    """
    credits_to_deduct = calculate_token_credits(total_tokens)
    
    if credits_to_deduct <= 0:
        return {"deducted": 0, "tokens": total_tokens, "previous_credits": 0, "current_credits": 0}
    
    previous = get_user_credits(user_id)
    new_credits = deduct_credits_atomic(user_id, credits_to_deduct)
    
    # 记录历史
    details = f"LLM Token: {total_tokens:,}"
    log_credits_history(user_id, details, -credits_to_deduct)
    
    return {
        "previous_credits": previous,
        "deducted": credits_to_deduct,
        "current_credits": new_credits,
        "tokens": total_tokens
    }

@router.get("/{user_id}")
def api_get_credits(user_id: str):
    """Get user's current credits"""
    try:
        credits = get_user_credits(user_id)
        return {"user_id": user_id, "credits": credits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/history")
def api_credits_history(user_id: str, page: int = 1, limit: int = 10):
    """Get user's credits usage history"""
    try:
        conn = get_db_connection()
        offset = (page - 1) * limit
        
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT details, credits_change, created_at 
                   FROM credits_history 
                   WHERE user_id = %s 
                   ORDER BY created_at DESC 
                   LIMIT %s OFFSET %s""",
                (user_id, limit, offset)
            )
            rows = cursor.fetchall()
            
            # Get total count
            cursor.execute(
                "SELECT COUNT(*) FROM credits_history WHERE user_id = %s",
                (user_id,)
            )
            total = cursor.fetchone()[0]
        
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
def api_add_credits(user_id: str, body: AddCreditsRequest):
    """Add credits to user (admin function)"""
    try:
        amount = body.amount
        
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
def api_deduct_credits(user_id: str, body: DeductCreditsRequest):
    """Deduct credits from user. Allows negative balance during conversation."""
    try:
        tool_count = body.tool_count
        details = body.details
        amount = tool_count * CREDITS_PER_TOOL
        
        # Use atomic function to prevent race conditions
        previous = get_user_credits(user_id)
        new_credits = deduct_credits_atomic(user_id, amount)
        
        # Log to history with negative value
        log_credits_history(user_id, details, -amount)
        
        return {
            "user_id": user_id,
            "previous_credits": previous,
            "deducted": amount,
            "current_credits": new_credits
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/deduct-tokens")
def api_deduct_token_credits(user_id: str, body: DeductTokenCreditsRequest):
    """Deduct credits based on token usage (5万 tokens = 1 credit).
    
    Called by frontend after stream completion with RunCompleted metrics.
    """
    try:
        total_tokens = body.total_tokens
        session_id = body.session_id
        
        if total_tokens <= 0:
            return {"user_id": user_id, "deducted": 0, "tokens": 0}
        
        result = deduct_token_credits(user_id, total_tokens, session_id)
        return {
            "user_id": user_id,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/can-chat")
def api_can_chat(user_id: str):
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
def api_checkin_status(user_id: str):
    """Check if user has checked in today"""
    try:
        conn = get_db_connection()
        today = datetime.now().strftime("%Y-%m-%d")
        
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM daily_checkins WHERE user_id = %s AND checkin_date = %s",
                (user_id, today)
            )
            row = cursor.fetchone()
        conn.close()
        
        return {
            "user_id": user_id,
            "checked_in_today": row is not None,
            "date": today
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/checkin")
def api_checkin(user_id: str):
    """Daily check-in to earn 10 credits"""
    CHECKIN_CREDITS = 10
    
    try:
        conn = get_db_connection()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check if already checked in today
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM daily_checkins WHERE user_id = %s AND checkin_date = %s",
                (user_id, today)
            )
            existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return {
                "success": False,
                "message": "You've already checked in today!",
                "credits_earned": 0
            }
        
        # All operations in a single transaction for consistency
        try:
            with conn.cursor() as cursor:
                # Record check-in
                cursor.execute(
                    "INSERT INTO daily_checkins (user_id, checkin_date, credits_earned) VALUES (%s, %s, %s)",
                    (user_id, today, CHECKIN_CREDITS)
                )
                
                # Ensure user exists in credits table
                cursor.execute(
                    "SELECT credits FROM user_credits WHERE user_id = %s", (user_id,)
                )
                existing_credits = cursor.fetchone()
                
                if existing_credits is None:
                    cursor.execute(
                        "INSERT INTO user_credits (user_id, credits) VALUES (%s, %s)",
                        (user_id, DEFAULT_CREDITS + CHECKIN_CREDITS)
                    )
                    new_credits = DEFAULT_CREDITS + CHECKIN_CREDITS
                else:
                    # Atomic update within same transaction
                    cursor.execute(
                        "UPDATE user_credits SET credits = credits + %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                        (CHECKIN_CREDITS, user_id)
                    )
                    cursor.execute("SELECT credits FROM user_credits WHERE user_id = %s", (user_id,))
                    row = cursor.fetchone()
                    new_credits = row["credits"]
                
                # Log to history
                cursor.execute(
                    "INSERT INTO credits_history (user_id, details, credits_change) VALUES (%s, %s, %s)",
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
