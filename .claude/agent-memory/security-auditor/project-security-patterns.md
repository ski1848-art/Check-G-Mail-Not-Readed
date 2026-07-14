---
name: Check Gmail Not Readed 보안 감사 이력
description: 2026-04-02 Cloud Run 배포 전 심층 보안 감사 결과 및 알려진 패턴
type: project
---

# 보안 감사 이력 (2026-04-02)

## 확인된 패턴 (PASS)
- admin-web API 전체: getServerSession() 인증 체크 일관되게 구현됨
- Slack HMAC: hmac.compare_digest + replay attack(5분) 방어 올바르게 구현
- Firestore 쿼리: 사용자 입력을 직접 쿼리 키로 사용하지 않음 (doc ID = slack_user_id, 화이트리스트 검증 후 사용)
- LLM API 키: 환경변수 경유 (Config.TOKEN_WATCHER_KEY, Config.AWS_ACCESS_KEY_ID)
- SSL: SlackService WebClient 기본 SSL 검증 사용 (이전에 ssl_verify=False 있었으나 제거됨)

## 알려진 취약점

### WARN (수정 권장)
1. `/run-batch` Flask 엔드포인트 — 인증 없음. Cloud Run 내부 + GCP Cloud Scheduler이 유일 호출자이므로 실용적 리스크 낮음. 단, Cloud Run URL이 공개되면 무단 배치 트리거 가능. 완화: OIDC 토큰 검증 추가 권장.
2. `/trigger-notification`, `/block-notification` Flask 엔드포인트 — 인증 없음. admin-web에서만 호출하는 내부 API이나, Flask URL 직접 접근 시 인증 없음.
3. CORS 설정: Flask에서 `/slack/*`, `/trigger-notification`, `/block-notification` 에 `origins: "*"` 설정. Slack interactive는 Slack 서버에서만 호출이나, trigger/block은 넓음.
4. `DEFAULT_COST_ALERT_RECIPIENT = "U04E9PMTLTZ"` 하드코딩 — 개인 Slack ID 노출. 보안 시크릿은 아니지만 소스코드 공개 시 개인 정보 노출.
5. `ADMIN_EMAIL` Config 기본값 하드코딩: `ski1848@hotseller.co.kr` — 이메일 주소 소스코드 노출.
6. `BEDROCK_MODEL_ID` ARN에 AWS 계정 ID 하드코딩: `arn:aws:bedrock:us-east-1:210506716773:...`

### CRITICAL npm 의존성
- next 패키지: GHSA-f82v-jwr5-mffw (Authorization Bypass in Middleware), GHSA-ggv3-7p47-pfv8 (HTTP request smuggling) 포함 다수 취약점. npm update next 필요.
- fast-xml-parser: GHSA-m7jm-9gc2-mpf2 (entity encoding bypass) 등 다수. 직접 사용 여부 확인 필요.

## False Positive 이력
- Slack Button value에 sender/subject 포함 → XSS 아님 (Slack Block Kit은 서버에서 렌더링, 브라우저 직접 노출 없음)
- DEFAULT_COST_ALERT_RECIPIENT Slack ID 하드코딩 → 보안 시크릿 아님 (public Slack User ID는 API로 조회 가능한 값)

**Why:** Cloud Run 배포 전 보안 최종 검토
**How to apply:** 다음 감사 시 동일 패턴 재확인, npm 업그레이드 여부 체크
