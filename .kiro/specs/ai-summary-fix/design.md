# AI 요약 품질 개선 Bugfix Design

## Overview

Gmail 메일 목록의 "AI 핵심 요약" 기능에서 한국어 메일 요약 품질이 현저히 낮은 버그를 수정합니다. 근본 원인은 (1) 시스템 프롬프트의 한국어 요약 지시 부족, (2) snippet만 전달하는 컨텍스트 부족, (3) Amazon Nova Micro 모델의 한국어 능력 한계, (4) 요약 품질 검증 부재입니다. 시스템 프롬프트 개선, 메일 본문 전달, 요약 품질 검증 로직 추가를 통해 수정합니다.

## Glossary

- **Bug_Condition (C)**: 한국어 메일이거나, 컨텍스트가 부족하거나, LLM이 빈/무의미한 요약을 반환하는 조건
- **Property (P)**: 한국어로 된 명확하고 핵심 내용을 담은 3줄 이내의 요약이 반환되는 것
- **Preservation**: 영문 메일 요약, 규칙 기반 분류, 폴백 메커니즘, 임계값 적용 등 기존 동작 유지
- **`_build_system_prompt()`**: `app/services/llm_service.py`의 메서드. LLM에 전달할 시스템 프롬프트를 생성. 현재 영어로만 작성되어 있으며 `"summary": "Korean"` 한 단어로만 한국어 요약을 지시
- **`_build_user_prompt()`**: `app/services/llm_service.py`의 메서드. 메일 정보를 LLM에 전달할 사용자 프롬프트로 구성. 현재 snippet만 전달하며 본문 미포함
- **`_parse()`**: `app/services/llm_service.py`의 메서드. LLM JSON 응답을 `AnalysisResult`로 파싱. 현재 summary 필드에 대한 품질 검증 없음
- **`classify()`**: `app/core/classifier.py`의 메서드. 3단계 분류 파이프라인 실행. 요약 품질 검증 로직 추가 대상
- **Token-Watcher**: 자체 LLM 프록시 게이트웨이. `apac.amazon.nova-micro-v1:0` 모델 사용
- **snippet**: Gmail API가 반환하는 메일 미리보기 텍스트 (약 100자 내외)

## Bug Details

### Fault Condition

한국어 메일이 수신되거나, snippet만으로 충분한 컨텍스트가 없거나, LLM이 빈/무의미한 요약을 반환할 때 버그가 발생합니다. `_build_system_prompt()`는 `"summary": "Korean"` 한 단어로만 한국어 요약을 지시하고, `_build_user_prompt()`는 snippet(~100자)만 전달하며, `_parse()`는 summary 품질을 검증하지 않습니다.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type EmailEvent
  OUTPUT: boolean

  isKoreanEmail ← contains_korean(input.subject) OR contains_korean(input.snippet)
  hasInsufficientContext ← length(input.snippet) < 50 AND input.body IS NULL
  hasLowQualitySummary ← input.summary IS NULL
                         OR trim(input.summary) = ""
                         OR length(input.summary) < 10

  RETURN isKoreanEmail OR hasInsufficientContext OR hasLowQualitySummary
END FUNCTION
```

### Examples

- 한국어 메일 (subject: "프로젝트 일정 변경 안내") → 현재: `"Korean"` 또는 의미 없는 영문 요약 반환 → 기대: 한국어 3줄 이내 핵심 요약
- snippet이 30자인 짧은 메일 → 현재: 정보 부족으로 `"No summary available"` 반환 → 기대: 본문 포함 전달로 충분한 요약 생성
- LLM이 빈 문자열 `""` 반환 → 현재: 빈 요약이 Slack 알림에 그대로 표시 → 기대: 요약 섹션 생략
- LLM이 `"요약"` (2자) 반환 → 현재: 무의미한 요약이 표시 → 기대: 10자 미만이므로 무효 처리, 요약 섹션 생략

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- 영문 메일 요약은 기존과 동일한 수준으로 정상 생성되어야 함
- 블랙리스트/스팸 키워드 기반 SILENT 분류는 AI 요약 없이 즉시 처리되어야 함
- 화이트리스트 도메인 메일은 NOTIFY 분류 후 AI 요약을 별도 호출하여 첨부해야 함
- LLM 서비스 연결 실패 시 Token-Watcher → Bedrock 직접 호출 폴백이 동작해야 함
- AI 분석 score가 `score_threshold_notify` 미만이면 SILENT로 분류되어야 함

**Scope:**
버그 조건(한국어 메일, 컨텍스트 부족, 저품질 요약)에 해당하지 않는 모든 입력은 수정의 영향을 받지 않아야 합니다. 이에 해당하는 것:
- 영문 메일의 요약 생성
- 규칙 기반 분류 로직 (블랙리스트, 화이트리스트, 스팸 키워드)
- LLM 폴백 메커니즘 (Token-Watcher → Bedrock)
- 임계값 기반 NOTIFY/SILENT 판정

## Hypothesized Root Cause

코드 분석 결과, 다음 4가지 근본 원인이 식별되었습니다:

1. **시스템 프롬프트의 한국어 요약 지시 부족**: `_build_system_prompt()`가 영어로만 작성되어 있으며, JSON 응답 형식에서 `"summary": "Korean"` 한 단어로만 한국어 요약을 지시합니다. 요약의 형식(3줄 이내), 길이, 품질 기준에 대한 구체적 지시가 전혀 없습니다.
   - 현재 프롬프트: `'...\"summary\": \"Korean\"...'`
   - LLM이 "Korean"이라는 단어를 요약 내용이 아닌 언어 라벨로 해석할 가능성이 높음

2. **사용자 프롬프트의 컨텍스트 부족**: `_build_user_prompt()`가 `event.raw_data.get('snippet', 'N/A')`로 snippet(~100자)만 전달합니다. Gmail API 호출 시 `format='metadata'`를 사용하여 본문을 가져오지 않으므로, 메일 본문이 `raw_data`에 포함되지 않습니다.
   - `_fetch_unread_for_user()`에서 `format='metadata'`로 호출 → 본문 미포함
   - `_parse_gmail_message()`에서 `raw_data`에 `gmail_id`와 `snippet`만 저장

3. **1차 모델(Amazon Nova Micro)의 한국어 능력 한계**: Token-Watcher를 통해 `apac.amazon.nova-micro-v1:0` 경량 모델을 우선 사용합니다. 이 모델은 비용 효율적이지만 한국어 요약 품질이 낮을 수 있습니다. 시스템 프롬프트 개선으로 경량 모델에서도 허용 가능한 수준의 한국어 요약을 유도할 수 있습니다.

4. **요약 품질 검증 부재**: `_parse()` 메서드에서 `p.get("summary")`를 그대로 반환하며, `classify()`에서도 summary 값에 대한 검증이 없습니다. 빈 문자열, None, 지나치게 짧은 요약이 Slack 알림에 그대로 표시됩니다.

## Correctness Properties

Property 1: Fault Condition - 한국어 메일 요약 품질 보장

_For any_ input where 한국어 메일이거나 컨텍스트가 부족한 조건이 충족되는 경우 (isBugCondition returns true), 수정된 generateSummary 함수는 SHALL 한국어로 된 10자 이상, 3줄 이내의 핵심 요약을 반환하거나, 품질 기준 미달 시 summary를 None으로 설정하여 Slack 알림에서 요약 섹션을 생략한다.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - 기존 동작 유지

_For any_ input where 버그 조건에 해당하지 않는 경우 (isBugCondition returns false), 수정된 코드는 SHALL 기존 코드와 동일한 결과를 생성하며, 영문 메일 요약, 규칙 기반 분류, 폴백 메커니즘, 임계값 적용 등 모든 기존 동작을 보존한다.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

근본 원인 분석이 정확하다는 가정 하에:

**File**: `app/services/llm_service.py`

**Function**: `_build_system_prompt()`

**Specific Changes**:
1. **시스템 프롬프트 한국어 지시 강화**: 영어 전용 프롬프트를 한국어 요약 요구사항이 명확한 프롬프트로 교체
   - 요약 언어: 반드시 한국어로 작성
   - 요약 형식: 핵심 내용을 3줄 이내로 요약
   - 요약 품질: 구체적이고 정보가 담긴 요약 (단순 번역이 아닌 핵심 추출)
   - JSON 응답의 `summary` 필드 예시를 한국어로 제공

**Function**: `_build_user_prompt()`

**Specific Changes**:
2. **메일 본문 컨텍스트 추가**: `raw_data`에 `body_text` 필드가 있으면 프롬프트에 포함
   - snippet과 함께 body_text를 전달하여 LLM이 충분한 컨텍스트로 요약 생성
   - body_text가 너무 긴 경우 앞부분 일정 길이(예: 2000자)로 truncate

**Function**: `_parse()`

**Specific Changes**:
3. **요약 품질 검증 추가**: LLM 응답의 summary 필드에 대한 기본 품질 검증
   - None, 빈 문자열, 공백만 있는 경우 → None으로 설정
   - 10자 미만인 경우 → None으로 설정 (무의미한 요약 필터링)

**File**: `app/services/gmail_service.py`

**Function**: `_fetch_unread_for_user()` 및 `_parse_gmail_message()`

**Specific Changes**:
4. **Gmail API에서 본문 가져오기**: `format='metadata'`를 `format='full'`로 변경하여 메일 본문을 가져오고, `_parse_gmail_message()`에서 본문 텍스트를 추출하여 `raw_data`에 `body_text`로 저장
   - MIME 파트에서 `text/plain` 또는 `text/html`을 추출
   - HTML인 경우 태그 제거하여 plain text로 변환
   - base64 디코딩 처리

**File**: `app/core/classifier.py`

**Function**: `classify()`

**Specific Changes**:
5. **요약 품질 최종 검증**: `classify()` 메서드에서 LLM 결과의 summary가 None이거나 품질 기준 미달인 경우 summary를 None으로 설정하여 Slack 알림에서 요약 섹션이 생략되도록 처리

## Testing Strategy

### Validation Approach

테스트 전략은 2단계로 진행합니다: 먼저 수정 전 코드에서 버그를 재현하는 반례를 확인하고, 수정 후 버그가 해결되었으며 기존 동작이 보존되었는지 검증합니다.

### Exploratory Fault Condition Checking

**Goal**: 수정 전 코드에서 버그를 재현하는 반례를 확인합니다. 근본 원인 분석을 확인하거나 반박합니다.

**Test Plan**: 한국어 메일 이벤트를 생성하여 현재 `_build_system_prompt()`, `_build_user_prompt()`, `_parse()` 메서드의 동작을 관찰합니다.

**Test Cases**:
1. **시스템 프롬프트 검증**: 현재 시스템 프롬프트에 한국어 요약 지시가 `"Korean"` 한 단어뿐인지 확인 (수정 전 코드에서 실패)
2. **사용자 프롬프트 컨텍스트 검증**: snippet만 전달되고 본문이 누락되는지 확인 (수정 전 코드에서 실패)
3. **빈 요약 통과 검증**: `_parse()`가 빈 문자열 summary를 그대로 반환하는지 확인 (수정 전 코드에서 실패)
4. **짧은 요약 통과 검증**: `_parse()`가 10자 미만 summary를 그대로 반환하는지 확인 (수정 전 코드에서 실패)

**Expected Counterexamples**:
- 시스템 프롬프트에 한국어 요약 형식/품질 지시가 없음
- 사용자 프롬프트에 메일 본문이 포함되지 않음
- 빈 문자열/짧은 요약이 필터링 없이 반환됨

### Fix Checking

**Goal**: 버그 조건이 충족되는 모든 입력에 대해 수정된 함수가 기대 동작을 생성하는지 검증합니다.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := generateSummary_fixed(input)
  ASSERT result.summary IS NULL
    OR (length(result.summary) >= 10
        AND line_count(result.summary) <= 3)
END FOR
```

### Preservation Checking

**Goal**: 버그 조건에 해당하지 않는 모든 입력에 대해 수정된 함수가 기존 함수와 동일한 결과를 생성하는지 검증합니다.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT generateSummary_original(input) = generateSummary_fixed(input)
END FOR
```

**Testing Approach**: 보존 검증에는 Property-Based Testing을 권장합니다:
- 입력 도메인 전체에 걸쳐 자동으로 많은 테스트 케이스를 생성
- 수동 단위 테스트가 놓칠 수 있는 엣지 케이스를 포착
- 모든 비버그 입력에 대해 동작이 변경되지 않았음을 강력하게 보장

**Test Plan**: 수정 전 코드에서 영문 메일 요약, 규칙 기반 분류 등의 동작을 먼저 관찰한 후, 수정 후에도 동일한 동작이 유지되는지 검증합니다.

**Test Cases**:
1. **영문 메일 요약 보존**: 영문 메일에 대한 요약이 수정 전후 동일한 품질로 생성되는지 검증
2. **규칙 기반 분류 보존**: 블랙리스트/화이트리스트/스팸 키워드 분류가 수정 전후 동일하게 동작하는지 검증
3. **폴백 메커니즘 보존**: Token-Watcher 실패 시 Bedrock 직접 호출이 수정 전후 동일하게 동작하는지 검증
4. **임계값 적용 보존**: score 기반 NOTIFY/SILENT 판정이 수정 전후 동일하게 동작하는지 검증

### Unit Tests

- `_build_system_prompt()` 반환값에 한국어 요약 지시(형식, 길이, 품질 기준)가 포함되는지 검증
- `_build_user_prompt()`가 `raw_data`에 `body_text`가 있을 때 프롬프트에 포함하는지 검증
- `_parse()`가 빈 문자열, None, 10자 미만 summary를 None으로 변환하는지 검증
- `_parse()`가 유효한 summary(10자 이상)를 정상 반환하는지 검증
- `_parse_gmail_message()`가 `format='full'` 응답에서 본문 텍스트를 추출하는지 검증
- `classify()`에서 summary가 None인 경우 그대로 유지되는지 검증

### Property-Based Tests

- 랜덤 한국어/영문 메일 이벤트를 생성하여 `_build_system_prompt()`가 항상 한국어 요약 지시를 포함하는지 검증
- 랜덤 길이의 summary 문자열을 생성하여 `_parse()`의 품질 검증 로직이 올바르게 동작하는지 검증
- 랜덤 영문 메일 이벤트를 생성하여 수정 전후 분류 결과가 동일한지 검증

### Integration Tests

- 한국어 메일 이벤트를 전체 파이프라인(classify → analyze_email → Slack 알림)에 통과시켜 한국어 요약이 생성되는지 검증
- 빈 요약이 반환된 경우 Slack 알림에서 요약 섹션이 생략되는지 검증
- Token-Watcher → Bedrock 폴백 시에도 한국어 요약 품질이 유지되는지 검증
