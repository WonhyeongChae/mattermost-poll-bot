# Mattermost Poll Bot

Mattermost 채널에서 슬래시 명령으로 투표를 만들고 대화형 버튼으로 참여하는 범용 투표 봇입니다.

## MVP 기능

- `/poll 질문 | 선택지 1 | 선택지 2 | ...` 형식의 투표 생성
- 선택지 2~10개 지원
- 사용자당 한 표 및 선택 변경
- 실시간 득표수 표시
- 생성자 전용 투표 종료
- 게시물·채널 정보가 일치하는 콜백만 처리
- 동시 투표를 위한 데이터베이스 UPSERT
- 채널별 복수 투표 지원
- SQLite 개발 환경과 PostgreSQL 운영 환경 지원

## 명령 예시

```text
/poll 점심 메뉴 | 한식 | 중식 | 일식
```

빈 선택지와 중복 선택지는 거부합니다. 선택지가 6개 이상이면 Mattermost 버튼 제한을 고려해 여러 영역으로 분할합니다.

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Windows PowerShell에서는 가상환경 활성화 명령으로 `.venv\Scripts\Activate.ps1`을 사용합니다.

상태 확인:

```text
GET http://localhost:8000/health
```

## 환경변수

| 이름 | 설명 |
|---|---|
| `DATABASE_URL` | SQLAlchemy 데이터베이스 주소 |
| `PUBLIC_BASE_URL` | Mattermost가 호출할 공개 HTTPS 주소 |
| `MATTERMOST_BASE_URL` | Mattermost 서버 주소 |
| `MATTERMOST_BOT_TOKEN` | 게시물 생성용 Bot 또는 Personal Access Token |
| `MATTERMOST_COMMAND_TOKEN` | Slash Command 요청 검증 토큰 |

비밀값은 `.env` 또는 배포 환경의 Secret으로만 관리합니다. 운영 서버는 시작 전에 `alembic upgrade head`를 실행해야 하며, 제공된 Dockerfile은 이를 자동 수행합니다.

## Mattermost 설정

Custom Slash Command를 다음 기준으로 생성합니다.

- Command Trigger Word: `poll`
- Request Method: `POST`
- Request URL: `https://<배포주소>/mattermost/commands/poll`
- Response Username: `Poll Bot`
- Autocomplete Hint: `질문 | 선택지 1 | 선택지 2`

생성 후 발급된 Token을 `MATTERMOST_COMMAND_TOKEN`에 등록합니다. 봇 계정은 대상 채널에 참여해야 합니다.

## 테스트

```bash
python -m pytest -q
```

## API

| 경로 | 역할 |
|---|---|
| `GET /health` | 서버 상태 확인 |
| `POST /mattermost/commands/poll` | 투표 생성 명령 처리 |
| `POST /mattermost/actions/vote` | 투표 선택 및 변경 |
| `POST /mattermost/actions/close` | 생성자 전용 종료 |

## 현재 단계

초기 MVP와 운영 안전성 보강 완료. 실제 SSAFY Mattermost 권한 확인, PostgreSQL 배포, Slash Command 연결이 다음 단계입니다.
