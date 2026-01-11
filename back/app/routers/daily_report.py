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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=60)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提高并发性能
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
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
    
    # Suggested questions table - AI生成的每日推荐问题
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suggested_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_date TEXT NOT NULL,
            language TEXT DEFAULT 'zh',
            questions TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(question_date, language)
        )
    """)
    
    # User question clicks table - 用户点击记录
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_question_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            question_date TEXT NOT NULL,
            current_index INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, question_date)
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


# ============= Suggested Questions API =============

class QuestionClickRequest(BaseModel):
    user_id: str
    question_index: int


@router.get("/api/suggested-questions")
async def get_suggested_question(user_id: str = "", language: str = "zh"):
    """
    获取用户当前应该看到的推荐问题
    返回单个问题，根据用户点击进度返回下一个未看过的
    """
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    
    # 获取今日的推荐问题
    cursor.execute("""
        SELECT questions FROM suggested_questions 
        WHERE question_date = ? AND language = ?
    """, (today, language))
    
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        # 如果今天还没生成问题，返回默认问题
        default_zh = [
            "今天市场怎么走？",
            "BTC 能买吗？",
            "什么板块最火？",
            "止盈点位在哪？",
            "链上有啥机会？",
            "山寨季来了吗？",
            "仓位怎么配？",
            "空投值得做吗？",
            "ETH 能追吗？",
            "DeFi 收益哪家强？"
        ]
        default_en = [
            "What's the market outlook?",
            "Should I buy BTC now?",
            "What sectors are hot?",
            "Where to take profit?",
            "Any on-chain alpha?",
            "Is altcoin season here?",
            "How to size positions?",
            "Any airdrop worth doing?",
            "Will ETH pump?",
            "Best DeFi yields?"
        ]
        questions = default_zh if language == "zh" else default_en
        current_index = 0
    else:
        import json
        questions = json.loads(row["questions"])
        
        # 获取用户当前的进度
        if user_id:
            cursor.execute("""
                SELECT current_index FROM user_question_clicks
                WHERE user_id = ? AND question_date = ?
            """, (user_id, today))
            click_row = cursor.fetchone()
            current_index = click_row["current_index"] if click_row else 0
        else:
            current_index = 0
        
        conn.close()
    
    # 循环显示问题
    if current_index >= len(questions):
        current_index = 0
    
    return {
        "question": questions[current_index],
        "current_index": current_index,
        "total": len(questions),
        "question_date": today,
        "all_questions": questions  # 前端可以预加载所有问题
    }


@router.post("/api/suggested-questions/click")
async def record_question_click(request: QuestionClickRequest):
    """
    记录用户点击问题，并返回下一个问题
    """
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    next_index = request.question_index + 1
    
    # 更新或插入用户点击记录
    cursor.execute("""
        INSERT OR REPLACE INTO user_question_clicks 
        (user_id, question_date, current_index, updated_at)
        VALUES (?, ?, ?, ?)
    """, (request.user_id, today, next_index, datetime.now().isoformat()))
    
    conn.commit()
    
    # 获取今日问题列表
    cursor.execute("""
        SELECT questions FROM suggested_questions 
        WHERE question_date = ?
    """, (today,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        import json
        questions = json.loads(row["questions"])
        # 循环
        if next_index >= len(questions):
            next_index = 0
        return {
            "next_question": questions[next_index],
            "next_index": next_index,
            "total": len(questions)
        }
    
    return {
        "next_question": None,
        "next_index": 0,
        "total": 0
    }


def save_suggested_questions(question_date: str, questions: list, language: str = "zh"):
    """保存AI生成的推荐问题到数据库"""
    conn = get_db()
    cursor = conn.cursor()
    
    import json
    questions_json = json.dumps(questions, ensure_ascii=False)
    
    cursor.execute("""
        INSERT OR REPLACE INTO suggested_questions 
        (question_date, language, questions, created_at)
        VALUES (?, ?, ?, ?)
    """, (question_date, language, questions_json, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    print(f"[SuggestedQuestions] Saved {len(questions)} questions for {question_date} ({language})")

