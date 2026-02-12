import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Patch sys.path to allow imports from back directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../back')))

from back.tools.technical_aggregator import get_all_technical_indicators
import json

# 模拟环境设置
os.environ["BINANCE_API_BASE"] = "https://api.binance.com"

print("="*60)
print("TEST: Technical Aggregator Output Format")
print("="*60)

try:
    print("Fetching technical data for BTC...")
    # 使用新默认参数：4h, 1d, 1w
    result = get_all_technical_indicators("BTC", output_format="compact", extra_timeframes="1d,1w")
    data = json.loads(result)
    btc_data = data.get("BTC", {})
    
    print(f"\nPrice: ${btc_data.get('price'):,.2f}")
    
    print("\n--- Timeframe Data Check ---")
    timeframes = btc_data.get("timeframes", {})
    for tf, tf_data in timeframes.items():
        print(f"\n[{tf}]")
        print(f"  EMA21: ${tf_data.get('ema21', 'N/A')}")
        print(f"  EMA55: ${tf_data.get('ema55', 'N/A')}")
        
        vegas = tf_data.get("vegas", {})
        if isinstance(vegas, dict):
            print(f"  Vegas ch1: {vegas.get('channel1')}")
            print(f"  Vegas ch2: {vegas.get('channel2')}")
            print(f"  Vegas ch3: {vegas.get('channel3')}")
        else:
            print(f"  Vegas (Old format): {vegas}")

    print("\n--- Key Levels Check ---")
    levels = btc_data.get("levels", {})
    
    support = levels.get("nearest_support")
    if support:
        print(f"Nearest Support: ${support.get('price')} ({support.get('dist_pct')}%) [{support.get('source')}]")
        
    resistance = levels.get("nearest_resistance")
    if resistance:
        print(f"Nearest Resistance: ${resistance.get('price')} ({resistance.get('dist_pct')}%) [{resistance.get('source')}]")
        
    print("\n--- Confluence Zones ---")
    confluence = levels.get("confluence_zones", [])
    if confluence:
        for zone in confluence[:3]:
            print(f"Zone: ${zone.get('price')} ({zone.get('dist_pct')}%) - {zone.get('indicators')}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
