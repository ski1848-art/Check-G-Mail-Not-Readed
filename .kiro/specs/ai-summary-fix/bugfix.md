# Bugfix Requirements Document

## Introduction

Gmail 메일 목록에서 "AI 핵심 요약" 기능의 요약 품질이 저하되는 버그를 수정합니다. 영문 메일은 어느 정도 요약이 되지만, 한국어 메일이나 특정 유형의 메일에서 요약 품질이 현저히 떨어지는 문제가 2월 28일경부터 발생하고 있습니다.

코드 분석 결과, 다음과 같은 근본 원인이 식별되었습니다:

1. **시스템 프롬프트의 한국어 요약 지시 부족**: `_build_system_prompt()`가 영어로만 작성되어 있으며, 요약 형식/품질에 대한 구체적 지시가 없음. `"summary": "Korean"` 이라는 단 한 단어로만 한국어 요약을 지시하고 있음.
2. **사용자 프롬프트의 컨텍스트 부족**: `_build_user_prompt()`가 메일의 snippet(미리보기 텍스트)만 전달하며, 메일 본문 전체를 전달하지 않아 요약에 필요한 정보가 부족함.
3. **1차 모델(Amazon Nova Micro)의 한국어 능력 한계**: Token-Watcher를 통해 `apac.amazon.nova-micro-v1:0` 모델을 우선 사용하는데, 이 모델은 경량 모델로서 한국어 요약 품질이 낮을 수 있음.
4. **요약 품질 검증 부재**: LLM 응답의 `summary` 필드에 대한 품질 검증이나 빈 값/무의미한 값 필터링이 없음.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN 한국어 메일이 수신되어 AI 요약이 생성될 때 THEN 시스템은 품질이 낮거나 부정확한 한국어 요약을 반환한다 (시스템 프롬프트에 한국어 요약 형식/품질에 대한 구체적 지시가 `"summary": "Korean"` 한 단어뿐임)

1.2 WHEN 메일 요약을 위해 LLM에 컨텍스트를 전달할 때 THEN 시스템은 Gmail snippet(미리보기 텍스트, 약 100자 내외)만 전달하여 충분한 요약 생성에 필요한 정보가 부족하다

1.3 WHEN Token-Watcher를 통해 Amazon Nova Micro 모델로 한국어 메일을 요약할 때 THEN 시스템은 경량 모델의 한국어 능력 한계로 인해 영문 메일 대비 현저히 낮은 품질의 요약을 생성한다

1.4 WHEN LLM이 빈 문자열이나 무의미한 요약을 반환할 때 THEN 시스템은 해당 값을 검증 없이 그대로 Slack 알림에 표시한다

### Expected Behavior (Correct)

2.1 WHEN 한국어 메일이 수신되어 AI 요약이 생성될 때 THEN 시스템은 SHALL 한국어로 된 명확하고 핵심 내용을 담은 3줄 이내의 요약을 반환한다 (시스템 프롬프트에 한국어 요약 형식, 길이, 품질 기준이 구체적으로 명시됨)

2.2 WHEN 메일 요약을 위해 LLM에 컨텍스트를 전달할 때 THEN 시스템은 SHALL 메일 제목, 발신자, 수신자, snippet에 더해 가능한 경우 메일 본문 텍스트를 함께 전달하여 충분한 컨텍스트를 제공한다

2.3 WHEN Token-Watcher를 통해 요약을 생성할 때 THEN 시스템은 SHALL 한국어 요약 품질이 충분한 모델을 사용하거나, 시스템 프롬프트를 개선하여 경량 모델에서도 허용 가능한 수준의 한국어 요약을 생성한다

2.4 WHEN LLM이 빈 문자열, None, 또는 지나치게 짧은(10자 미만) 요약을 반환할 때 THEN 시스템은 SHALL 해당 요약을 무효로 처리하고 Slack 알림에서 AI 요약 섹션을 생략한다

### Unchanged Behavior (Regression Prevention)

3.1 WHEN 영문 메일이 수신되어 AI 요약이 생성될 때 THEN 시스템은 SHALL CONTINUE TO 기존과 동일한 수준의 영문 요약을 정상적으로 생성한다

3.2 WHEN 규칙 기반(블랙리스트/스팸 키워드)으로 SILENT 분류된 메일일 때 THEN 시스템은 SHALL CONTINUE TO AI 요약 없이 즉시 SILENT 처리한다

3.3 WHEN 화이트리스트 도메인에서 온 메일일 때 THEN 시스템은 SHALL CONTINUE TO NOTIFY로 분류하고 AI 요약을 별도로 호출하여 첨부한다

3.4 WHEN LLM 서비스 연결이 실패할 때 THEN 시스템은 SHALL CONTINUE TO 폴백 메커니즘(Token-Watcher → Bedrock 직접 호출)을 통해 분석을 시도한다

3.5 WHEN AI 분석 결과의 score가 임계값(score_threshold_notify) 미만일 때 THEN 시스템은 SHALL CONTINUE TO 해당 메일을 SILENT로 분류한다


---

## Bug Condition (Pseudocode)

### Bug Condition Function

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type EmailEvent
  OUTPUT: boolean
  
  // 버그는 다음 조건 중 하나 이상이 충족될 때 발생:
  // 1. 한국어 메일인 경우 (시스템 프롬프트의 한국어 지시 부족)
  // 2. snippet만으로는 요약에 충분한 컨텍스트가 없는 경우
  // 3. LLM이 빈/무의미한 요약을 반환하는 경우
  
  isKoreanEmail ← contains_korean(X.subject) OR contains_korean(X.snippet)
  hasInsufficientContext ← length(X.snippet) < 50 AND X.body IS NULL
  hasLowQualitySummary ← X.summary IS NULL OR length(X.summary) < 10
  
  RETURN isKoreanEmail OR hasInsufficientContext OR hasLowQualitySummary
END FUNCTION
```

### Property Specification - Fix Checking

```pascal
// Property: Fix Checking - 한국어 메일 요약 품질 보장
FOR ALL X WHERE isBugCondition(X) DO
  result ← generateSummary'(X)
  ASSERT result.summary IS NOT NULL
    AND length(result.summary) >= 10
    AND is_korean(result.summary)
    AND line_count(result.summary) <= 3
END FOR
```

### Preservation Goal

```pascal
// Property: Preservation Checking - 기존 동작 유지
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT generateSummary(X) = generateSummary'(X)
END FOR
```

이 보존 속성은 영문 메일 요약, 규칙 기반 분류, 폴백 메커니즘, 임계값 적용 등 기존 동작이 수정 후에도 동일하게 유지됨을 보장합니다.
