import sqlite3
from multiprocessing import Process
import time

def writer(i):
    conn = sqlite3.connect('workprogress.db')
    try:
        conn.execute("INSERT INTO comments (progress_id, author_email, author_name, content) VALUES (1, 'test', 'test', ?)", (f"test{i}",))
        conn.commit()
        print(f"Writer {i} done")
    except Exception as e:
        print(f"Writer {i} error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    processes = []
    for i in range(20):
        p = Process(target=writer, args=(i,))
        processes.append(p)
        p.start()
    for p in processes:
        p.join()
