import sqlite3
conn = sqlite3.connect('workprogress.db')
c = conn.cursor()
print("=== progress_logs ===")
for row in c.execute("PRAGMA table_info(progress_logs)"):
    print(row)
print("=== comments ===")
for row in c.execute("PRAGMA table_info(comments)"):
    print(row)
print("=== items ===")
for row in c.execute("PRAGMA table_info(items)"):
    print(row)
conn.close()
