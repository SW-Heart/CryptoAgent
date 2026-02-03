
import os
import sys

# Add parent directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_connection

def cleanup_testnet_keys():
    """Delete all user API keys where is_testnet is True."""
    print("Connecting to database...")
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check count before deleting
            cursor.execute("SELECT COUNT(*) FROM user_binance_keys WHERE is_testnet = TRUE")
            count = cursor.fetchone()[0]
            print(f"Found {count} testnet API key records.")
            
            if count > 0:
                print("Deleting records...")
                cursor.execute("DELETE FROM user_binance_keys WHERE is_testnet = TRUE")
                deleted = cursor.rowcount
                conn.commit()
                print(f"Successfully deleted {deleted} records.")
                
                # Also verify if any users need trading status disabled? 
                # The prompt just said "DELETE FROM ...", so we stick to that.
                # Disabling trading status might be aggressive if they have other keys (though unlikely)
                
            else:
                print("No records to delete.")
                
        conn.close()
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    cleanup_testnet_keys()
