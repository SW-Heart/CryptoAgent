import os
import sqlite3
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    print("Error: DB_URL not found in .env")
    exit(1)

# SQLite 数据库路径列表
SQLITE_DBS = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tmp', 'test.db'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tmp', 'price_alerts.db')
]

# 类型映射: SQLite -> Postgres
TYPE_MAPPING = {
    'INTEGER': 'INTEGER',
    'INT': 'INTEGER',
    'REAL': 'DOUBLE PRECISION',
    'FLOAT': 'DOUBLE PRECISION',
    'TEXT': 'TEXT',
    'BLOB': 'BYTEA',
    'VARCHAR': 'TEXT',
    'DATETIME': 'TIMESTAMP',
    'timestamp': 'TIMESTAMP',
    'BOOLEAN': 'BOOLEAN'
}

def get_pg_connection():
    return psycopg2.connect(DB_URL)

def migrate_db(sqlite_path):
    if not os.path.exists(sqlite_path):
        print(f"Skipping {sqlite_path} (not found)")
        return

    print(f"\n--- Migrating {os.path.basename(sqlite_path)} ---")
    
    # 连接 SQLite
    sq_conn = sqlite3.connect(sqlite_path)
    sq_cursor = sq_conn.cursor()
    
    # 连接 Postgres
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    # 获取所有表
    sq_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = sq_cursor.fetchall()
    
    for (table_name,) in tables:
        if table_name.startswith('sqlite_'):
            continue
            
        print(f"Migrating table: {table_name}...")
        
        # 获取表结构
        sq_cursor.execute(f"PRAGMA table_info({table_name})")
        columns = sq_cursor.fetchall()
        
        # 构建 CREATE TABLE 语句
        create_cols = []
        col_names = []
        bool_col_indices = set()
        
        for idx, col in enumerate(columns):
            cid, name, type_name, notnull, dflt_value, pk = col
            pg_type = TYPE_MAPPING.get(type_name.upper(), 'TEXT')
            
            # 记录布尔类型的列索引
            if type_name.upper() == 'BOOLEAN':
                bool_col_indices.add(idx)
            
            # 处理自增主键
            if pk and type_name.upper() in ('INTEGER', 'INT'):
                col_def = f'"{name}" SERIAL PRIMARY KEY'
            else:
                col_def = f'"{name}" {pg_type}'
                if pk:
                    col_def += " PRIMARY KEY"
            
            create_cols.append(col_def)
            col_names.append(name)
            
        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(create_cols)});'
        
        try:
            pg_cursor.execute(create_sql)
            pg_conn.commit()
        except Exception as e:
            print(f"  Error creating table {table_name}: {e}")
            pg_conn.rollback()
            continue
            
        # 迁移数据
        sq_cursor.execute(f'SELECT * FROM "{table_name}"')
        rows = sq_cursor.fetchall()
        
        if not rows:
            print("  No data to migrate.")
            continue
            
        # 处理数据转换 (主要是 Boolean: 1/0 -> True/False)
        converted_rows = []
        for row in rows:
            new_row = list(row)
            for idx in bool_col_indices:
                val = new_row[idx]
                if val is not None:
                    new_row[idx] = bool(val)
            converted_rows.append(tuple(new_row))
            
        insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, col_names)),
            sql.SQL(', ').join(sql.Placeholder() * len(col_names))
        )
        
        try:
            # 批量插入
            pg_cursor.executemany(insert_sql, converted_rows)
            pg_conn.commit()
            print(f"  Migrated {len(converted_rows)} rows.")
        except Exception as e:
            print(f"  Error inserting data for {table_name}: {e}")
            pg_conn.rollback()
            
    sq_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    if not os.getenv("DB_URL"):
        print("Please set DB_URL in .env first")
    else:
        try:
            for db_path in SQLITE_DBS:
                migrate_db(db_path)
            print("\nMigration Complete!")
        except Exception as e:
            print(f"\nMigration Failed: {e}")
