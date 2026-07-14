# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Fault Condition** - 한국어 메일 요약 품질 버그 재현
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: 한국어 메일 이벤트, 컨텍스트 부족 메일, 빈/짧은 요약 케이스에 대해 property를 scope
  - Bug Condition: `isBugCondition(input)` where `contains_korean(input.subject) OR contains_korean(input.snippet) OR (length(input.snippet) < 50 AND input.body IS NULL) OR input.summary IS NULL OR trim(input.summary) = "" OR length(input.summary) < 10`
  - Test 1: `_build_system_prompt()` 반환값에 한국어 요약 형식/품질 지시가 `"Korean"` 한 단어뿐인지 확인 → 수정 후에는 구체적 한국어 요약 지시가 포함되어야 함
  - Test 2: `_build_user_prompt()`가 snippet만 전달하고 body_text를 포함하지 않는지 확인 → 수정 후에는 body_text가 포함되어야 함
  - Test 3: `_parse()`가 빈 문자열 `""` summary를 그대로 반환하는지 확인 → 수정 후에는 None으로 변환되어야 함
  - Test 4: `_parse()`가 10자 미만 summary `"요약"`을 그대로 반환하는지 확인 → 수정 후에는 None으로 변환되어야 함
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: 시스템 프롬프트에 한국어 지시 부재, 본문 미포함, 빈/짧은 요약 미필터링
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - 기존 동작 유지 검증
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: 영문 메일 이벤트에 대한 `_build_system_prompt()`, `_build_user_prompt()`, `_parse()` 동작을 수정 전 코드에서 관찰
  - Observe: 규칙 기반 분류(블랙리스트/화이트리스트/스팸 키워드)가 AI 요약 없이 정상 동작하는지 관찰
  - Observe: `_parse()`가 유효한 summary(10자 이상)를 정상 반환하는지 관찰
  - Observe: score 기반 NOTIFY/SILENT 판정이 정상 동작하는지 관찰
  - Write property-based test: 랜덤 영문 메일 이벤트를 생성하여 `_build_system_prompt()` 반환값이 기존과 동일한 구조를 유지하는지 검증
  - Write property-based test: 랜덤 길이의 유효한 summary(10자 이상)를 생성하여 `_parse()`가 정상 반환하는지 검증
  - Write property-based test: 규칙 기반 분류 로직이 수정 전후 동일하게 동작하는지 검증 (블랙리스트 → SILENT, 화이트리스트 → NOTIFY)
  - Write property-based test: score가 `score_threshold_notify` 미만이면 SILENT로 분류되는지 검증
  - Write property-based test: LLM 서비스 연결 실패 시 폴백 메커니즘이 동작하는지 검증
  - Verify all tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix for AI 요약 품질 개선

  - [x] 3.1 시스템 프롬프트 한국어 지시 강화 (`_build_system_prompt()`)
    - `app/services/llm_service.py`의 `_build_system_prompt()` 메서드 수정
    - 영어 전용 프롬프트를 한국어 요약 요구사항이 명확한 프롬프트로 교체
    - 요약 언어: 반드시 한국어로 작성하도록 지시
    - 요약 형식: 핵심 내용을 3줄 이내로 요약하도록 지시
    - 요약 품질: 구체적이고 정보가 담긴 요약 (단순 번역이 아닌 핵심 추출) 지시
    - JSON 응답의 `summary` 필드 예시를 한국어로 제공
    - _Bug_Condition: isBugCondition(input) where contains_korean(input.subject) OR contains_korean(input.snippet) — 시스템 프롬프트에 한국어 요약 지시가 "Korean" 한 단어뿐_
    - _Expected_Behavior: 시스템 프롬프트에 한국어 요약 형식(3줄 이내), 길이(10자 이상), 품질 기준이 구체적으로 명시됨_
    - _Preservation: 영문 메일 요약 생성에 영향 없어야 함_
    - _Requirements: 2.1, 2.3_

  - [x] 3.2 Gmail API에서 메일 본문 가져오기 (`_fetch_unread_for_user()`, `_parse_gmail_message()`)
    - `app/services/gmail_service.py`의 `_fetch_unread_for_user()` 메서드에서 `format='metadata'`를 `format='full'`로 변경
    - `_parse_gmail_message()`에서 MIME 파트의 `text/plain` 또는 `text/html` 본문 추출
    - HTML인 경우 태그 제거하여 plain text로 변환
    - base64 디코딩 처리
    - 추출된 본문을 `raw_data`에 `body_text`로 저장
    - _Bug_Condition: hasInsufficientContext where length(snippet) < 50 AND body IS NULL_
    - _Expected_Behavior: raw_data에 body_text 필드가 포함되어 LLM에 충분한 컨텍스트 전달_
    - _Preservation: 기존 metadata(subject, from, to, snippet) 추출에 영향 없어야 함_
    - _Requirements: 2.2_

  - [x] 3.3 사용자 프롬프트에 메일 본문 컨텍스트 추가 (`_build_user_prompt()`)
    - `app/services/llm_service.py`의 `_build_user_prompt()` 메서드 수정
    - `raw_data`에 `body_text` 필드가 있으면 프롬프트에 포함
    - body_text가 너무 긴 경우 앞부분 2000자로 truncate
    - snippet과 함께 body_text를 전달하여 LLM이 충분한 컨텍스트로 요약 생성
    - _Bug_Condition: hasInsufficientContext where snippet만 전달되고 body 미포함_
    - _Expected_Behavior: 사용자 프롬프트에 snippet + body_text가 포함되어 충분한 컨텍스트 제공_
    - _Preservation: body_text가 없는 경우 기존 동작(snippet만 전달)과 동일해야 함_
    - _Requirements: 2.2_

  - [x] 3.4 요약 품질 검증 추가 (`_parse()`, `classify()`)
    - `app/services/llm_service.py`의 `_parse()` 메서드에서 summary 품질 검증 추가
    - None, 빈 문자열, 공백만 있는 경우 → None으로 설정
    - 10자 미만인 경우 → None으로 설정 (무의미한 요약 필터링)
    - `app/core/classifier.py`의 `classify()` 메서드에서 summary가 None이거나 품질 기준 미달인 경우 summary를 None으로 유지
    - Slack 알림에서 summary가 None인 경우 요약 섹션 생략되도록 처리
    - _Bug_Condition: hasLowQualitySummary where summary IS NULL OR trim(summary) = "" OR length(summary) < 10_
    - _Expected_Behavior: 빈/짧은 요약은 None으로 변환되어 Slack 알림에서 요약 섹션 생략_
    - _Preservation: 유효한 summary(10자 이상)는 기존과 동일하게 정상 반환_
    - _Requirements: 2.4_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - 한국어 메일 요약 품질 보장
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - 기존 동작 유지 확인
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - 모든 탐색적 테스트(Property 1)가 PASS하는지 확인
  - 모든 보존 테스트(Property 2)가 PASS하는지 확인
  - 기존 단위 테스트가 모두 PASS하는지 확인
  - 문제가 있으면 사용자에게 질문하여 해결
