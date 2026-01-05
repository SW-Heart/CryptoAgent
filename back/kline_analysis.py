"""
K 线图分析工具
使用 CHART-IMG API 生成 TradingView 图表，调用视觉 LLM 分析形态
"""
import os
import requests
import base64
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# CHART-IMG API 端点
CHARTIMG_API_V1 = "https://api.chart-img.com/v1/tradingview/advanced-chart"


def get_chart_image(symbol: str, interval: str = "D") -> tuple:
    """
    使用 CHART-IMG API 生成 TradingView 图表
    
    Args:
        symbol: 币种符号 (如 BTC, ETH)
        interval: 时间周期 (1, 5, 15, 30, 60, 120, 240, D, W, M)
    
    Returns:
        (base64_image, image_url) 或 (None, error_message)
    """
    api_key = os.getenv("CHARTIMG_API_KEY", "")
    
    if not api_key:
        return None, "❌ 未配置 CHARTIMG_API_KEY 环境变量"
    
    # 构建 TradingView 符号格式
    tv_symbol = f"BINANCE:{symbol.upper()}USDT"
    
    # CHART-IMG interval 格式映射
    interval_map = {
        "1": "1",      # 1分钟
        "5": "5",      # 5分钟
        "15": "15",    # 15分钟
        "30": "30",    # 30分钟
        "60": "1h",    # 1小时
        "120": "2h",   # 2小时
        "240": "4h",   # 4小时
        "D": "1d",     # 日线
        "W": "1w",     # 周线
        "M": "1M",     # 月线
    }
    api_interval = interval_map.get(interval, "1d")
    
    # 技术指标配置
    # 维加斯通道核心：EMA 144, 169, 288, 338, 576, 676
    # 加上 EMA 55 和基础均线
    studies = [
        "EMA:21",      # 短期趋势
        "EMA:55",      # 用户指定
        "EMA:144",     # 维加斯通道 - 内轨
        "EMA:169",     # 维加斯通道 - 内轨
        "EMA:288",     # 维加斯通道 - 中轨
        "EMA:338",     # 维加斯通道 - 中轨  
        "EMA:576",     # 维加斯通道 - 外轨
        "EMA:676",     # 维加斯通道 - 外轨
        "RSI",         # RSI 指标
        "MACD",        # MACD 指标
    ]
    
    # 构建请求 URL (width/height 限制: 320-800)
    params = {
        "key": api_key,
        "symbol": tv_symbol,
        "interval": api_interval,
        "theme": "dark",
        "width": 800,
        "height": 600,
    }
    
    # 添加指标参数
    url = CHARTIMG_API_V1 + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
    for study in studies:
        url += f"&studies={study}"
    
    try:
        resp = requests.get(url, timeout=30)
        
        if resp.status_code == 200:
            image_b64 = base64.b64encode(resp.content).decode()
            return image_b64, url
        else:
            return None, f"API 错误 ({resp.status_code}): {resp.text[:200]}"
            
    except Exception as e:
        return None, f"请求失败: {str(e)}"


def analyze_chart_with_vision(image_base64: str, symbol: str, interval: str) -> str:
    """
    使用视觉 LLM 分析 K 线图（通过 TTAPI 中转）
    
    Args:
        image_base64: Base64 编码的图片
        symbol: 币种符号
        interval: 时间周期
    
    Returns:
        AI 分析结果
    """
    # 使用 TTAPI 中转端点
    api_url = "https://api.ttapi.io/v1/chat/completions"
    api_key = os.getenv("TT_API_KEY")
    
    if not api_key:
        return "❌ 未配置 TT_API_KEY 环境变量"
    
    # 周期名称映射
    interval_names = {
        "1": "1分钟", "5": "5分钟", "15": "15分钟", "30": "30分钟",
        "60": "1小时", "120": "2小时", "240": "4小时",
        "D": "日线", "W": "周线", "M": "月线"
    }
    interval_name = interval_names.get(interval, interval)
    
    prompt = f"""你是一位专业的加密货币技术分析师。请分析这张 {symbol} {interval_name} K 线图。

图表包含以下指标：
- 维加斯通道 (EMA 144/169, 288/338, 576/676)
- EMA 21 (短期趋势)
- EMA 55 (中期趋势)
- RSI 指标
- MACD 指标

请从以下几个方面进行分析：

1. **趋势判断**：当前处于上升/下降/横盘趋势？
2. **维加斯通道分析**：价格相对于各轨道的位置，是否有突破或回踩信号？
3. **均线排列**：多头排列/空头排列/缠绕？
4. **关键价位**：识别重要的支撑和阻力位
5. **形态识别**：是否存在头肩顶/底、双顶/底、三角形、旗形等形态？
6. **RSI/MACD 信号**：超买超卖、背离、金叉死叉等
7. **交易建议**：基于以上分析给出操作建议

请用简洁的中文回答，重点突出关键信息。"""

    headers = {
        "Content-Type": "application/json",
        "TT-API-KEY": api_key
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{image_base64}",
                    "detail": "high"
                }}
            ]
        }],
        "max_tokens": 1500,
        "temperature": 0.3
    }

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
        
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            return f"❌ API 错误 ({resp.status_code}): {resp.text[:200]}"
        
    except Exception as e:
        return f"❌ AI 分析失败: {str(e)}"


def analyze_kline(symbol: str = "BTC", intervals: str = "D") -> str:
    """
    分析 K 线图形态 - Agent 工具函数
    
    使用 CHART-IMG 生成包含维加斯通道、EMA55 等指标的 TradingView 图表，
    然后调用 GPT-4o-mini 进行视觉分析，识别趋势、形态和交易信号。
    
    Args:
        symbol: 币种符号 (如 BTC, ETH, SOL, DOGE)
        intervals: 时间周期，逗号分隔可分析多周期
                   支持: 1, 5, 15, 30, 60, 120, 240, D, W, M
                   示例: "D" 或 "240,D,W"
    
    Returns:
        多周期 K 线技术分析报告
    """
    symbol = symbol.upper().strip()
    interval_list = [i.strip() for i in intervals.split(",")]
    
    # 验证周期参数
    valid_intervals = {"1", "5", "15", "30", "60", "120", "240", "D", "W", "M"}
    interval_list = [i for i in interval_list if i in valid_intervals]
    
    if not interval_list:
        return "❌ 无效的时间周期参数，支持: 1, 5, 15, 30, 60, 120, 240, D, W, M"
    
    # 周期名称映射
    interval_names = {
        "1": "1分钟", "5": "5分钟", "15": "15分钟", "30": "30分钟",
        "60": "1小时", "120": "2小时", "240": "4小时",
        "D": "日线", "W": "周线", "M": "月线"
    }
    
    report = f"📊 {symbol} K 线技术分析\n"
    report += "=" * 50 + "\n"
    report += "📈 指标：维加斯通道 | EMA 21/55 | RSI | MACD\n"
    report += "=" * 50 + "\n\n"
    
    for interval in interval_list:
        interval_name = interval_names.get(interval, interval)
        
        # 获取图表
        image_b64, result = get_chart_image(symbol, interval)
        
        if not image_b64:
            report += f"### ⏱ {interval_name}\n❌ 图表获取失败: {result}\n\n"
            continue
        
        # AI 分析
        analysis = analyze_chart_with_vision(image_b64, symbol, interval)
        
        report += f"### ⏱ {interval_name}\n\n{analysis}\n\n"
        report += "-" * 50 + "\n\n"
    
    return report.strip()


# 导出给 Agent 使用
__all__ = ["analyze_kline"]
