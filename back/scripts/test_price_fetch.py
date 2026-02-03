
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.binance_trading_tools import binance_get_current_price

if __name__ == "__main__":
    print("Testing price fetch for BTC...")
    price = binance_get_current_price("BTC")
    print(f"Price: {price}")
