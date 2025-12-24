"""
Sessions API router.
Handles session listing, history, renaming, and deletion.
"""
from fastapi import APIRouter, Request, HTTPException
import sqlite3
import json

router = APIRouter(prefix="/api", tags=["sessions"])

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect("tmp/test.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_session_titles_table():
    """Initialize session titles table if not exists"""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_titles (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

@router.get("/sessions")
async def get_sessions(user_id: str):
    """Get all sessions for a specific user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT session_id, runs, updated_at FROM test_agent WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        
        title_cursor = conn.execute("SELECT session_id, title FROM session_titles")
        custom_titles = {row["session_id"]: row["title"] for row in title_cursor.fetchall()}
        
        sessions = []
        for row in rows:
            session_id = row["session_id"]
            
            if session_id in custom_titles:
                title = custom_titles[session_id]
            else:
                title = "New Chat"
                try:
                    runs = json.loads(row["runs"])
                    if isinstance(runs, str):
                        runs = json.loads(runs)
                    if runs and len(runs) > 0:
                        first_run_messages = runs[0].get("messages", [])
                        for msg in first_run_messages:
                            if msg.get("role") == "user":
                                content = msg.get("content", "")
                                title = content[:30] + "..." if len(content) > 30 else content
                                break
                except Exception:
                    pass
            
            sessions.append({
                "session_id": session_id,
                "title": title,
                "updated_at": row["updated_at"]
            })
            
        conn.close()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(session_id: str):
    """Get full chat history for a session."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT runs FROM test_agent WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
            
        runs = json.loads(row["runs"])
        if isinstance(runs, str):
            runs = json.loads(runs)
        all_messages = []
        
        for run in runs:
            msgs = run.get("messages", [])
            i = 0
            while i < len(msgs):
                msg = msgs[i]
                role = msg.get("role")
                
                if role == 'user':
                    all_messages.append({
                        "role": "user", 
                        "content": msg.get("content", "")
                    })
                    i += 1
                elif role == 'assistant':
                    content = msg.get("content", "") or ""
                    
                    if "tool_calls" in msg:
                        for tc in msg["tool_calls"]:
                            func = tc.get("function", {})
                            name = func.get("name", "unknown_tool")
                            args = func.get("arguments", "{}")
                            
                            try:
                                args_obj = json.loads(args)
                                args_str = ", ".join([f"{k}={v}" for k, v in args_obj.items()])
                                call_str = f"{name}({args_str})"
                            except:
                                call_str = f"{name}({args})"

                            content += f"\n{call_str} completed"

                    if all_messages and all_messages[-1]["role"] == "assistant":
                        all_messages[-1]["content"] += "\n" + content
                    else:
                        all_messages.append({
                            "role": "assistant",
                            "content": content
                        })
                    i += 1
                else:
                    i += 1
                    
        conn.close()
        return {"messages": all_messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/rename")
async def rename_session(session_id: str, request: Request):
    """Rename a session"""
    try:
        data = await request.json()
        new_title = data.get("title", "").strip()
        
        if not new_title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        
        conn = get_db_connection()
        conn.execute(
            """INSERT OR REPLACE INTO session_titles (session_id, title) VALUES (?, ?)""",
            (session_id, new_title)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "session_id": session_id, "title": new_title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM test_agent WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_titles WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        
        return {"success": True, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/title")
async def get_session_title(session_id: str):
    """Get custom title for a session"""
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT title FROM session_titles WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        conn.close()
        
        if row:
            return {"session_id": session_id, "title": row["title"]}
        return {"session_id": session_id, "title": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
