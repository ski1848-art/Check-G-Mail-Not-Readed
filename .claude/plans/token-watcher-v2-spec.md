# Token Watcher v2 통합 — 구현 스펙

> 작성일: 2026-04-07
> 작성자: code-architect (Opus)
> 기반: `app/services/llm_service.py`, `app/config.py`, `test_token_watcher.py` 직접 읽기 분석

---

## 개요

Token Watcher v2 프록시를 LLM 호출 1순위로 재도입하고, Bedrock 직접 호출을 폴백으로 유지한다.
v2의 핵심 변경은 `pass_through_body` 필드 — Bedrock invoke-model 형식을 그대로 감싸서 전달.

**현재 상태**: `LLMService`가 `AnthropicBedrock` SDK로 직접 호출만 수행.
**목표 상태**: Token Watcher v2 → (실패 시) Bedrock 직접 → (실패 시) 안전 기본값.

---

## 요구사항

### R1: v2 API 호출

**설명**: Token Watcher v2 `pass_through_body` 형식으로 LLM 호출 수행.

**인수 기준 (AC)**:
- GIVEN Token Watcher URL/Key가 설정된 상태
- WHEN `analyze_email()` 또는 `summarize_email()` 호출 시
- THEN `{TOKEN_WATCHER_URL}/v1/chat/completions`에 v2 형식 POST 전송
- AND 응답에서 텍스트 + usage 정보 정상 추출

### R2: 폴백 전략

**설명**: Token Watcher 장애 시 기존 Bedrock 직접 호출로 자동 폴백.

**인수 기준 (AC)**:
- GIVEN Token Watcher가 응답하지 않거나 HTTP 5xx 반환 시
- WHEN LLM 호출 실행
- THEN Bedrock 직접 호출(`AnthropicBedrock` SDK)로 폴백
- AND 폴백 발생 사실을 WARNING 로그로 기록
- AND 폴백 성공 시 정상 AnalysisResult 반환 (source는 LLM 유지)

**서킷브레이커**:
- GIVEN Token Watcher 연속 실패 3회 이상
- WHEN 다음 LLM 호출 시
- THEN 30초간 Token Watcher 스킵, Bedrock 직접 호출 우선
- AND 30초 후 Token Watcher 재시도 (half-open)

### R3: 에러 처리

**설명**: v2 에러 응답 형식 파싱 및 적절한 처리.

**인수 기준 (AC)**:
- GIVEN Token Watcher가 에러 응답 반환 (HTTP 4xx/5xx)
- WHEN 에러 응답 body에 `{"error": {"message": ..., "code": ...}}` 포함
- THEN 에러 메시지와 `provider_status`를 로그에 기록
- AND `PROXY_PROVIDER_ERROR` + `provider_status >= 500`이면 폴백 트리거
- AND `provider_status == 400` (잘못된 요청)이면 폴백 없이 NOTIFY 안전 기본값 반환

### R4: summarize_email 통합

**설명**: `summarize_email()`도 동일한 v2 경로 사용.

**인수 기준 (AC)**:
- GIVEN summarize_email 호출 시
- WHEN Token Watcher v2 활성 상태
- THEN analyze_email과 동일한 v2 → Bedrock 폴백 경로 사용
- AND max_tokens=150, cache_control 없음 (경량 호출)

---

## 기술 설계

### 변경 파일 목록

| 파일 | 변경 성격 | 변경 규모 |
|------|---------|---------|
| `app/services/llm_service.py` | 핵심 변경 — v2 호출/파싱/폴백 추가 | L |
| `app/config.py` | TOKEN_WATCHER_URL, TOKEN_WATCHER_KEY 환경변수 추가 | S |
| `deploy.sh` | Cloud Run 배포 시 환경변수 추가 | S |
| `requirements.txt` | httpx 의존성 재추가 | S |
| `test_token_watcher.py` | v2 형식으로 업데이트 (선택) | S |

### API Request 형식 (v2)

```python
# POST {TOKEN_WATCHER_URL}/v1/chat/completions
# Headers: Authorization: Bearer {TOKEN_WATCHER_KEY}, Content-Type: application/json

# analyze_email용 (cache_control 포함)
{
    "provider": "bedrock",
    "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",  # Config.BEDROCK_MODEL_ID에서 ARN→model_id 변환
    "stream": False,
    "pass_through_body": {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "system": [
            {"type": "text", "text": "<system_prompt>", "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "<user_prompt>"}]}
        ],
        "temperature": 0.0
    }
}

# summarize_email용 (cache_control 없음, max_tokens 작음)
{
    "provider": "bedrock",
    "model_id": "...",
    "stream": False,
    "pass_through_body": {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 150,
        "system": [
            {"type": "text", "text": "<summarize_prompt>"}
        ],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "<user_prompt>"}]}
        ],
        "temperature": 0.0
    }
}
```

### model_id 변환

현재 `Config.BEDROCK_MODEL_ID`는 ARN 형식:
```
arn:aws:bedrock:us-east-1:210506716773:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0
```

Token Watcher v2에는 짧은 model_id가 필요:
```
us.anthropic.claude-haiku-4-5-20251001-v1:0
```

**변환 로직**: ARN에서 마지막 `/` 이후 부분 추출. ARN이 아니면 그대로 사용.
```python
def _extract_model_id(self) -> str:
    mid = self.model_id
    if mid.startswith("arn:"):
        return mid.rsplit("/", 1)[-1]
    return mid
```

### API Response 형식 (v2 예상)

v2는 `pass_through_body`로 Bedrock 형식 그대로 전달하므로, 응답도 Bedrock Messages API 형식 그대로 반환될 가능성이 높음:

```python
# 성공 응답 (예상 — Bedrock Messages API 형식)
{
    "id": "msg_...",
    "type": "message",
    "role": "assistant",
    "content": [
        {"type": "text", "text": "..."}
    ],
    "usage": {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0
    },
    "stop_reason": "end_turn"
}

# 또는 v1 형식 래핑 (확인 필요)
{
    "output": {
        "message": {
            "content": [{"text": "..."}]
        }
    },
    "usage": {...}
}
```

**구현 전략**: 두 형식 모두 처리 가능한 파서 작성.
```python
def _parse_tw_response(self, data: dict) -> tuple[str, dict | None]:
    """Token Watcher v2 응답에서 (text, usage) 추출.
    
    Bedrock Messages API 형식과 v1 래핑 형식 모두 지원.
    """
    # 형식 1: Bedrock Messages API (content[].text)
    if "content" in data and isinstance(data["content"], list):
        text = "".join(
            c.get("text", "") for c in data["content"] if c.get("type") == "text"
        ).strip()
        usage = data.get("usage")
        return text, usage
    
    # 형식 2: v1 래핑 (output.message.content[].text)
    if "output" in data:
        text = data["output"]["message"]["content"][0].get("text", "")
        usage = data.get("usage")
        return text, usage
    
    raise ValueError(f"Unknown TW response format: {list(data.keys())}")
```

### 에러 응답 파싱

```python
# Token Watcher v2 에러 응답
{
    "error": {
        "message": "[Proxy] bedrock error: ...",
        "type": "api_error",
        "code": "PROXY_PROVIDER_ERROR"
    },
    "provider_status": 400,
    "provider_error": {
        "message": "..."
    }
}
```

```python
def _handle_tw_error(self, data: dict, status_code: int) -> bool:
    """에러 처리. 폴백 가능 여부 반환."""
    err = data.get("error", {})
    provider_status = data.get("provider_status", 0)
    logger.warning(
        f"Token Watcher error: {err.get('message')} "
        f"(code={err.get('code')}, provider_status={provider_status})"
    )
    # provider 5xx → 폴백 가능 (서버 일시 장애)
    # provider 4xx → 폴백 불가 (요청 자체 문제 — Bedrock도 같은 결과)
    # HTTP 5xx (TW 자체 장애) → 폴백 가능
    return provider_status >= 500 or status_code >= 500
```

### 메서드 설계 — LLMService 변경

```
LLMService
├── __init__()                          # 변경: httpx.Client + 서킷브레이커 상태 초기화
├── _init_client()                      # 유지: Bedrock SDK 클라이언트 (폴백용)
├── _init_tw_client()                   # 신규: httpx.Client 초기화
├── _extract_model_id()                 # 신규: ARN → short model_id 변환
│
├── analyze_email(event, upm)           # 변경: _call_llm() 호출로 통합
├── summarize_email(event)              # 변경: _call_llm() 호출로 통합
│
├── _call_llm(sp, up, max_tokens, use_cache)  # 신규: TW v2 → Bedrock 폴백 오케스트레이션
│   ├── _should_use_tw()                # 신규: 서킷브레이커 상태 확인
│   ├── _call_token_watcher(sp, up, max_tokens, use_cache)  # 신규: v2 API 호출
│   ├── _call_bedrock(sp, up)           # 유지: Bedrock 직접 호출 (폴백)
│   └── _record_tw_failure()            # 신규: 서킷브레이커 실패 카운트 증가
│
├── _build_tw_payload(sp, up, max_tokens, use_cache)  # 신규: v2 request body 구성
├── _parse_tw_response(data)            # 신규: v2 응답 파싱
├── _extract_tw_usage(data)             # 신규: v2 usage 추출
│
├── _parse(ct)                          # 유지: JSON → AnalysisResult 변환
├── _extract_usage(r)                   # 유지: Bedrock SDK 응답 usage 추출
├── _build_system_prompt()              # 유지
└── _build_user_prompt(event, upm)      # 유지
```

### _call_llm() 흐름 (핵심 오케스트레이션)

```
_call_llm(system_prompt, user_prompt, max_tokens=512, use_cache=True)
    │
    ├─ _should_use_tw()? ─── No ──→ _call_bedrock() ──→ return
    │       │
    │      Yes
    │       │
    ├─ _call_token_watcher()
    │       │
    │   ┌── 성공? ──→ return AnalysisResult
    │   │
    │   └── 실패
    │       ├─ _record_tw_failure()
    │       ├─ 폴백 가능? ──→ _call_bedrock() ──→ return
    │       └─ 폴백 불가 ──→ return 안전 기본값 (NOTIFY)
    │
    └─ (TW 미설정) ──→ _call_bedrock() ──→ return
```

### 서킷브레이커 상태

```python
class LLMService:
    # 서킷브레이커 상태 (인스턴스 레벨)
    _tw_fail_count: int = 0           # 연속 실패 횟수
    _tw_circuit_open_until: float = 0  # time.time() 기준 open 해제 시각
    
    TW_FAIL_THRESHOLD = 3   # 연속 3회 실패 시 circuit open
    TW_CIRCUIT_TIMEOUT = 30  # 30초 후 half-open
    
    def _should_use_tw(self) -> bool:
        if not (Config.TOKEN_WATCHER_URL and Config.TOKEN_WATCHER_KEY):
            return False
        if self._tw_fail_count >= self.TW_FAIL_THRESHOLD:
            if time.time() < self._tw_circuit_open_until:
                return False  # circuit open 상태
            # half-open: 한 번 시도
        return True
    
    def _record_tw_failure(self):
        self._tw_fail_count += 1
        if self._tw_fail_count >= self.TW_FAIL_THRESHOLD:
            self._tw_circuit_open_until = time.time() + self.TW_CIRCUIT_TIMEOUT
            logger.warning(f"Token Watcher circuit OPEN for {self.TW_CIRCUIT_TIMEOUT}s")
    
    def _record_tw_success(self):
        self._tw_fail_count = 0
        self._tw_circuit_open_until = 0
```

### 설정 변경 (config.py)

```python
# 추가할 환경변수 (Config 클래스)
TOKEN_WATCHER_URL: str = os.environ.get("TOKEN_WATCHER_URL", "")
TOKEN_WATCHER_KEY: str = os.environ.get("TOKEN_WATCHER_KEY", "")
```

### 배포 변경 (deploy.sh)

```bash
# Cloud Run 배포 시 추가
--set-env-vars TOKEN_WATCHER_URL="${TOKEN_WATCHER_URL}" \
--set-env-vars TOKEN_WATCHER_KEY="${TOKEN_WATCHER_KEY}" \
```

### 의존성 변경 (requirements.txt)

```
httpx>=0.27.0
```

---

## 엣지 케이스

| # | 케이스 | 처리 |
|---|--------|------|
| E1 | TOKEN_WATCHER_URL/KEY 미설정 | Bedrock 직접 호출만 사용 (기존과 동일) |
| E2 | TW 응답 형식이 예상과 다름 | ValueError catch → 폴백 + WARNING 로그 |
| E3 | TW 타임아웃 (30초) | httpx.TimeoutException → 폴백 |
| E4 | TW + Bedrock 모두 실패 | NOTIFY 안전 기본값 (기존 동작 유지) |
| E5 | TW 응답 200이나 body 파싱 실패 | JSONDecodeError → 폴백 |
| E6 | TW 응답의 text가 빈 문자열 | 빈 문자열도 정상 처리 → _parse()가 처리 |
| E7 | model_id가 ARN 아닌 짧은 형식 | 그대로 사용 (변환 불필요) |

---

## 비기능 요구사항

| 항목 | 요구사항 |
|------|---------|
| **성능** | httpx.Client 재사용 (커넥션 풀링). 요청당 타임아웃 30초. |
| **보안** | TOKEN_WATCHER_KEY는 환경변수 경유만 허용. 로그에 키 노출 금지. |
| **가용성** | 서킷브레이커로 TW 장애 시 30초 이내 Bedrock 폴백 전환. |
| **관찰성** | TW 호출 성공/실패, 폴백 발생, 서킷 상태 변경 모두 INFO/WARNING 로그. |
| **하위호환** | TW 미설정 시 기존 Bedrock 전용 동작과 100% 동일. |

---

## 보존 항목 (변경하지 않는 것)

- `_build_system_prompt()` — 프롬프트 내용 그대로 유지
- `_build_user_prompt()` — 프롬프트 내용 그대로 유지
- `_parse()` — JSON → AnalysisResult 변환 로직 그대로 유지
- `Classifier` 클래스 — LLMService 내부 변경이므로 호출자 변경 없음
- `models.py` — 데이터 모델 변경 없음
- `admin-web/` — 프론트엔드 변경 없음

---

## 인수 조건 (Acceptance Criteria) 종합

| # | 조건 | 검증 방법 |
|---|------|---------|
| AC1 | TW v2 설정 시 TW 우선 호출 | 로그에 "Token Watcher v2 call" 기록 확인 |
| AC2 | TW 실패 시 Bedrock 폴백 | TW URL을 잘못된 값으로 설정 → 로그에 폴백 기록 + 정상 분석 결과 |
| AC3 | 서킷브레이커 3회 실패 후 open | 연속 3회 TW 에러 → 4번째 호출이 TW 스킵 로그 출력 |
| AC4 | TW 미설정 시 기존 동작 유지 | TOKEN_WATCHER_URL="" → Bedrock 직접 호출만 사용 |
| AC5 | summarize_email도 TW v2 경유 | 화이트리스트 메일 처리 시 TW v2 호출 로그 확인 |
| AC6 | usage 정보 정상 추출 | 비용 통계 API에서 TW 경유 호출의 토큰 사용량 확인 |
| AC7 | pass_through_body 형식 정확 | TW 서버 로그에서 Bedrock invoke-model 형식 수신 확인 |

---

## 구현 순서 (의존성 기반)

```
1. config.py — TOKEN_WATCHER_URL, TOKEN_WATCHER_KEY 추가
2. requirements.txt — httpx 추가
3. llm_service.py — 핵심 변경 (아래 순서)
   3a. _init_tw_client(), _extract_model_id() 신규 메서드
   3b. _build_tw_payload() — v2 request body 구성
   3c. _parse_tw_response(), _extract_tw_usage() — v2 응답 파싱
   3d. _call_token_watcher() — v2 HTTP 호출
   3e. _should_use_tw(), _record_tw_failure/success() — 서킷브레이커
   3f. _call_llm() — 오케스트레이션 메서드
   3g. analyze_email(), summarize_email() — _call_llm() 호출로 변경
4. deploy.sh — 환경변수 추가
5. test_token_watcher.py — v2 형식으로 업데이트 (선택)
```

---

## TODO (구현 전 확인 필요)

- `TODO:` v2 응답 형식 실제 확인 필요 — Bedrock Messages API 형식인지 v1 래핑 형식인지 TW 서버 문서/테스트로 확정. 현재 스펙은 양쪽 모두 지원하도록 설계.
- `TODO:` httpx.Client의 connection pool 설정 (max_connections, max_keepalive_connections) — Cloud Run 단일 인스턴스 환경에서 기본값 충분한지 확인.
