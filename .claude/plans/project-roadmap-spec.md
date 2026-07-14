# Check Gmail Not Readed - 프로젝트 발전 로드맵

> 작성일: 2026-04-02
> 작성자: code-architect (Opus)
> 기반: 전체 코드베이스 직접 읽기 분석

---

## 1. Bedrock 과금 최소화 전략 (최우선)

### 1.1 현재 LLM 호출 구조 분석

**호출 경로** (`classifier.py:67-96`):
```
GmailEvent → _apply_rules() → [PASS?] → LLM 호출 → _apply_thresholds()
                ↓                              ↑
         SILENT/NOTIFY(즉시)          화이트리스트 NOTIFY도
                                      요약용 LLM 재호출 (L77-80)
```

**현재 비용 구조**:
- 모델: Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`)
- 입력 단가: $0.80/1M tokens, 출력 단가: $4.00/1M tokens
- 비용 계산: `main.py:356` — `cost_usd = ((input_tokens * 0.80) + (output_tokens * 4.00)) / 1_000_000`
- 일일 한도: 기본 1000 calls, $5.0 (`settings_store.py:124`)
- 배치 주기: 5분 (`Cloud Scheduler`)

**현재 비용 절감 메커니즘** (이미 구현됨):
1. 규칙 기반 사전 필터: 블랙리스트/스팸키워드 → SILENT (LLM 미호출) (`classifier.py:98-119`)
2. 캐시 재사용: 이미 처리된 메일 → 기존 결과 재사용 (`main.py:263-279`)
3. Token-Watcher 프록시: LLM 호출 추적/제어 (`llm_service.py:52-54`)
4. Bedrock ephemeral 캐시: system prompt 캐싱 (`llm_service.py:81`)
5. 일일 한도 자동 차단 (`settings_store.py:267-287`)
6. 콘텐츠 기반 중복 방지: 10분 윈도우 (`state_store.py:292-313`)

### 1.2 추가 최적화 전략

#### S1. 규칙 기반 필터링 강화 (비용 절감 효과: 높음)

**현재 문제점**:
- `spam_filter.json`의 블랙리스트/키워드가 매우 제한적 (8개 도메인, 7개 키워드)
- `urgent_keywords`는 현재 코드에서 사용 안 됨 (`classifier.py:116-117` 주석 처리)
- 자동학습된 차단 패턴(`user_feedback` 컬렉션)이 규칙 필터에 미반영

**개선안**:
- **R1-1. 자동 블랙리스트 승격**: `user_feedback` 컬렉션에서 N명 이상이 차단한 발신자/도메인 → 자동으로 `blacklist_domains`에 승격하는 배치 작업 추가
  - AC: GIVEN 3명 이상 사용자가 동일 발신자를 차단 WHEN 일일 배치 실행 THEN 해당 발신자가 블랙리스트에 자동 추가되어 LLM 호출 스킵
- **R1-2. 도메인 기반 no-reply 자동 SILENT**: `noreply@`, `no-reply@`, `mailer-daemon@` 패턴을 규칙에 추가
  - AC: GIVEN 발신자가 no-reply 패턴 WHEN 분류 시 THEN LLM 호출 없이 SILENT 처리
- **R1-3. 반복 메일 패턴 학습**: 매일 동일 시간에 오는 자동화 메일(리포트, 알림) 패턴을 감지하여 규칙화
  - AC: GIVEN 동일 발신자+유형이 7일 연속 도착 WHEN 분류 시 THEN 학습된 규칙으로 LLM 스킵

**예상 효과**: LLM 호출 20-40% 감소 (no-reply + 반복 메일이 전체 메일의 상당 비율)

#### S2. 스마트 캐싱 강화 (비용 절감 효과: 중간)

**현재 문제점**:
- 캐시가 `message_id` 기반 (동일 메일만 히트)
- 유사한 메일(같은 발신자+같은 유형)은 매번 LLM 호출

**개선안**:
- **R2-1. 발신자+유형 캐시**: 최근 24시간 내 동일 발신자+동일 유형패턴의 분류 결과를 캐시
  - 구현: `learning_store.py`의 `extract_email_type_pattern()` 활용하여 캐시 키 생성
  - AC: GIVEN 동일 발신자가 동일 유형 메일을 24시간 내 재전송 WHEN 분류 시 THEN 캐시된 category+score 재사용 (요약은 새로 생성)
- **R2-2. 요약 생략 옵션**: 사용자 설정에 따라 NOTIFY일 때만 요약 생성 (현재 화이트리스트도 요약 호출)
  - 현재: `classifier.py:77-80`에서 화이트리스트 NOTIFY도 요약용 LLM 호출
  - AC: GIVEN 화이트리스트 발신자 WHEN 분류 시 THEN 사용자 설정에 따라 요약 생략 가능

**예상 효과**: LLM 호출 추가 10-20% 감소

#### S3. 배치 최적화 (비용 절감 효과: 낮음-중간)

**현재 문제점**:
- `llm_service.py:133-134`에서 본문을 2000자로 잘라 전송하지만, 많은 메일은 snippet만으로 충분
- 각 메일마다 독립 LLM 호출 (배치 API 미활용)

**개선안**:
- **R3-1. 2단계 분류**: 1단계에서 snippet(짧은 텍스트)만으로 빠른 판단 → 불확실한 경우만 2단계 본문 분석
  - AC: GIVEN 메일 snippet WHEN 1단계 점수가 0.2 미만 또는 0.8 이상 THEN 2단계 스킵
- **R3-2. 토큰 사용량 최적화**: system prompt를 더 간결하게 압축 (현재 `_build_system_prompt`가 상당히 김)

#### S4. 비용 모니터링/알림 자동화 (운영 효율)

**현재 상태**: 대시보드에서 수동 확인만 가능 (`page.tsx:274-307`)

**개선안**:
- **R4-1. 비용 알림**: 일일 한도 80% 도달 시 관리자 Slack 알림 전송
  - AC: GIVEN 일일 비용이 한도의 80% 도달 WHEN 배치 실행 시 THEN 관리자에게 Slack 경고 메시지 전송
- **R4-2. 주간 비용 리포트**: 매주 월요일 자동 비용 요약 Slack 메시지
  - AC: GIVEN 월요일 오전 WHEN 스케줄러 실행 THEN 지난주 비용 요약 Slack 전송

---

## 2. 기능 발전 로드맵

### P0: 핵심 안정성 (즉시 필요)

| ID | 기능 | 근거 | 영향도 |
|----|------|------|--------|
| P0-1 | Slack 서명 검증 미적용 | `main.py:397-668` — `/slack/interactive`에 HMAC 검증 없음. 현재 CORS만 설정. SLACK_SIGNING_SECRET은 Config에 있지만 검증 로직 없음 | 보안 Critical |
| P0-2 | Firestore 클라이언트 중복 초기화 | `routing_store.py`, `settings_store.py`, `learning_store.py`, `state_store.py` — 4개 모듈이 각각 독립적으로 Firestore 클라이언트 초기화. 환경변수 조작(backup/restore)이 각 모듈에 중복됨 | 안정성/유지보수 |
| P0-3 | SSL 검증 비활성화 | `slack_service.py:41` — `urllib3.disable_warnings()` + `ssl.CERT_NONE`. 프로덕션에서도 적용됨 | 보안 Medium |
| P0-4 | 에러 복구 전략 부재 | Gmail API 실패 시 재시도 로직 없음 (`gmail_service.py:153-163`). 단순 `except` → 빈 리스트 반환 | 안정성 |

### P1: 사용자 경험 개선 (3개월 내)

| ID | 기능 | 설명 | 가치 |
|----|------|------|------|
| P1-1 | 스레드 기반 알림 그룹화 | 현재 동일 스레드의 메일도 개별 알림. Gmail의 thread_id 활용하여 Slack 스레드로 묶기 | 알림 노이즈 대폭 감소 |
| P1-2 | 알림 스케줄 설정 | 사용자별 알림 수신 시간대 설정 (예: 업무 시간에만). 현재 24시간 무차별 전송 | 사용자 만족도 |
| P1-3 | AI 분류 정확도 피드백 루프 | Slack 버튼에 "잘못 분류됨" 옵션 추가 → 분류 정확도 개선 데이터 수집 | 장기 품질 |
| P1-4 | 다국어 요약 지원 | 영어 메일의 한국어 요약 품질 향상 (현재 프롬프트에 한국어 지시만) | 사용성 |
| P1-5 | 대시보드 실시간 웹소켓 | 현재 폴링 방식(30초). 웹소켓으로 실시간 업데이트 | UX |
| P1-6 | Slack 앱 홈 탭 | Slack 내에서 직접 설정/통계 확인 가능한 App Home | 접근성 |

### P2: 장기 발전 (6개월+)

| ID | 기능 | 설명 | 가치 |
|----|------|------|------|
| P2-1 | 멀티 워크스페이스 지원 | 현재 단일 Google Workspace 전용. 다수 조직 지원 | 확장성 |
| P2-2 | Calendar/Drive 연동 | 메일 외에 캘린더 초대, Drive 공유 알림도 분류 | 범위 확장 |
| P2-3 | 자동 응답 초안 | AI가 간단한 답장 초안을 Slack에서 제공 | 생산성 |
| P2-4 | 분류 모델 파인튜닝 | 축적된 피드백 데이터로 분류 모델 미세조정 (또는 few-shot learning 고도화) | 정확도 |
| P2-5 | Outlook/Microsoft 365 지원 | Gmail 외 Microsoft 생태계 지원 | 범위 확장 |
| P2-6 | 모바일 알림 통합 | Slack 외에 모바일 푸시(FCM) 직접 지원 | 채널 확장 |

---

## 3. 기술 부채

### 우선순위 순 목록

| 순위 | 항목 | 위치 | 심각도 | 설명 |
|:----:|------|------|:------:|------|
| 1 | Firestore 클라이언트 중복 초기화 | `routing_store.py:44-74`, `settings_store.py:52-70`, `learning_store.py:24-65`, `state_store.py:150-201` | High | 4개 모듈이 각각 독립적으로 Firestore 초기화 + GOOGLE_APPLICATION_CREDENTIALS 환경변수 조작. 공통 팩토리로 통합 필요 |
| 2 | 타입 안전성 부재 (admin-web) | `admin-web/app/users/page.tsx:12` | Medium | `useState<any[]>([])` — 타입 미정의. API 응답 타입이 인터페이스로 정의되지 않은 곳 다수 |
| 3 | import 구조 비일관성 | `main.py:106,262,297` | Low | 함수 내부에서 `from ... import ...` 반복. 모듈 레벨 import로 통일 필요 |
| 4 | 설정값 하드코딩 | `main.py:356` — Haiku 단가 직접 기재, `settings_store.py:124` — 일일 한도 기본값 | Low | Config 또는 Firestore 설정으로 이동 |
| 5 | Prior 시스템 미활용 | `learning_store.py:501-840` | Medium | `get_org_prior`, `get_user_prior`, `calculate_engagement_score` 등 정교한 Prior 계산 로직이 구현되어 있으나 `classifier.py`에서 호출하지 않음. 분류 파이프라인에 통합 필요 |
| 6 | 테스트 부족 | `tests/` 디렉토리 존재하나 커버리지 미확인 | Medium | classifier, router 핵심 로직의 단위 테스트 보강 필요 |
| 7 | boto3 불필요 의존성 | `requirements.txt:12` | Low | `anthropic` 라이브러리가 Bedrock 접근을 직접 처리하므로 `boto3` 불필요할 수 있음 |
| 8 | openai 불필요 의존성 | `requirements.txt:4` | Low | OpenAI SDK가 포함되어 있으나 코드에서 사용하지 않음 |
| 9 | Dead Code | `slack_service.py:260-291` | Low | `_build_message()` 레거시 메서드 미사용 |
| 10 | admin-web 서비스 정보 하드코딩 | `admin-web/app/page.tsx:420-429` | Low | 버전, AI 엔진명 등이 JSX에 직접 하드코딩 |

---

## 4. admin-web 개선안

### 4.1 현재 상태 평가

**잘 된 점**:
- 대시보드 구성이 종합적 (통계, 비용, 시스템 제어 통합)
- 이벤트 모니터링 자동 새로고침, 필터링 잘 구현
- Block Kit 스타일 Tailwind CSS 일관성
- 시스템 제어 (일시중지/재시작/수동배치) 관리자 기능 완비

**개선 필요 영역**:

| ID | 영역 | 현재 | 개선안 |
|----|------|------|--------|
| A1 | 사용자 차단 목록 관리 | 차단 목록을 admin-web에서 볼 수 없음 | `user_feedback` 컬렉션 조회/편집 UI 추가. 사용자별 차단 패턴 목록, 삭제 기능 |
| A2 | AI 분류 정확도 대시보드 | 없음 | 알림 전송 → 사용자 열람률, 차단 전환률 등 AI 품질 지표 시각화 |
| A3 | 비용 알림 설정 UI | 대시보드에서 수동 확인만 | 한도 설정 + 알림 임계값 + 알림 채널(Slack/이메일) 설정 UI |
| A4 | 이벤트 상세 모달 | `alert()`으로 판별 사유 표시 (`events/page.tsx:291-296`) | 모달로 전환: AI 요약, 점수, 사유, 토큰 사용량, 원본 메일 미리보기 |
| A5 | 반응형 개선 | 대시보드 일부 요소 모바일 미대응 | 모바일 레이아웃 최적화, 테이블 → 카드 뷰 토글 |
| A6 | 검색 고도화 | 텍스트 매칭만 (`events/page.tsx:151-156`) | 날짜 범위, 점수 범위, 발신자 도메인, 분류 소스(Rule/AI) 복합 필터 |
| A7 | 설정 페이지 확장 | 블랙리스트/키워드 관리 | 화이트리스트 관리, 임계값 슬라이더, 배치 주기 설정 추가 |
| A8 | 감사 로그 강화 | 기본 로그 목록 | 변경 diff, 변경 전/후 값 비교, 필터링 |

### 4.2 UI 와이어프레임: 사용자 차단 목록 관리 (A1)

```
┌─────────────────────────────────────────────────────────┐
│ 사용자 관리 > [홍길동 (U04E9PMTLTZ)]                      │
├─────────────────────────────────────────────────────────┤
│  [기본 정보]  [알림 설정]  [차단 목록]  [활동 이력]          │
│  ─────────────────────────────────────────               │
│  차단 목록 (3건)                          [+ 수동 추가]    │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 발신자           │ 유형 패턴          │ 차단일   │ 작업│
│  │ news@example.com │ 뉴스레터           │ 03/15  │ [삭제]│
│  │ noreply@hr.co    │ 채용 지원 알림      │ 03/20  │ [삭제]│
│  │ alert@monitor.io │ 일일 리포트         │ 03/28  │ [삭제]│
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 4.3 UI 와이어프레임: 이벤트 상세 모달 (A4)

```
┌─────────────────────────────────────────────────┐
│ [X]  메일 처리 상세                                │
├─────────────────────────────────────────────────┤
│                                                   │
│  제목: [긴급] 서버 장애 발생                        │
│  발신자: admin@server.com                          │
│  수신자: team@company.com                          │
│  수신 시각: 2026-04-02 14:30:22 KST               │
│                                                   │
│  ── AI 분석 결과 ──                                │
│  분류: [알림 전송]  점수: 0.92  소스: AI 분석       │
│  사유: 서버 장애 관련 긴급 알림으로 즉각적인...      │
│                                                   │
│  ── AI 요약 ──                                     │
│  * 프로덕션 서버 3대 장애 발생                      │
│  * 현재 복구 작업 진행 중                           │
│  * 영향 범위 확인 후 공유 예정                      │
│                                                   │
│  ── 비용 정보 ──                                   │
│  입력 토큰: 1,234  출력 토큰: 89                    │
│  비용: $0.0013                                     │
│                                                   │
│  ── 알림 대상 ──                                   │
│  [홍길동] [김철수]                                  │
│                                                   │
│              [Gmail 열기]  [닫기]                   │
└─────────────────────────────────────────────────┘
```

---

## 5. 구현 순서 / 의존성

```
Phase 1 (즉시 - 보안+안정성):
  P0-1 Slack 서명 검증 ─────┐
  P0-3 SSL 검증 정상화 ─────┤
  P0-4 에러 재시도 로직 ────┘─→ [배포]

Phase 2 (1-2주 - 비용 절감):
  S1. 규칙 필터 강화 ──────────→ [배포]
  S2. 발신자+유형 캐시 ────────→ [배포]
  P0-2 Firestore 클라이언트 통합 → [배포]

Phase 3 (1개월 - UX):
  A1 차단 목록 관리 UI ────┐
  A4 이벤트 상세 모달 ─────┤
  A3 비용 알림 설정 UI ────┘─→ [배포]
  P1-1 스레드 그룹화 ─────────→ [배포]

Phase 4 (3개월 - 고도화):
  P1-2 알림 스케줄 ────────┐
  P1-3 피드백 루프 ────────┤
  S4 비용 자동 알림 ───────┘─→ [배포]
  기술부채 #5 Prior 시스템 통합 → [배포]

Phase 5 (6개월+ - 확장):
  P2 항목들 (멀티 워크스페이스, Calendar, 자동 응답 등)
```

---

## 6. 비기능 요구사항

### 성능
- 배치 처리: 50건 메일 → 30초 이내 완료 (현재 ThreadPoolExecutor 15 workers)
- LLM 응답: 10초 이내 (현재 timeout 180초 → 과도, 30초 적정)
- admin-web 초기 로딩: 3초 이내 (현재 3개 API 병렬 호출)

### 보안
- Slack 인터랙션 HMAC 검증 필수 (P0-1)
- 모든 admin API에 Firebase Auth 토큰 검증 (현재 구현됨)
- AWS 키, Slack 토큰 환경변수 경유 (현재 구현됨)
- SSL 검증 프로덕션 활성화 (P0-3)

### 접근성
- admin-web 키보드 내비게이션
- 스크린 리더 지원 (시맨틱 HTML)
- 색상 대비 WCAG 2.1 AA

### 관찰성 (Observability)
- 구조화 로깅 (현재 JSON 형식, Cloud Logging 연동)
- 비용 추적 (현재 Firestore daily_usage)
- 에러 추적 (현재 로그만, Sentry 등 미연동)

---

## 7. 엣지 케이스

| 시나리오 | 현재 동작 | 개선 필요 |
|---------|---------|---------|
| Gmail API 할당량 초과 | 배치 전체 실패 | 사용자별 독립 실패 처리 + 재시도 |
| LLM 서비스 장애 | Token-Watcher→Bedrock 폴백 | 모두 실패 시 규칙 기반만으로 처리 + 관리자 알림 |
| Firestore 장애 | 학습/상태 저장 실패, 알림은 계속 | 메모리 캐시 폴백은 있으나 재시작 시 유실 |
| 동시 배치 실행 | Cloud Scheduler 중복 호출 가능 | 배치 잠금 메커니즘 (Firestore transaction) |
| 대용량 메일 본문 | 2000자 절삭 | 적절하나, 절삭 위치가 의미 경계 무시 |
| 사용자 Gmail 권한 취소 | 403 에러 → 빈 리스트 | 관리자에게 권한 문제 알림 필요 |
| 신규 사용자 첫 배치 | `newer_than:1d` 쿼리로 최근 1일 메일 | 첫날 대량 메일 처리 → LLM 비용 급증 가능 → 초기 한도 별도 설정 필요 |

---

## 8. DB 스키마 변경 사항

### 신규 컬렉션 (제안)

```
# 자동 블랙리스트 승격용 (S1 규칙 강화)
auto_blacklist_candidates:
  doc_id: {sender_hash}
  fields:
    sender: string
    blocked_by_users: string[]  # 차단한 사용자 ID 목록
    blocked_count: int
    first_blocked_at: timestamp
    promoted_to_blacklist: bool
    promoted_at: timestamp | null

# 발신자+유형 캐시 (S2 캐싱 강화)
classification_cache:
  doc_id: {sender}_{type_pattern_hash}
  fields:
    sender: string
    type_pattern: string
    cached_category: string  # "notify" | "silent"
    cached_score: float
    cached_reason: string
    hit_count: int
    created_at: timestamp
    expires_at: timestamp  # TTL 24시간
```

### 기존 컬렉션 수정

```
# routing_rules — 변경 없음
# email_events — 변경 없음
# user_feedback — 변경 없음
# system_settings — 비용 알림 임계값 추가
  + cost_alert_threshold_percent: float (default: 0.8)
  + cost_alert_slack_channel: string
# system_control — 변경 없음
# daily_usage — 변경 없음
```

---

## 스펙 품질 체크리스트

- [x] 모든 요구사항(R)에 인수 기준(AC)이 있는가? — S1, S2의 핵심 항목 AC 포함
- [x] 비기능 요구사항(성능/보안/접근성)이 포함되었는가? — 섹션 6
- [x] 엣지 케이스가 정의되었는가? — 섹션 7 (7개 시나리오)
- [x] UI 와이어프레임/ASCII가 포함되었는가? — 섹션 4.2, 4.3
- [x] API 엔드포인트 목록이 있는가? — 기존 API 유지, 신규는 Phase별 상세 스펙에서
- [x] DB 스키마 변경이 명시되었는가? — 섹션 8
- [x] 구현 순서/의존성이 정의되었는가? — 섹션 5 (5개 Phase)
