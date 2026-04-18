import sys
import os
import json

# Setup path
sys.path.append("/Users/sunshuwen/AI_code/cryptoquant/server")

from app.services.workspace_service import list_workspaces, list_trader_instances
from tools.exchange_trading_tools import get_trader_instance, get_trading_client

# Find user ID
db_user_id = "497b46fa-67c4-44d6-a81b-21f45fe4f2e5" # from previous chats

# get client
client, err = get_trading_client(db_user_id)
if err:
    print(f"Error getting client: {err}")
    sys.exit(1)

print(f"Client exchange: {client.get_exchange_name()}")

try:
    print("\n--- Testing get_trade_history(BTCUSDT) ---")
    trades = client.get_trade_history("BTCUSDT", limit=10)
    print(f"Trades count: {len(trades)}")
    if trades:
        print(f"First trade: {json.dumps(trades[0], indent=2)}")
except Exception as e:
    print(f"Error in trade history: {e}")

try:
    print("\n--- Testing get_trade_history(ETHUSDT) ---")
    trades = client.get_trade_history("ETHUSDT", limit=10)
    print(f"Trades count: {len(trades)}")
    if trades:
        print(f"First trade: {json.dumps(trades[0], indent=2)}")
except Exception as e:
    print(f"Error in trade history: {e}")

try:
    print("\n--- Testing get_income_history() ---")
    income = client.get_income_history(limit=10)
    print(f"Income count: {len(income)}")
    if income:
        print(f"First income: {json.dumps(income[0], indent=2)}")
except Exception as e:
    print(f"Error in income history: {e}")

