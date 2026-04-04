import sqlite3
import os

db_path = 'workprogress.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("--- TABLES ---")
tables = [r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in tables:
    print(f"\n[{t}]")
    cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
    for c in cols:
        print(f"  {c['name']} ({c['type']})")
    
    # Check for foreign keys pointing to this table
    fk_list = conn.execute(f"PRAGMA foreign_key_list({t})").fetchall()
    if fk_list:
        print("  Foreign Keys:")
        for fk in fk_list:
            print(f"    {fk['from']} -> {fk['table']}({fk['to']})")

print("\n--- SCHEMA ---")
for t in tables:
    sql = conn.execute(f"SELECT sql FROM sqlite_master WHERE name='{t}'").fetchone()
    print(f"\n{t}: {sql['sql'] if sql else 'None'}")

conn.close()
