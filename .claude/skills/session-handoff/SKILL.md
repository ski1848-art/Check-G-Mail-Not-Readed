---
name: session-handoff
description: 세션 핸드오프 — 컨텍스트 압축/세션 종료 전 작업 상태를 .claude/handoff.md에 저장하여 다음 세션에서 이어받기.
user-invocable: true
disable-model-invocation: false
---

# Session Handoff (세션 이어가기)

`/session-handoff` 또는 세션 종료 직전에 사용한다.

## 현재 상태 수집
```bash
# 작업 브랜치 확인
git branch --show-current

# 변경사항 확인
git status --short

# 최근 커밋
git log --oneline -5

# 미완료 TODO 확인 (존재 시)
cat .claude/plans/*-tasks.md 2>/dev/null || echo "없음"
```

## Handoff 파일 생성

`.claude/handoff.md`에 아래 구조로 저장:

```markdown
# Session Handoff — {{날짜 YYYY-MM-DD HH:mm}}

## 작업 요약
{{이번 세션에서 한 일 2~3줄}}

## 현재 상태
- 브랜치: {{branch}}
- 미커밋 변경: {{있음/없음 + 파일 목록}}
- 빌드 상태: {{통과/실패/미확인}}

## 미완료 작업
1. {{남은 작업 1}}
2. {{남은 작업 2}}

## 다음 세션에서 할 일
1. {{우선순위 1}}
2. {{우선순위 2}}

## 컨텍스트 (다음 세션 에이전트가 알아야 할 것)
- {{핵심 결정사항}}
- {{주의사항/함정}}
- {{참조 파일 경로}}

## 실행 중이던 에이전트
- {{에이전트명}}: {{상태}} (완료/진행중/대기)
```

## 다음 세션 시작 시

새 세션에서 자동 확인:
1. `.claude/handoff.md` 존재 여부 체크
2. 존재하면 내용 읽고 사용자에게 이전 작업 요약 보고
3. 이어서 작업할지 새로 시작할지 확인
4. 이어가기 선택 시 handoff 파일 기반으로 TODO 복원

## 자동 트리거 조건
- 컨텍스트 윈도우 사용량 80% 이상 시 자동 제안
- 사용자가 "오늘 여기까지" / "나중에 이어서" 등 종료 의사 표현 시

## 정리
작업이 완전히 완료되면 handoff.md 삭제:
```bash
rm .claude/handoff.md
```
