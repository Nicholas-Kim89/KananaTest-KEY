import sqlite3
import threading
import time

def setup_db():
    conn = sqlite3.connect('workprogress.db')
    conn.execute("PRAGMA journal_mode=delete;")
    conn.commit()
    conn.close()

def writer():
    conn = sqlite3.connect('workprogress.db')
    conn.execute("BEGIN EXCLUSIVE")
    time.sleep(6) # sleep for longer than default timeout (5s)
    conn.execute("INSERT INTO comments (progress_id, author_email, author_name, content) VALUES (1, 'test', 'test', 'test')")
    conn.commit()
    conn.close()

def writer2():
    try:
        conn = sqlite3.connect('workprogress.db')
        conn.execute("INSERT INTO comments (progress_id, author_email, author_name, content) VALUES (1, 'test', 'test', 'test2')")
        conn.commit()
        conn.close()
        print("Writer 2 success")
    except Exception as e:
        print("Writer 2 error:", e)

def reader():
    try:
        conn = sqlite3.connect('workprogress.db')
        conn.execute("SELECT * FROM comments").fetchall()
        print("Reader success")
    except Exception as e:
        print("Reader error:", e)


setup_db()
t1 = threading.Thread(target=writer)
t2 = threading.Thread(target=reader)
t1.start()
time.sleep(1)
t2.start()
t1.join()
t2.join()
