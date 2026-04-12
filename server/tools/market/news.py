"""
新闻与搜索工具：专业媒体情报、叙事分析、搜索引擎
"""
import requests
import os
import re
from collections import Counter

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/developer/v2/posts/"

def get_pro_crypto_news(limit: int = 8) -> str:
    """
    Get latest crypto news from self-hosted PANews API.
    Returns curated and important crypto news sorted by time (newest first).
    
    Args:
        limit: Number of news items to return (default: 8, max: 20)
    """
    limit = min(max(1, limit), 20)  # Clamp between 1-20
    
    try:
        NEWS_API_URL = f"http://142.171.245.211:8080/api/news?limit={limit}&sort=desc"
        resp = requests.get(NEWS_API_URL, timeout=10)
        
        if resp.status_code != 200:
            return f"News API error ({resp.status_code}): Unable to fetch news"
        
        data = resp.json()
        news_list = data.get("data", [])
        
        if not news_list:
            return "No news available at the moment"
        
        report = "📰 加密货币快讯 (PANews)\n"
        report += "=" * 40 + "\n\n"
        
        for i, item in enumerate(news_list, 1):
            title = item.get("title", "No title")
            content = item.get("content", "")
            publish_time = item.get("publish_time", "")
            source = item.get("source", "PANews")
            link = item.get("link", "")
            
            # Time display
            time_str = f"[{publish_time}]" if publish_time else ""
            
            report += f"{i}. {time_str} {title}\n"
            
            # Show snippet of content (max 150 chars)
            if content:
                snippet = content[:150] + "..." if len(content) > 150 else content
                report += f"   {snippet}\n"
            
            if link:
                report += f"   🔗 {link}\n"
            
            report += "\n"
        
        return report.strip()
        
    except Exception as e:
        return f"News fetch failed: {str(e)}"

# ==========================================
# 📊 [V2适配版] 工具：叙事强度分析
# ==========================================

def get_narrative_dominance() -> str:
    """
    Analyze dominant crypto narratives (AI, Meme, L2, RWA, DeFi, etc.) by scanning news keywords.
    Returns bar chart showing sector strength.
    """
    if "你的" in CRYPTOPANIC_API_KEY:
        return "❌ 配置错误: 请填入 Key"

    try:
        # 即使是分析叙事，我们也拉取 'hot' 或 'rising' 的列表
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "public": "true",
            "filter": "hot",   # 分析当前最热的内容
            "kind": "news",
            "regions": "en"
        }
        
        resp = requests.get(CRYPTOPANIC_BASE_URL, params=params, timeout=10)
        
        if resp.status_code != 200:
            return f"API request failed: {resp.status_code}"

        data = resp.json()
        if "results" not in data:
            return "API returned empty data"

        # Extract all titles for local keyword analysis
        all_text = " ".join([p.get('title', '') for p in data['results']])
        
        # Narrative keyword library
        narrative_keywords = {
            "AI": ["ai", "gpt", "compute", "render", "fet", "tao"],
            "Meme": ["meme", "doge", "pepe", "wif", "bonk", "shib", "cult"],
            "RWA": ["rwa", "blackrock", "ondo", "tokenization"],
            "Layer2": ["l2", "optimism", "base", "arb", "zk"],
            "Solana": ["solana", "sol", "pump"],
            "Regulation": ["sec", "gensler", "trump", "law", "etf"],
            "Macro": ["fed", "cpi", "rate", "powell"],
            "DeFi": ["defi", "dex", "swap", "yield"]
        }
        
        scores = {k: 0 for k in narrative_keywords}
        lower_text = all_text.lower()
        
        for category, keys in narrative_keywords.items():
            for k in keys:
                scores[category] += lower_text.count(k)
        
        top_narratives = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        res = "[Current Market Narrative Strength]\n"
        has_narrative = False
        for name, score in top_narratives:
            if score > 0:
                has_narrative = True
                res += f"{name}: {score} mentions\n"
        
        if not has_narrative:
            res += "No significant narrative keywords detected in current news flow."
            
        return res
        
    except Exception as e:
        return f"Narrative analysis error: {str(e)}"


# ==========================================
# 🔍 自定义搜索工具 (过滤 imageUrl)
# ==========================================
import os

def search_news(query: str, num_results: int = 5) -> str:
    """
    Search Google News via Serper API. Primary news search tool.
    
    Args:
        query: Search keywords (2-5 words best)
        num_results: Number of results (default 5)
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "❌ 配置错误: 未设置 SERPER_API_KEY"
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": num_results,
            "type": "news"
        }
        
        resp = requests.post("https://google.serper.dev/news", json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return f"Search failed: HTTP {resp.status_code}"
        
        data = resp.json()
        news_items = data.get("news", [])
        
        if not news_items:
            return f"No news found for '{query}'"
        
        result = f"Latest news for '{query}':\n\n"
        for i, item in enumerate(news_items[:num_results], 1):
            title = item.get("title", "No title")
            link = item.get("link", "")
            snippet = item.get("snippet", "")[:200]
            source = item.get("source", "Unknown")
            date = item.get("date", "")
            
            result += f"{i}. {title}\n"
            result += f"   Date: {date} | Source: {source}\n"
            result += f"   {snippet}\n"
            result += f"   Link: {link}\n\n"
        
        return result
        
    except Exception as e:
        return f"Search error: {str(e)}"


def search_google(query: str, num_results: int = 5) -> str:
    """
    Search Google via Serper API. Primary web search for research.
    Includes Knowledge Graph info when available.
    
    Args:
        query: Search keywords (2-5 words best)
        num_results: Number of results (default 5)
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "❌ 配置错误: 未设置 SERPER_API_KEY"
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": num_results
        }
        
        resp = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return f"Search failed: HTTP {resp.status_code}"
        
        data = resp.json()
        organic = data.get("organic", [])
        
        if not organic:
            return f"No results found for '{query}'"
        
        result = f"Search results for '{query}':\n\n"
        for i, item in enumerate(organic[:num_results], 1):
            title = item.get("title", "No title")
            link = item.get("link", "")
            snippet = item.get("snippet", "")[:300]
            
            result += f"{i}. {title}\n"
            result += f"   {snippet}\n"
            result += f"   Link: {link}\n\n"
        
        # Add Knowledge Graph info (if available)
        kg = data.get("knowledgeGraph", {})
        if kg:
            result += "\nKnowledge Graph:\n"
            if kg.get("title"):
                result += f"   {kg.get('title')}"
                if kg.get("type"):
                    result += f" ({kg.get('type')})"
                result += "\n"
                result += f"   {kg.get('description')[:200]}\n"
        
        return result
        
    except Exception as e:
        return f"Search error: {str(e)}"

