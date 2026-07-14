---
name: team-docs
description: 문서 작업 전용. "문서 정리", "docs 업데이트", "README 작성", "규칙 문서화" 시 사용.
argument-hint: "[문서 작업 내용]"
user-invocable: true
---

# 문서 작업 — team-docs

## 실행 조건
- "문서 정리", "docs 업데이트", "README 작성", "규칙 문서화"
- docs/ 또는 문서 파일만 수정하는 작업

## Phase 구성 (3-Phase)

Phase 1: 현황 파악
└── p1-explore (general-purpose, model=sonnet) — 현재 문서 상태 탐색

Phase 2: 작성
└── p2-writer (general-purpose, model=sonnet) — 문서 작성/업데이트

Phase 3: 검증
└── p3-review (general-purpose, model=sonnet) — 일관성, 누락, 구조 오류 검증

## 정보 계층 (team-build와 동일)
Phase 시작: ━━━ Phase N/M | {팀명} ━━━
팀 활동: ◎ {에이전트} {상태}
이벤트: ↳ [태그] {내용}
게이트: ✅ [PHASE_GATE] Phase N→M | 조건

## 통신 원칙
- 모든 소통 = SendMessage
- 워커 완료 → 보고 → 즉시 셧다운 (idle 유지 금지)

## 파일 소유권
- 수정 가능: docs/**, README.md, .claude/rules/*.md
- 수정 금지: 코드 파일, 에이전트 정의, 스킬 정의
