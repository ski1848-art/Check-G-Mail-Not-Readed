# Implementation Spec: Check Gmail Not Readed 전체 개선

> 작성일: 2026-04-02
> 작성자: code-architect (Opus)
> 기반: 전체 코드베이스 직접 읽기 분석 + project-roadmap-spec.md

---

## 구현 항목 총괄

| # | 항목 | 우선순위 | 난이도 | 워커 | 의존성 |
|---|------|:-------:|:-----:|------|-------|
| A1 | 배치 내 LLM 한도 재확인 | P0 | S | api-worker | 없음 |
| A2 | Token-Watcher 서킷 브레이커 | P0 | M | api-worker | 없음 |
| A3 | 화이트리스트 요약 경량화 | P1 | S | api-worker | 없음 |
| A4 | no-reply 자동 SILENT 규칙 | P1 | S | api-worker + db-worker | 없음 |
| A5 | 수동 배치 빈도 제한 | P1 | S | api-worker | 없음 |
| B1 | Slack HMAC 서명 검증 | P0 | M | api-worker | 없음 |
| B2 | SSL 검증 정상화 | P0 | S | api-worker | 없음 |
| C1 | Prior 시스템 연결 | P2 | L | api-worker | A1 완료 후 |
| D1 | Firestore 팩토리 통합 | P1 | M | api-worker | 없음 |
| E1 | 이벤트 상세 모달 | P1 | M | ui-worker | 없음 |
| E2 | 사용자 차단 목록 탭 개선 | P1 | S | ui-worker | 없음 |
| E3 | 비용 알림 임계값 설정 UI | P1 | M | ui-worker + api-worker | 없음 |
| F1 | openai/boto3 불필요 의존성 제거 | P2 | S | api-worker | 없음 |
| F2 | Dead code 정리 | P2 | S | api-worker | 없음 |

---

## A. 과금 방어 (최우선)

### A1. 배치 내 LLM 한도 재확인

**WHY**: 현재 `is_system_enabled()`은 `run_batch()` 진입 시 1회만 호출됨(`main.py:84-96`). 50건 배치 중 40번째에서 한도를 초과해도 나머지 10건은 그대로 LLM 호출.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/main.py:282-290` (process_single_event 내 LLM 호출 직전) | 수정 |

**구체적 변경**:
- `process_single_event()` 내에서 `classifier.classify()` 호출 직전에 `settings.check_daily_limit_exceeded()` 재확인
- 초과 시 LLM 스킵하고 `AnalysisResult(score=0.0, category=SILENT, reason="일일 한도 초과로 AI 분석 스킵", source=RULE)` 반환
- `SettingsStore`가 이미 싱글톤 + 캐시(TTL 5분)이므로 성능 부담 없음

**인수 기준 (AC)**:
- GIVEN 일일 한도가 80% 이상 소진된 상태
- WHEN 50건 배치 실행 중 한도 초과 시점 도달
- THEN 해당 시점 이후 메일은 LLM 호출 없이 SILENT 처리, 초과 호출 0건

**워커**: api-worker
**난이도**: S (5줄 이내)
**예상 효과**: 한도 초과 시 불필요 과금 완전 차단

---

### A2. Token-Watcher 서킷 브레이커

**WHY**: `llm_service.py:55-58`에서 Token-Watcher 실패 시 Bedrock 직접 호출로 폴백하는데, 배치 내 연속 실패가 발생하면 매 건마다 Token-Watcher 타임아웃(최대 180초) + Bedrock 호출이 반복되어 배치 시간 폭증.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/services/llm_service.py` | 수정 |

**구체적 변경**:
- `LLMService` 클래스에 인스턴스 변수 추가: `_tw_fail_count: int = 0`, `_tw_circuit_open: bool = False`
- `_call_token_watcher()` 실패 시 `_tw_fail_count += 1`
- `_tw_fail_count >= 3`이면 `_tw_circuit_open = True` → 이후 배치 내에서 Token-Watcher 시도 자체를 스킵
- 다음 배치(`analyze_email()` 첫 호출 시) 리셋

**인수 기준 (AC)**:
- GIVEN Token-Watcher가 3회 연속 실패
- WHEN 4번째 이상 LLM 호출
- THEN Token-Watcher 시도 없이 바로 Bedrock 직접 호출, 타임아웃 대기 시간 0

**워커**: api-worker
**난이도**: M (15-20줄)
**예상 효과**: Token-Watcher 장애 시 배치 시간 3분 이상 → 30초 이내 단축

---

### A3. 화이트리스트 요약 경량화

**WHY**: `classifier.py:76-80`에서 화이트리스트 NOTIFY 메일도 요약용 LLM 호출 수행. 화이트리스트는 이미 "중요" 판정이므로 점수/카테고리 재분석 불필요하고, 요약만 필요. 그런데 현재 `analyze_email()`은 전체 분석(점수+카테고리+요약)을 수행.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/services/llm_service.py` | 수정 (메서드 추가) |
| `app/core/classifier.py:76-80` | 수정 |

**구체적 변경**:
- `LLMService`에 `summarize_only(event)` 메서드 추가: system prompt를 "요약만 하라. JSON 없이 불릿 포인트 텍스트만 반환"으로 변경, max_tokens를 256으로 축소
- `classifier.py:79`의 `self.llm_service.analyze_email(event, user_preferences_map)` → `self.llm_service.summarize_only(event)` 호출
- 응답에서 summary만 추출, 나머지(score/category/reason)는 기존 rule_result 유지

**인수 기준 (AC)**:
- GIVEN 화이트리스트 발신자의 메일
- WHEN 분류 파이프라인 실행
- THEN max_tokens 256으로 요약만 생성 (기존 512 대비 50% 절감), 출력 토큰 감소

**워커**: api-worker
**난이도**: S (새 메서드 20줄 + 호출부 변경 3줄)
**예상 효과**: 화이트리스트 메일당 출력 토큰 40-50% 절감

---

### A4. no-reply 자동 SILENT 규칙

**WHY**: `noreply@`, `no-reply@`, `mailer-daemon@` 등의 발신자는 거의 100% 자동화 메일. 현재 `spam_filter.json`에 일부만 등록(`workspace-noreply@google.com`, `no-reply@accounts.google.com`). 패턴 기반으로 일괄 처리 필요.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/core/classifier.py:98-119` (_apply_rules 내부) | 수정 |
| `config/spam_filter.json` | 수정 (noreply_patterns 키 추가) |

**구체적 변경**:
- `_apply_rules()`에 블랙리스트 체크 전 no-reply 패턴 체크 추가:
  ```python
  # No-reply 패턴 → 즉시 SILENT
  noreply_patterns = ["noreply@", "no-reply@", "no_reply@", "mailer-daemon@", "donotreply@"]
  if any(p in sender for p in noreply_patterns):
      return AnalysisResult(score=0.0, category=SILENT, reason=f"자동 발신 메일 (no-reply: {sender})", source=RULE)
  ```
- `spam_filter.json`에 `"noreply_patterns"` 키 추가 (관리자가 패턴 추가/삭제 가능하도록)
- settings_store를 통해 Firestore에서 동적 관리 가능 (기존 패턴 따름)

**인수 기준 (AC)**:
- GIVEN 발신자가 noreply@, no-reply@ 패턴
- WHEN 분류 파이프라인 실행
- THEN LLM 호출 없이 즉시 SILENT 처리

**워커**: api-worker (코드) + db-worker (config JSON)
**난이도**: S (10줄 이내)
**예상 효과**: 전체 메일 중 no-reply 비율에 따라 LLM 호출 10-15% 추가 감소

---

### A5. 수동 배치 빈도 제한

**WHY**: `admin-web/app/api/system/route.ts:120-142`의 `run_batch` 액션에 빈도 제한 없음. 관리자가 연속 클릭하면 중복 배치 실행 → 불필요한 LLM 비용.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `admin-web/app/api/system/route.ts` (POST, case "run_batch") | 수정 |

**구체적 변경**:
- `run_batch` 실행 전 `system_control/status`의 `last_batch_at` 확인
- 마지막 배치 실행 후 2분 이내면 `{ success: false, message: "최소 2분 간격으로 실행 가능합니다." }` 반환
- Firestore 읽기 1회 추가 (이미 GET에서 읽는 collection이므로 비용 무시)

**인수 기준 (AC)**:
- GIVEN 마지막 배치 실행 후 2분 미만
- WHEN 관리자가 "수동 실행" 클릭
- THEN 실행 거부 + 남은 대기 시간 메시지 반환

**워커**: api-worker
**난이도**: S (10줄 이내)
**예상 효과**: 실수에 의한 중복 배치 방지

---

## B. 보안 패치 (P0)

### B1. Slack HMAC 서명 검증

**WHY**: `main.py:397-669`의 `/slack/interactive` 엔드포인트에 HMAC 검증 **전혀 없음**. `Config.SLACK_SIGNING_SECRET`이 존재하고 `hmac`, `hashlib`가 이미 import 되어 있으나, 검증 로직이 구현되지 않음. 외부에서 Slack 인터랙션을 위조하여 `silent_forever`, `undo_silent`, `mark_as_read_gmail` 등의 액션을 실행할 수 있는 보안 취약점.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/main.py:397-410` (/slack/interactive 진입부) | 수정 |

**구체적 변경**:
- `/slack/interactive` 핸들러 시작부에 서명 검증 함수 추가:
  ```python
  def _verify_slack_signature(request) -> bool:
      """Slack 요청의 HMAC-SHA256 서명을 검증"""
      signing_secret = Config.SLACK_SIGNING_SECRET
      if not signing_secret:
          logger.warning("SLACK_SIGNING_SECRET not configured, skipping verification")
          return True  # 미설정 시 패스 (기존 동작 유지)
      
      timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
      signature = request.headers.get('X-Slack-Signature', '')
      
      # 5분 이상 오래된 요청은 거부 (리플레이 공격 방지)
      if abs(time.time() - int(timestamp)) > 300:
          return False
      
      sig_basestring = f"v0:{timestamp}:{request.get_data(as_text=True)}"
      my_signature = 'v0=' + hmac.new(
          signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
      ).hexdigest()
      
      return hmac.compare_digest(my_signature, signature)
  ```
- `slack_interactive()` 진입부에 호출: 실패 시 `return '', 403`
- `import time` 추가 (main.py 상단)

**인수 기준 (AC)**:
- GIVEN SLACK_SIGNING_SECRET이 설정된 환경
- WHEN Slack이 아닌 외부에서 /slack/interactive POST 요청
- THEN 403 반환, 액션 실행 안 됨

**워커**: api-worker
**난이도**: M (20줄)
**예상 효과**: Slack 인터랙션 위조 방지 (보안 Critical)

---

### B2. SSL 검증 정상화

**WHY**: `slack_service.py:41-48`에서 `urllib3.disable_warnings()` + `ssl.CERT_NONE` 설정이 모듈 레벨에서 적용되어 프로덕션에서도 SSL 검증이 비활성화됨. 단, Slack WebClient는 `ssl_context` 파라미터를 통해 별도 제어 가능하며, 실제로 `slack_service.py:61`에서 기본 SSL context로 WebClient를 초기화하므로 Slack 통신 자체는 정상 SSL 사용. 문제는 `get_ssl_context()` 함수와 `urllib3.disable_warnings()`가 다른 모듈(requests 등)에 영향을 줄 수 있다는 점.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/services/slack_service.py:40-48` | 삭제 |

**구체적 변경**:
- `urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)` 삭제
- `get_ssl_context()` 함수 삭제 (사용처 없음 -- 호출하는 코드가 없음)
- `import ssl`, `import urllib3`, `from urllib3.util.ssl_ import create_urllib3_context` import 삭제 (다른 곳에서 미사용)

**인수 기준 (AC)**:
- GIVEN 프로덕션 환경
- WHEN Slack API 호출 또는 requests.post() 호출
- THEN 정상 SSL 인증서 검증 수행

**워커**: api-worker
**난이도**: S (코드 삭제만)
**예상 효과**: SSL MITM 공격 방어 (보안 Medium)

---

## C. Prior 시스템 연결

### C1. Prior 시스템을 분류 파이프라인에 연결

**WHY**: `learning_store.py:501-839`에 정교한 Prior 계산 로직(조직/개인 단위, engagement 점수 기반)이 완전히 구현되어 있으나 `classifier.py`에서 호출하지 않음. 또한 `Config`에 `PRIOR_MIN_SAMPLES`, `IMPLICIT_POS_READ_MIN`, `IMPLICIT_SCORE_READ_STRONG`, `BASELINE_PRIOR` 등의 상수가 **정의되어 있지 않아** Prior 관련 함수가 현재 런타임에서 `AttributeError`를 발생시킬 수 있음.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/config.py` | 수정 (Prior 관련 상수 추가) |
| `app/core/classifier.py` | 수정 (Prior 조회 + 점수 조정) |
| `app/main.py:330-347` (snapshot 저장부) | 수정 (prior_used/prior_value 실제값 전달) |

**구체적 변경**:

1. **config.py**: Prior 관련 상수 추가
   ```python
   # Prior 시스템 설정
   PRIOR_MIN_SAMPLES: int = int(os.environ.get("PRIOR_MIN_SAMPLES", "5"))
   BASELINE_PRIOR: float = float(os.environ.get("BASELINE_PRIOR", "0.5"))
   PRIOR_ALPHA: float = float(os.environ.get("PRIOR_ALPHA", "0.3"))  # prior 가중치
   
   # Implicit Feedback 점수
   IMPLICIT_POS_READ_MIN: int = 10   # 읽음까지 10분 이내 = 강한 긍정
   IMPLICIT_POS_READ_2H: int = 120   # 읽음까지 2시간 이내 = 약한 긍정
   IMPLICIT_SCORE_READ_STRONG: float = 1.0
   IMPLICIT_SCORE_READ_WEAK: float = 0.5
   IMPLICIT_SCORE_CLICK: float = 0.2
   ```

2. **classifier.py**: `classify()` 내 LLM 결과에 Prior 적용
   ```python
   # Step 2.5: Prior 조정 (LLM 결과 후, 임계값 적용 전)
   from app.services.learning_store import get_org_prior, get_user_prior
   
   org_prior, org_samples, org_source = get_org_prior(event.sender, sender_domain)
   if org_prior is not None:
       alpha = Config.PRIOR_ALPHA
       llm_result.score = alpha * org_prior + (1 - alpha) * llm_result.score
   ```

3. **main.py**: snapshot 저장 시 실제 prior 값 전달 (현재 `prior_used="none"` 하드코딩)

**인수 기준 (AC)**:
- GIVEN 발신자가 5회 이상 메일을 보냈고 engagement 데이터가 있는 경우
- WHEN 분류 파이프라인 실행
- THEN Prior 값이 LLM 점수에 반영되어 조정된 최종 점수로 판정

**워커**: api-worker
**난이도**: L (3개 파일, config 상수 + 분류 로직 + 저장 로직 변경)
**예상 효과**: 반복 발신자에 대한 분류 정확도 개선 (장기)
**의존성**: A1 완료 후 (한도 체크 먼저 안정화)

---

## D. Firestore 팩토리 통합

### D1. 4개 모듈의 중복 Firestore 초기화를 공통 팩토리로 통합

**WHY**: `routing_store.py:44-74`, `settings_store.py:52-70`, `learning_store.py:24-65`, `state_store.py:150-201` -- 4개 모듈이 각각 독립적으로 Firestore 클라이언트를 초기화. 특히 `GOOGLE_APPLICATION_CREDENTIALS` 환경변수 조작(JSON 문자열 감지 → 임시 제거 → 복원) 로직이 3곳에서 중복.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/services/firestore_factory.py` | 신규 생성 |
| `app/services/routing_store.py:44-74` | 수정 (팩토리 사용) |
| `app/services/settings_store.py:52-70` | 수정 (팩토리 사용) |
| `app/services/learning_store.py:24-65` | 수정 (팩토리 사용) |
| `app/utils/state_store.py:150-201` | 수정 (팩토리 사용) |

**구체적 변경**:
- `firestore_factory.py` 신규 생성:
  ```python
  """Firestore 클라이언트 공통 팩토리 (싱글톤)"""
  _client = None
  _lock = threading.Lock()
  
  def get_firestore_client():
      global _client
      if _client is not None:
          return _client
      with _lock:
          if _client is not None:
              return _client
          # GOOGLE_APPLICATION_CREDENTIALS JSON 처리 로직 1회만
          ...
          _client = firestore.Client(project=..., credentials=...)
          return _client
  ```
- 4개 모듈의 Firestore 초기화 코드를 `get_firestore_client()` 호출로 교체
- 기존 모듈별 캐시/TTL 로직은 유지 (팩토리는 클라이언트 생성만 담당)

**인수 기준 (AC)**:
- GIVEN 앱 시작
- WHEN 4개 모듈이 Firestore 클라이언트 요청
- THEN 단일 클라이언트 인스턴스 공유, GOOGLE_APPLICATION_CREDENTIALS 조작 1회만 실행

**워커**: api-worker
**난이도**: M (신규 파일 1개 + 4개 파일 수정)
**예상 효과**: 코드 중복 제거, Firestore 연결 안정성 향상

---

## E. admin-web UX 개선

### E1. 이벤트 상세 모달

**WHY**: `events/page.tsx:291-296`에서 판별 사유를 `alert()`으로 표시. AI 요약, 점수, 토큰/비용 정보 등 풍부한 데이터가 Firestore에 있으나 UI에 노출되지 않음.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `admin-web/app/events/page.tsx` | 수정 (모달 컴포넌트 추가) |

**구체적 변경**:
- 기존 `alert()` 호출을 모달 열기로 교체
- 모달에 표시할 정보 (Firestore `email_events`에 이미 저장된 필드):
  - 제목, 발신자, 수신자, 수신 시각
  - AI 분류 결과: category, score, source(Rule/AI)
  - AI 판별 사유 (reason)
  - AI 핵심 요약 (summary)
  - 토큰 사용량: llm_input_tokens, llm_output_tokens
  - 비용: 계산식 적용 (input * 0.80 + output * 4.00) / 1M
  - 알림 대상자 (slack_targets_with_names)
- 모달 UI: ESC 닫기, 외부 클릭 닫기, body scroll lock

**와이어프레임**:
```
+---------------------------------------------------+
| [X]  메일 처리 상세                                  |
+---------------------------------------------------+
|                                                     |
|  제목: [긴급] 서버 장애 발생                          |
|  발신자: admin@server.com                            |
|  수신자: team@company.com                            |
|  수신 시각: 2026-04-02 14:30:22 KST                 |
|                                                     |
|  -- AI 분석 결과 --                                  |
|  분류: [알림 전송]  점수: 0.92  소스: AI 분석         |
|  사유: 서버 장애 관련 긴급 알림으로 즉각적인...        |
|                                                     |
|  -- AI 요약 --                                       |
|  * 프로덕션 서버 3대 장애 발생                        |
|  * 현재 복구 작업 진행 중                             |
|  * 영향 범위 확인 후 공유 예정                        |
|                                                     |
|  -- 비용 정보 --                                     |
|  입력 토큰: 1,234  출력 토큰: 89                      |
|  비용: $0.0013                                       |
|                                                     |
|  -- 알림 대상 --                                     |
|  [홍길동] [김철수]                                    |
|                                                     |
|              [Gmail 열기]  [닫기]                     |
+---------------------------------------------------+
```

**인수 기준 (AC)**:
- GIVEN 이벤트 목록의 "사유" 아이콘 클릭
- WHEN 모달이 열림
- THEN AI 요약, 점수, 토큰, 비용이 표시됨. ESC로 닫힘

**워커**: ui-worker
**난이도**: M (모달 컴포넌트 50-80줄)
**예상 효과**: 관리자가 AI 판단 근거를 한눈에 파악

**API 변경**: 없음 (기존 `/api/email-events` 응답에 이미 모든 필드 포함)

---

### E2. 사용자 차단 목록 탭 개선

**WHY**: `users/[slackUserId]/page.tsx:330-364`에 차단 목록이 이미 구현되어 있으나, `subject_pattern` (유형 패턴)이 표시되지 않음. 현재 `pref.sender`만 표시. Firestore `user_feedback` 컬렉션에 `subject_pattern` 필드가 저장되어 있으나 API가 반환하지 않을 수 있음.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `admin-web/app/users/[slackUserId]/page.tsx:330-364` | 수정 |
| `admin-web/app/api/routing-rules/[slackUserId]/preferences/route.ts` | 수정 (subject_pattern 포함 확인) |

**구체적 변경**:
- `Preference` 인터페이스에 `subject_pattern: string` 추가
- 차단 목록 카드에 유형 패턴 표시 (발신자 아래에 작은 글씨로)
- DELETE 시 `subject` 파라미터도 전달하여 정확한 패턴 매칭 삭제

**와이어프레임**:
```
+---------------------------------------------------+
| 사용자 차단 목록                                     |
+---------------------------------------------------+
| news@example.com                                    |
| 유형: 뉴스레터             차단일: 03/15   [해제]    |
|-----------------------------------------------------|
| noreply@hr.co                                       |
| 유형: 채용 지원 알림        차단일: 03/20   [해제]    |
+---------------------------------------------------+
```

**인수 기준 (AC)**:
- GIVEN 사용자 상세 페이지
- WHEN 차단 목록 표시
- THEN 발신자 + 유형 패턴 + 차단일이 모두 표시됨

**워커**: ui-worker
**난이도**: S (기존 UI 수정 10줄)
**예상 효과**: 관리자가 "어떤 유형"이 차단되었는지 정확히 파악

---

### E3. 비용 알림 임계값 설정 UI

**WHY**: 대시보드(`page.tsx:274-307`)에서 일일 한도 게이지를 볼 수 있으나, 한도 도달 전 경고 알림을 설정하는 UI가 없음. `system/route.ts`의 `set_limits` 액션은 있으나 알림 임계값은 미구현.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `admin-web/app/settings/page.tsx` | 수정 (새 탭 또는 기존 "AI & 성능" 탭에 추가) |
| `admin-web/app/api/settings/route.ts` | 수정 (cost_alert 필드 추가) |

**구체적 변경**:
- settings/page.tsx의 "AI & 성능" 탭에 추가:
  - 비용 알림 임계값 슬라이더 (50% ~ 95%, 기본 80%)
  - 알림 대상 Slack 채널 입력 (선택)
- Firestore `system_settings/general`에 추가 필드:
  - `cost_alert_threshold_percent: number` (기본 0.8)
  - `cost_alert_slack_channel: string` (선택)
- Python 백엔드에서 `settings_store.py`의 `check_daily_limit_exceeded()` 확장:
  - 임계값 도달 시 경고 (실제 Slack 알림 전송은 별도 항목)

**인수 기준 (AC)**:
- GIVEN 관리자가 설정 페이지 접근
- WHEN 비용 알림 임계값을 70%로 변경 후 저장
- THEN Firestore에 cost_alert_threshold_percent: 0.7 저장됨

**워커**: ui-worker (설정 UI) + api-worker (API 수정)
**난이도**: M (UI 30줄 + API 10줄)
**예상 효과**: 비용 사전 경고 기반 마련 (실제 Slack 알림 전송은 추후)

---

## F. 기술 부채

### F1. openai/boto3 불필요 의존성 제거

**WHY**: `requirements.txt:4`에 `openai>=1.0.0`, `requirements.txt:12`에 `boto3>=1.34.0`이 있으나, 코드 전체에서 `import openai`/`from openai` 또는 `import boto3`/`from boto3`가 **사용되지 않음** (Grep 확인 완료). `anthropic` 패키지가 Bedrock 접근을 직접 처리(`AnthropicBedrock` 클래스, `llm_service.py:23`).

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `requirements.txt` | 수정 (2줄 삭제) |

**구체적 변경**:
- `openai>=1.0.0` 삭제
- `boto3>=1.34.0` 삭제

**인수 기준 (AC)**:
- GIVEN requirements.txt에서 두 패키지 삭제
- WHEN `pip install -r requirements.txt && python -c "from app.main import app"` 실행
- THEN 에러 없이 앱 로딩 성공

**워커**: api-worker
**난이도**: S (2줄 삭제)
**예상 효과**: Docker 이미지 크기 약 50-100MB 감소 (boto3 의존성 트리가 매우 큼)

---

### F2. Dead code 정리

**WHY**: `slack_service.py:260-291`의 `_build_message()` 메서드는 레거시 텍스트 메시지 빌더. `send_notification()`에서 `_build_blocks()`만 사용하고, `_build_message()`는 호출처 없음.

**변경 파일**:
| 파일 | 변경 성격 |
|------|---------|
| `app/services/slack_service.py:260-291` | 삭제 |

**구체적 변경**:
- `_build_message()` 메서드 전체 삭제

**인수 기준 (AC)**:
- GIVEN 메서드 삭제
- WHEN pytest 실행
- THEN 테스트 통과, 기존 기능 정상

**워커**: api-worker
**난이도**: S (삭제만)
**예상 효과**: 코드 가독성 향상

---

## 워커별 파일 소유권

### api-worker
| 파일 | 항목 |
|------|------|
| `app/main.py` | A1, B1 |
| `app/core/classifier.py` | A3, A4, C1 |
| `app/services/llm_service.py` | A2, A3 |
| `app/services/slack_service.py` | B2, F2 |
| `app/services/firestore_factory.py` (신규) | D1 |
| `app/services/routing_store.py` | D1 |
| `app/services/settings_store.py` | D1 |
| `app/services/learning_store.py` | D1 |
| `app/utils/state_store.py` | D1 |
| `app/config.py` | C1 |
| `requirements.txt` | F1 |
| `admin-web/app/api/system/route.ts` | A5 |
| `admin-web/app/api/settings/route.ts` | E3 |

### ui-worker
| 파일 | 항목 |
|------|------|
| `admin-web/app/events/page.tsx` | E1 |
| `admin-web/app/users/[slackUserId]/page.tsx` | E2 |
| `admin-web/app/settings/page.tsx` | E3 |

### db-worker
| 파일 | 항목 |
|------|------|
| `config/spam_filter.json` | A4 |

### 공유 파일 (메인 소유)
| 파일 | 설명 |
|------|------|
| `admin-web/lib/firebase-admin.ts` | 변경 없음 |
| `admin-web/lib/utils.ts` | 변경 없음 |
| `app/models.py` | 변경 없음 |

---

## 구현 순서 / 의존성

```
Phase 1 (보안 + 즉시 과금 방어):
  B1 Slack HMAC 서명 검증 ──────┐
  B2 SSL 검증 정상화 ───────────┤
  A1 배치 내 LLM 한도 재확인 ───┤
  A2 서킷 브레이커 ─────────────┘─→ [배포 1]

Phase 2 (비용 최적화 + 기술 부채):
  A3 화이트리스트 요약 경량화 ──┐
  A4 no-reply 자동 SILENT ──────┤
  A5 수동 배치 빈도 제한 ───────┤
  D1 Firestore 팩토리 통합 ─────┤
  F1 의존성 제거 ───────────────┤
  F2 Dead code 정리 ────────────┘─→ [배포 2]

Phase 3 (UX 개선):
  E1 이벤트 상세 모달 ──────────┐
  E2 차단 목록 탭 개선 ─────────┤
  E3 비용 알림 임계값 UI ───────┘─→ [배포 3]

Phase 4 (고도화):
  C1 Prior 시스템 연결 ────────────→ [배포 4]
```

---

## 비기능 요구사항

### 성능
- A1: 한도 체크 추가 호출은 SettingsStore 캐시(TTL 5분) 덕분에 Firestore I/O 0
- A2: 서킷 오픈 후 Token-Watcher 타임아웃(180초) 제거 → 배치 시간 단축
- D1: Firestore 커넥션 4개 → 1개로 통합 → 커넥션 풀 효율

### 보안
- B1: OWASP API Security Top 10 - API5 Broken Function Level Authorization 대응
- B2: 프로덕션 SSL 검증 정상화

### 접근성
- E1: 모달에 aria-label, role="dialog", 포커스 트랩 적용
- E2: 시맨틱 마크업 유지

---

## 엣지 케이스

| 항목 | 시나리오 | 처리 방안 |
|------|---------|---------|
| A1 | 한도 체크 시점에 Firestore 장애 | `check_daily_limit_exceeded()` 실패 시 초과 안 한 것으로 간주 (기존 동작 유지) |
| A2 | 서킷 오픈 후 Bedrock도 장애 | 기존 폴백 로직 유지: `AnalysisResult(category=SILENT, reason="AI연결불가")` |
| A4 | no-reply인데 실제 중요 메일 | no-reply 패턴은 `_apply_rules()`에서 블랙리스트/스팸 체크 후 적용 → 화이트리스트가 우선이므로 화이트리스트 도메인의 no-reply는 그대로 NOTIFY |
| B1 | SLACK_SIGNING_SECRET 미설정 | 기존 동작 유지 (검증 스킵, 경고 로그) |
| C1 | Config에 Prior 상수 미정의 (현재 상태) | config.py에 기본값 포함하여 추가 → AttributeError 방지 |
| E1 | summary가 null인 이벤트 | 모달에서 "AI 요약 없음" 표시 |

---

## DB 스키마 변경

### 기존 컬렉션 수정

```
# system_settings/general
  + cost_alert_threshold_percent: float (기본 0.8)
  + cost_alert_slack_channel: string (선택)

# system_control/status — 변경 없음 (last_batch_at 이미 존재)
```

### 신규 컬렉션 — 없음

---

## 스펙 품질 체크리스트

- [x] 모든 요구사항(R)에 인수 기준(AC)이 있는가? — 14개 항목 전부 AC 포함
- [x] 비기능 요구사항(성능/보안/접근성)이 포함되었는가? — 명시
- [x] 엣지 케이스가 정의되었는가? — 6개 시나리오
- [x] UI 와이어프레임/ASCII가 포함되었는가? — E1, E2
- [x] API 엔드포인트 목록이 있는가? — 기존 API 수정만, 신규 없음
- [x] DB 스키마 변경이 명시되었는가? — system_settings에 2개 필드 추가
- [x] 구현 순서/의존성이 정의되었는가? — 4개 Phase

## 예상 총 변경 파일 수

- Python 백엔드: 9개 (수정 8 + 신규 1)
- admin-web: 5개 (수정 5)
- config: 1개 (수정 1)
- **총 15개 파일**
