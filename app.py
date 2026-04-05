from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import json
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from google import genai
from google.genai import types
import rag

# Gemini 설정
GEMINI_API_KEY = 'AIzaSyAf1YQMQU6fy-g-Q8HzhJboeA2g_3j86Lw'
GEMINI_MODEL   = 'gemini-2.5-flash'
gemini_client  = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = 'super_secret_key'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            email = user['email']
            role = None
            
            # 조직도 매핑 체크
            if conn.execute('SELECT * FROM divisions WHERE leader_email = ?', (email,)).fetchone():
                role = '담당장'
            elif conn.execute('SELECT * FROM teams WHERE leader_email = ?', (email,)).fetchone():
                role = '팀장'
            elif conn.execute('SELECT * FROM members WHERE email = ?', (email,)).fetchone():
                role = '팀원'
                
            conn.close()
            
            if role:
                session['user_id'] = user_id
                session['email'] = email
                session['name'] = user['name']
                session['role'] = role
                return redirect(url_for('index'))
            else:
                flash('조직도에 배정되어 있지 않은 계정입니다. 로그인이 차단되었습니다.')
                return redirect(url_for('login'))
        else:
            conn.close()
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('새 비밀번호가 일치하지 않습니다.')
            return redirect(url_for('change_password'))
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        
        if user and check_password_hash(user['password_hash'], current_password):
            new_hash = generate_password_hash(new_password)
            conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, session['user_id']))
            conn.commit()
            flash('비밀번호가 성공적으로 변경되었습니다.')
            conn.close()
            return redirect(url_for('index'))
        else:
            conn.close()
            flash('현재 비밀번호가 틀립니다.')
            return redirect(url_for('change_password'))
            
    return render_template('change_password.html')

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/my-progress')
@login_required
def my_progress():
    return render_template('index.html', title='나의 진척 관리')

@app.route('/ai-summary')
@login_required
def ai_summary():
    conn  = get_db_connection()
    role  = session.get('role')
    email = session.get('email')

    my_team_id      = None
    my_items        = []   # 팀원/팀장 전용: 자기 팀의 아이템 목록
    available_teams = []
    items_by_team   = {}   # 담당장 전용: {team_id: [items]}

    if role == '팀원':
        # 팀원: 자신의 소속 팀 아이템만
        m = conn.execute('SELECT team_id FROM members WHERE email=?', (email,)).fetchone()
        if m:
            my_team_id = m['team_id']
            rows = conn.execute(
                'SELECT id, title, status, due_date FROM items WHERE team_id=? ORDER BY created_at DESC',
                (my_team_id,)
            ).fetchall()
            my_items = [dict(r) for r in rows]

    elif role == '팀장':
        # 팀장: 자기 팀 ID 및 소속 담당 내 모든 팀
        t = conn.execute('SELECT * FROM teams WHERE leader_email=?', (email,)).fetchone()
        if t:
            my_team_id = t['id']
            division_id = t['division_id']
            # 소속 담당 내 모든 팀 (자기 팀 제일 먼저)
            all_div_teams = conn.execute(
                '''SELECT * FROM teams WHERE division_id=? ORDER BY (id = ?) DESC, name ASC''',
                (division_id, my_team_id)
            ).fetchall()
            available_teams = [dict(t2) for t2 in all_div_teams]
            # 자기 팀의 아이템 목록
            rows = conn.execute(
                'SELECT id, title, status, due_date FROM items WHERE team_id=? ORDER BY created_at DESC',
                (my_team_id,)
            ).fetchall()
            my_items = [dict(r) for r in rows]

    else:
        # 담당장: 소속 담당 내 전체 팀
        d = conn.execute('SELECT * FROM divisions WHERE leader_email=?', (email,)).fetchone()
        division_id = d['id'] if d else None
        if division_id:
            available_teams = [dict(t) for t in conn.execute(
                'SELECT id, name FROM teams WHERE division_id=? ORDER BY name', (division_id,)
            ).fetchall()]
        else:
            available_teams = [dict(t) for t in conn.execute(
                'SELECT id, name FROM teams ORDER BY name'
            ).fetchall()]
        # 팀별 아이템 목록 (JS 동적 필터용)
        items_by_team = {}
        for team in available_teams:
            rows = conn.execute(
                'SELECT id, title, status, due_date FROM items WHERE team_id=? ORDER BY created_at DESC',
                (team['id'],)
            ).fetchall()
            items_by_team[team['id']] = [dict(r) for r in rows]

    conn.close()

    today    = datetime.now().date()
    week_ago = today - timedelta(days=7)

    return render_template('ai_summary.html',
                           title='AI 요약 보고서',
                           available_teams=available_teams,
                           my_team_id=my_team_id,
                           my_items=my_items,
                           items_by_team=items_by_team if role == '담당장' else {},
                           role=role,
                           default_start=week_ago.strftime('%Y-%m-%d'),
                           default_end=today.strftime('%Y-%m-%d'))


@app.route('/api/ai-summary', methods=['POST'])
@login_required
def api_ai_summary():
    """진척사항 + 댓글 데이터를 Gemini로 요약"""
    data       = request.get_json(force=True)
    team_id    = data.get('team_id', '')     # 팀장/담당장 전용
    item_id    = data.get('item_id', '')     # 팀원/팀장(자기팀) 전용
    start_date = data.get('start_date')
    end_date   = data.get('end_date')
    role       = session.get('role')
    email      = session.get('email')

    if not start_date or not end_date:
        return jsonify({'error': '기간을 선택해 주세요.'}), 400

    end_dt_incl = end_date + ' 23:59:59'
    start_dt    = start_date + ' 00:00:00'

    conn = get_db_connection()

    # 팀장의 자기 팀 ID 미리 조회
    leader_team_id = None
    if role == '팀장':
        t = conn.execute('SELECT id FROM teams WHERE leader_email=?', (email,)).fetchone()
        leader_team_id = t['id'] if t else None

    # ── 팀원: 특정 아이템 1개만 ──────────────────────────────────
    if role == '팀원':
        if not item_id:
            conn.close()
            return jsonify({'error': '요약할 아이템을 선택해 주세요.'}), 400
        m = conn.execute('SELECT team_id FROM members WHERE email=?', (email,)).fetchone()
        my_team_id = m['team_id'] if m else None
        item_check = conn.execute(
            'SELECT id FROM items WHERE id=? AND team_id=?', (item_id, my_team_id)
        ).fetchone()
        if not item_check:
            conn.close()
            return jsonify({'error': '해당 아이템에 접근 권한이 없습니다.'}), 403
        logs = conn.execute(
            '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                      t.name as team_name
               FROM progress_logs pl
               JOIN items i ON pl.item_id = i.id
               JOIN teams t ON i.team_id = t.id
               WHERE pl.item_id = ? AND pl.created_at BETWEEN ? AND ?
               ORDER BY pl.created_at ASC''',
            (item_id, start_dt, end_dt_incl)
        ).fetchall()
        team_name    = logs[0]['team_name'] if logs else None
        show_sources = True

    # ── 팀장: 팀 + 선택적 아이템 필터 ───────────────────────────
    elif role == '팀장':
        if not team_id:
            conn.close()
            return jsonify({'error': '팀을 선택해 주세요.'}), 400
        t = conn.execute('SELECT * FROM teams WHERE id=?', (team_id,)).fetchone()
        team_name = t['name'] if t else None
        is_own_team  = (str(team_id) == str(leader_team_id))
        show_sources = is_own_team

        if is_own_team and item_id:
            # 자기 팀 + 특정 아이템
            item_check = conn.execute(
                'SELECT id FROM items WHERE id=? AND team_id=?', (item_id, team_id)
            ).fetchone()
            if not item_check:
                conn.close()
                return jsonify({'error': '해당 아이템에 접근 권한이 없습니다.'}), 403
            logs = conn.execute(
                '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                          t.name as team_name
                   FROM progress_logs pl
                   JOIN items i ON pl.item_id = i.id
                   JOIN teams t ON i.team_id = t.id
                   WHERE pl.item_id = ? AND pl.created_at BETWEEN ? AND ?
                   ORDER BY pl.created_at ASC''',
                (item_id, start_dt, end_dt_incl)
            ).fetchall()
        else:
            # 자기 팀 모든 아이템 OR 다른 팀 전체
            logs = conn.execute(
                '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                          t.name as team_name
                   FROM progress_logs pl
                   JOIN items i ON pl.item_id = i.id
                   JOIN teams t ON i.team_id = t.id
                   WHERE i.team_id = ? AND pl.created_at BETWEEN ? AND ?
                   ORDER BY pl.created_at ASC''',
                (team_id, start_dt, end_dt_incl)
            ).fetchall()

    # ── 담당장: 팀 선택 + 선택적 아이템 필터 ─────────────────
    else:
        show_sources = True   # 담당장은 출처 표시 (접기/펼치기)
        team_name    = None
        # 소속 담당 ID 확인 (권한 검증용)
        d = conn.execute('SELECT id FROM divisions WHERE leader_email=?', (email,)).fetchone()
        division_id  = d['id'] if d else None
        allowed_team_ids = set()
        if division_id:
            rows = conn.execute('SELECT id FROM teams WHERE division_id=?', (division_id,)).fetchall()
            allowed_team_ids = {str(r['id']) for r in rows}

        if team_id:
            # 선택한 팀이 담당 소속인지 안전검증
            if division_id and str(team_id) not in allowed_team_ids:
                conn.close()
                return jsonify({'error': '해당 팀에 대한 접근 권한이 없습니다.'}), 403
            t = conn.execute('SELECT * FROM teams WHERE id=?', (team_id,)).fetchone()
            if t: team_name = t['name']

            if item_id:
                # 특정 팀 + 특정 아이템
                item_check = conn.execute(
                    'SELECT id FROM items WHERE id=? AND team_id=?', (item_id, team_id)
                ).fetchone()
                if not item_check:
                    conn.close()
                    return jsonify({'error': '해당 아이템에 접근 권한이 없습니다.'}), 403
                logs = conn.execute(
                    '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                              t.name as team_name
                       FROM progress_logs pl
                       JOIN items i ON pl.item_id = i.id
                       JOIN teams t ON i.team_id = t.id
                       WHERE pl.item_id = ? AND pl.created_at BETWEEN ? AND ?
                       ORDER BY pl.created_at ASC''',
                    (item_id, start_dt, end_dt_incl)
                ).fetchall()
            else:
                # 특정 팀 전체 아이템
                logs = conn.execute(
                    '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                              t.name as team_name
                       FROM progress_logs pl
                       JOIN items i ON pl.item_id = i.id
                       JOIN teams t ON i.team_id = t.id
                       WHERE i.team_id = ? AND pl.created_at BETWEEN ? AND ?
                       ORDER BY pl.created_at ASC''',
                    (team_id, start_dt, end_dt_incl)
                ).fetchall()
        else:
            # 전체 팀 (담당 소속)
            if division_id:
                logs = conn.execute(
                    '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                              t.name as team_name
                       FROM progress_logs pl
                       JOIN items i ON pl.item_id = i.id
                       JOIN teams t ON i.team_id = t.id
                       WHERE t.division_id = ? AND pl.created_at BETWEEN ? AND ?
                       ORDER BY pl.created_at ASC''',
                    (division_id, start_dt, end_dt_incl)
                ).fetchall()
            else:
                logs = conn.execute(
                    '''SELECT pl.*, i.title as item_title, i.subtitle, i.status, i.due_date,
                              t.name as team_name
                       FROM progress_logs pl
                       JOIN items i ON pl.item_id = i.id
                       JOIN teams t ON i.team_id = t.id
                       WHERE pl.created_at BETWEEN ? AND ?
                       ORDER BY pl.created_at ASC''',
                    (start_dt, end_dt_incl)
                ).fetchall()

    if not logs:
        conn.close()
        return jsonify({'error': f'선택한 기간({start_date} ~ {end_date})에 진척사항이 없습니다.'}), 404

    # 로그별 댓글
    log_ids      = [l['id'] for l in logs]
    placeholders = ','.join('?' * len(log_ids))
    comments     = conn.execute(
        f'SELECT * FROM comments WHERE progress_id IN ({placeholders}) ORDER BY created_at ASC',
        log_ids
    ).fetchall()
    conn.close()

    # 통계
    active_members = len(set(l['member_email'] for l in logs))
    total_logs     = len(logs)
    total_comments = len(comments)

    # 아이템별 데이터 구성
    items_data       = {}
    items_for_prompt = {}

    for log in logs:
        iid = log['item_id']
        if iid not in items_data:
            items_data[iid] = {
                'title':     log['item_title'],
                'subtitle':  log['subtitle'] or '',
                'status':    log['status'],
                'due_date':  log['due_date'] or '미정',
                'team_name': log['team_name'],
                'sources':   []
            }
            items_for_prompt[iid] = {
                'title':    log['item_title'],
                'status':   log['status'],
                'due_date': log['due_date'] or '미정',
                'logs':     []
            }
        log_comments = [c for c in comments if c['progress_id'] == log['id']]
        is_flagged = log['is_flagged'] if 'is_flagged' in log.keys() else 0
        items_data[iid]['sources'].append({
            'date':     log['created_at'][:16],
            'author':   log['member_name'],
            'content':  log['content'],
            'is_flagged': is_flagged,
            'comments': [{'author': c['author_name'], 'date': c['created_at'][:16],
                          'text': c['content']} for c in log_comments]
        })
        items_for_prompt[iid]['logs'].append({
            'date':     log['created_at'][:10],
            'content':  log['content'],
            'is_flagged': is_flagged,
            'comments': [c['content'] for c in log_comments]
        })

    # ── Gemini 프롬프트 ─────────────────────────────────────────
    scope_desc = f'{team_name} 팀' if team_name else '전체 팀'
    items_json = json.dumps(list(items_for_prompt.values()), ensure_ascii=False, indent=2)

    prompt = f"""당신은 업무 진척 요약 전문가입니다.
아래는 {scope_desc}의 {start_date} ~ {end_date} 기간 업무 진척 데이터입니다.

{items_json}

[작성 규칙]
- 각 아이템(title)마다 독립된 요약을 작성하세요.
- 요약은 반드시 **글머리 기호(- ) 목록 형식**으로 작성하세요.
- 항목 수는 **최대 4개**입니다. 절대 5개 이상 쓰지 마세요.
- 각 항목은 **한 줄**로, 완료된 사항은 과거형(~함, ~완료), 진행 중은 현재형(~중)으로 간결하게 쓰세요.
- 마감일이 있는 진행 중 항목은 끝에 (~마감일) 형태로 기재하세요. 예: `- RAG 파이프라인 초안 설계 중. (~2026-05-04)`
- 이름(사람)은 절대 포함하지 마세요.
- 모든 팀원의 진척을 합쳐서 하나의 흐름으로 요약하세요.
- 데이터에 "is_flagged": 1인 로그는 "주요 이슈"로 표시된 중요 항목입니다. 이 로그의 내용이 요약에 반영될 때, 해당 항목 앞에 [주요 이슈] 태그를 반드시 붙여서 작성하세요.
- 출력 형식:

## [status] 아이템 제목 (마감일: due_date)
- 항목1
- [주요 이슈] 항목2 (이슈 플래그된 로그 기반일 경우)
- 항목3
- 항목4 (있을 경우)
"""

    # ── Gemini API 호출 ─────────────────────────────────────────
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL, contents=prompt
        )
        summary_text = response.text
    except Exception as e:
        return jsonify({'error': f'Gemini API 오류: {str(e)}'}), 500

    # 보너스 통계 (담당장 전체 요약용)
    item_count = len(items_data)
    team_count = len(set(v['team_name'] for v in items_data.values()))
    # 담당장 + 전체 팀 선택 여부
    is_division_all = (role == '담당장' and not team_id)

    return jsonify({
        'summary':          summary_text,
        'items':            list(items_data.values()),
        'team_name':        team_name,
        'start_date':       start_date,
        'end_date':         end_date,
        'show_sources':     show_sources,
        'is_division_all':  is_division_all,
        'leader_team_id':   str(leader_team_id) if leader_team_id else None,
        'stats': {
            'total_logs':     total_logs,
            'total_comments': total_comments,
            'active_members': active_members,
            'team_count':     team_count,
            'item_count':     item_count,
        }
    })


@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html', title='알림')


def _get_notification_items(email, role, conn, limit=10):
    """
    역할별 알림 항목을 시간 역순으로 최대 limit개 반환.
    type: 'log' (진척 로그) | 'comment' (댓글)
    자기 자신이 올린 항목은 제외.
    """
    notifications = []

    # ── 1) 팀/담당 범위의 새 진척 로그 알림 ──────────────────────
    if role == '팀원':
        # 자신이 배정된 아이템의 로그 (본인 제외)
        logs = conn.execute('''
            SELECT pl.id, pl.item_id, pl.member_email, pl.member_name,
                   pl.content, pl.created_at,
                   i.title as item_title, t.name as team_name
            FROM progress_logs pl
            JOIN items i ON pl.item_id = i.id
            JOIN teams t ON i.team_id = t.id
            JOIN item_members im ON im.item_id = pl.item_id AND im.email = ?
            WHERE pl.member_email != ?
            ORDER BY pl.created_at DESC
        ''', (email, email)).fetchall()
    elif role == '팀장':
        team = conn.execute('SELECT id FROM teams WHERE leader_email = ?', (email,)).fetchone()
        if team:
            logs = conn.execute('''
                SELECT pl.id, pl.item_id, pl.member_email, pl.member_name,
                       pl.content, pl.created_at,
                       i.title as item_title, t.name as team_name
                FROM progress_logs pl
                JOIN items i ON pl.item_id = i.id
                JOIN teams t ON i.team_id = t.id
                WHERE i.team_id = ? AND pl.member_email != ?
                ORDER BY pl.created_at DESC
            ''', (team['id'], email)).fetchall()
        else:
            logs = []
    else:  # 담당장
        d = conn.execute('SELECT id FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        if d:
            logs = conn.execute('''
                SELECT pl.id, pl.item_id, pl.member_email, pl.member_name,
                       pl.content, pl.created_at,
                       i.title as item_title, t.name as team_name
                FROM progress_logs pl
                JOIN items i ON pl.item_id = i.id
                JOIN teams t ON i.team_id = t.id
                WHERE t.division_id = ? AND pl.member_email != ?
                ORDER BY pl.created_at DESC
            ''', (d['id'], email)).fetchall()
        else:
            logs = []

    # 읽음 여부 조회
    read_logs = {r['ref_id'] for r in conn.execute(
        "SELECT ref_id FROM notification_reads WHERE user_email = ? AND ref_type = 'log'",
        (email,)
    ).fetchall()}

    for log in logs:
        notifications.append({
            'type': 'log',
            'ref_id': log['id'],
            'item_id': log['item_id'],
            'item_title': log['item_title'],
            'team_name': log['team_name'],
            'author': log['member_name'],
            'content': log['content'],
            'created_at': log['created_at'],
            'is_read': log['id'] in read_logs,
        })

    # ── 2) 내가 쓴 로그/댓글에 달린 댓글 알림 ─────────────────────
    # 내가 쓴 진척 로그에 달린 댓글 (본인 제외)
    my_log_comments = conn.execute('''
        SELECT c.id, c.progress_id, c.author_email, c.author_name,
               c.content, c.created_at,
               pl.item_id, pl.content as log_content,
               i.title as item_title, t.name as team_name
        FROM comments c
        JOIN progress_logs pl ON c.progress_id = pl.id
        JOIN items i ON pl.item_id = i.id
        JOIN teams t ON i.team_id = t.id
        WHERE pl.member_email = ? AND c.author_email != ? AND c.parent_id IS NULL
        ORDER BY c.created_at DESC
    ''', (email, email)).fetchall()

    # 내가 쓴 댓글에 달린 대댓글 (본인 제외)
    my_reply_comments = conn.execute('''
        SELECT c.id, c.progress_id, c.author_email, c.author_name,
               c.content, c.created_at,
               pl.item_id, pl.content as log_content,
               i.title as item_title, t.name as team_name
        FROM comments c
        JOIN comments parent_c ON c.parent_id = parent_c.id
        JOIN progress_logs pl ON c.progress_id = pl.id
        JOIN items i ON pl.item_id = i.id
        JOIN teams t ON i.team_id = t.id
        WHERE parent_c.author_email = ? AND c.author_email != ?
        ORDER BY c.created_at DESC
    ''', (email, email)).fetchall()

    read_comments = {r['ref_id'] for r in conn.execute(
        "SELECT ref_id FROM notification_reads WHERE user_email = ? AND ref_type = 'comment'",
        (email,)
    ).fetchall()}

    comment_ids_added = set()
    for c in list(my_log_comments) + list(my_reply_comments):
        if c['id'] in comment_ids_added:
            continue
        comment_ids_added.add(c['id'])
        notifications.append({
            'type': 'comment',
            'ref_id': c['id'],
            'item_id': c['item_id'],
            'item_title': c['item_title'],
            'team_name': c['team_name'],
            'author': c['author_name'],
            'content': c['content'],
            'created_at': c['created_at'],
            'is_read': c['id'] in read_comments,
        })

    # 시간 역순 정렬
    notifications.sort(key=lambda x: x['created_at'], reverse=True)
    return notifications


@app.route('/api/notifications')
@login_required
def api_notifications():
    email = session.get('email')
    role = session.get('role')
    count_only = request.args.get('count_only', '0') == '1'

    conn = get_db_connection()
    all_items = _get_notification_items(email, role, conn)
    conn.close()

    unread_count = sum(1 for n in all_items if not n['is_read'])
    total_count  = len(all_items)

    if count_only:
        return jsonify({'unread_count': unread_count, 'total_count': total_count})

    # 페이지네이션
    per_page = int(request.args.get('per_page', 10))
    page     = int(request.args.get('page', 1))
    total_pages = max(1, -(-total_count // per_page))  # ceil
    start = (page - 1) * per_page
    end   = start + per_page
    paged = all_items[start:end]

    return jsonify({
        'items':        paged,
        'unread_count': unread_count,
        'total_count':  total_count,
        'page':         page,
        'per_page':     per_page,
        'total_pages':  total_pages,
    })


@app.route('/api/notifications/read/<ref_type>/<int:ref_id>', methods=['POST'])
@login_required
def mark_notification_read(ref_type, ref_id):
    if ref_type not in ('log', 'comment'):
        return jsonify({'error': 'invalid ref_type'}), 400
    email = session.get('email')
    conn = get_db_connection()
    conn.execute(
        'INSERT OR IGNORE INTO notification_reads (user_email, ref_type, ref_id) VALUES (?, ?, ?)',
        (email, ref_type, ref_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    email = session.get('email')
    role  = session.get('role')
    conn  = get_db_connection()
    all_items = _get_notification_items(email, role, conn)  # limit 없이 전체
    for n in all_items:
        conn.execute(
            'INSERT OR IGNORE INTO notification_reads (user_email, ref_type, ref_id) VALUES (?, ?, ?)',
            (email, n['type'], n['ref_id'])
        )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/dashboard')
@login_required
def api_dashboard():
    """대시보드 통계 API"""
    email = session.get('email')
    role  = session.get('role')
    conn  = get_db_connection()

    # 미읽은 알림 수
    all_notifs   = _get_notification_items(email, role, conn)
    unread_count = sum(1 for n in all_notifs if not n['is_read'])

    # 소속 팀 이름
    team_name = None
    if role == '팀원':
        m = conn.execute('SELECT t.name FROM members m JOIN teams t ON m.team_id = t.id WHERE m.email = ?', (email,)).fetchone()
        team_name = m['name'] if m else '-'
    elif role == '팀장':
        t = conn.execute('SELECT name FROM teams WHERE leader_email = ?', (email,)).fetchone()
        team_name = t['name'] if t else '-'
    else:  # 담당장
        d = conn.execute('SELECT name FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        team_name = d['name'] if d else '-'

    # 추진 아이템 수
    item_count = 0
    if role == '팀원':
        m = conn.execute('SELECT team_id FROM members WHERE email = ?', (email,)).fetchone()
        if m:
            row = conn.execute('SELECT COUNT(*) as cnt FROM item_members im JOIN items i ON im.item_id = i.id WHERE im.email = ?', (email,)).fetchone()
            item_count = row['cnt'] if row else 0
    elif role == '팀장':
        t = conn.execute('SELECT id FROM teams WHERE leader_email = ?', (email,)).fetchone()
        if t:
            row = conn.execute('SELECT COUNT(*) as cnt FROM items WHERE team_id = ?', (t['id'],)).fetchone()
            item_count = row['cnt'] if row else 0
    else:
        d = conn.execute('SELECT id FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        if d:
            row = conn.execute('SELECT COUNT(*) as cnt FROM items i JOIN teams t ON i.team_id = t.id WHERE t.division_id = ?', (d['id'],)).fetchone()
            item_count = row['cnt'] if row else 0

    # 이번 주 진척 건수
    from datetime import datetime, timedelta
    today     = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())  # 월요일
    week_str  = week_start.strftime('%Y-%m-%d')

    if role == '팀원':
        row = conn.execute(
            'SELECT COUNT(*) as cnt FROM progress_logs pl JOIN item_members im ON pl.item_id = im.item_id WHERE im.email = ? AND pl.created_at >= ?',
            (email, week_str)
        ).fetchone()
    elif role == '팀장':
        t = conn.execute('SELECT id FROM teams WHERE leader_email = ?', (email,)).fetchone()
        if t:
            row = conn.execute(
                'SELECT COUNT(*) as cnt FROM progress_logs pl JOIN items i ON pl.item_id = i.id WHERE i.team_id = ? AND pl.created_at >= ?',
                (t['id'], week_str)
            ).fetchone()
        else:
            row = None
    else:
        d = conn.execute('SELECT id FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        if d:
            row = conn.execute(
                'SELECT COUNT(*) as cnt FROM progress_logs pl JOIN items i ON pl.item_id = i.id JOIN teams t ON i.team_id = t.id WHERE t.division_id = ? AND pl.created_at >= ?',
                (d['id'], week_str)
            ).fetchone()
        else:
            row = None
    week_progress = row['cnt'] if row else 0

    conn.close()
    return jsonify({
        'unread_count':   unread_count,
        'team_name':      team_name,
        'item_count':     item_count,
        'week_progress':  week_progress,
        'role':           role,
        'name':           session.get('name'),
    })

@app.route('/org-manage')
@login_required
def org_manage():
    role = session.get('role')
    
    # Check permissions strictly
    if role not in ['담당장', '팀장']:
        flash('권한이 없습니다.')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    groups = conn.execute('SELECT * FROM groups').fetchall()
    divisions = conn.execute('SELECT * FROM divisions').fetchall()
    teams = conn.execute('SELECT * FROM teams').fetchall()
    members = conn.execute('SELECT * FROM members').fetchall()
    conn.close()
    
    # 데이터 구조화 (계층형)
    org_data = []
    for g in groups:
        g_data = dict(g)
        g_data['divisions'] = []
        for d in divisions:
            if d['group_id'] == g['id']:
                d_data = dict(d)
                d_data['teams'] = []
                for t in teams:
                    if t['division_id'] == d['id']:
                        t_data = dict(t)
                        t_data['members'] = [dict(m) for m in members if m['team_id'] == t['id']]
                        d_data['teams'].append(t_data)
                g_data['divisions'].append(d_data)
        org_data.append(g_data)

    return render_template('org_manage.html', title='조직 관리', org_data=org_data, role=role)

@app.route('/api/add-team', methods=['POST'])
@login_required
def add_team():
    division_id = request.form.get('division_id')
    name = request.form.get('name')
    leader_name = request.form.get('leader_name')
    leader_position = request.form.get('leader_position')
    leader_email = request.form.get('leader_email')
    
    if division_id and name:
        conn = get_db_connection()
        conn.execute('INSERT INTO teams (division_id, name, leader_name, leader_position, leader_email) VALUES (?, ?, ?, ?, ?)',
                     (division_id, name, leader_name, leader_position, leader_email))
        conn.commit()
        conn.close()
        flash('새 팀이 성공적으로 추가되었습니다.')
    
    return redirect(url_for('org_manage'))

@app.route('/api/add-member', methods=['POST'])
@login_required
def add_member():
    team_id = request.form.get('team_id')
    name = request.form.get('name')
    position = request.form.get('position')
    email = request.form.get('email')
    
    if team_id and name and position:
        conn = get_db_connection()
        conn.execute('INSERT INTO members (team_id, name, position, email) VALUES (?, ?, ?, ?)',
                     (team_id, name, position, email))
        conn.commit()
        conn.close()
        flash('새 팀원이 성공적으로 배정되었습니다.')
        
    return redirect(url_for('org_manage'))

@app.route('/api/delete-team/<int:team_id>', methods=['GET', 'POST'])
@login_required
def delete_team(team_id):
    role = session.get('role')
    if role == '담당장':
        conn = get_db_connection()
        conn.execute('DELETE FROM members WHERE team_id = ?', (team_id,))
        conn.execute('DELETE FROM teams WHERE id = ?', (team_id,))
        conn.commit()
        conn.close()
        flash('팀이 삭제되었습니다.')
    return redirect(url_for('org_manage'))

@app.route('/api/delete-member/<int:member_id>', methods=['GET', 'POST'])
@login_required
def delete_member(member_id):
    role = session.get('role')
    # 팀장 또는 담당장만 팀원 삭제 가능
    if role in ['담당장', '팀장']:
        conn = get_db_connection()
        conn.execute('DELETE FROM members WHERE id = ?', (member_id,))
        conn.commit()
        conn.close()
        flash('팀원이 삭제되었습니다.')
    else:
        flash('삭제 권한이 없습니다.')
    return redirect(url_for('org_manage'))

@app.route('/items')
@login_required
def items():
    conn = get_db_connection()
    role = session.get('role')
    email = session.get('email')

    # 팀장 로그인인 경우 자기 팀 items만, 담당장/팀원은 전체 or 담당 소속 팀
    if role == '팀장':
        team = conn.execute('SELECT * FROM teams WHERE leader_email = ?', (email,)).fetchone()
        team_ids = [team['id']] if team else []
    elif role == '담당장':
        division = conn.execute('SELECT * FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        if division:
            teams = conn.execute('SELECT id FROM teams WHERE division_id = ?', (division['id'],)).fetchall()
            team_ids = [t['id'] for t in teams]
        else:
            team_ids = []
    else:
        # 팀원: 소속 팀 아이템만 조회
        member = conn.execute('SELECT team_id FROM members WHERE email = ?', (email,)).fetchone()
        team_ids = [member['team_id']] if member else []

    if team_ids:
        placeholders = ','.join('?' * len(team_ids))
        items_list = conn.execute(
            f'SELECT i.*, t.name as team_name FROM items i JOIN teams t ON i.team_id = t.id WHERE i.team_id IN ({placeholders}) ORDER BY i.created_at DESC',
            team_ids
        ).fetchall()
    else:
        items_list = []

    # 각 아이템의 팀원 목록 가져오기
    items_with_members = []
    for item in items_list:
        members = conn.execute('SELECT * FROM item_members WHERE item_id = ?', (item['id'],)).fetchall()
        items_with_members.append({'item': dict(item), 'members': [dict(m) for m in members]})

    # 팀 목록 (팀장은 본인 팀만)
    if role == '팀장':
        team = conn.execute('SELECT * FROM teams WHERE leader_email = ?', (email,)).fetchone()
        teams_list = [dict(team)] if team else []
    elif role == '담당장':
        division = conn.execute('SELECT * FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        if division:
            teams_list = [dict(t) for t in conn.execute('SELECT * FROM teams WHERE division_id = ?', (division['id'],)).fetchall()]
        else:
            teams_list = []
    else:
        teams_list = []

    # 팀원 목록 (배정 시 사용)
    all_members = {}
    for t in teams_list:
        mems = conn.execute('SELECT * FROM members WHERE team_id = ?', (t['id'],)).fetchall()
        all_members[t['id']] = [dict(m) for m in mems]

    conn.close()
    return render_template('items.html', title='추진 아이템',
                           items_with_members=items_with_members,
                           teams_list=teams_list,
                           all_members=all_members,
                           role=role)

@app.route('/api/add-item', methods=['POST'])
@login_required
def add_item():
    role = session.get('role')
    if role not in ['팀장']:
        flash('아이템 추가 권한이 없습니다.')
        return redirect(url_for('items'))

    team_id = request.form.get('team_id')
    title = request.form.get('title')
    subtitle = request.form.get('subtitle', '')
    description = request.form.get('description', '')
    status = request.form.get('status', '계획')
    due_date = request.form.get('due_date', '')
    extra_note = request.form.get('extra_note', '')

    if team_id and title:
        conn = get_db_connection()
        cursor = conn.execute(
            'INSERT INTO items (team_id, title, subtitle, description, status, due_date, created_by, extra_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (team_id, title, subtitle, description, status, due_date, session.get('name'), extra_note)
        )
        item_id = cursor.lastrowid

        # 팀원 배정 처리
        member_ids = request.form.getlist('member_ids')
        for mid in member_ids:
            member = conn.execute('SELECT * FROM members WHERE id = ?', (mid,)).fetchone()
            if member:
                conn.execute('INSERT INTO item_members (item_id, member_id, name, position, email) VALUES (?, ?, ?, ?, ?)',
                             (item_id, member['id'], member['name'], member['position'], member['email']))

        conn.commit()
        conn.close()
        
        # RAG 동기화
        rag.upsert_item(item_id)
        
        flash('추진 아이템이 추가되었습니다.')

    return redirect(url_for('items'))

@app.route('/api/edit-item/<int:item_id>', methods=['POST'])
@login_required
def edit_item(item_id):
    role = session.get('role')
    if role not in ['팀장', '담당장']:
        flash('수정 권한이 없습니다.')
        return redirect(url_for('items'))

    title = request.form.get('title')
    subtitle = request.form.get('subtitle', '')
    description = request.form.get('description', '')
    status = request.form.get('status', '계획')
    due_date = request.form.get('due_date', '')
    extra_note = request.form.get('extra_note', '')

    conn = get_db_connection()
    conn.execute(
        'UPDATE items SET title=?, subtitle=?, description=?, status=?, due_date=?, extra_note=? WHERE id=?',
        (title, subtitle, description, status, due_date, extra_note, item_id)
    )

    # 팀원 재배정
    conn.execute('DELETE FROM item_members WHERE item_id = ?', (item_id,))
    member_ids = request.form.getlist('member_ids')
    for mid in member_ids:
        member = conn.execute('SELECT * FROM members WHERE id = ?', (mid,)).fetchone()
        if member:
            conn.execute('INSERT INTO item_members (item_id, member_id, name, position, email) VALUES (?, ?, ?, ?, ?)',
                         (item_id, member['id'], member['name'], member['position'], member['email']))

    conn.commit()
    conn.close()
    
    # RAG 동기화
    rag.upsert_item(item_id)
    
    flash('아이템이 수정되었습니다.')
    return redirect(url_for('items'))

@app.route('/api/delete-item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def delete_item(item_id):
    role = session.get('role')
    if role == '팀장':
        conn = get_db_connection()
        conn.execute('DELETE FROM item_members WHERE item_id = ?', (item_id,))
        conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        
        # RAG 삭제
        rag.delete_item_from_rag(item_id)
        
        flash('아이템이 삭제되었습니다.')
    else:
        flash('삭제 권한이 없습니다.')
    return redirect(url_for('items'))

@app.route('/api/delete-item-member/<int:im_id>', methods=['GET', 'POST'])
@login_required
def delete_item_member(im_id):
    role = session.get('role')
    if role in ['팀장', '담당장']:
        conn = get_db_connection()
        conn.execute('DELETE FROM item_members WHERE id = ?', (im_id,))
        conn.commit()
        conn.close()
        flash('팀원이 제거되었습니다.')
    return redirect(url_for('items'))

# ─── 진척 사항 ─────────────────────────────────────────
@app.route('/progress')
@login_required
def progress():
    conn = get_db_connection()
    role = session.get('role')
    email = session.get('email')

    if role == '팀장':
        # 팀장: 자기 팀의 모든 아이템 + 각 팀원의 진척
        team = conn.execute('SELECT * FROM teams WHERE leader_email = ?', (email,)).fetchone()
        if team:
            item_members = conn.execute(
                '''SELECT im.*, i.title, i.subtitle, i.status, i.due_date, i.team_id
                   FROM item_members im
                   JOIN items i ON im.item_id = i.id
                   JOIN teams t ON i.team_id = t.id
                   WHERE t.id = ?
                   ORDER BY i.id, im.name''', (team['id'],)
            ).fetchall()
        else:
            item_members = []

    elif role == '담당장':
        # 담당장: 소속 팀 전체 아이템
        division = conn.execute('SELECT * FROM divisions WHERE leader_email = ?', (email,)).fetchone()
        if division:
            item_members = conn.execute(
                '''SELECT im.*, i.title, i.subtitle, i.status, i.due_date, i.team_id,
                          t.name as team_name
                   FROM item_members im
                   JOIN items i ON im.item_id = i.id
                   JOIN teams t ON i.team_id = t.id
                   WHERE t.division_id = ?
                   ORDER BY t.name, i.id, im.name''', (division['id'],)
            ).fetchall()
        else:
            item_members = []

    else:
        # 팀원: 자신에게 배정된 아이템만
        item_members = conn.execute(
            '''SELECT im.*, i.title, i.subtitle, i.status, i.due_date, i.team_id
               FROM item_members im
               JOIN items i ON im.item_id = i.id
               WHERE im.email = ?
               ORDER BY i.id''', (email,)
        ).fetchall()

    # 아이템별로 그룹핑 + 진척 로그 + 댓글
    items_map = {}
    for im in item_members:
        iid = im['item_id']
        if iid not in items_map:
            items_map[iid] = {
                'item_id': iid,
                'title': im['title'],
                'subtitle': im['subtitle'] if 'subtitle' in im.keys() else '',
                'status': im['status'],
                'due_date': im['due_date'] if im['due_date'] else '',
                'team_id':   im['team_id'] if 'team_id' in im.keys() else None,
                'team_name': im['team_name'] if 'team_name' in im.keys() else '',
                'assignees': [],   # 배정 팀원들
                'logs_by_member': {}  # email → [logs]
            }
        assignee = {
            'im_id': im['id'],
            'name': im['name'],
            'position': im['position'],
            'email': im['email']
        }
        if assignee not in items_map[iid]['assignees']:
            items_map[iid]['assignees'].append(assignee)

    # 각 아이템의 진척 로그 조회
    for iid, data in items_map.items():
        logs = conn.execute(
            'SELECT * FROM progress_logs WHERE item_id = ? ORDER BY created_at DESC', (iid,)
        ).fetchall()
        for log in logs:
            mem_email = log['member_email']
            if mem_email not in data['logs_by_member']:
                data['logs_by_member'][mem_email] = []
            # 댓글 조회 (parent_id IS NULL: 최상위 댓글)
            top_comments = conn.execute(
                'SELECT * FROM comments WHERE progress_id = ? AND parent_id IS NULL ORDER BY created_at ASC',
                (log['id'],)
            ).fetchall()
            comment_tree = []
            for c in top_comments:
                replies = conn.execute(
                    'SELECT * FROM comments WHERE parent_id = ? ORDER BY created_at ASC', (c['id'],)
                ).fetchall()
                comment_tree.append({'comment': dict(c), 'replies': [dict(r) for r in replies]})
            log_dict = dict(log)
            log_dict['is_flagged'] = log.get('is_flagged', 0) if hasattr(log, 'get') else (log['is_flagged'] if 'is_flagged' in log.keys() else 0)
            data['logs_by_member'][mem_email].append({
                'log': log_dict,
                'comment_tree': comment_tree
            })

    conn.close()
    return render_template('progress.html', title='진척 사항',
                           items_map=items_map, role=role, user_email=email,
                           user_name=session.get('name'))


@app.route('/api/add-progress', methods=['POST'])
@login_required
def add_progress():
    item_id = request.form.get('item_id')
    content = request.form.get('content', '').strip()
    target_email = request.form.get('target_email')
    if item_id and content:
        role = session.get('role')
        user_email = session.get('email')
        user_name = session.get('name')
        
        member_email = user_email
        member_name = user_name
        
        conn = get_db_connection()
        if role == '팀장' and target_email and target_email != user_email:
            member = conn.execute('SELECT name FROM members WHERE email = ?', (target_email,)).fetchone()
            if member:
                member_email = target_email
                member_name = member['name']
                
        conn.execute(
            'INSERT INTO progress_logs (item_id, member_email, member_name, content) VALUES (?, ?, ?, ?)',
            (item_id, member_email, member_name, content)
        )
        conn.commit()
        log_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        
        # RAG 증분 동기화
        rag.upsert_progress(log_id)
        
        flash('진척사항이 등록되었습니다.')
    return redirect(url_for('progress'))


@app.route('/api/add-comment', methods=['POST'])
@login_required
def add_comment():
    progress_id = request.form.get('progress_id')
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id') or None
    if progress_id and content:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO comments (progress_id, author_email, author_name, content, parent_id) VALUES (?, ?, ?, ?, ?)',
            (progress_id, session.get('email'), session.get('name'), content, parent_id)
        )
        conn.commit()
        conn.close()
    return redirect(url_for('progress'))


@app.route('/api/delete-progress/<int:log_id>', methods=['POST'])
@login_required
def delete_progress(log_id):
    conn = get_db_connection()
    try:
        log = conn.execute('SELECT * FROM progress_logs WHERE id = ?', (log_id,)).fetchone()
        if not log or log['member_email'] != session.get('email'):
            return jsonify({'ok': False, 'error': 'unauthorized'}), 403

        # 댓글(대댓글 포함)을 먼저 삭제한 후 진척 로그 삭제 (cascade)
        conn.execute('DELETE FROM comments WHERE progress_id = ?', (log_id,))
        conn.execute('DELETE FROM progress_logs WHERE id = ?', (log_id,))
        conn.commit()

        # RAG 동기화
        try:
            rag.delete_progress_from_rag(log_id)
        except Exception as e:
            print(f"RAG sync error during deletion: {e}")

        return jsonify({'ok': True})
    except Exception as e:
        print(f"Server error during delete_progress: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/edit-progress/<int:log_id>', methods=['POST'])
@login_required
def edit_progress(log_id):
    """진척 로그 수정 (본인만 가능)"""
    from datetime import datetime
    content = request.form.get('content', '').strip()
    if not content:
        return jsonify({'ok': False, 'error': 'empty'}), 400
    conn = get_db_connection()
    log = conn.execute('SELECT * FROM progress_logs WHERE id = ?', (log_id,)).fetchone()
    if not log or log['member_email'] != session.get('email'):
        conn.close()
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        'UPDATE progress_logs SET content = ?, updated_at = ? WHERE id = ?',
        (content, now, log_id)
    )
    conn.commit()
    conn.close()
    # RAG 재동기화
    rag.upsert_progress(log_id)
    return jsonify({'ok': True, 'updated_at': now})


@app.route('/api/edit-comment/<int:comment_id>', methods=['POST'])
@login_required
def edit_comment(comment_id):
    """댓글 수정 (본인만 가능)"""
    from datetime import datetime
    content = request.form.get('content', '').strip()
    if not content:
        return jsonify({'ok': False, 'error': 'empty'}), 400
    conn = get_db_connection()
    c = conn.execute('SELECT * FROM comments WHERE id = ?', (comment_id,)).fetchone()
    if not c or c['author_email'] != session.get('email'):
        conn.close()
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        'UPDATE comments SET content = ?, updated_at = ? WHERE id = ?',
        (content, now, comment_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'updated_at': now})


@app.route('/api/delete-comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """댓글 삭제 (본인만, 대댓글 있으면 불가)"""
    conn = get_db_connection()
    c = conn.execute('SELECT * FROM comments WHERE id = ?', (comment_id,)).fetchone()
    if not c or c['author_email'] != session.get('email'):
        conn.close()
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    # 대댓글이 있으면 삭제 불가
    reply_count = conn.execute(
        'SELECT COUNT(*) as cnt FROM comments WHERE parent_id = ?', (comment_id,)
    ).fetchone()['cnt']
    if reply_count > 0:
        conn.close()
        return jsonify({'ok': False, 'error': 'has_replies'}), 400
    conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/toggle-flag/<int:log_id>', methods=['POST'])
@login_required
def toggle_flag(log_id):
    """진척 로그의 주요 이슈 플래그 토글 (모든 역할 가능)"""
    conn = get_db_connection()
    log = conn.execute('SELECT * FROM progress_logs WHERE id = ?', (log_id,)).fetchone()
    if not log:
        conn.close()
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    current = log['is_flagged'] if 'is_flagged' in log.keys() else 0
    new_val = 0 if current else 1
    conn.execute('UPDATE progress_logs SET is_flagged = ? WHERE id = ?', (new_val, log_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'is_flagged': new_val})




@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    data = request.get_json()
    message = data.get('message', '')
    history = data.get('history', [])
    
    if not message:
        return jsonify({'error': '메시지가 없습니다.'}), 400
        
    role = session.get('role')
    email = session.get('email')
    
    # RAG 질의 (타이밍 맞게 rag 모듈 호출)
    try:
        reply = rag.query_chatbot(message, role, email, history)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 서버 기동 시 백그라운드 데이터 동기화
    print("RAG ChromaDB 데이터를 동기화합니다...")
    rag.sync_all()
    print("RAG 동기화 완료!")
    
    app.run(debug=True, port=5000)

