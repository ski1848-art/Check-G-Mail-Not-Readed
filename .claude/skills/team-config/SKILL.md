---
name: team-config
description: 하네스/에이전트/스킬/설정 수정 전용. "설정 바꿔", "스킬 추가", "CLAUDE.md 개선", "하네스 수정" 시 사용.
argument-hint: "[수정 내용]"
user-invocable: true
---

# 하네스 설정 수정 — team-config

## 실행 조건
- "설정 바꿔", "스킬 추가", "에이전트 수정", "CLAUDE.md 개선", "하네스 수정"
- .claude/ 하위 파일만 수정하는 작업

## 분기 판단
- 단순 조정 (1~2파일, 명확한 변경): **경량 2-Phase**
- 전수 재설계 (3+파일, 구조 변경): **풀 4-Phase**

## 경량 모드 (2-Phase)

Phase 1: 설계
└── p1-arch (code-architect, model=opus) — 변경 스펙 작성

Phase 2: 적용 + 검증
└── p2-config (general-purpose, model=sonnet) — 파일 수정 + harness-audit 재실행

## 풀 모드 (4-Phase)

Phase 1: 감사
├── ops-audit (harness-audit, model=sonnet) — 현재 상태 정량 평가
└── p1-explore (general-purpose, model=sonnet) — 관련 파일 탐색

Phase 2: 설계
└── p2-arch (code-architect, model=opus) — 변경 스펙 → .claude/plans/config-{task}.md

Phase 3: 적용
└── p3-config (general-purpose, model=sonnet) — 실제 파일 수정

Phase 4: 재감사
└── ops-audit-2 (harness-audit, model=sonnet) — Before/After 비교

## 정보 계층 (team-build와 동일)
Phase 시작: ━━━ Phase N/M | {팀명} ━━━
팀 활동: ◎ {에이전트} {상태}
이벤트: ↳ [태그] {내용}
게이트: ✅ [PHASE_GATE] Phase N→M | 조건

## 통신 원칙
- 모든 소통 = SendMessage (파일 인수인계 금지)
- 워커 완료 → 보고 → 즉시 셧다운 (idle 유지 금지)

## 파일 소유권
- 수정 가능: .claude/agents/*.md, .claude/skills/**/*.md, .claude/rules/*.md, .claude/scripts/*.sh, CLAUDE.md
- 수정 금지: 코드 파일 (.tsx, .ts, .css 등)
