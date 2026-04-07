import sqlite3
import os
import yaml
from werkzeug.security import generate_password_hash

DB_PATH = 'workprogress.db'

def init_db():
    # 데이터베이스 파일이 이미 존재하면 연결
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()

    # schema.sql 읽기
    with open('schema.sql', 'r', encoding='utf-8') as f:
        cursor.executescript(f.read())
        
    print("스키마가성공적으로 적용되었습니다.")

    # 기본 데이터 (그룹 및 담당) 생성
    # AX그룹 삽입
    cursor.execute(
        "INSERT INTO groups (name, leader_name, leader_position, leader_email) VALUES (?, ?, ?, ?)", 
        ('AX그룹', '마영일', '상무', 'yilma@lgchem.com')
    )
    group_id = cursor.lastrowid
    print(f"'AX그룹' 생성 완료 (ID: {group_id})")

    # 경영AX담당 삽입
    cursor.execute(
        "INSERT INTO divisions (group_id, name, leader_name, leader_position, leader_email) VALUES (?, ?, ?, ?, ?)", 
        (group_id, '경영AX담당', '박정재', '책임', 'rosynante@lgchem.com')
    )
    division_id = cursor.lastrowid
    print(f"'경영AX담당' 생성 완료 (ID: {division_id})")

    # users.yaml 파싱 및 DB에 사용자 계정 초기화
    try:
        with open('users.yaml', 'r', encoding='utf-8') as yf:
            users_data = yaml.safe_load(yf)
            
            for user in users_data.get('users', []):
                uid = user['id']
                email = user['email']
                name = user['name']
                # 초기 비밀번호는 ID와 동일하게 설정 (추후 로그인 후 변경)
                pw_hash = generate_password_hash(uid)
                
                cursor.execute(
                    "INSERT INTO users (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
                    (uid, name, email, pw_hash)
                )
            print(f"{len(users_data.get('users', []))}명의 사용자 계정이 초기화되었습니다.")
    except Exception as e:
        print(f"사용자 초기화 중 오류 발생: {e}")

    # 샘플 팀 (선택적)
    # cursor.execute("INSERT INTO teams (division_id, name, leader_name) VALUES (?, ?, ?)", (division_id, 'AI솔루션팀', '홍길동 선임'))

    conn.commit()
    conn.close()
    print("초기 데이터 구축 완료!")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

if __name__ == '__main__':
    init_db()
