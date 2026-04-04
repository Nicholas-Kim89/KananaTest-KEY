"""
진척 로그 및 댓글에 updated_at 컬럼 추가 마이그레이션
"""
import sqlite3

DB = 'workprogress.db'

conn = sqlite3.connect(DB)
c = conn.cursor()

# progress_logs 에 updated_at 추가
c.execute("PRAGMA table_info(progress_logs)")
col_names = [row[1] for row in c.fetchall()]
if 'updated_at' not in col_names:
    c.execute("ALTER TABLE progress_logs ADD COLUMN updated_at TEXT")
    print("progress_logs: updated_at 컬럼 추가됨")
else:
    print("progress_logs: updated_at 컬럼 이미 존재")

# comments 에 updated_at 추가
c.execute("PRAGMA table_info(comments)")
col_names = [row[1] for row in c.fetchall()]
if 'updated_at' not in col_names:
    c.execute("ALTER TABLE comments ADD COLUMN updated_at TEXT")
    print("comments: updated_at 컬럼 추가됨")
else:
    print("comments: updated_at 컬럼 이미 존재")

conn.commit()
conn.close()
print("마이그레이션 완료!")
