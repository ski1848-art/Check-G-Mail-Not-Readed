"""
tests/conftest.py — 테스트 환경 격리 (운영 자격증명 차단)

[목적]
어느 폴더(메인 체크아웃, 워크트리 .claude/worktrees/..., CI)에서 pytest를 돌리든
운영 자격증명(.env의 AWS 키, Slack 토큰, Token-Watcher 접속 정보 등)이
테스트에 섞여 들어가지 않도록 세션 시작 시 빈 값으로 고정한다.

[배경 — 2026-10-28]
app/config.py의 load_dotenv()가 상위 폴더를 거슬러 올라가 메인 체크아웃의
운영 .env를 읽었고, 그 결과 LLMService 등이 운영 자격으로 외부 접속을 준비하느라
hypothesis 테스트 13건이 기본 deadline(200ms)을 넘겨 DeadlineExceeded로 실패했다.
(app/config.py는 프로젝트 루트의 .env만 읽도록 함께 수정됨 — 이 파일은 2중 안전장치.)

[동작 원리]
- pytest는 테스트 모듈을 import하기 전에 이 conftest.py를 먼저 로드한다.
- 여기서 os.environ에 빈 값을 넣어두면 app.config의 load_dotenv()(override=False)가
  .env 값으로 덮어쓰지 못한다. 결과적으로 Config.* 자격증명은 모두 빈 문자열이 되어
  각 서비스가 "자격 없음" 경로(외부 호출 생략)로 동작한다.
- 반드시 모듈 최상위에서 실행해야 한다. fixture(session scope 포함)는 collection
  이후에 실행되므로 이미 import된 Config 클래스 속성에는 영향을 주지 못한다.
- 운영(Cloud Run)에는 영향 없음 — pytest 실행 시에만 로드되는 파일이다.
"""
import os
import sys

# 이 파일이 app.config보다 먼저 로드된다는 전제를 명시적으로 검증한다.
# (플러그인 등이 app을 먼저 import하면 아래 환경변수 고정이 소용없어지므로 즉시 알린다.)
assert "app.config" not in sys.modules, (
    "tests/conftest.py가 app.config보다 늦게 로드되었습니다. "
    "운영 자격증명 차단이 동작하지 않으니 import 순서를 확인하세요."
)

# 테스트에서 절대 사용하면 안 되는 운영 자격증명/외부 접속 설정.
_PRODUCTION_CREDENTIAL_KEYS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "LLM_API_KEY",
    "TOKEN_WATCHER_URL",
    "TOKEN_WATCHER_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "INTERNAL_API_KEY",
)

for _key in _PRODUCTION_CREDENTIAL_KEYS:
    os.environ[_key] = ""
