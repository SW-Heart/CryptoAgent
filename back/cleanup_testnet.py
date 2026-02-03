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

def cleanup_testnet_data():
    print("🧹 Starting cleanup for Mainnet deployment...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Delete Testnet API Keys
            print("1️⃣  Deleting testnet API keys...")
            cursor.execute("DELETE FROM user_binance_keys WHERE is_testnet = TRUE")
            print(f"   - Removed {cursor.rowcount} testnet key entries.")

            # 2. Clear Strategy Logs (Optional, but recommended for clean slate)
            print("2️⃣  Clearing strategy analysis logs...")
            cursor.execute("TRUNCATE TABLE strategy_logs")
            print("   - Strategy logs cleared.")
            
            # 3. Reset User Trading Status (force re-enable)
            # print("3️⃣  Resetting user trading status...")
            # cursor.execute("UPDATE user_trading_status SET is_trading_enabled = FALSE")
            # print(f"   - Disabled trading for {cursor.rowcount} users (require manual re-enable).")

            conn.commit()
            print("\n✅ Cleanup complete!")
            print("---------------------------------------------------")
            print("👉 Next Steps:")
            print("1. Update .env: Ensure BINANCE_TESTNET=false (or remove it)")
            print("2. Restart Backend: python main.py")
            print("3. Add Mainnet Keys: Go to UI -> Settings -> Configure Binance Keys")
            
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during cleanup: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    confirm = input("⚠️  This will DELETE all Testnet keys and logs. Continue? (y/n): ")
    if confirm.lower() == 'y':
        cleanup_testnet_data()
    else:
        print("Cancelled.")
