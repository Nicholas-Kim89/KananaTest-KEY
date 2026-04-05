import sqlite3

conn = sqlite3.connect('workprogress.db')
try:
    conn.execute('ALTER TABLE items ADD COLUMN extra_note TEXT DEFAULT ""')
    conn.commit()
    print('OK: extra_note 컬럼이 추가되었습니다.')
except Exception as e:
    print(f'오류 (이미 존재할 수 있음): {e}')
finally:
    conn.close()
