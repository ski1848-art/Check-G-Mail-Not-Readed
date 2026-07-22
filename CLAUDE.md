# Check Gmail Not Readed — Claude Code 가이드

## 사용자 권한 (최우선)
- **사용자 명시 지시 > 하네스 규칙 > 에이전트 자율 판단**
- "오케스트라/팀/사업부" 명시 시 **규모 무관 팀 생성 필수**
- **자기 코드 자기 검증 = 검증 아님** — 메인 작성 코드는 별도 에이전트가 교차 검증
- 예외: 보안 훅과 `## 절대 금지`는 오버라이드 불가

## 기획↔실행
- 기획 최대 2라운드 → 구현 착수. Python 코드 수정 후 **자동 테스트(pytest) 실행** 권장.
- IOV: WHY → OUTCOME → VERIFY 3단 게이트. 상세 → `rules/iov-framework.md`

## 절대 금지
1. Bedrock 키, Slack 토큰, Gmail 서비스 계정 키 코드에 하드코딩 금지 → 환경변수 경유
2. Firestore에 직접 서비스 계정 JSON 내용 노출 금지
3. "안 된다" 즉시 선언 금지 — 최소 2가지 대안 후 불가 보고
4. 정석 우선 — 임시 우회는 정석 불가 시에만
5. 2회 동일 실패 → 근본 원인 분석 필수
6. `/run-batch` 수정 시 멱등성(중복 실행 안전성) 반드시 유지

## 프로젝트 핵심
- **목적**: Google Workspace Gmail → AI 분류 → Slack 라우팅 자동화
- **백엔드**: Python 3 + Flask, `app/` 디렉터리
- **AI**: AWS Bedrock (Claude Haiku) + Token-Watcher 프록시 게이트웨이
- **데이터**: Firebase Firestore (상태/라우팅/학습 저장)
- **관리 UI**: Next.js 14 + TypeScript + Tailwind CSS, `admin-web/` 디렉터리
- **인증(admin-web)**: Firebase Auth (NextAuth.js 연동)
- **배포**: Docker + Google Cloud Run, `deploy.sh` 사용
- **스케줄러**: Google Cloud Scheduler 5분 주기 `/run-batch` 호출

---

## 핵심 경로

| 경로 | 역할 |
|------|------|
| `app/main.py` | Flask 엔트리포인트 — run-batch, trigger-notification, block-notification, slack/interactive |
| `app/core/classifier.py` | 규칙 + AI(Bedrock) 이메일 중요도 분류기 |
| `app/core/router.py` | 이메일 → Slack 대상 라우팅 결정 |
| `app/services/gmail_service.py` | Gmail API 클라이언트 (도메인 위임) |
| `app/services/slack_service.py` | Slack Bot 메시지 전송 |
| `app/services/llm_service.py` | Bedrock / Token-Watcher LLM 호출 |
| `app/services/routing_store.py` | 라우팅 규칙 저장소 (Firestore 또는 JSON) |
| `app/services/learning_store.py` | 피드백 학습 데이터 저장 |
| `app/services/settings_store.py` | 시스템 설정 (Firestore `system_settings`) |
| `app/utils/state_store.py` | 중복 알림 방지 상태 (File 또는 Firestore) |
| `admin-web/app/api/` | Next.js API Routes (Firestore Admin SDK 사용) |
| `admin-web/lib/firebase-admin.ts` | Firebase Admin SDK 초기화 — `getDb()`(Firestore) / `getAuth()` 제공 |
| `admin-web/lib/utils.ts` | 공통 유틸리티 |
| `config/routing_rules.json` | 라우팅 규칙 (JSON 모드 시) |
| `config/spam_filter.json` | 스팸/노이즈 필터 설정 |

---

## Flask 배치 처리 흐름

```
Cloud Scheduler (5분) → POST /run-batch
  → GmailService.get_unread_emails() (모든 사용자)
  → 병렬: process_single_event()
      → Router.get_targets()
      → state_store.is_duplicate() 체크
      → Classifier.classify() [규칙 → AI]
      → SlackService.send_notification()
      → Firestore 스냅샷 저장
```

> **AI 비용 절감**: 중요도 판단(AI)은 본문 없이 수행하고, 알림 대상(NOTIFY)으로 확정된 메일만 본문으로 요약한다.
> **재발 방지**: 일일 한도 외에 월 비용 상한(`MONTHLY_LIMIT_COST_USD`)과 사용량 급증 감지(`SettingsStore.check_usage_spike` — 최근 평균 대비 총비용/통당 비용 급증 시 Slack 알림)를 적용한다.

---

## Admin Web API (Next.js)

| 경로 | 역할 |
|------|------|
| `GET/POST /api/routing-rules` | 전체 라우팅 규칙 목록/생성 |
| `GET/PUT/DELETE /api/routing-rules/[slackUserId]` | 개별 규칙 조회/수정/삭제 |
| `GET/POST /api/routing-rules/[slackUserId]/preferences` | 사용자 알림 선호도 |
| `GET /api/routing-rules/[slackUserId]/history` | 라우팅 이력 |
| `GET/POST /api/email-events` | 이메일 이벤트 목록/조회 |
| `POST /api/email-events/[id]/block` | 이벤트 차단 |
| `POST /api/email-events/[id]/trigger` | 이벤트 수동 트리거 |
| `GET/PUT /api/settings` | 시스템 설정 |
| `GET /api/stats` | 처리 통계 |
| `GET /api/stats/cost` | LLM 비용 통계 |
| `GET /api/audit-logs` | 감사 로그 |
| `GET /api/system` | 시스템 상태 확인 |

---

## 팀메이트 (오케스트라 시 스폰, 실시간 협업)

| 팀메이트 | 모델 | 담당 |
|---------|------|------|
| `code-architect` | Opus | 설계 + 구현 스펙 작성 |
| `api-worker` | Sonnet | Flask API + Next.js API Routes 구현 |
| `ui-worker` | Sonnet | admin-web Next.js 컴포넌트/페이지 구현 |
| `spec-compliance-reviewer` | Opus | 구현 결과 스펙 준수 검증 |

---

## 서브에이전트 (백그라운드 실행, 결과만 반환)

| 서브에이전트 | 모델 | 담당 |
|------------|------|------|
| `test-runner` | Sonnet | pytest (Python) + tsc --noEmit (admin-web) |
| `parallel-reviewer` | Sonnet | 코드 품질/컨벤션 검토 |
| `perf-reviewer` | Sonnet | 성능 분석 (N+1, 불필요 API 호출 등) |
| `security-auditor` | Opus | 보안 감사 (토큰 노출, HMAC 검증 등) |
| `root-cause-analyst` | Opus | 버그 근본 원인 분석 |
| `doc-syncer` | Sonnet | docs/ 문서 동기화 |
| `ui-designer` | Sonnet | admin-web UI/UX 설계+구현 |
| `ui-ux-expert` | Sonnet | UX 검증 |
| `harness-audit` | Sonnet | 하네스 설정 평가 |

경로: `.claude/agents/{name}.md`

---

## 스킬 (자동 주입 + 사용자 직접 호출)

| 스킬 | 자동 트리거 / 용도 |
|------|------------------|
| `security-checklist` | `app/main.py`, `admin-web/app/api/**` 수정 시 |
| `ui-ux-expert` | `admin-web/app/**/*.tsx` 수정 시 |
| `playwright-verify` | admin-web UI 변경 후 3-breakpoint 검증 |
| `tdd` | 신규 기능 개발 시 TDD 워크플로우 |
| `feature-planning` | 신규 기능 스펙 작성 |
| `team-build` | 오케스트라 빌드 |
| `session-handoff` | 컨텍스트 압축 전 상태 저장 |
| `deep-security` | 심층 보안 감사 필요 시 |
| `team-config` | 하네스/에이전트/스킬/설정 수정 시 |
| `team-docs` | 문서 정리 작업 시 |
| `prd-writer` | PRD/스펙 문서 작성 시 |
| `restart-server` | admin-web 개발 서버 재시작 (포트 2222) |

경로: `.claude/skills/{name}/SKILL.md`
> 범용 스킬(`architecture`, `research`, `learn`, `tdd`, `full-sweep` 등)은 글로벌(`~/.claude/skills/`)에서 자동 로딩됩니다.

---

## MCP 서버

| MCP 서버 | 용도 | 연결 에이전트 |
|---------|------|-------------|
| `playwright` | admin-web 스냅샷/UI 검증 (`.mcp.json`에 설정됨) | ui-worker, spec-compliance-reviewer, ui-designer |

> Gmail 조회가 필요하면 claude.ai Gmail 커넥터(`mcp__claude_ai_Gmail__*`)를 사용. 별도 프로젝트 MCP 서버는 미설정.

---

## 테스트

```bash
# Python 단위 테스트 (프로젝트 루트에서)
python -m pytest tests/ -v

# admin-web TypeScript 타입 검증
cd admin-web && npx tsc --noEmit

# admin-web 개발 서버 (포트 2222 — package.json의 next dev -p 2222)
cd admin-web && npm run dev
```
