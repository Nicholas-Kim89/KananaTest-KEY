# Nexus AI: 리눅스 가상 분석 환경 배포 및 구동 가이드

회사 클라우드의 리눅스 기반 분석 가상 환경(과제당 1개 할당, Python 3.11 기본 설치)으로 `Nexus AI` 소스 코드를 옮긴 후, 구조를 설정하고 URL을 구성원에게 공유할 수 있도록 설정하는 과정입니다.

---

## 🚀 1. 준비 사항 및 소스 코드 복사

### 1-1. 복사할 파일 대상
윈도우 환경에서 리눅스 분석 환경으로 소스 코드를 복사(SFTP, SCP, Git 등 활용)합니다.

*   `app.py`, `db.py`, `rag.py`
*   `templates/`, `static/` 디렉터리 전체
*   `requirements.txt`
*   `create_db.py`, `migrate_notifications.py` (신규 설치 시 DB 구성용)

**※ 중요 사항**: 
분석 환경은 과제당 하나씩 독립적으로 생성되므로, **파이썬 가상환경(`venv`)을 만들지 않고 시스템(Global) Python 3.11을 그대로 사용합니다.** 따라서 기존 윈도우 환경에 있던 `venv` 폴더는 절대로 복사하지 마세요. 
(현재 사용 중인 실제 데이터(`workprogress.db` 및 `chroma_db` 폴더)를 유지하고 싶다면 함께 복사하고, 클린 상태로 시작하려면 제외하세요.)

---

## 🛠️ 2. 패키지 설치

리눅스 서버에 접속한 후, 소스코드가 복사된 디렉터리로 이동하여 필요한 파이썬 라이브러리를 전역으로 설치합니다.

```bash
# 1. 소스코드가 있는 경로로 이동 (예시)
cd /workspace/nexus-ai-minutes

# 2. 필수 라이브러리 설치 (가상환경 없이 전역 환경에 설치)
pip install -r requirements.txt

# 3. 추가 라이브러리 설치 (기존 파일에 누락된 필수 라이브러리)
pip install chromadb flask-cors gunicorn
```
*(참고: `gunicorn`은 Flask 애플리케이션을 안정적인 프로덕션 모드로 구동하기 위한 WSGI 서버입니다.)*

---

## 🗄️ 3. 데이터베이스 초기화 (클린 설치의 경우)

기존 파이썬 DB 파일(`.db`)을 복사해오지 않았다면, 깡통 데이터베이스를 구성해야 합니다.

```bash
# 1. SQLite 핵심 스키마 생성
python create_db.py

# 2. (선택사항) 알림 리드 테이블 등 추가 테이블 반영
python migrate_notifications.py
```
*(기록된 초기 관리자 계정 생성 혹은 데모 계정이 필요할 경우 데모 유저 생성 스크립트(`seed_demo_data.py`)를 실행하여 초기화할 수 있습니다.)*

---

## 🌐 4. 웹 서버 구동하기

테스트 환경에서는 `python app.py`로 띄웠지만, 접근성을 높히기 위해 `gunicorn` 백그라운드 데몬 프로세스를 추천합니다. 

```bash
# Gunicorn을 이용한 백그라운드 구동
# 워커 4개(-w 4), 클라우드의 모든 Inbound 접근 허용(-b 0.0.0.0:5000), 백그라운드 데몬화(--daemon)
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon

# (만약 Gunicorn 구동을 중지하고 싶다면)
# pkill gunicorn
```

서버 구동이 완료되면, 클라우드 내부망에서 해당 분석 환경 인스턴스의 IP를 확인하여 **`http://<가상머신내부IP>:5000`** 로 접속할 수 있습니다.

---

## 🔗 5. 구성원과 URL 공유 (포트 확인)

해당 URL 주소를 팀원에게 배포하기 전 다음 사항을 확인해야 합니다.

1. **포트(Port) 개방 여부**: 리눅스 머신의 보안 그룹 또는 Inbound 규칙상 **TCP 5000번 포트가 오픈**되어 있어야 합니다.
2. **Reverse Proxy (Nginx 적용 시 참고)**: 클라우드 접속 정책상 80번(기본 HTTP) 포트만 포워딩된다면 리눅스에 Nginx 설정을 추가해 5000번 포트와 연결시켜주시면 됩니다.
   ```nginx
   server {
       listen 80;
       server_name _;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
       }
   }
   ```

포트 연결이 확인되면 담당 구성원들에게 **"Nexus AI 접속 주소: http://(서버IP 혹은 내부도메인):5000"** 과 함께 접속 아이디를 안내해주시면 즉시 사용할 수 있습니다.
