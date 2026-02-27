---
inclusion: always
---

# 메일 분류 파이프라인 & Firestore 구조

## 분류 파이프라인 (classifier.py)

```
Step 0: 노이즈 필터 (Rule)
  → blacklist_domains, spam_keywords 매칭 시 즉시 SILENT (LLM 호출 X)

Step 1: 화이트리스트 (Rule)
  → whitelist_domains 매칭 시 NOTIFY 결정 후 LLM으로 요약만 생성

Step 2: LLM 판별 (AWS Bedrock / Claude Haiku)
  → Input: Subject, Sender, Receiver, 사용자 차단 선호도
  → Output: { score(0~1), category, reason, summary }

Step 3: 임계값 적용
  → score >= score_threshold_notify(기본 0.5) → NOTIFY
  → score < threshold → SILENT
```

## 중복 방지 & 캐싱
- `state_store.is_processed(message_id, target_id)` — 이미 처리된 메일 스킵
- `state_store.is_duplicate_by_content(sender, subject, target_id, window=10min)` — 내용 기반 중복 체크
- Firestore에 이미 저장된 이벤트(`get_email_event`)가 있으면 LLM 재호출 없이 캐시 결과 재사용

## 사용자 학습 (learning_store.py)
- `save_user_silent_preference(user_id, sender, subject)` — 차단 학습 저장
- `delete_user_silent_preference(user_id, sender, subject)` — 차단 해제
- `should_silence_for_user(user_id, sender, subject)` — 차단 여부 확인
- `extract_email_type_pattern(subject)` — 제목에서 유형 패턴 추출

## Firestore 컬렉션 구조

### `email_events` — 처리된 메일 스냅샷
| 필드 | 설명 |
|---|---|
| `email_id` | Gmail Message ID |
| `subject` | 메일 제목 |
| `from_email` / `to_email` | 발신자 / 수신자 |
| `timestamp` | 수신 시각 |
| `rule_decision` | rule / llm |
| `llm_score_raw` | LLM 점수 (0~1) |
| `final_category` | notify / silent |
| `reason` | 분류 사유 |
| `summary` | AI 3줄 요약 |
| `slack_targets` | 알림 전송 대상 Slack ID 목록 |
| `llm_input_tokens` / `llm_output_tokens` | 토큰 사용량 |
| `manually_triggered` / `manually_blocked` | 수동 처리 여부 |

### `routing_rules` — Gmail → Slack 라우팅 규칙
- gmail 주소별 Slack User ID / Channel ID 매핑

### `settings` — 시스템 설정
- `blacklist_domains`, `whitelist_domains`, `spam_keywords`, `urgent_keywords`
- `score_threshold_notify`
- 시스템 활성화/일시정지 상태
- 일일 LLM 사용량 및 비용 한도

### `user_preferences` — 사용자별 차단 학습 데이터
- 사용자 ID별 발신자 + 메일 유형 패턴 차단 목록

## 라우팅 (router.py)
- `ROUTING_SOURCE=firestore` (기본): Firestore에서 실시간 조회
- `ROUTING_SOURCE=json`: `config/routing_rules.json` 파일 사용 (fallback)
- Firestore 조회 실패 시 JSON으로 자동 fallback

## Slack 인터랙션
- `/slack/interactive` 엔드포인트에서 버튼 클릭 처리
- `silent_forever`: 해당 발신자 유형 차단 학습 + 메시지 업데이트
- `undo_silent`: 차단 해제 + 메시지 복구
- Cold Start 타임아웃 방지를 위해 `response_url`로 비동기 응답 처리 (threading)
