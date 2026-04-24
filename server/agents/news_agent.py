import json
import logging
from datetime import datetime
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
import os
import requests
import hashlib
from app.database import get_db

try:
    from tavily import TavilyClient  # type: ignore[import-not-found]
except ImportError:
    TavilyClient = None

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

LLM_KEY = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)

def generate_news_id(title: str, source: str) -> str:
    return hashlib.md5(f"{source}_{title}".encode()).hexdigest()

def get_latest_news_data() -> list:
    """Gets recent raw news items to process from multiple authoritative sources."""
    news_items = []
    
    # 1. Serper (Google News) - Focuses on macro UI/crypto policies
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        try:
            headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}
            queries = [
                "加密货币 突发快讯 site:jin10.com",
                "Bloomberg Bitcoin OR cryptocurrency",
                "美联储 降息 鲍威尔 宏观"
            ]
            for query in queries:
                # "tbs": "qdr:d" Means exactly in the past 24 hours
                resp = requests.post("https://google.serper.dev/news", json={"q": query, "num": 4, "type": "news", "tbs": "qdr:d"}, headers=headers, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json().get("news", []):
                        news_items.append({
                            "title": item.get("title", ""),
                            "content": item.get("snippet", ""),
                            "source": f"Serper-{item.get('source', 'News')}",
                            "published_at": item.get("date", str(datetime.now()))
                        })
        except Exception as e:
            logger.error(f"[NewsAgent] Serper fetch error: {e}")

    # 2. Tavily Search Pipeline
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key and TavilyClient:
        try:
            client = TavilyClient(api_key=tavily_key)
            queries = [
                "latest breaking crypto news from CoinDesk or Reuters"
            ]
            for query in queries:
                response = client.search(
                    query=query, 
                    search_depth="basic", 
                    topic="news", 
                    days=1, 
                    max_results=5
                )
                for res in response.get("results", []):
                    news_items.append({
                        "title": res.get("title", ""),
                        "content": res.get("content", ""),
                        "source": "Tavily",
                        "published_at": str(res.get("published_date", datetime.now()))
                    })
        except Exception as e:
            logger.error(f"[NewsAgent] Tavily fetch error: {e}")

    # 3. DuckDuckGo Pipeline (Free Fallback)
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        # timelimit='d' means last day
        results = ddgs.news("cryptocurrency macro", timelimit='d', max_results=5)
        for r in results:
            news_items.append({
                "title": r.get("title", ""),
                "content": r.get("body", ""),
                "source": f"DDG-{r.get('source', 'News')}",
                "published_at": str(r.get("date", datetime.now()))
            })
    except Exception as e:
        logger.error(f"[NewsAgent] DuckDuckGo fetch error: {e}")

    # 4. Remove duplicates roughly by title
    seen_titles = set()
    unique_items = []
    for item in news_items:
        title_stripped = str(item.get("title", "")).strip().lower()
        if not title_stripped or title_stripped in seen_titles:
            continue
        seen_titles.add(title_stripped)
        unique_items.append(item)

    return unique_items

class NewsAgent:
    def __init__(self):
        # Create an intelligent agent using OpenAI (or DeepSeek via proxy if configured)
        # Assuming OPENAI_API_KEY is set in env
        self.agent = Agent(
            model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
            description="You are a professional crypto financial news analyst.",
            instructions=[
                "Analyze the provided news item and determine its impact on the cryptocurrency market.",
                "Score the impact from 0 to 5:",
                "0 = No impact",
                "1 = Minor / negligible impact",
                "2 = Moderate impact (normal news)",
                "3 = Significant impact (notable price movement expected)",
                "4 = Major impact / Breaking news (e.g. ETF approval, major exchange hack, Fed rate cut)",
                "5 = Unprecedented / Black Swan event",
                "Provide a short 1-2 sentence reason for the score in Chinese.",
                "Always output valid JSON strictly with keys: 'impact_score' (int) and 'impact_reason' (string)."
            ]
        )
        
    def process_and_store_news(self):
        """Fetch, evaluate, and store news in the database."""
        logger.info("[NewsAgent] Starting news evaluation cycle...")
        items = get_latest_news_data()
        
        with get_db() as conn:
            with conn.cursor() as cur:
                new_critical_alerts = []
                
                for item in items:
                    title = item["title"]
                    if not title: continue
                    
                    news_id = generate_news_id(title, item["source"])
                    
                    # Check if already processed
                    cur.execute("SELECT 1 FROM news_intelligence WHERE news_id = %s", (news_id,))
                    if cur.fetchone():
                        continue
                        
                    # Evaluate impact
                    prompt = f"Title: {title}\nSummary: {item['content']}\nSource: {item['source']}\nPlease evaluate the impact and return JSON."
                    try:
                        resp = self.agent.run(prompt)
                        # Parse JSON from response
                        import re
                        json_str = re.search(r'\{.*\}', resp.content, re.DOTALL)
                        if json_str:
                            eval_data = json.loads(json_str.group())
                            score = int(eval_data.get("impact_score", 0))
                            reason = str(eval_data.get("impact_reason", ""))
                        else:
                            score, reason = 0, "Parse error"
                    except Exception as e:
                        logger.error(f"[NewsAgent] AI Evaluation failed for '{title[:30]}...': {e}")
                        score, reason = 0, "Evaluation failed"
                        
                    # Insert into DB
                    # Map Serper's relative dates to real dates would be better, but for simplicity we rely on DB CURRENT_TIMESTAMP if needed
                    # Let's just use Now for published_at as it's fetched now
                    pub_date = datetime.now()
                    
                    try:
                        cur.execute("""
                            INSERT INTO news_intelligence (news_id, title, content, source, published_at, impact_score, impact_reason)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (news_id, title, item['content'], item['source'], pub_date, score, reason))
                        conn.commit()
                        logger.info(f"[NewsAgent] Stored news: {title[:30]}... (Score: {score})")
                        
                        if score >= 4:
                            new_critical_alerts.append({
                                "title": title,
                                "score": score,
                                "reason": reason
                            })
                    except Exception as db_e:
                        logger.error(f"[NewsAgent] DB Insert error: {db_e}")
                        conn.rollback()
                
                # Check for critical alerts
                if new_critical_alerts:
                    for alert in new_critical_alerts:
                        self._trigger_emergency(alert)
                        
    def _trigger_emergency(self, alert_data):
        from notifier import notifier
        from scheduler import trigger_strategy, SCHEDULER_USER_ID, get_db
        
        msg = f"标题: {alert_data['title']}\n影响评级: {alert_data['score']}/5\n分析: {alert_data['reason']}"
        
        # Send system-wide broadcast to all users
        with get_db() as conn:
            with conn.cursor() as cur:
                # Find all users with active notifiers for NEWS_ALERT
                cur.execute("SELECT DISTINCT user_id FROM notification_configs WHERE is_active = TRUE AND enabled_events::jsonb @> '\"NEWS_ALERT\"'")
                users = cur.fetchall()
                for row in users:
                    notifier.send_event(row["user_id"], "NEWS_ALERT", "🚨 重大行市预警", msg, "URGENT")
                    
        logger.info(f"[NewsAgent] Emergency triggered for '{alert_data['title'][:30]}...'")
        
        # Wake up trading agent by forcing an immediate strategy trigger
        logger.info("[NewsAgent] Waking up Strategy Agent for emergency evaluation!")
        import threading
        threading.Thread(target=trigger_strategy, daemon=True).start()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    agent = NewsAgent()
    agent.process_and_store_news()
