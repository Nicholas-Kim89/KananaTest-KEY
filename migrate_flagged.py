"""progress_logs 테이블에 is_flagged 컬럼 추가 마이그레이션"""
import sqlite3

DB_PATH = 'workprogress.db'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 컬럼 존재 여부 확인
    cols = [row[1] for row in cursor.execute("PRAGMA table_info(progress_logs)").fetchall()]
    if 'is_flagged' not in cols:
        cursor.execute("ALTER TABLE progress_logs ADD COLUMN is_flagged INTEGER DEFAULT 0")
        conn.commit()
        print("✅ is_flagged 컬럼이 progress_logs 테이블에 추가되었습니다.")
    else:
        print("ℹ️ is_flagged 컬럼이 이미 존재합니다.")

    conn.close()

if __name__ == '__main__':
    migrate()
