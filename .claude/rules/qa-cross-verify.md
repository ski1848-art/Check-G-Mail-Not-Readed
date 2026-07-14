---
description: QA사업부 교차 검증 빈도 제한 규칙
globs: .claude/agents/**
---

# QA 교차 검증 규칙

## 조건부 교차 통보 (허용)
perf-reviewer → security-auditor:
- 트리거: "인증 없이 대량 데이터 반환하는 N+1 패턴" 발견 시만
- 형식: [REVIEW_FINDING] 1회 통보, 응답 불필요
- p3-sec가 참고 후 자체 판단

## 제거된 교차 (금지)
- sec → code: 스펙과 코드 품질은 별개 도메인
- code → build: REVIEW_FINDING으로 이미 충분
- 전수 교차 교환: 비용 대비 가치 없음

## Codex 교차 검증 (codex exec 직접 호출)

- 메인이 `codex exec -m gpt-5.6-sol` 로 Codex 리뷰 실행 → 결과를 Claude QA와 합산
- Codex 결과는 `[CODEX_FINDING]` 태그로 정리
- Claude와 Codex 판단 상충 → 양쪽 제시 + 사용자 결정 (자동 합의 금지)

## 원칙
- Claude 내부 교차 통보는 SendMessage 사용
- Claude ↔ Codex 교차는 `codex exec` (Bash 직접 호출, 메인이 중계)
- 파일 기반 교차 보고 금지
