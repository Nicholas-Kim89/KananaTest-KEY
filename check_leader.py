import sqlite3
import json
conn = sqlite3.connect('workprogress.db')
conn.row_factory = sqlite3.Row
divisions = [dict(t) for t in conn.execute("SELECT * FROM divisions").fetchall()]
with open('divisions_dump.json', 'w', encoding='utf-8') as f:
    json.dump(divisions, f, ensure_ascii=False, indent=2)
