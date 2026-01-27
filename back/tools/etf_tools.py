"""
ETF Data Tools - Farside ETF Fund Flow Data

Data source: http://142.171.245.211:8000 (Farside Investors scraper)
Units: Million USD (US$m)
Positive = Inflow, Negative = Outflow

IMPORTANT: ETF markets are closed on weekends (Saturday/Sunday) and US holidays.
No trading data available on these days.
"""

import requests
from typing import Optional
from datetime import datetime, timedelta

ETF_API_BASE = "http://142.171.245.211:8000"


def _is_weekend(date: datetime) -> bool:
    """检查是否为周末（周六=5, 周日=6）"""
    return date.weekday() >= 5


def _get_weekend_notice() -> str:
    """如果今天是周末，返回提示信息"""
    today = datetime.now()
    if _is_weekend(today):
        return "\n\n⏸️ 注意：今天是周末，ETF市场休市，无最新交易数据。上述为最近交易日数据。"
    return ""


# ==========================================
# 🏦 ETF 资金流工具
# ==========================================

def get_etf_flows(etf_type: str = "btc", days: int = 7) -> str:
    """
    Get ETF fund flow history for trend analysis.
    Shows daily net flow with breakdown by major issuers (e.g., IBIT, FBTC, GBTC).
    
    Args:
        etf_type: ETF type - "btc", "eth", or "sol"
        days: Number of days to query (1-365, default 7)
    
    Returns:
        Recent ETF fund flows with issuer breakdown, sorted by date descending.
    """
    try:
        url = f"{ETF_API_BASE}/api/etf/{etf_type.lower()}/flows"
        resp = requests.get(url, params={"days": days}, timeout=10)
        
        # 处理数据未爬取的情况
        if resp.status_code == 404 or (resp.status_code == 200 and "detail" in resp.text):
            return f"⚠️ {etf_type.upper()} ETF 数据暂不可用（数据源未爬取）。目前仅支持 BTC ETF。"
        
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            return f"No {etf_type.upper()} ETF data available for the last {days} days."
        
        # Format output with issuer details
        lines = [f"📊 {etf_type.upper()} ETF Fund Flows (Last {len(data)} trading days)"]
        lines.append("-" * 50)
        
        total_net = 0
        for record in data:
            date = record.get("date", "Unknown")
            total_flow = record.get("total_flow", 0)
            total_net += total_flow if total_flow else 0
            
            flow_str = f"+${total_flow:.1f}M" if total_flow > 0 else f"${total_flow:.1f}M"
            emoji = "🟢" if total_flow > 0 else "🔴" if total_flow < 0 else "⚪"
            
            line = f"{emoji} {date}: {flow_str}"
            
            # Add major issuer breakdown
            ticker_flows = record.get("ticker_flows", {})
            if ticker_flows:
                # Sort by absolute value, show top 3 contributors
                sorted_tickers = sorted(
                    ticker_flows.items(), 
                    key=lambda x: abs(x[1]) if x[1] else 0, 
                    reverse=True
                )[:3]
                ticker_parts = []
                for ticker, flow in sorted_tickers:
                    if flow and flow != 0:
                        sign = "+" if flow > 0 else ""
                        ticker_parts.append(f"{ticker}:{sign}{flow:.1f}")
                if ticker_parts:
                    line += f" ({', '.join(ticker_parts)})"
            
            lines.append(line)
        
        lines.append("-" * 50)
        net_emoji = "🟢" if total_net > 0 else "🔴"
        net_str = f"+${total_net:.1f}M" if total_net > 0 else f"${total_net:.1f}M"
        lines.append(f"{net_emoji} Net Flow ({len(data)} days): {net_str}")
        
        return "\n".join(lines) + _get_weekend_notice()
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching {etf_type.upper()} ETF flows: {str(e)}"
    except Exception as e:
        return f"Error processing {etf_type.upper()} ETF data: {str(e)}"


def get_etf_daily(etf_type: str = "btc", date: Optional[str] = None) -> str:
    """
    Get ETF fund flow for a specific date with full issuer breakdown.
    Default: yesterday (most recent available data).
    
    Args:
        etf_type: ETF type - "btc", "eth", or "sol"
        date: Date in YYYY-MM-DD format (default: yesterday)
    
    Returns:
        Single day ETF data with all issuer flows.
    """
    try:
        # Default to yesterday (ETF data usually lags 1 day)
        if not date:
            yesterday = datetime.now() - timedelta(days=1)
            date = yesterday.strftime("%Y-%m-%d")
        
        url = f"{ETF_API_BASE}/api/etf/{etf_type.lower()}/date/{date}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 404:
            # Try 2 days ago if yesterday not available
            two_days_ago = datetime.now() - timedelta(days=2)
            date = two_days_ago.strftime("%Y-%m-%d")
            url = f"{ETF_API_BASE}/api/etf/{etf_type.lower()}/date/{date}"
            resp = requests.get(url, timeout=10)
        
        # 处理数据未爬取的情况
        if resp.status_code == 404 or (resp.status_code == 200 and "detail" in resp.text):
            return f"⚠️ {etf_type.upper()} ETF 数据暂不可用（数据源未爬取）。目前仅支持 BTC ETF。"
            
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            return f"No {etf_type.upper()} ETF data for {date}."
        
        total_flow = data.get("total_flow", 0)
        ticker_flows = data.get("ticker_flows", {})
        
        # Format output
        emoji = "🟢" if total_flow > 0 else "🔴" if total_flow < 0 else "⚪"
        flow_str = f"+${total_flow:.1f}M" if total_flow > 0 else f"${total_flow:.1f}M"
        
        lines = [f"📊 {etf_type.upper()} ETF Flow - {date}"]
        lines.append(f"{emoji} Total Net Flow: {flow_str}")
        lines.append("")
        lines.append("📋 Issuer Breakdown:")
        
        # Sort by absolute value
        sorted_tickers = sorted(
            ticker_flows.items(),
            key=lambda x: abs(x[1]) if x[1] else 0,
            reverse=True
        )
        
        for ticker, flow in sorted_tickers:
            if flow and flow != 0:
                sign = "+" if flow > 0 else ""
                t_emoji = "🟢" if flow > 0 else "🔴"
                lines.append(f"  {t_emoji} {ticker}: {sign}${flow:.1f}M")
        
        return "\n".join(lines) + _get_weekend_notice()
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching {etf_type.upper()} ETF daily: {str(e)}"
    except Exception as e:
        return f"Error processing {etf_type.upper()} ETF data: {str(e)}"


def get_etf_summary(etf_type: str = "btc") -> str:
    """
    Get ETF cumulative summary with total inflow/outflow and issuer rankings.
    Best for understanding overall institutional positioning.
    
    Args:
        etf_type: ETF type - "btc", "eth", or "sol"
    
    Returns:
        Summary statistics including net flow, issuer totals, and daily averages.
    """
    try:
        url = f"{ETF_API_BASE}/api/etf/{etf_type.lower()}/summary"
        resp = requests.get(url, timeout=10)
        
        # 处理数据未爬取的情况
        if resp.status_code == 404 or (resp.status_code == 200 and "detail" in resp.text):
            return f"⚠️ {etf_type.upper()} ETF 数据暂不可用（数据源未爬取）。目前仅支持 BTC ETF。"
        
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            return f"No {etf_type.upper()} ETF summary available."
        
        # Extract fields
        start_date = data.get("start_date", "N/A")
        end_date = data.get("end_date", "N/A")
        total_inflow = data.get("total_inflow", 0)
        total_outflow = data.get("total_outflow", 0)
        net_flow = data.get("net_flow", 0)
        avg_daily = data.get("avg_daily_flow", 0)
        trading_days = data.get("trading_days", 0)
        ticker_totals = data.get("ticker_totals", {})
        
        # Format output
        net_emoji = "🟢" if net_flow > 0 else "🔴"
        net_str = f"+${net_flow:.1f}M" if net_flow > 0 else f"${net_flow:.1f}M"
        avg_str = f"+${avg_daily:.1f}M" if avg_daily > 0 else f"${avg_daily:.1f}M"
        
        lines = [f"📊 {etf_type.upper()} ETF Summary ({start_date} to {end_date})"]
        lines.append("-" * 50)
        lines.append(f"📈 Total Inflow: +${total_inflow:.1f}M")
        lines.append(f"📉 Total Outflow: ${total_outflow:.1f}M")
        lines.append(f"{net_emoji} Net Flow: {net_str}")
        lines.append(f"📅 Trading Days: {trading_days}")
        lines.append(f"📊 Avg Daily: {avg_str}")
        lines.append("")
        lines.append("🏦 Issuer Rankings (Cumulative):")
        
        # Sort by value (positive first, then negative)
        sorted_tickers = sorted(
            ticker_totals.items(),
            key=lambda x: x[1] if x[1] else 0,
            reverse=True
        )
        
        for ticker, total in sorted_tickers:
            if total and total != 0:
                sign = "+" if total > 0 else ""
                t_emoji = "🟢" if total > 0 else "🔴"
                lines.append(f"  {t_emoji} {ticker}: {sign}${total:.1f}M")
        
        return "\n".join(lines)
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching {etf_type.upper()} ETF summary: {str(e)}"
    except Exception as e:
        return f"Error processing {etf_type.upper()} ETF data: {str(e)}"


def get_etf_ticker(etf_type: str = "btc", ticker: str = "IBIT", days: int = 30) -> str:
    """
    Get fund flow history for a specific ETF issuer (e.g., BlackRock IBIT, Fidelity FBTC).
    Useful for tracking individual institution behavior.
    
    Args:
        etf_type: ETF type - "btc", "eth", or "sol"
        ticker: Issuer ticker (e.g., "IBIT", "FBTC", "GBTC", "ETHA")
        days: Number of days (default 30)
    
    Returns:
        Historical fund flow for the specified issuer.
    """
    try:
        url = f"{ETF_API_BASE}/api/etf/{etf_type.lower()}/ticker/{ticker.upper()}"
        resp = requests.get(url, params={"days": days}, timeout=10)
        
        # 处理数据未爬取的情况
        if resp.status_code == 404 or (resp.status_code == 200 and "detail" in resp.text):
            return f"⚠️ {etf_type.upper()} ETF 数据暂不可用（数据源未爬取）。目前仅支持 BTC ETF。"
        
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            return f"No data for {ticker.upper()} in {etf_type.upper()} ETFs."
        
        # Calculate totals
        total = sum(d.get("flow_usd", 0) or 0 for d in data)
        
        lines = [f"🏦 {ticker.upper()} ({etf_type.upper()}) - Last {len(data)} trading days"]
        lines.append("-" * 40)
        
        for record in data[:10]:  # Show last 10 days
            date = record.get("date", "Unknown")
            flow = record.get("flow_usd", 0)
            if flow:
                emoji = "🟢" if flow > 0 else "🔴"
                sign = "+" if flow > 0 else ""
                lines.append(f"{emoji} {date}: {sign}${flow:.1f}M")
        
        if len(data) > 10:
            lines.append(f"... and {len(data) - 10} more days")
        
        lines.append("-" * 40)
        net_emoji = "🟢" if total > 0 else "🔴"
        net_str = f"+${total:.1f}M" if total > 0 else f"${total:.1f}M"
        lines.append(f"{net_emoji} Total: {net_str}")
        
        return "\n".join(lines)
        
    except requests.exceptions.RequestException as e:
        return f"Error fetching {ticker} data: {str(e)}"
    except Exception as e:
        return f"Error processing {ticker} data: {str(e)}"
