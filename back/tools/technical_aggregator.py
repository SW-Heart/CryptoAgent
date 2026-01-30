"""
Technical Analysis Aggregator Tool

This module aggregates various technical analysis tools into a single entry point
to reduce the number of tool calls required by the agent.
"""
from typing import Dict, Any, List
import json

# Import underlying technical analysis tools
from technical_analysis import (
    get_multi_timeframe_analysis,
    get_volume_analysis,
    get_volume_profile
)
from pattern_recognition import (
    get_trendlines,
    find_confluence_zones
)
from indicator_memory import get_indicator_reliability

def get_all_technical_indicators(
    symbols: str, 
    timeframe: str = "1d",
    extra_timeframes: str = "4h,1h",
    deep_analysis: bool = False
) -> str:
    """
    Get all technical indicators for one or more symbols in a single call.
    
    This tool aggregates:
    1. Multi-timeframe trend analysis (MA/EMA, MACD, etc.)
    2. Volume analysis (Volume profile, Volume/Price divergence)
    3. Pattern recognition (Trendlines, Channels)
    4. Confluence zones (Key levels, Fibs)
    5. Indicator reliability checking
    
    Args:
        symbols: Comma-separated list of symbols (e.g., "BTC,ETH,SOL") or single symbol ("BTC").
        timeframe: Primary analysis timeframe (default: "1d").
        extra_timeframes: Secondary timeframes for multi-period analysis (default: "4h,1h").
        deep_analysis: Whether to perform deep analysis (more computationally expensive).
        
    Returns:
        String containing structured reports for all requested symbols.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
    if not symbol_list:
        return "Error: No valid symbols provided."
        
    final_report = []
    
    for symbol in symbol_list:
        report_section = [f"\n{'='*40}"]
        report_section.append(f"📊 COMPREHENSIVE ANALYSIS: {symbol}")
        report_section.append(f"{'='*40}\n")
        
        try:
            # 1. Multi-Timeframe Analysis (The Core Trend)
            mta = get_multi_timeframe_analysis(symbol, timeframes=f"{timeframe},{extra_timeframes}", deep_analysis=deep_analysis)
            report_section.append("--- 1. TREND STRUCTURE (Multi-Timeframe) ---")
            if isinstance(mta, dict):
                # If it returns a dict, try to get a summary string or format it
                # Assuming get_multi_timeframe_analysis might return a dict or string based on existing code.
                # Looking at outline, it seems to return a report string usually, or we might need to verify.
                # Let's assume it returns a dict-like object or string. 
                # If existing code returns a huge dict, we might want to ask it to return text or format it here.
                # Based on 'technical_analysis.py' outline, it has score_to_text etc, implies it calculates things.
                # Let's verify existing usage. trading_agent.py used it as a tool, so it probably returns a string description
                # or the agent natively handles the dict. Tools usually return strings for LLMs.
                report_section.append(str(mta))
            else:
                report_section.append(str(mta))
            report_section.append("")

            # 2. Confluence Zones (Support/Resistance)
            confluence = find_confluence_zones(symbol, timeframe=timeframe)
            report_section.append("--- 2. CONFLUENCE ZONES (Support/Resistance) ---")
            report_section.append(str(confluence))
            report_section.append("")

            # 3. Volume Analysis
            vol = get_volume_analysis(symbol, timeframe=timeframe)
            report_section.append("--- 3. VOLUME ANALYSIS ---")
            report_section.append(str(vol))
            report_section.append("")

            # 4. Pattern / Trendlines
            patterns = get_trendlines(symbol, timeframes=timeframe)
            report_section.append("--- 4. PATTERNS & TRENDLINES ---")
            report_section.append(str(patterns))
            report_section.append("")

            # 5. Indicator Reliability
            reliability = get_indicator_reliability(symbol, timeframe=timeframe)
            report_section.append("--- 5. HISTORICAL RELIABILITY ---")
            report_section.append(str(reliability))
            
        except Exception as e:
            report_section.append(f"❌ Error analyzing {symbol}: {str(e)}")
            
        final_report.append("\n".join(report_section))
        
    return "\n\n".join(final_report)
