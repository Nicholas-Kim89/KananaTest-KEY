import sqlite3
import threading

def write_db():
    try:
        conn = sqlite3.connect('workprogress.db')
        conn.execute("INSERT INTO comments (progress_id, author_email, author_name, content) VALUES (1, 'test', 'test', 'test')")
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error:", e)

threads = [threading.Thread(target=write_db) for _ in range(50)]
for t in threads: t.start()
for t in threads: t.join()
