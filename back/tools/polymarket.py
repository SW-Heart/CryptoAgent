"""
Polymarket 市场情绪工具 - 预测市场多空比查询

用于查询 Polymarket 预测市场上的事件赔率，作为市场情绪指标。
让 Agent 可以通过关键词搜索相关事件，返回多空比例帮助投资决策。

使用示例:
    from tools.polymarket_sentiment import get_market_odds
    
    # 查询 BTC 相关预测市场事件
    result = get_market_odds("BTC 2026")
    
    # 查询 Bitcoin 100K 事件
    result = get_market_odds("Bitcoin 100K January")
"""

import json
import requests
from typing import Optional, List, Dict, Any


# API 配置
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
DEFAULT_HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}
DEFAULT_TIMEOUT = 30


def _parse_json_field(value: Any) -> Any:
    """解析可能是 JSON 字符串的字段"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _calculate_sentiment(yes_odds: float) -> tuple:
    """
    根据看多概率计算市场情绪
    返回: (情绪标签, 情绪解读)
    """
    if yes_odds >= 80:
        return ("强烈看多", "市场高度看好该事件发生")
    elif yes_odds >= 65:
        return ("看多", "市场倾向于认为该事件会发生")
    elif yes_odds >= 55:
        return ("略微看多", "市场略微偏向该事件会发生")
    elif yes_odds >= 45:
        return ("中性/分歧", "市场存在较大分歧，多空接近五五开")
    elif yes_odds >= 35:
        return ("略微看空", "市场略微偏向该事件不会发生")
    elif yes_odds >= 20:
        return ("看空", "市场倾向于认为该事件不会发生")
    else:
        return ("强烈看空", "市场高度不看好该事件发生")


def _search_events(query: str, limit: int = 20) -> List[Dict]:
    """
    搜索 Polymarket 事件
    使用 Events API 获取更完整的数据
    改进的匹配逻辑：加密货币关键词必须在标题中出现
    """
    try:
        url = f"{GAMMA_API_BASE}/events"
        params = {
            "limit": 100,  # 获取更多以便过滤
            "order": "volume",
            "ascending": "false",
            "active": "true",
            "closed": "false"
        }
        
        response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        events = response.json()
        
        # 关键词过滤 - 改进版
        query_lower = query.lower()
        query_words = [w.strip() for w in query_lower.split() if w.strip()]
        
        # 加密货币关键词 - 这些必须精确匹配
        crypto_mapping = {
            'btc': 'bitcoin',
            'eth': 'ethereum', 
            'sol': 'solana',
            'xrp': 'xrp',
            'doge': 'dogecoin',
            'bitcoin': 'bitcoin',
            'ethereum': 'ethereum',
            'solana': 'solana',
            'dogecoin': 'dogecoin',
            'crypto': 'crypto'
        }
        
        # 识别查询中的加密货币关键词
        crypto_must_match = []
        other_keywords = []
        
        for word in query_words:
            if word in crypto_mapping:
                crypto_must_match.append(crypto_mapping[word])
            else:
                other_keywords.append(word)
        
        matched_events = []
        for event in events:
            title = event.get('title', '').lower()
            description = event.get('description', '').lower()
            
            # 如果查询包含加密货币关键词，必须在标题中出现
            if crypto_must_match:
                crypto_found = any(ck in title for ck in crypto_must_match)
                if not crypto_found:
                    continue
            
            # 计算匹配分数
            match_score = 0
            
            # 加密货币匹配权重最高
            for ck in crypto_must_match:
                if ck in title:
                    match_score += 10
            
            # 其他关键词匹配
            for word in other_keywords:
                if word in title:
                    match_score += 2
                elif word in description:
                    match_score += 1
            
            if match_score > 0:
                event['_match_score'] = match_score
                matched_events.append(event)
        
        # 按匹配分数排序
        matched_events.sort(key=lambda x: x.get('_match_score', 0), reverse=True)
        
        return matched_events
    
    except requests.RequestException as e:
        return []


def _search_markets(query: str, limit: int = 50) -> List[Dict]:
    """
    搜索 Polymarket 市场（作为补充搜索）
    使用改进的匹配逻辑：加密货币关键词必须在问题中出现
    """
    try:
        url = f"{GAMMA_API_BASE}/markets"
        params = {
            "limit": 100,
            "order": "volume",
            "ascending": "false",
            "active": "true",
            "closed": "false"
        }
        
        response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        markets = response.json()
        
        # 关键词过滤 - 与 _search_events 保持一致
        query_lower = query.lower()
        query_words = [w.strip() for w in query_lower.split() if w.strip()]
        
        # 加密货币关键词映射
        crypto_mapping = {
            'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana',
            'xrp': 'xrp', 'doge': 'dogecoin', 'bitcoin': 'bitcoin',
            'ethereum': 'ethereum', 'solana': 'solana', 'dogecoin': 'dogecoin',
            'crypto': 'crypto'
        }
        
        crypto_must_match = []
        other_keywords = []
        
        for word in query_words:
            if word in crypto_mapping:
                crypto_must_match.append(crypto_mapping[word])
            else:
                other_keywords.append(word)
        
        matched_markets = []
        for market in markets:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            
            # 如果查询包含加密货币关键词，必须在问题中出现
            if crypto_must_match:
                crypto_found = any(ck in question for ck in crypto_must_match)
                if not crypto_found:
                    continue
            
            match_score = 0
            for ck in crypto_must_match:
                if ck in question:
                    match_score += 10
            for word in other_keywords:
                if word in question:
                    match_score += 2
                elif word in description:
                    match_score += 1
            
            if match_score > 0:
                market['_match_score'] = match_score
                matched_markets.append(market)
        
        matched_markets.sort(key=lambda x: x.get('_match_score', 0), reverse=True)
        
        return matched_markets
    
    except requests.RequestException as e:
        return []


def get_market_odds(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Search Polymarket prediction markets and return odds/sentiment for a given query.
    Use this tool to gauge market sentiment on crypto prices, political events, or any
    topic with active prediction markets. Returns bullish/bearish percentages.
    
    Args:
        query: Search keywords (e.g., "BTC 100K", "Bitcoin January", "Trump 2024")
        limit: Maximum number of results to return (default 5)
    
    Returns:
        Dictionary with matched events and their odds, including:
        - question: The prediction market question
        - yes_odds/no_odds: Probability percentages for Yes/No outcomes
        - volume: Total trading volume (indicates market confidence)
        - sentiment: Market sentiment interpretation
    
    Example:
        >>> get_market_odds("Bitcoin 100K January")
        {
            "query": "Bitcoin 100K January",
            "found": 1,
            "summary": "市场对BTC 1月能否达到100K持中性态度...",
            "events": [...]
        }
    """
    result = {
        "query": query,
        "found": 0,
        "summary": "",
        "events": []
    }
    
    # 先搜索事件
    events = _search_events(query, limit=50)
    
    processed_events = []
    seen_questions = set()
    
    for event in events[:limit * 2]:  # 获取更多以便过滤
        markets = event.get('markets', [])
        
        for market in markets:
            question = market.get('question', '')
            if question in seen_questions:
                continue
            seen_questions.add(question)
            
            # 解析赔率
            outcomes = _parse_json_field(market.get('outcomes', '[]'))
            prices = _parse_json_field(market.get('outcomePrices', '[]'))
            
            if not outcomes or not prices:
                continue
            
            # 提取 Yes/No 赔率
            yes_odds = 0.0
            no_odds = 0.0
            other_outcomes = []
            
            for outcome, price in zip(outcomes, prices):
                try:
                    pct = float(price) * 100
                    outcome_lower = outcome.lower()
                    
                    if outcome_lower in ('yes', 'up'):
                        yes_odds = pct
                    elif outcome_lower in ('no', 'down'):
                        no_odds = pct
                    else:
                        other_outcomes.append({"name": outcome, "odds": round(pct, 1)})
                except (ValueError, TypeError):
                    continue
            
            # 如果没有标准 Yes/No，但有其他选项，使用第一个作为"看多"
            if yes_odds == 0 and no_odds == 0 and len(other_outcomes) >= 2:
                yes_odds = other_outcomes[0]['odds']
                no_odds = other_outcomes[1]['odds']
            
            sentiment, interpretation = _calculate_sentiment(yes_odds)
            
            # 格式化交易量和流动性
            volume = float(market.get('volume', 0) or 0)
            liquidity = float(market.get('liquidity', 0) or 0)
            
            if volume >= 1_000_000:
                volume_str = f"${volume/1_000_000:.1f}M"
            elif volume >= 1_000:
                volume_str = f"${volume/1_000:.0f}K"
            else:
                volume_str = f"${volume:.0f}"
            
            event_data = {
                "question": question,
                "yes_odds": round(yes_odds, 1),
                "no_odds": round(no_odds, 1),
                "volume": volume_str,
                "volume_raw": volume,
                "liquidity": f"${liquidity:,.0f}",
                "end_date": market.get('endDate', '')[:10] if market.get('endDate') else 'N/A',
                "sentiment": sentiment,
                "interpretation": interpretation
            }
            
            if other_outcomes:
                event_data["other_outcomes"] = other_outcomes
            
            processed_events.append(event_data)
    
    # 如果事件搜索结果不足，补充从 markets 搜索
    if len(processed_events) < limit:
        markets = _search_markets(query, limit=50)
        
        for market in markets:
            question = market.get('question', '')
            if question in seen_questions:
                continue
            seen_questions.add(question)
            
            outcomes = _parse_json_field(market.get('outcomes', '[]'))
            prices = _parse_json_field(market.get('outcomePrices', '[]'))
            
            if not outcomes or not prices:
                continue
            
            yes_odds = 0.0
            no_odds = 0.0
            
            for outcome, price in zip(outcomes, prices):
                try:
                    pct = float(price) * 100
                    if outcome.lower() in ('yes', 'up'):
                        yes_odds = pct
                    elif outcome.lower() in ('no', 'down'):
                        no_odds = pct
                except (ValueError, TypeError):
                    continue
            
            if yes_odds == 0 and no_odds == 0:
                continue
            
            sentiment, interpretation = _calculate_sentiment(yes_odds)
            volume = float(market.get('volume', 0) or 0)
            
            if volume >= 1_000_000:
                volume_str = f"${volume/1_000_000:.1f}M"
            elif volume >= 1_000:
                volume_str = f"${volume/1_000:.0f}K"
            else:
                volume_str = f"${volume:.0f}"
            
            processed_events.append({
                "question": question,
                "yes_odds": round(yes_odds, 1),
                "no_odds": round(no_odds, 1),
                "volume": volume_str,
                "volume_raw": volume,
                "end_date": market.get('endDate', '')[:10] if market.get('endDate') else 'N/A',
                "sentiment": sentiment,
                "interpretation": interpretation
            })
    
    # 按交易量排序，取 top N
    processed_events.sort(key=lambda x: x.get('volume_raw', 0), reverse=True)
    final_events = processed_events[:limit]
    
    # 移除 volume_raw（只用于排序）
    for e in final_events:
        e.pop('volume_raw', None)
    
    result["found"] = len(final_events)
    result["events"] = final_events
    
    # 生成摘要
    if final_events:
        top = final_events[0]
        result["summary"] = (
            f"找到 {len(final_events)} 个相关预测市场。"
            f"最活跃的市场: \"{top['question']}\" - "
            f"看多 {top['yes_odds']}% vs 看空 {top['no_odds']}% ({top['sentiment']})"
        )
    else:
        result["summary"] = f"未找到与 \"{query}\" 相关的活跃预测市场"
    
    return result


def get_crypto_prediction_odds(token: str = "BTC", timeframe: str = "2026") -> Dict[str, Any]:
    """
    Get prediction market odds for a cryptocurrency's price targets.
    Specialized function for crypto price predictions on Polymarket.
    
    Args:
        token: Cryptocurrency symbol (e.g., "BTC", "ETH", "Bitcoin")
        timeframe: Time period to search (e.g., "2026", "January", "Q1")
    
    Returns:
        Dictionary with price prediction events and their odds
    
    Example:
        >>> get_crypto_prediction_odds("BTC", "January")
        Returns BTC price prediction markets for January
    """
    # 构建搜索查询
    query = f"{token} {timeframe}"
    
    # 同时搜索 token 的不同表达
    if token.upper() == "BTC":
        query = f"Bitcoin {timeframe}"
    elif token.upper() == "ETH":
        query = f"Ethereum {timeframe}"
    
    result = get_market_odds(query, limit=10)
    
    # 添加额外的标签
    result["token"] = token.upper()
    result["timeframe"] = timeframe
    
    return result


# ==========================================
# 便捷别名（兼容不同调用方式）
# ==========================================
search_prediction_markets = get_market_odds
get_polymarket_sentiment = get_market_odds


if __name__ == "__main__":
    # 测试示例
    print("=" * 60)
    print("测试 1: 搜索 BTC 2026 相关预测市场")
    print("=" * 60)
    result = get_market_odds("BTC 2026")
    print(f"摘要: {result['summary']}")
    print(f"找到: {result['found']} 个事件")
    for e in result['events'][:3]:
        print(f"\n  📌 {e['question']}")
        print(f"     看多: {e['yes_odds']}% | 看空: {e['no_odds']}%")
        print(f"     交易量: {e['volume']} | 情绪: {e['sentiment']}")
    
    print("\n" + "=" * 60)
    print("测试 2: 搜索 Bitcoin January 100K")
    print("=" * 60)
    result = get_market_odds("Bitcoin January 100")
    print(f"摘要: {result['summary']}")
    for e in result['events'][:3]:
        print(f"\n  📌 {e['question']}")
        print(f"     看多: {e['yes_odds']}% | 看空: {e['no_odds']}%")
        print(f"     情绪: {e['sentiment']} - {e['interpretation']}")
