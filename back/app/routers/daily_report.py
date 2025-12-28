"""
Daily Report Router - API for crypto daily reports and email subscriptions
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, date, timedelta
import sqlite3
import uuid
import os

router = APIRouter()

DB_PATH = os.getenv("DB_PATH", "tmp/test.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_daily_report_tables():
    """Initialize database tables for daily reports"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Daily reports table - supports multi-language reports per day
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            language TEXT DEFAULT 'en',
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(report_date, language)
        )
    """)
    
    # Email subscriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            language TEXT DEFAULT 'en',
            verified INTEGER DEFAULT 1,
            unsubscribe_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("[DailyReport] Tables initialized")


# Initialize tables on import
init_daily_report_tables()


# ============= API Models =============

class SubscribeRequest(BaseModel):
    email: EmailStr
    language: str = "en"  # 'en' or 'zh'


class ReportResponse(BaseModel):
    report_date: str
    language: str
    content: str
    created_at: str


# ============= API Endpoints =============

@router.get("/api/daily-report")
async def get_latest_report(language: str = "en"):
    """Get the latest daily report"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT report_date, language, content, created_at 
        FROM daily_reports 
        WHERE language = ?
        ORDER BY report_date DESC 
        LIMIT 1
    """, (language,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # Return a placeholder if no reports yet
        return {
            "report_date": str(date.today()),
            "language": language,
            "content": "# 📰 Daily Report\n\nNo report available yet. The first report will be generated at UTC 0:00.",
            "created_at": datetime.now().isoformat()
        }
    
    return {
        "report_date": row["report_date"],
        "language": row["language"],
        "content": row["content"],
        "created_at": row["created_at"]
    }


@router.get("/api/daily-report/dates")
async def get_available_dates(language: str = "en", limit: int = 30):
    """Get list of available report dates"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT report_date 
        FROM daily_reports 
        WHERE language = ?
        ORDER BY report_date DESC 
        LIMIT ?
    """, (language, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return {"dates": [row["report_date"] for row in rows]}


@router.get("/api/daily-report/{report_date}")
async def get_report_by_date(report_date: str, language: str = "en"):
    """Get report for a specific date (YYYY-MM-DD)"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT report_date, language, content, created_at 
        FROM daily_reports 
        WHERE report_date = ? AND language = ?
    """, (report_date, language))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Report not found for this date")
    
    return {
        "report_date": row["report_date"],
        "language": row["language"],
        "content": row["content"],
        "created_at": row["created_at"]
    }


@router.post("/api/subscribe")
async def subscribe_email(request: SubscribeRequest):
    """Subscribe to daily report emails"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if already subscribed
    cursor.execute("SELECT unsubscribe_token FROM email_subscriptions WHERE email = ?", (request.email,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return {"success": True, "message": "Already subscribed", "token": existing["unsubscribe_token"]}
    
    # Generate unsubscribe token
    unsubscribe_token = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO email_subscriptions (email, language, unsubscribe_token)
        VALUES (?, ?, ?)
    """, (request.email, request.language, unsubscribe_token))
    
    conn.commit()
    conn.close()
    
    # Send confirmation email with language
    try:
        from services.email_service import send_subscription_confirmation
        result = send_subscription_confirmation(request.email, request.language)
        print(f"[Subscribe] Confirmation email sent: {result}")
    except Exception as e:
        print(f"[Subscribe] Failed to send confirmation: {e}")
        import traceback
        traceback.print_exc()
    
    return {"success": True, "message": "Subscribed successfully", "token": unsubscribe_token}


@router.get("/api/unsubscribe/{token}")
async def unsubscribe_email(token: str):
    """Unsubscribe from daily report emails by token"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM email_subscriptions WHERE unsubscribe_token = ?", (token,))
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    if deleted > 0:
        return {"success": True, "message": "Unsubscribed successfully"}
    else:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe token")


@router.delete("/api/unsubscribe-email")
async def unsubscribe_by_email(email: str):
    """Unsubscribe from daily report emails by email address"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM email_subscriptions WHERE email = ?", (email,))
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    if deleted > 0:
        return {"success": True, "message": "Unsubscribed successfully"}
    else:
        raise HTTPException(status_code=404, detail="Email not found in subscriptions")


# ============= Internal Functions for Scheduler =============

def save_daily_report(report_date: str, content: str, language: str = "en"):
    """Save a generated daily report to database"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO daily_reports (report_date, language, content)
        VALUES (?, ?, ?)
    """, (report_date, language, content))
    
    conn.commit()
    conn.close()
    print(f"[DailyReport] Saved report for {report_date} ({language})")


def get_all_subscribers(language: str = None):
    """Get all email subscribers"""
    conn = get_db()
    cursor = conn.cursor()
    
    if language:
        cursor.execute("""
            SELECT email, unsubscribe_token, language 
            FROM email_subscriptions 
            WHERE language = ?
        """, (language,))
    else:
        cursor.execute("""
            SELECT email, unsubscribe_token, language 
            FROM email_subscriptions
        """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{"email": row["email"], "token": row["unsubscribe_token"], "language": row["language"]} for row in rows]
