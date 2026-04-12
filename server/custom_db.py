import os
from agno.db.postgres import PostgresDb as PgDb
from dotenv import load_dotenv

load_dotenv()

class WalSqliteDb(PgDb):
    """
    Alias for PgDb to maintain compatibility with updated agent code.
    Connects to PostgreSQL using DB_URL in .env.
    """
    def __init__(self, db_file: str = None, session_table: str = "sessions", **kwargs):
        db_url = os.getenv("DB_URL")
        # 忽略 db_file, 使用环境变量中的 DB_URL
        # 将 session_table 映射为 PgDb 的 table_name
        
        super().__init__(db_url=db_url, session_table=session_table, db_schema="public", **kwargs)
