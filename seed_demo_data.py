"""
가상 진척 데이터 시드 스크립트
기존 DB에 테스트용 팀/아이템/진척로그/댓글 데이터를 삽입합니다.
"""
import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

DB_PATH = 'workprogress.db'

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ── 기존 division 가져오기 ──────────────────────────────
    division = c.execute('SELECT * FROM divisions LIMIT 1').fetchone()
    if not division:
        print("division이 없습니다. db.py 로 init_db() 먼저 실행하세요.")
        conn.close()
        return
    division_id = division['id']
    print(f"사용 담당: {division['name']} (id={division_id})")

    # ── 팀 & 팀장 계정 추가 ────────────────────────────────
    teams_data = [
        ('AI솔루션팀',   '김민준', '책임', 'minjun.kim@lgchem.com',   'minjun'),
        ('데이터분석팀', '이서연', '선임', 'seoyeon.lee@lgchem.com',  'seoyeon'),
        ('플랫폼개발팀', '박지훈', '사원', 'jihoon.park@lgchem.com',  'jihoon'),
    ]
    team_ids = []
    for tname, lname, lpos, lemail, lid in teams_data:
        ex = c.execute('SELECT id FROM teams WHERE name=?', (tname,)).fetchone()
        if ex:
            team_ids.append(ex['id'])
            print(f"  팀 이미 존재: {tname}")
        else:
            c.execute('INSERT INTO teams (division_id, name, leader_name, leader_position, leader_email) VALUES (?,?,?,?,?)',
                      (division_id, tname, lname, lpos, lemail))
            tid = c.lastrowid
            team_ids.append(tid)
            print(f"  팀 생성: {tname} (id={tid})")

        # 팀장 user 계정
        if not c.execute('SELECT id FROM users WHERE id=?', (lid,)).fetchone():
            c.execute('INSERT INTO users (id, name, email, password_hash) VALUES (?,?,?,?)',
                      (lid, lname, lemail, generate_password_hash(lid)))

    # ── 팀원 추가 ──────────────────────────────────────────
    members_data = [
        # (team_idx, name, position, email, uid)
        (0, '최유진', '선임', 'yujin.choi@lgchem.com',   'yujin'),
        (0, '강도현', '사원', 'dohyun.kang@lgchem.com',  'dohyun'),
        (1, '윤하영', '책임', 'hayoung.yoon@lgchem.com', 'hayoung'),
        (1, '정수민', '사원', 'sumin.jung@lgchem.com',   'sumin'),
        (2, '한지원', '선임', 'jiwon.han@lgchem.com',    'jiwon'),
        (2, '오태양', '사원', 'taeyang.oh@lgchem.com',   'taeyang'),
    ]
    member_ids_by_team = {i: [] for i in range(len(team_ids))}
    for tidx, mname, mpos, memail, muid in members_data:
        tid = team_ids[tidx]
        ex = c.execute('SELECT id FROM members WHERE email=?', (memail,)).fetchone()
        if ex:
            mid = ex['id']
        else:
            c.execute('INSERT INTO members (team_id, name, position, email) VALUES (?,?,?,?)',
                      (tid, mname, mpos, memail))
            mid = c.lastrowid
        member_ids_by_team[tidx].append({'id': mid, 'name': mname, 'position': mpos, 'email': memail})
        # user 계정
        if not c.execute('SELECT id FROM users WHERE id=?', (muid,)).fetchone():
            c.execute('INSERT INTO users (id, name, email, password_hash) VALUES (?,?,?,?)',
                      (muid, mname, memail, generate_password_hash(muid)))

    # ── 아이템 추가 ────────────────────────────────────────
    now = datetime.now()
    items_data = [
        (0, 'LLM 기반 자동화 파이프라인 구축', 'AI 업무 자동화', '사내 반복 업무를 LLM으로 자동화하는 파이프라인 설계 및 구현', '진행중',  (now + timedelta(days=30)).strftime('%Y-%m-%d'), '김민준'),
        (0, '챗봇 프로토타입 개발',            'AI 챗봇',        'GPT 기반 사내 문서 검색 챗봇 MVP 개발',                           '완료',     (now - timedelta(days=5 )).strftime('%Y-%m-%d'), '김민준'),
        (1, '데이터 품질 관리 체계 수립',      '데이터 거버넌스', '데이터 입력·가공·검증 기준 및 프로세스 문서화',                   '진행중',  (now + timedelta(days=14)).strftime('%Y-%m-%d'), '이서연'),
        (1, '대시보드 자동화',                 'BI 고도화',       '월별 KPI 대시보드 자동 갱신 시스템 구축',                         '계획',     (now + timedelta(days=45)).strftime('%Y-%m-%d'), '이서연'),
        (2, '마이크로서비스 전환',             '아키텍처 개선',   '모놀리식 레거시 시스템의 MSA 전환 기획 및 1차 구현',              '진행중',  (now + timedelta(days=60)).strftime('%Y-%m-%d'), '박지훈'),
    ]
    item_ids = []
    team_leader_emails = [td[3] for td in teams_data]
    for tidx, title, subtitle, desc, status, due, creator in items_data:
        ex = c.execute('SELECT id FROM items WHERE title=? AND team_id=?', (title, team_ids[tidx])).fetchone()
        if ex:
            item_ids.append((ex['id'], tidx))
            print(f"  아이템 이미 존재: {title}")
        else:
            c.execute('INSERT INTO items (team_id, title, subtitle, description, status, due_date, created_by) VALUES (?,?,?,?,?,?,?)',
                      (team_ids[tidx], title, subtitle, desc, status, due, creator))
            iid = c.lastrowid
            item_ids.append((iid, tidx))
            print(f"  아이템 생성: {title} (id={iid})")
            # 팀원 배정
            for m in member_ids_by_team[tidx]:
                c.execute('INSERT OR IGNORE INTO item_members (item_id, member_id, name, position, email) VALUES (?,?,?,?,?)',
                          (iid, m['id'], m['name'], m['position'], m['email']))

    # ── 진척 로그 + 댓글 ───────────────────────────────────
    def dt_str(days_ago, hour=10):
        return (now - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')

    progress_seed = [
        # (item_idx, member_idx_in_team, days_ago, content)
        # 아이템 0: LLM 자동화 파이프라인
        (0, 0, 7,  '요구사항 분석 완료. 자동화 대상 업무 목록 15개 확보하였음. RAG 아키텍처 검토 시작.'),
        (0, 0, 6,  'RAG 파이프라인 설계 초안 완성. LangChain 기반으로 구성하기로 결정.'),
        (0, 1, 6,  '인프라 환경 세팅 완료. Docker Compose 구성하여 로컬 테스트 환경 준비함.'),
        (0, 0, 4,  '벡터DB(Chroma) 연동 완료. 문서 임베딩 파이프라인 1차 구현.'),
        (0, 1, 3,  'FastAPI 기반 API 서버 구성. 기본 엔드포인트 /query, /ingest 개발 완료.'),
        (0, 0, 2,  '내부 테스트 시작. 10개 문서 기준 평균 응답시간 1.2초 확인. 목표는 0.8초.'),
        (0, 1, 1,  '캐싱 레이어 추가 후 응답시간 0.85초로 개선. 거의 목표치에 근접.'),
        # 아이템 1: 챗봇 프로토타입
        (1, 0, 10, '사용자 인터뷰 5건 완료. 핵심 요구사항: 사내 규정 문서 검색 + 자연어 질의.'),
        (1, 1, 9,  'OpenAI API 연동 및 기본 프롬프트 엔지니어링 완료.'),
        (1, 0, 7,  'UI 프로토타입 Figma 작업 완료. 팀장 검토 후 승인받음.'),
        (1, 0, 5,  'React 기반 챗봇 UI 개발 완료. 백엔드 연동 테스트 중.'),
        (1, 1, 4,  '사내 문서 100건 벡터 인덱싱 완료. 검색 정확도 87%.'),
        (1, 0, 2,  '최종 QA 완료. 버그 3건 수정. 배포 준비 완료.'),
        (1, 0, 0,  '운영 서버 배포 완료. 사용자 피드백 수집 시작.'),
        # 아이템 2: 데이터 품질 관리
        (2, 0, 7,  '현행 데이터 입력 프로세스 현황 조사 완료. 문제점 12개 도출.'),
        (2, 1, 6,  '데이터 품질 기준 초안 작성 (정확성, 완전성, 일관성, 시의성 4개 차원).'),
        (2, 0, 4,  '유관 부서 인터뷰(3개 팀) 완료. 공통 문제: 중복 입력, 코드 불일치.'),
        (2, 0, 2,  '데이터 품질 지표 KPI 정의 완료. 월별 측정 계획 수립.'),
        (2, 1, 1,  '자동 검증 스크립트 초안 작성. Python pandas 활용.'),
        # 아이템 3: 대시보드 자동화 (계획 단계)
        (3, 0, 5,  '이해관계자 미팅. 자동화 대상 대시보드 10개 선정.'),
        (3, 1, 3,  'Power BI vs Tableau 검토 완료. Power BI 선정 (기존 MS 인프라 활용).'),
        # 아이템 4: MSA 전환
        (4, 0, 7,  '현행 시스템 도메인 분석 완료. 8개 도메인으로 분리 가능 확인.'),
        (4, 1, 6,  '1단계 전환 대상: 사용자 인증 서비스 선정. JWT 기반 인증 모듈 설계.'),
        (4, 0, 4,  '인증 마이크로서비스 개발 완료. 단위 테스트 통과.'),
        (4, 1, 3,  'API Gateway 구성(Kong) 완료. 라우팅 및 인증 미들웨어 통합.'),
        (4, 0, 1,  '통합 테스트 진행 중. 레거시와 신규 서비스 간 데이터 정합성 확인 작업.'),
    ]

    team_members_flat = [
        [member_ids_by_team[0][0], member_ids_by_team[0][1]],  # 아이템0,1 → team0
        [member_ids_by_team[0][0], member_ids_by_team[0][1]],
        [member_ids_by_team[1][0], member_ids_by_team[1][1]],  # 아이템2,3 → team1
        [member_ids_by_team[1][0], member_ids_by_team[1][1]],
        [member_ids_by_team[2][0], member_ids_by_team[2][1]],  # 아이템4 → team2
    ]

    log_ids = []
    for item_idx, mem_idx, days_ago, content in progress_seed:
        iid, tidx = item_ids[item_idx]
        m = team_members_flat[item_idx][mem_idx]
        created = dt_str(days_ago, hour=random.choice([9, 10, 11, 14, 15, 16]))
        # 중복 방지
        ex = c.execute('SELECT id FROM progress_logs WHERE item_id=? AND member_email=? AND content=?',
                       (iid, m['email'], content)).fetchone()
        if ex:
            log_ids.append(ex['id'])
        else:
            c.execute('INSERT INTO progress_logs (item_id, member_email, member_name, content, created_at) VALUES (?,?,?,?,?)',
                      (iid, m['email'], m['name'], content, created))
            lid2 = c.lastrowid
            log_ids.append(lid2)

    # 댓글 삽입 (팀장이 주요 로그에 댓글)
    comments_seed = [
        # (log_position_in_list, commenter_name, commenter_email, comment, days_ago, parent_position)
        (3,  '김민준', 'minjun.kim@lgchem.com', 'Chroma 선택 좋습니다. 스케일아웃 시 Qdrant 전환도 고려해 봅시다.', 4, None),
        (5,  '김민준', 'minjun.kim@lgchem.com', '목표치에 근접했군요! 캐싱 전략 문서화 부탁드립니다.', 2, None),
        (6,  '최유진', 'yujin.choi@lgchem.com', '네, 이번 주 안으로 작성하겠습니다.', 1, 5),  # parent=5번 위치
        (12, '김민준', 'minjun.kim@lgchem.com', '배포 수고하셨습니다! 모니터링 대시보드 링크 공유 부탁드립니다.', 0, None),
        (15, '이서연', 'seoyeon.lee@lgchem.com', '잘 정리됐네요. 단, 시의성 KPI 기준값 재검토 필요합니다.', 2, None),
        (18, '이서연', 'seoyeon.lee@lgchem.com', '스크립트 PR 올리면 리뷰 해드리겠습니다.', 1, None),
        (22, '박지훈', 'jihoon.park@lgchem.com', '통합 테스트 시 EDA 데이터도 포함해 주세요.', 1, None),
    ]

    for log_pos, cname, cemail, ccontent, days_ago, parent_pos in comments_seed:
        if log_pos >= len(log_ids):
            continue
        log_id = log_ids[log_pos]
        parent_id = log_ids[parent_pos] if parent_pos is not None and parent_pos < len(log_ids) else None
        created = dt_str(days_ago, hour=random.choice([10, 11, 15, 16]))
        ex = c.execute('SELECT id FROM comments WHERE progress_id=? AND author_email=? AND content=?',
                       (log_id, cemail, ccontent)).fetchone()
        if not ex:
            c.execute('INSERT INTO comments (progress_id, author_email, author_name, content, parent_id, created_at) VALUES (?,?,?,?,?,?)',
                      (log_id, cemail, cname, ccontent, parent_id, created))

    conn.commit()
    conn.close()
    print("\n✅ 가상 데이터 삽입 완료!")
    print("테스트 계정:")
    print("  팀장: minjun / minjun, seoyeon / seoyeon, jihoon / jihoon")
    print("  팀원: yujin / yujin, dohyun / dohyun, hayoung / hayoung, sumin / sumin, jiwon / jiwon, taeyang / taeyang")

if __name__ == '__main__':
    seed()
