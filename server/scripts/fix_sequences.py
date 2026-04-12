
import os
import sys

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_connection

def fix_sequences():
    """Reset PostgreSQL sequences to max(id) for all tables"""
    print("Fixing PostgreSQL sequences...")
    
    tables_to_fix = [
        "daily_checkins",
        "credits_history",
        "strategy_logs",
        "orders",
        "positions",
        "virtual_wallet",
        "price_alerts",
        "daily_reports",
        "session_titles" # Check if this has serial? No, session_id is PK text usually. Checking code...
    ]
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        for table in tables_to_fix:
            try:
                # Check if table exists and has an 'id' column
                cursor.execute(f"""
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' AND column_name = 'id'
                """)
                if not cursor.fetchone():
                    print(f"Skipping {table} (no 'id' column or table missing)")
                    continue
                
                # Check if id is a sequence (auto-increment)
                # PostgreSQL uses a specific naming convention or dependency.
                # Simplest way is to try to setval.
                
                # Construct query to reset sequence
                query = f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'), 
                        COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, 
                        false
                    );
                """
                cursor.execute(query)
                print(f"Successfully reset sequence for {table}")
                
            except Exception as e:
                # If sequence doesn't exist (e.g. integer primary key but not serial), it will fail safely
                print(f"Skipping {table}: {e}")
                conn.rollback()
                continue
                
        conn.commit()
    conn.close()
    print("Sequence fix complete.")

if __name__ == "__main__":
    fix_sequences()
