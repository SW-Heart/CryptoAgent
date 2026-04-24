import sys
import os

sys.path.append("/Users/sunshuwen/AI_code/cryptoquant/server")
from app.services.workspace_service import list_workspaces
from tools.trading._client import _get_trading_client
import json

workspaces = list_workspaces()
for w in workspaces:
    for acct in w.get("exchange_accounts", []):
        if acct["exchange"] == "okx":
            user_id = str(acct["id"])
            client, err = _get_trading_client(user_id)
            if err:
                continue
                
            print(f"\n==== Testing User: {user_id} ====")
            
            try:
                print("--- Testing get_trade_history(BTCUSDT) without start_time ---")
                trades = client.get_trade_history("BTCUSDT", limit=10)
                print(f"Trades count: {len(trades)}")
                if trades:
                    print(f"First trade keys: {list(trades[0].keys())}")
            except Exception as e:
                print(f"Error in trade history: {e}")

            try:
                print("--- Testing get_income_history() ---")
                income = client.get_income_history(limit=10)
                print(f"Income count: {len(income)}")
                if income:
                    print(f"First income keys: {list(income[0].keys())}")
            except Exception as e:
                print(f"Error in income history: {e}")
            sys.exit(0)
