#!/usr/bin/env python3
"""
Test script for email service
Run from back/ directory: python test_email.py
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Print current SMTP config
print("=" * 50)
print("SMTP Configuration Check:")
print("=" * 50)
print(f"SMTP_HOST: {os.getenv('SMTP_HOST', 'NOT SET')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT', 'NOT SET')}")
print(f"SMTP_USER: {os.getenv('SMTP_USER', 'NOT SET')}")
print(f"SMTP_PASSWORD: {'*' * len(os.getenv('SMTP_PASSWORD', '')) if os.getenv('SMTP_PASSWORD') else 'NOT SET'}")
print(f"SMTP_FROM_NAME: {os.getenv('SMTP_FROM_NAME', 'NOT SET')}")
print("=" * 50)

# Test email service
from services.email_service import send_subscription_confirmation, send_daily_report_email, get_smtp_config

config = get_smtp_config()
print(f"\nget_smtp_config() returns:")
print(f"  host: {config['host']}")
print(f"  port: {config['port']}")
print(f"  user: {config['user']}")
print(f"  password: {'*' * len(config['password']) if config['password'] else 'NOT SET'}")
print(f"  from_name: {config['from_name']}")

# Ask for test email
test_email = input("\nEnter your email to test (or press Enter to skip): ").strip()

if test_email:
    print("\nSelect email type to test:")
    print("1. Subscription confirmation (订阅确认)")
    print("2. Daily report - Chinese (日报-中文)")
    print("3. Daily report - English (日报-英文)")
    choice = input("Enter choice (1/2/3): ").strip()
    
    if choice == "1":
        lang = input("Language (en/zh): ").strip() or "zh"
        print(f"\nSending subscription confirmation to {test_email}...")
        result = send_subscription_confirmation(test_email, lang)
    elif choice in ["2", "3"]:
        lang = "zh" if choice == "2" else "en"
        # Sample daily report content
        sample_content = """
### 📅 Alpha情报局 | 加密早报 [2026/01/02]

> 📌 **今日要点**: **BTC 在 98k 附近横盘整理，ETF 资金持续流入，AI 板块领涨**

#### 📊 市场脉搏
*   📈 **情绪**: 贪婪 (指数: 72)
*   💰 **BTC**: $98,150 (24h: +1.2%)
*   🔄 **ETF 资金**: BTC +$285M | ETH +$42M

#### ⚡ 隔夜头条
*   **MicroStrategy 再次增持**: 新增 2,530 BTC -> **持续买入信号，机构信心坚定**
*   **以太坊 Pectra 升级确认**: Q1 上线 -> **利好 ETH 生态，关注 L2 板块**

#### 🧭 趋势与点位
*   **BTC结构**: 上升旗形整理中
    *   🗝️ 关键位: 支撑 $96,500 | 阻力 $100,000
    *   📝 判词: 只要守住96k，多头结构依然完整。

#### 💡 Alpha 策略
*   **稳健**: 当前位置盈亏比极佳，可尝试在98k附近分批低吸，跌破96k止损。
""" if lang == "zh" else """
### 📅 Alpha Intelligence | Crypto Daily Brief [2026/01/02]

> 📌 **TL;DR**: **BTC consolidates near 98k amid strong ETF inflows; AI sector leads gains**

#### 📊 Market Pulse
*   📈 **Sentiment**: Greed (Index: 72)
*   💰 **BTC**: $98,150 (24h: +1.2%)
*   🔄 **ETF Flows**: BTC +$285M | ETH +$42M

#### ⚡ Overnight Headlines
*   **MicroStrategy adds more BTC**: +2,530 BTC -> **Bullish signal, institutional confidence remains strong**
*   **Ethereum Pectra upgrade confirmed**: Q1 launch -> **Bullish for ETH ecosystem, watch L2 sector**

#### 🧭 Trends & Levels
*   **BTC Structure**: Bullish flag consolidation
    *   🗝️ Key Levels: Support $96,500 | Resistance $100,000
    *   📝 Verdict: Structure remains bullish as long as 96k holds.

#### 💡 Alpha Strategy
*   **Balanced**: R/R excellent at current levels, consider scaling in near 98k, stop below 96k.
"""
        print(f"\nSending daily report ({lang}) to {test_email}...")
        result = send_daily_report_email(test_email, "2026-01-02", sample_content, "test-token-123", lang)
    else:
        print("Invalid choice")
        result = False
    
    print(f"Result: {result}")
    if result:
        print("✅ Email sent successfully! Check your inbox.")
    else:
        print("❌ Email sending failed. Check the error messages above.")
else:
    print("\nSkipping email test.")
