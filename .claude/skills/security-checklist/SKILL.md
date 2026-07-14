---
name: security-checklist
description: Gmail 알림 라우팅 프로젝트 보안 체크리스트 — Flask 백엔드(app/) + admin-web(Next.js) API Routes 대상. security-auditor 에이전트가 참조.
paths:
  - "app/**/*.py"
  - "app/main.py"
  - "admin-web/app/api/**/*.ts"
  - "admin-web/lib/firebase-admin.ts"
---

# 보안 체크리스트 (Check Gmail Not Readed)

## 도구 기반 스캔 (설치되어 있으면 실행, 없으면 스킵)
```bash
gitleaks detect --no-git
grep -rnE "SLACK_BOT_TOKEN|AKIA[0-9A-Z]{16}|xox[bp]-[0-9A-Za-z-]+" app/ admin-web/app admin-web/lib \
  --include="*.py" --include="*.ts" --include="*.tsx"
cd admin-web && npm audit --json 2>/dev/null | jq '.metadata.vulnerabilities'
trivy fs --scanners vuln,secret --severity HIGH,CRITICAL --quiet .   # 선택
```

## Flask 백엔드 (app/) 체크리스트

### Slack 요청 검증 (`/slack/interactive`)
- [ ] `hmac.compare_digest`로 서명 검증 (문자열 `==` 비교 금지 — 타이밍 공격 방어). 기존 패턴: `app/main.py`의 `slack_signing_secret` 검증 블록
- [ ] `SLACK_SIGNING_SECRET` 미설정 시 요청을 **거부**하는지 확인 (스킵하고 통과시키면 안 됨)
- [ ] `X-Slack-Request-Timestamp`와 현재 시각 차이가 5분을 넘으면 재전송(replay) 공격으로 간주하고 거부하는 로직이 있는지 확인 (없으면 추가 검토)

### 내부 API 인증 (`/run-batch`, `/trigger-notification`, `/block-notification`)
- [ ] 각 라우트 진입 직후 `_check_internal_auth()` 호출 확인 (`Authorization: Bearer {INTERNAL_API_KEY}`)
- [ ] `INTERNAL_API_KEY` 미설정 시 인증이 스킵되는 것은 로컬 개발 전용 동작 — 운영(Cloud Run) 배포 전 실제로 설정돼 있는지 `deploy.sh`/환경변수로 확인
- [ ] Cloud Scheduler가 호출하는 엔드포인트에 인증을 우회할 수 있는 대체 경로(다른 메서드, 트레일링 슬래시 등)가 없는지 확인

### 시크릿 하드코딩 금지
- [ ] `SLACK_BOT_TOKEN`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `LLM_API_KEY`, `TOKEN_WATCHER_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`(서비스 계정 키 경로) 값을 코드에 직접 기입 금지 → `app/config.py`의 `Config.*` (환경변수) 경유
- [ ] Gmail 서비스 계정 키 JSON 원문을 로그, API 응답, Firestore 문서에 노출 금지

### 예외 응답 노출
- [ ] `jsonify({"status": "error", "message": str(e)})` 형태로 예외 원문을 그대로 클라이언트에 반환하는 핸들러가 다수 있음(`app/main.py`) — 내부 경로·DB 연결 정보 등 민감 정보가 메시지에 섞이지 않는지 확인, 필요 시 일반화된 메시지로 치환
- [ ] 상세 스택트레이스는 `logger.error(..., exc_info=True)`로 서버 로그에만 남기기

### Firestore 입력 검증
- [ ] 요청 바디에서 받은 값(`email_id`, `target_ids` 등)을 검증 없이 그대로 `collection(...).document(...)` 의 문서 ID로 사용하는 곳 확인 (예: `/trigger-notification`의 `email_id`) — 빈 문자열, `/` 포함 등 비정상 값 방지
- [ ] `app/services/routing_store.py`, `app/utils/state_store.py`의 `document(doc_id)` 호출부에서 doc_id 생성 로직이 신뢰 가능한 값(해시/내부 생성)인지, 외부 입력을 직접 쓰는지 확인

## admin-web (Next.js API Routes) 체크리스트

### 인증
- [ ] `admin-web/app/api/**/route.ts`의 모든 핸들러가 `getServerSession()` (next-auth) 호출 후 세션 없으면 401 반환하는지 확인 — 기존 12개 라우트(routing-rules, settings, email-events, stats, audit-logs, system 등) 전부 적용된 패턴이므로 신규/수정 라우트도 동일하게 유지
- [ ] `admin-web/app/api/auth/[...nextauth]/route.ts`의 `signIn` 콜백(`ALLOWED_EMAIL_DOMAIN` / `ADMIN_EMAILS` 화이트리스트)을 우회할 수 있는 경로가 없는지 확인
- [ ] `admin-web/lib/firebase-admin.ts`의 `getDb()` / `getAuth()`는 서버 전용 — `"use client"` 컴포넌트에서 import 금지 (클라이언트 번들에 서비스 계정 정보 유입 방지)

### Firestore 접근
- [ ] `GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64` (서비스 계정 Base64) 값이 API 응답이나 클라이언트 번들로 새어나가지 않는지 확인
- [ ] Firestore 쓰기 시 `updated_by: session.user.email` 같은 감사 필드를 요청 바디로 덮어쓸 수 없는지 확인 (`{ ...body }` 형태로 통째로 spread하지 말고 필드 화이트리스트 사용)

### XSS
- [ ] `dangerouslySetInnerHTML` 사용 금지 (현재 admin-web 소스에는 사용처 없음 — 신규로 추가한다면 반드시 사유 확인 및 sanitize)
- [ ] 사용자 입력을 렌더링할 때 React 기본 이스케이프에 의존 (직접 HTML 문자열을 조립해 삽입 금지)

### 민감 데이터
- [ ] `.env`, 서비스 계정 키 파일 등 로컬 시크릿이 Git에 커밋되거나 API 응답에 포함되지 않는지 확인
- [ ] API 응답에 Firebase 서비스 계정 키, Slack 토큰, AWS 키가 포함되지 않는지 확인
