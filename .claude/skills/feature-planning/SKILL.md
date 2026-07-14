---
name: feature-planning
description: 스펙 기반 개발 워크플로우 — 작업 유형(Feature/Refactor/Bugfix)을 자동 판별하여 적절한 프로세스를 적용한다.
user-invocable: true
disable-model-invocation: false
---

# 스펙 기반 개발 워크플로우

사용자가 "스펙으로 진행해" 또는 `/feature-planning`을 호출하면 실행한다.

## 현재 프로젝트 상태
- 최근 커밋: !`git log --oneline -5`
- 변경 파일: !`git status --short | head -10`
- 기존 플랜: !`ls .claude/plans/ 2>/dev/null || echo "없음"`

## 인자 처리
- `$ARGUMENTS`가 있으면 작업 요청으로 사용
- 없으면 사용자에게 어떤 작업인지 질문

---

## Step 0: 유형 판별

사용자의 요청을 분석하여 3가지 유형 중 하나로 분류한다.

| 유형 | 트리거 키워드 | 예시 |
|------|-------------|------|
| **Feature** | 추가, 신규, 구현, 기능, 만들어 | "자산 감가상각 기능 추가" |
| **Refactor** | 통합, 정리, 마이그레이션, 개선, 정합성, 리팩토링 | "FK 통합", "_by 컬럼 정리" |
| **Bugfix** | 에러, 버그, 수정, 안됨, 터짐, 위반 | "매칭 시 FK 위반 에러" |

판별이 애매하면 사용자에게 확인한다. 판별 후 해당 유형의 워크플로우를 실행한다.

---

## Type A: Feature (신규 기능)

> 뭘 만들지 정의하는 게 핵심. 요구사항 누락이 최대 리스크.

### A-1. 기획 (Plan 모드)

`EnterPlanMode` 호출 후, Plan 파일에 아래 구조로 작성:

```markdown
# <기능명> — 스펙

## 개요
<목적과 배경 2~3줄>

## 요구사항
### R1: <기능 단위>
<역할>은 <행위>를 할 수 있어야 한다.
#### 인수 조건
- When <이벤트>, the system shall <응답>

### 비기능 요구사항
- 성능 / 보안 / 제약사항

## 기술 설계
### DB 스키마
### API 엔드포인트
### UI 컴포넌트
### 영향 분석
### 요구사항 매핑
| Requirement | 구현 위치 |
```

작성 전 내부 품질 체크:
1. 요구사항 가설 5가지 (시나리오, 역할, 엣지케이스)
2. 설계 가설 5가지 (DB, API, UI, 재활용, 성능)
3. 권한 분기, 예외 처리, 기존 기능 충돌 검증

`ExitPlanMode`로 승인 → **설계 산출물 자동 저장**:
승인된 스펙을 `.claude/plans/{feature-name}-spec.md`에 Write 도구로 저장한다.

### A-2. 태스크 분해

승인된 스펙을 기반으로 실행 계획 작성:
- **(P)** = 병렬 가능, **_R1, R2_** = 요구사항 추적
- 각 태스크를 2~5분 단위로 분해
- 사용자 확인 후 구현 진행

**실행 계획 자동 저장**:
태스크 목록을 `.claude/plans/{feature-name}-tasks.md`에 Write 도구로 저장한다.

### A-2.5. 인수 기준 협상 (사전 계약)

태스크 분해 완료 후, 구현 전에 **spec-compliance-reviewer Phase A**를 실행:
1. 스펙의 각 요구사항에서 검증 가능한 인수 기준(AC) 추출
2. 각 AC를 `[code]` 또는 `[browser]` 검증 유형으로 분류
3. 메인에게 `[ACCEPTANCE_CRITERIA]` 전달 → 메인이 워커 스폰 시 AC 포함
4. 구현 완료 후 Phase B에서 합의된 기준으로만 검증

> 이 단계는 Anthropic 가이드의 "negotiated contract" 원칙 적용.
> 생략 조건: 스펙이 3개 이하 요구사항이거나 Bugfix/Refactor 유형

### A-3. 구현

(P) 태스크 3개 이상 + 2개 이상 영역 → 에이전트 팀 병렬
그 외 → TodoWrite 순차 구현

### A-4. 후처리 (자동)

test-runner → spec-compliance-reviewer **Phase B** (합의 기준 검증) → parallel-reviewer + perf-reviewer (품질+성능) → doc-syncer
UI 컴포넌트 수정 포함 시: → ui-ux-expert (critic 모드, ui-designer 구현물 외부 평가)

---

## Type B: Refactor (리팩토링/정합성 개선)

> 어디가 영향받는지 파악하는 게 핵심. 영향범위 누락이 최대 리스크.

### B-1. 영향 분석 (Plan 모드)

`EnterPlanMode` 호출 후, Plan 파일에 아래 구조로 작성:

```markdown
# <작업명> — 영향 분석

## 배경
<왜 이 리팩토링이 필요한가 2~3줄>

## 현황
### 전수 조사 결과
| 위치 | 현재 상태 | 문제 |
### 영향받는 데이터
| 테이블 | 건수 | 변환 방법 |

## 실행 계획
### 변경 목록
| # | 파일/테이블 | 변경 내용 |
### 실행 순서
### 롤백 방법
```

작성 전 내부 품질 체크:
1. 전수 조사가 빠짐없이 되었는가 (Explore 에이전트 활용)
2. 데이터 마이그레이션이 필요한가, 있다면 매핑이 정확한가
3. 다른 모듈에 영향이 없는가

`ExitPlanMode`로 승인 → **1회 승인으로 바로 구현**

### B-2. 구현

Plan 승인 후 바로 구현 (별도 태스크 분해 불필요, TodoWrite로 추적)

### B-3. 후처리 (자동)

test-runner → parallel-reviewer + perf-reviewer (백그라운드) → doc-syncer (백그라운드)

---

## Type C: Bugfix (버그 수정)

> 왜 터지는지 원인 파악이 핵심. 원인 오판이 최대 리스크.

### C-1. 원인 분석

Plan 모드 없이 바로 탐색:
- 에러 메시지 / 재현 조건 확인
- 관련 코드 추적 (Explore 에이전트)
- 근본 원인 특정

사용자에게 원인과 수정 방안을 **텍스트로 브리핑** (문서 생성 불필요)

### C-2. 수정

사용자 확인 후 바로 수정 (승인 게이트 없음)

### C-3. 후처리 (자동)

test-runner → parallel-reviewer + perf-reviewer (백그라운드) → doc-syncer (백그라운드)

---

## 규칙
- 유형 판별은 Step 0에서 1회만 수행, 이후 변경하지 않음
- Feature만 .claude/plans/ 파일 생성, Refactor/Bugfix는 커밋과 task-log로 충분
- 후처리 트리거 체인은 3가지 유형 공통
- 단순 오타/스타일 변경은 이 워크플로우 자체를 생략
