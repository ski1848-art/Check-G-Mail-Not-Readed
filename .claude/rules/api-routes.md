---
paths:
  - "app/**/*.py"
  - "admin-web/app/api/**/*.ts"
---

# API Route 규칙

## Flask 백엔드 (app/)

### 응답 형식
- 성공: `jsonify({"success": True, "data": ...}), 200`
- 실패: `jsonify({"success": False, "error": str(e)}), 4xx/500`
- 모든 핸들러 try-except 감싸기

### 인증/보안
- Slack 인터랙션: `hmac.compare_digest`로 서명 검증 필수 (`SLACK_SIGNING_SECRET`)
- 관리자 API: Firebase ID 토큰 검증 또는 내부 호출만 허용
- 환경변수 직접 코드 하드코딩 금지 → `Config.*` 경유

### Cloud Scheduler 호출 (`/run-batch`)
- 멱등성 보장 (중복 실행 안전)
- `state_store`로 중복 알림 체크 후 처리
- 처리 실패는 개별 로깅 후 계속 진행 (전체 배치 중단 금지)

## Next.js Admin Web API (admin-web/app/api/)

### 인증
- next-auth `getServerSession()` 으로 세션 검증 (`const session = await getServerSession(); if (!session) return 401`)
- 모든 보호 라우트에서 세션 체크 필수

### 응답 형식
- 성공: `NextResponse.json({ success: true, data: ... })`
- 실패: `NextResponse.json({ success: false, error: string }, { status: 4xx })`

### Firestore 접근
- `admin-web/lib/firebase-admin.ts`의 `getDb()` 로 인스턴스 획득 후 사용
- 직접 서비스 계정 키 경로 참조 금지 → 환경변수 `GOOGLE_APPLICATION_CREDENTIALS` 경유

## 공통
- 외부 시스템 상태(Gmail, Slack, Bedrock)는 직접 API 확인 우선 — 로컬 상태만으로 "정상" 결론 금지
- 2회 동일 실패 → 근본 원인 분석 후 대안 제시
