# CloudTajo Settlement Backend

CloudTajo 서비스의 정산 업무를 처리하는 FastAPI 백엔드 프로젝트입니다.

## 백엔드의 역할

프론트엔드에서 전달한 정산 관련 요청을 받아 다음 업무를 담당합니다.

- 정산 대상 데이터와 요청 값 검증
- 정산 기준에 따른 금액 계산 및 정산 결과 생성
- 정산 데이터 저장·조회·수정
- 사용자 인증 및 역할별 접근 권한 처리
- 필요 시 데이터베이스와 클라우드 인프라 연동

현재는 백엔드 기본 구조와 개발 환경을 검증하기 위한 단계입니다. 이후 실제 정산 정책이 확정되면 도메인 모델, PostgreSQL 저장소, 인증/인가, 운영 환경 설정을 순차적으로 추가합니다.

## 개발 환경

| 항목 | 버전 및 설정 |
| --- | --- |
| 언어 | Python 3.14.7 |
| 웹 프레임워크 | FastAPI 0.142.2 |
| ASGI 서버 | Uvicorn 0.54.0 |
| 서비스 포트 | TCP 8000 |

## macOS 로컬 실행

프로젝트 루트에서 다음 명령어를 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

로컬 개발 서버는 `127.0.0.1:8000`에서 실행됩니다. API 문서는 다음 주소에서 확인할 수 있습니다.

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

## 네이버 클라우드 실행 정보

네이버 클라우드 서버에서 외부 요청을 받을 때는 다음 명령어를 사용합니다.

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

네트워크 설정에서는 백엔드 서버의 TCP `8000` 포트 인바운드 접근을 허용해야 합니다. 
운영 환경에서는 필요한 대상만 허용하도록 ACG 규칙을 제한하고, 가능하면 리버스 프록시를 통해 외부에 공개합니다.

## 테스트

```bash
pytest
```

## DB 연결 확인

프로젝트 루트의 `.env`에 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`를 설정합니다.
애플리케이션은 SQLAlchemy와 PyMySQL을 사용하고, `.env`를 자동으로 읽어 MySQL 연결을 구성합니다.

```bash
python -c 'from app.common.database import check_database_connection; check_database_connection(); print("DB connection ok")'
```

DB 연결이 되지 않으면 Cloud DB의 접근 제어, VPC·Subnet 경로, 포트 `3306`, 계정 권한을 확인해야 합니다.

## 임시 로그인 테스트 계정

회원가입 API가 구현되기 전까지 로그인 테스트에 사용할 수 있는 개발용 계정입니다.

```text
이메일: test@example.com
비밀번호: test1234!
역할: USER
```

이 계정은 현재 인메모리 저장소에만 존재하며, 실제 `users` 테이블 연결 후에는 DB 시드 데이터로 이전해야 합니다.
