import sqlite3

def migrate():
    conn = sqlite3.connect('workprogress.db')
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notification_reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                ref_type TEXT NOT NULL, /* 'log' or 'comment' */
                ref_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_email, ref_type, ref_id)
            )
        ''')
        conn.commit()
        print("Migration successful: notification_reads table created.")
    except Exception as e:
        print("Error during migration:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
