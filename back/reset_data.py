import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("❌ Error: DB_URL not found in environment variables.")
        exit(1)
    return psycopg2.connect(db_url)

def reset_data():
    conn = get_db_connection()
    try:
        print("\n⚠️  WARNING: This script will delete data from your Mainnet database.")
        print("    It is designed to clear 'test data' (logs, virtual history) generated during testing.")
        print("    It will NOT delete your API Keys.\n")

        with conn.cursor() as cursor:
            # 1. Strategy Logs
            if input("1️⃣  Clear Strategy Logs (strategy_logs)? [y/N]: ").lower() == 'y':
                cursor.execute("TRUNCATE TABLE strategy_logs")
                print("   ✅ Strategy logs cleared.")
            else:
                print("   Skipped.")

            # 2. Virtual Trading Data & History
            if input("2️⃣  Clear Trading History (positions, orders, sync_state)? [y/N]: ").lower() == 'y':
                # 修正表名：positions, orders (非 virtual_前缀)
                # 同时也清除 binance_sync_state (正式网统计数据)
                tables = ["orders", "positions", "virtual_wallet", "binance_sync_state"]
                for table in tables:
                    try:
                        cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
                        print(f"   Table {table} cleared.")
                    except psycopg2.errors.UndefinedTable:
                        conn.rollback() # 回滚以继续
                        print(f"   ⚠️  Table {table} not found, skipping.")
                        # 重新开启事务
                        cursor.execute("SELECT 1") 
                    except Exception as e:
                        conn.rollback()
                        print(f"   ❌ Error clearing {table}: {e}")
                        cursor.execute("SELECT 1")
                print("   ✅ Trading data cleared.")
            else:
                print("   Skipped.")

            # 3. Price Alerts
            if input("3️⃣  Clear Price Alerts (price_alerts)? [y/N]: ").lower() == 'y':
                cursor.execute("TRUNCATE TABLE price_alerts")
                print("   ✅ Price alerts cleared.")
            else:
                print("   Skipped.")
            
            # 4. API Keys (Protection)
            print("4️⃣  API Keys (user_binance_keys) will remain UNTOUCHED.")

            if input("\nCommit these changes? (Type 'CONFIRM' to execute): ") == 'CONFIRM':
                conn.commit()
                print("\n🚀 Database reset complete!")
            else:
                conn.rollback()
                print("\n❌ Operation cancelled. No changes made.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_data()
