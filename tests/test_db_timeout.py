import sqlite3
import threading
import time

def writer():
    conn = sqlite3.connect('workprogress.db')
    cursor = conn.cursor()
    cursor.execute("BEGIN EXCLUSIVE")
    print("Writer locked")
    time.sleep(3)
    cursor.execute("UPDATE items SET status = '진행중' WHERE id = 1")
    conn.commit()
    conn.close()
    print("Writer done")

def reader():
    conn = sqlite3.connect('workprogress.db')
    try:
        conn.execute("SELECT * FROM items").fetchall()
        print("Reader success")
    except Exception as e:
        print(f"Reader error: {e}")
    conn.close()

t1 = threading.Thread(target=writer)
t2 = threading.Thread(target=reader)

t1.start()
time.sleep(0.5)
t2.start()

t1.join()
t2.join()
