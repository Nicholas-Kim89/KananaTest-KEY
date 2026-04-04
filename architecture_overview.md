# Nexus AI: 시스템 아키텍처 및 코드 구조 가이드

이 문서는 Nexus AI(업무 진척 관리 시스템)의 전체적인 시스템 작동 방식, 아키텍처 구성, 그리고 각 파일이 실제 서비스(운영)에 사용되는지 혹은 테스트/설정을 위한 것인지를 구분하여 설명합니다.

---

## 1. 시스템 아키텍처 개요

Nexus AI 시스템은 **Python Flask 기반의 웹 애플리케이션**으로 구성되어 있으며, 데이터는 **SQLite(정형 데이터)**와 **ChromaDB(비정형 벡터 데이터)**에 나뉘어 저장됩니다. 또한 구글의 **Gemini AI** 모델을 활용해 진척 데이터를 요약해주는 핵심 기능을 제공합니다.

### 🧩 주요 기술 스택
- **Backend**: Python 3, Flask
- **Database**: SQLite3 (관계형 DB), ChromaDB (Vector DB - RAG 검색용)
- **Frontend**: Vanilla HTML5, CSS (Custom Design System), Vanilla JavaScript
- **AI Integration**: Google GenAI SDK (`gemini-2.5-flash`, `text-embedding-004`)

### 🔄 전체 데이터 흐름
1. **사용자 액션**: 웹 UI에서 등록/수정/삭제 요청 (예: 진척사항 등록)
2. **Flask API**: `app.py`에서 요청을 수신 및 권한 검사
3. **DB 저장**: `SQLite (workprogress.db)`에 원본 데이터(텍스트, 일자, 부서 등) 저장
4. **RAG 동기화**: `rag.py`를 통해 새롭게 생성된 텍스트 데이터를 임베딩(Vectorize)하여 `ChromaDB`에 동기화
5. **AI 문서 요약 요청 시**: 사용자가 요약 요청 시, ChromaDB에서 연관 데이터를 검색하고, 그 결과를 Gemini AI에 문맥으로 전달하여 최종 요약 보고서를 생성(`app.py` -> `rag.py` -> Gemini API)

---

## 2. 파일 및 디렉토리 구조 (운영 vs 설정용)

리눅스 등 실제 운영 환경으로 이전할 때, 코드 베이스에 포함된 파일들을 **핵심 구동 파트**와 **초기 설정/테스트 파트**로 나눌 수 있습니다.

### 🟢 [핵심 운영 파일] (동작을 위해 반드시 필요한 필수 코드)
실제 웹사이트가 구동되고 서비스되는 데 직접적으로 관여하는 소스코드입니다. 리눅스 서버로 복사할 때 *반드시 포함*해야 합니다.

*   `app.py`: **애플리케이션의 메인 진입점(Entry Point)**. 백엔드 라우팅, 로그인/세션 관리, 권한 로직, API 엔드포인트 등을 담당합니다.
*   `db.py`: SQLite 데이터베이스 연결 및 초기화 관련 유틸리티 파일입니다.
*   `rag.py`: Gemini AI SDK 및 ChromaDB와의 연동을 담당하는 핵심 모듈로, AI 검색 및 벡터 동기화를 처리합니다.
*   `/templates/`: 웹 페이지 UI를 구성하는 HTML Jinja2 템플릿 폴더입니다. (`base.html`, `index.html`, `login.html`, `progress.html` 등)
*   `/static/`: 웹 페이지 렌더링에 필요한 정적 자산 폴더입니다. (`index.css` 등)
*   `requirements.txt`: Python 라이브러리 의존성 목록 파일입니다.

### 💾 [데이터 저장소] (운영 시 생성 및 유지보수 대상)
*   `workprogress.db`: SQLite 메인 데이터베이스 파일 (사용자, 조직, 시스템 데이터 전체)
*   `/chroma_db/`: ChromaDB가 생성하는 벡터 데이터 인덱스 폴더

*(참고: 클린 설치로 처음부터 텅 빈 환경에서 시작하고 싶다면, 위 파일/폴더를 복사하지 않고 서버에서 `create_db.py`를 실행해 새로 생성하면 됩니다. 기존 데이터를 그대로 가져가려면 함께 복사하세요.)*

### 🟡 [초기 설정 및 데이터 마이그레이션 도구] (초기에만 사용)
운영 중에는 직접 실행되지 않으나, 시스템을 처음 구축할 때 환경을 세팅하기 위해 만들어진 스크립트들입니다.

*   `create_db.py`: SQLite 테이블 스키마 및 초기 테이블(`users`, `teams`, `divisions`, `progress_logs`, `comments` 등)을 생성하는 스크립트.
*   `migrate_notifications.py`: 기존 DB가 있을 경우 새로운 테이블(`notification_reads`)을 추가하기 위한 마이그레이션 스크립트.

### 🔴 [개발/테스트용 코드] (운영에 불필요함)
개발 중 데이터 확인이나 강제 데이터 삽입을 위해 사용된 스크립트로, 실제 서버 실행 시에는 사용되지 않습니다. 제외하고 복사해도 무방합니다.

*   `seed_demo_data.py`: 초기 테스트를 위해 가상의 조직도, 사용자를 DB에 욱여넣는 스크립트.
*   `seed_test_data.py`: 더 많은 더미 데이터 생성을 위한 스크립트.
*   `check_tables.py`, `db_dump.py`: 개발 과정에서 DB 테이블의 스키마와 데이터 상태를 디버깅하기 위해 생성한 덤프 스크립트.

---

## 3. 핵심 정리

*   **웹 서비스 구동**: `python app.py` (혹은 서버 환경에서는 Gunicorn 사용) 명령만으로 켜지는 구조입니다. `app.py`가 모든 요청을 통제합니다.
*   리눅스 서버 환경에 배포할 때는 **`🟢 핵심 운영 파일`**과 `requirements.txt`만 넘긴 뒤, 필요한 라이브러리를 설치하고 구동시키기만 하면 시스템은 완전히 분리 독립되어 동작합니다.
