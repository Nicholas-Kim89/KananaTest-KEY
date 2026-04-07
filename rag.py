import sqlite3
import os
import chromadb

DB_PATH = 'workprogress.db'
CHROMA_PATH = './chroma_db'
COLLECTION_NAME = 'workprogress_collection'
GEMINI_API_KEY = 'AIzaSyAf1YQMQU6fy-g-Q8HzhJboeA2g_3j86Lw'

# Chroma DB 클라이언트 초기화
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
except Exception as e:
    print(f"Error initializing ChromaDB: {e}")
    collection = None

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def sync_all():
    """초기 데이터 동기화"""
    if not collection: return
    # 이미 데이터가 있으면 스킵하거나 옵셔널하게 리셋 가능
    if collection.count() > 0:
        return

    conn = get_db()
    
    # 1. 아이템 데이터
    items = conn.execute('''
        SELECT i.*, t.name as team_name, t.division_id 
        FROM items i JOIN teams t ON i.team_id = t.id
    ''').fetchall()
    
    docs, metadatas, ids = [], [], []
    for item in items:
        docs.append(f"[아이템] 팀: {item['team_name']}\n제목: {item['title']}\n과제 목표: {item['subtitle']}\n상태: {item['status']}\n기한: {item['due_date']}\n내용: {item['description']}")
        metadatas.append({
            "doc_type": "item",
            "item_id": item['id'],
            "team_id": item['team_id'],
            "division_id": item['division_id'],
            "author": item['created_by'] or "",
            "created_at": str(item['created_at'])
        })
        ids.append(f"item_{item['id']}")
        
    # 2. 진척 사항 데이터
    logs = conn.execute('''
        SELECT p.*, i.title, i.team_id, t.division_id, t.name as team_name
        FROM progress_logs p 
        JOIN items i ON p.item_id = i.id
        JOIN teams t ON i.team_id = t.id
    ''').fetchall()
    
    for log in logs:
        docs.append(f"[진척일지] 팀: {log['team_name']}\n작성자: {log['member_name']}\n상위아이템: {log['title']}\n내용: {log['content']}")
        metadatas.append({
            "doc_type": "progress_log",
            "item_id": log['item_id'],
            "team_id": log['team_id'],
            "division_id": log['division_id'],
            "author": log['member_name'],
            "created_at": str(log['created_at'])
        })
        ids.append(f"log_{log['id']}")
        
    if docs:
        batch_size = 100
        for i in range(0, len(docs), batch_size):
            collection.upsert(
                documents=docs[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )
            
    conn.close()

def upsert_item(item_id):
    if not collection: return
    conn = get_db()
    item = conn.execute('''
        SELECT i.*, t.name as team_name, t.division_id 
        FROM items i JOIN teams t ON i.team_id = t.id
        WHERE i.id = ?
    ''', (item_id,)).fetchone()
    if item:
        doc = f"[아이템] 팀: {item['team_name']}\n제목: {item['title']}\n과제 목표: {item['subtitle']}\n상태: {item['status']}\n기한: {item['due_date']}\n내용: {item['description']}"
        meta = {
            "doc_type": "item", "item_id": item['id'], "team_id": item['team_id'],
            "division_id": item['division_id'], "author": item['created_by'] or "",
            "created_at": str(item['created_at'])
        }
        try:
            collection.upsert(documents=[doc], metadatas=[meta], ids=[f"item_{item['id']}"])
        except Exception as e:
            print("chromadb upsert error:", e)
    conn.close()

def delete_item_from_rag(item_id):
    if not collection: return
    try:
        collection.delete(where={"item_id": item_id})  # 진척사항도 같이 item_id로 삭제
    except:
        pass

def upsert_progress(log_id):
    if not collection: return
    conn = get_db()
    log = conn.execute('''
        SELECT p.*, i.title, i.team_id, t.division_id, t.name as team_name
        FROM progress_logs p 
        JOIN items i ON p.item_id = i.id
        JOIN teams t ON i.team_id = t.id
        WHERE p.id = ?
    ''', (log_id,)).fetchone()
    if log:
        doc = f"[진척일지] 팀: {log['team_name']}\n작성자: {log['member_name']}\n상위아이템: {log['title']}\n내용: {log['content']}"
        meta = {
            "doc_type": "progress_log", "item_id": log['item_id'], "team_id": log['team_id'],
            "division_id": log['division_id'], "author": log['member_name'],
            "created_at": str(log['created_at'])
        }
        try:
            collection.upsert(documents=[doc], metadatas=[meta], ids=[f"log_{log['id']}"])
        except Exception as e:
            print("chromadb upsert error:", e)
    conn.close()

def delete_progress_from_rag(log_id):
    if not collection: return
    try:
        collection.delete(ids=[f"log_{log_id}"])
    except:
        pass

def query_chatbot(query_text, role, user_email, list_of_history_dicts, n_results=50):
    """
    history: [{'role': 'user', 'text': '안녕'}, {'role': 'model', 'text': '네 안녕...'}]
    """
    if not collection: 
        return "현재 RAG 검색 시스템이 초기화되지 않았습니다."
    
    conn = get_db()
    
    # 환경 컨텍스트 변수
    user_name = ""
    my_team_name = ""
    my_division_name = ""
    my_team_members_str = ""
    
    my_team_id, my_division_id = None, None
    
    u_info = conn.execute('SELECT name FROM users WHERE email=?', (user_email,)).fetchone()
    if u_info: user_name = u_info['name']

    if role == '팀장':
        t = conn.execute('SELECT * FROM teams WHERE leader_email=?', (user_email,)).fetchone()
        if t:
            my_team_id = t['id']
            my_division_id = t['division_id']
            my_team_name = t['name']
    elif role == '담당장':
        d = conn.execute('SELECT * FROM divisions WHERE leader_email=?', (user_email,)).fetchone()
        if d:
            my_division_id = d['id']
            my_division_name = d['name']
    else:
        m = conn.execute('SELECT * FROM members WHERE email=?', (user_email,)).fetchone()
        if m:
            my_team_id = m['team_id']
            t2 = conn.execute('SELECT division_id, name FROM teams WHERE id=?', (my_team_id,)).fetchone()
            if t2:
                my_division_id = t2['division_id']
                my_team_name = t2['name']
                
    if my_team_id:
        m_list = conn.execute('SELECT name, position FROM members WHERE team_id=?', (my_team_id,)).fetchall()
        my_team_members_str = ", ".join([f"{row['name']} {row['position']}" for row in m_list])

    if not my_division_name and my_division_id:
        d_info = conn.execute('SELECT name FROM divisions WHERE id=?', (my_division_id,)).fetchone()
        if d_info:
            my_division_name = d_info['name']
            
    conn.close()

    # ACL 기반 필터 적용
    where_filter = {}
    if role == '팀원' and my_team_id:
        where_filter = {"team_id": my_team_id}
    elif role in ['팀장', '담당장'] and my_division_id:
        where_filter = {"division_id": my_division_id}
        
    try:
        if where_filter:
            results = collection.query(query_texts=[query_text], n_results=n_results, where=where_filter)
        else:
            results = collection.query(query_texts=[query_text], n_results=n_results)
    except Exception as e:
        return f"검색 중 오류 발생: {e}"
        
    context_text = ""
    if results and results['documents'] and len(results['documents'][0]) > 0:
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        
        for doc, meta in zip(docs, metas):
            cur_doc = doc
            # 담당장: 마스킹 없음
            # 팀원: 어차피 자기팀 문서만 나옴
            # 팀장: 자기 담당안의 다른 팀 문서는 이름을 타 팀원으로 마스킹
            if role == '팀장' and str(meta.get('team_id')) != str(my_team_id):
                author_name = meta.get('author', '')
                if author_name and author_name in cur_doc:
                    cur_doc = cur_doc.replace(author_name, "타 팀원")
                cur_doc = cur_doc.replace("작성자:", "작성자: 타 팀원 (") # Extra layer of masking
            
            context_text += f"---\n{cur_doc}\n"
            
    # Gemini SDK 사용
    from google import genai
    from google.genai import types
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    
    system_prompt = f"""당신은 사내 진척 관리 시스템의 전문 AI 챗봇입니다.
접속한 사용자 정보:
- 사용자: {user_name} (권한: {role})
- 소속 담당: {my_division_name}
- 소속 팀: {my_team_name if my_team_name else '없음'}
- 소속 팀원: {my_team_members_str if my_team_members_str else '없음'}

당신은 위 사용자 정보와 소속을 정확히 인지하고 있습니다. 사용자가 '우리 팀', '우리 담당'이라고 하면 위 소속을 의미합니다.
사용자가 특정 팀원을 물어보면 '소속 팀원' 목록에 있는지 확인하세요.
아래 제공된 [검색된 회사 데이터]를 기반으로 사용자의 질문에 대답하세요. 데이터에 없는 내용은 지어내지 마세요.
"""
    if role == '팀장':
         system_prompt += "\n주의: 사용자는 팀장이며 타 팀 데이터 열람 시 담당자 구체 정보 제공이 제한되어 있습니다. 검색결과에 '타 팀원'으로 표시된 부분은 개인정보 보호를 위해 그대로 '타 팀 또는 다른 사람'이라고 칭하세요."
         
    prompt = f"[검색된 회사 데이터]\n{context_text}\n\n[사용자 최신 질문]: {query_text}"
    
    # 멀티턴 기록 구성 (Gemini)
    history = []
    # 시스템 프롬프트는 config로 넘어감
    for h in list_of_history_dicts:
        role_type = 'user' if h['role'] == 'user' else 'model'
        history.append(types.Content(role=role_type, parts=[types.Part.from_text(text=h.get('text', ''))]))
        
    try:
        chat = gemini_client.chats.create(
            model='gemini-2.5-flash',
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3
            ),
            history=history
        )
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"응답 생성 중 오류가 발생했습니다: {str(e)}"
