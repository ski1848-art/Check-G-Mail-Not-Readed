---
name: team-build
description: 기획→개발→검증 3팀 빌드. 코드 구현 포함 작업 전용. 외부 조사=team-research, 내부 진단=직접 에이전트(root-cause-analyst 등)
argument-hint: "[작업 설명]"
user-invocable: true
---

# 3팀 빌드 체인 — Agent + SendMessage 기반

## 실행 조건

**team-build** (코드 구현 포함):
- "3팀 돌려", "팀 구성", "기획/개발/검증", "사업부" 등 사용자 요청 시
- 3파일 이상 수정이 예상되는 Feature/Refactor 작업

**team-plan 모드** (스펙만):
- "스펙만 짜줘", "설계만 해줘", "기획팀만 돌려"
- Phase 1 → Phase 4 (Phase 2, 3 스킵)

## Codex 교차 리뷰 (Phase 3 자동)

Codex 설치 시 Phase 3에서 **자동으로** gpt-5.6-sol 교차 리뷰 실행:
- `codex exec -m gpt-5.6-sol "변경 파일 리뷰"` → Claude QA 결과와 합산
- 특히 UI/프론트엔드, CLI/스크립트 변경 시 Codex 관점 우선 참고 (벤치마크 강점)
- Claude와 Codex 판단 상충 시 → 사용자 결정
- Codex 미설치 시 자동 스킵 (fail-graceful)

## Step 1. 팀 구성 준비

세션당 팀은 하나(암묵적)이며 별도 "팀 생성" API는 없다. 메인이 Step 2의 각 Phase에서 역할별로 `Agent(name="...", subagent_type="...", ...)`를 직접 호출해 teammate를 스폰하고, 이후 `SendMessage({to: "그 name", message: ...})`로 이름 기준 소통한다. teammate가 완료 보고 후에도 종료되지 않으면 메인이 `TaskStop({task_id: "그 name"})`으로 정리한다.

**Codex 교차 리뷰 사용 시:** 별도 초기화 불필요. Phase 3에서 메인이 `codex exec -m gpt-5.6-sol "..."`를 Bash(run_in_background)로 직접 호출한다. 미설치 시 스킵(fail-graceful).

## Step 2. TodoWrite로 Phase + 서브태스크 추적

전용 태스크 관리 API가 없으므로 메인이 `TodoWrite`로 Phase 진행 상황을 추적한다.

```
TodoWrite 항목 예시:
  [ ] Phase 1: 기획 — 스펙 작성 + UX 검증
      [ ] 1-1. p1-plan-arch: 스펙 초안 작성
      [ ] 1-2. p1-plan-ux: UX 리뷰
      [ ] 1-3. 스펙 최종 확정 (Phase 게이트)

  [ ] Phase 2: 개발 — 스펙 기반 구현 (Phase 1 완료 후 착수)
      [ ] 2-1. p2-dev-api: API 구현 (Flask app/ 또는 admin-web API Routes, 필요 시)
      [ ] 2-2. p2-dev-ui: UI 구현 (admin-web 컴포넌트/페이지, 필요 시)
      [ ] 2-3. API 계약 교환 (UI+API 병렬 시)

  [ ] Phase 3: 검증 — 빌드 + 스펙 대조 + 코드 리뷰 (Phase 2 완료 후 착수)
      [ ] 3-1. p3-qa-lead: 서브에이전트 4종 병렬 검증 + 스펙 대조 + 종합 판정 (Phase 게이트)
      # pytest/tsc·code·perf·sec는 p3-qa-lead 내부 서브에이전트 호출 — 별도 TodoWrite 항목 불필요

  [ ] Phase 4: 정리 — 산출물 아카이브 + 팀 정리 (Phase 3 완료 후 착수)
```

**이 프로젝트는 Firestore만 사용(SQL DB 없음)** — Phase 2는 api-worker(Flask `app/` + admin-web API Routes) + ui-worker(admin-web 컴포넌트) 2역할 중심이며 DB 마이그레이션 서브태스크는 없다.

에이전트별 서브태스크는 스폰 프롬프트에 전달 → 완료 보고 수신 시 메인이 TodoWrite 항목을 `completed`로 갱신.

---

## 정보 계층 — 메인 에이전트 출력 의무 (전 Phase 공통)

사용자에게 팀 상황을 직관적으로 전달하기 위해 아래 4단계 계층을 준수한다.

```
Level 1 (항상): Phase 전환 헤더
  ━━━ Phase N/M | {팀 이름} ━━━━━━━━━━━━━━━━━━━━
  구성: {에이전트 이름 목록}

Level 2 (Phase 시작/완료 시): 팀 활동 요약
  ◎ {에이전트}  {현재 상태 요약}

Level 3 (이벤트 발생 시): 계약 교환 / 에러
  ↳ [MSG_RELAY] {발신자} → {수신자} | {요약}
  ↳ ⚠ [FIX_REQUEST] {에이전트} | {에러 목록}

Level 1 게이트 (Phase 전환 판정):
  ✅ [PHASE_GATE] Phase N→M | 조건 목록

Level 4 (기본 숨김): 에이전트 내부 동작 — 출력 안 함
```

**시각 구분**: 태그를 읽지 않아도 들여쓰기(◎=2칸, ↳=4칸)와 아이콘만으로 계층 인식 가능.

### MSG_RELAY 빈도 제한 (노이즈 방지)

메인 에이전트가 사용자에게 릴레이하는 SendMessage 기준:

```
릴레이 대상 (Level 3 출력):
- [API_CONTRACT]   팀 간 API 계약 교환
- [FIX_REQUEST]    FAIL 후 재작업 요청
- [VERIFY_RESULT]  검증 개별 결과
- [TEAM_JUDGMENT]  검증팀 종합 판정

릴레이 생략 (Level 4 / 숨김):
- 일반 진행 보고 ("스펙 작성 중", "읽는 중")
- 에이전트 간 내부 확인 메시지
- 분석 진행 경과 알림
```

---

## Step 3. Phase별 팀 운영

### Phase 0: 조사 + 팀 규모 확정 (Phase 1 선행)

`agent-spawn.md` 기준으로 team-build는 Phase 1 착수 전에 반드시 조사 단계를 거친다. 목적은 변경 대상 파일, 의존성, 독립 스트림을 먼저 확인하고 그 결과로 팀 규모를 확정하는 것이다.

**Step 1. 내부 조사 — Explore 에이전트 (`model="sonnet"`):**
```
- 파일 목록 수집
- 의존성 추적
- 독립 스트림 식별
- 판정 제안 작성
```

**Step 2. 외부 조사 — Codex (`codex exec`):**
```bash
codex exec -m gpt-5.6-sol "웹검색으로 {작업 주제} 베스트프랙티스와 기술 선택지를 비교하고, 현재 코드베이스 제약과 충돌 가능성을 요약."
```
```
- 웹검색 기반 베스트프랙티스 확인
- 대안 기술/구현 방식 비교
- 프로젝트 제약과 충돌하는 선택지 제외
```
Codex 미설치 시 fail-graceful로 스킵하고 Claude 단독 판단.

**Step 3. 조사 결과 기반 방식 확정 — 메인 에이전트:**
```
- Explore 조사 + Codex 외부 조사 결과 검토
- 독립 스트림 수에 따라 팀 규모 결정
  - 독립 스트림 1개, 5파일 이하 → 메인 직접 또는 teammate 1명
  - 독립 스트림 2개 → teammate 2명
  - 독립 스트림 3개 이상 → 오케스트라 유지
- 공유 파일(타입, 유틸)은 메인 에이전트 소유로 분리
- 1줄 브리핑 후 Phase 1 진입
```

**독립 스트림 정의 (`agent-spawn.md` 일치):**
- 파일 소유권이 겹치지 않는 작업 단위
- 공유 파일(타입, 유틸)은 메인 에이전트 소유 → 스트림에 포함하지 않음

**Phase 0 완료 조건:**
- 파일 목록 확보
- 독립 스트림 식별 완료
- 팀 규모 확정

### Phase 1: 기획팀 (2명, flat 직접 보고)

**flat 구조 원칙**: 2~3명 팀은 모든 teammate가 메인에게 직접 보고. 별도 종합자 불필요.

**구성:**
| 역할 | name | 에이전트 | 책임 |
|------|------|---------|------|
| **기획 종합** | `p1-plan-arch` | `code-architect` | 스펙 초안 작성, UX 피드백 반영, 최종 스펙 확정, plan_approval_request 발행 |
| **UX 검증** | `p1-plan-ux` | `ui-ux-expert` | 스펙 UX 검증, 정보 계층/스캔 패턴/인터랙션 리뷰 |

**에이전트 스폰 (메인이 직접 호출):**
```
Agent(name="p1-plan-arch", subagent_type="code-architect", ...)
Agent(name="p1-plan-ux",   subagent_type="ui-ux-expert",   ...)
```
스폰 직후 메인이 TodoWrite의 "1-1. p1-plan-arch" 항목을 `in_progress`로 갱신하고, 정보 계층 Level 2 형식(`◎ p1-plan-arch  스펙 작성 중`)으로 직접 출력한다 — 별도 상태 갱신 함수 없음.

**상호작용 프로토콜:**
```
1. p1-plan-arch가 스펙 초안 작성 → .claude/plans/{feature}-spec.md 저장
2. p1-plan-ux가 스펙 읽고 UX 리뷰 → SendMessage to 메인
   - 메인이 핵심 피드백을 p1-plan-arch에 relay
3. p1-plan-arch가 피드백 반영 → 스펙 업데이트
4. 합의 도달 → p1-plan-arch가 SendMessage로 메인에 완료 보고 → 메인이 TodoWrite에서 해당 서브태스크를 completed로 갱신
```

**Plan Approval 게이트 (Phase 1 → Phase 2 전환 필수):**
```
5. p1-plan-arch → [plan_approval_request] SendMessage to 메인
   - 스펙 파일 경로, 핵심 설계 결정, 구현 착수 전 확인 필요 사항 포함
6. 메인이 스펙 검토 → approve 또는 reject
   - approve: Phase 2 태스크 unblock → 개발팀 스폰
   - reject: 수정 요청 사항과 함께 p1-plan-arch에 SendMessage → 재작업 (최대 2라운드)
```

**메인 에이전트 출력 예시:**
```
━━━ Phase 1/4 | 기획팀 ━━━━━━━━━━━━━━━━━━━━━━━━━
구성: p1-plan-arch(기획종합), p1-plan-ux(UX검증)
  ◎ p1-plan-arch  스펙 초안 작성 완료
  ◎ p1-plan-ux    UX 리뷰 완료
    ↳ [MSG_RELAY] 메인 | p1-plan-ux → p1-plan-arch | UX 피드백 3건
    ↳ [MSG_RELAY] p1-plan-arch | 피드백 반영 완료 (2라운드 합의)
    ↳ [plan_approval_request] p1-plan-arch → 메인 | 스펙 확정, Phase 2 착수 승인 요청
✅ [PHASE_GATE] Phase 1→2 | 스펙 파일 ✅ | UX 합의 ✅ | 메인 approve ✅
```

**최대 2라운드.** 3라운드 이상은 사용자 명시 요청 시에만.

**Phase 1→2 전환 게이트 (메인 에이전트 — 직접 검증 필수):**
1. `.claude/plans/{feature}-spec.md` 파일 존재 확인 (Glob)
2. 파일 없으면 → 메인 에이전트가 code-architect 출력을 직접 저장
3. **plan_approval_request 수신 → 메인이 스펙 파일을 직접 Read**
4. **메인 직접 검증 (Opus 1M 활용):**
   - 스펙 누락/모순 체크 (요구사항 빠짐, 엣지케이스 미고려)
   - ACCEPTANCE_CRITERIA 존재 + 충분성 확인
   - 변경 파일 목록 vs 실제 파일 교차 확인
   - 기존 코드와 충돌 가능성 판단
5. approve → Phase 2 unblock / reject → 구체적 피드백 SendMessage to p1-plan-arch

**에이전트 셧다운 원칙 (전 Phase 공통):**
- **작업 완료 → 메인 보고 → 즉시 셧다운** — idle 유지 금지
- Phase 간 질의/피드백은 **메인이 수신 후 relay**
- 이전 Phase 맥락이 다시 필요하면 메인이 동일 역할 워커를 재스폰하고 핵심 요약 + 파일 경로를 전달
- Phase 4는 잔여 teammate 정리(TaskStop) 단계이며, 셧다운 지연 근거가 아니다

**p1-plan-arch 완료 조건:**
- 스펙 파일 저장됨
- UX 검증 teammate 합의 또는 2라운드 완료
- 변경 파일 목록 + 보존 항목 + 체크리스트 포함
- plan_approval_request 발행 및 메인 approve 수신

**기획팀 금지 사항:**
- 코드 수정 금지 (Read/Grep/Glob만, Write는 .claude/plans/에만)
- API 호출/DB 쿼리 실행 금지
- 구현 세부 코드 작성 금지 (의사코드/구조만 기술)

---

### Phase 2: 개발팀 (1~3명, flat 직접 보고)

**teammate vs 서브에이전트 원칙**: 상호 소통이 필요한 경우에만 teammate(name 지정)로 스폰. 독립 작업(소통 불필요)은 서브에이전트로 호출. Phase 2는 UI↔API 계약 교환이 필요하므로 teammate 유지. 1~3명 팀은 모든 teammate가 메인에게 직접 보고.

**구성 (규모별):**
| 규모 | name | 에이전트 | 병렬 |
|------|------|---------|------|
| 1~2파일 | `p2-dev-ui` | ui-worker 1명 | 단독 |
| 3~5파일 (UI+API) | `p2-dev-ui` + `p2-dev-api` | ui-worker + api-worker | 병렬 |
| 6+파일 | 다중 워커 + worktree 격리 | | 병렬 |

**메인이 전원 스폰 (오케스트레이션):**

```
Agent(name="p2-dev-ui",  subagent_type="ui-worker",  ...)
Agent(name="p2-dev-api", subagent_type="api-worker", ...)
```
스폰 직후 메인이 TodoWrite 항목을 `in_progress`로 갱신하고, 정보 계층 Level 2 형식(`◎ p2-dev-ui  구현 중`)으로 직접 출력한다.

**상호작용 프로토콜 (UI+API 병렬 시):**
```
1. p2-dev-api가 API 구현 완료 → [API_CONTRACT] SendMessage to 메인
   - 메인이 p2-dev-ui에 relay
   - 엔드포인트, 응답 타입, 파라미터 명세
2. p2-dev-ui가 API 계약 수신 → fetch URL/타입 일치 확인
3. 부족한 필드 → [API_CHANGE_REQUEST] SendMessage to 메인
   - 메인이 p2-dev-api에 relay
4. 양쪽 완료 → 각자 SendMessage to 메인(완료 보고) → 즉시 셧다운 → 메인이 TodoWrite에서 해당 서브태스크를 completed로 갱신
```

**Ralph Loop (Phase 2 실패 복구 규칙):**
```
MAX_ITERATIONS=5 (같은 작업 최대 재시도)

- 1회 실패: 오류 내용 분석 후 재시도
- 2회 동일 실패: 근본 원인 분석 브리핑 필수 (CLAUDE.md 규칙과 통합)
  → "왜 실패하는지" 먼저 밝히고 정석 해법 제시 후 재시도
- 3회 동일 오류: 자동 일시정지 → [RALPH_ESCALATION] SendMessage to 메인
  → 메인이 근본 원인 확인 후 방향 결정 (재시도 / 방식 변경 / 스펙 수정)
- 5회 초과: 강제 에스컬레이션, 메인이 직접 개입
```

**메인 에이전트 출력 예시:**
```
━━━ Phase 2/4 | 개발팀 ━━━━━━━━━━━━━━━━━━━━━━━━━
구성: p2-dev-ui(UI구현), p2-dev-api(API구현) — flat, 메인에 직접 보고
  ◎ p2-dev-api  API 구현 완료
  ◎ p2-dev-ui   UI 구현 완료
    ↳ [MSG_RELAY] 메인 | [API_CONTRACT] p2-dev-api → p2-dev-ui | GET /api/vendors 외 2개
✅ [PHASE_GATE] Phase 2→3 | 개발 완료 ✅ | 메인 검증 ✅
```

**Phase 2→3 전환 게이트 (메인 에이전트 — 직접 검증 필수):**
1. 개발 teammate 전원 완료 보고 수신 (보고 후 각자 셧다운)
2. **메인이 변경 파일을 직접 Read** (스펙 대비 구현 누락 체크)
   - 스펙 체크리스트 항목 하나씩 대조
   - 타입 정합성, import 누락, 하드코딩 체크
   - Flask(app/main.py) ↔ admin-web API 응답 형식({success,data}/{success,error}) 일관성 확인
3. 문제 발견 → 메인이 해당 역할 워커를 재스폰하여 교정 요청 (Phase 2 재진입)
4. 문제 없음 → Phase 3 unblock

**파일 소유권 규칙 (MECE):**
```
p2-dev-ui 소유:   admin-web/app/**/*.tsx, admin-web/components/**/*.tsx
p2-dev-api 소유:  app/main.py(Flask) + app/services/*, admin-web/app/api/**/*.ts
공유 금지:        한 파일을 두 에이전트가 동시 수정 금지
공용 파일:        config/*.json, 공유 타입 등은 메인 에이전트가 직접 처리
```

**개발팀 프롬프트 필수 포함:**
```
### 스펙 참조
.claude/plans/{feature}-spec.md를 읽고 체크리스트 항목을 하나씩 구현하라.

### React 규칙 (admin-web 수정 시 — 위반 시 런타임 크래시)
- hooks(useState/useEffect/useMemo)는 조건부 return 전에 모두 호출
- if (!isOpen) return null 같은 early return 위에서 hooks 완료

### 백엔드 규칙 (Flask app/ 수정 시)
- 응답 jsonify({"success": True/False, ...}), 모든 핸들러 try-except
- Slack 요청은 HMAC 서명 검증 필수, /run-batch 계열은 멱등성 유지
- 데이터는 Firestore (SQL 아님) — 사용자 입력을 문서 키로 쓰기 전 검증

### 공통
- 사용자 노출 문구는 한국어 (영문 에러/예외 원문 노출 금지)
- 시크릿 하드코딩 금지 → Config.* / 환경변수 경유

### 계층참조 체크리스트 (수정 시)
1. rules/ui-components.md (admin-web UI) 또는 rules/api-routes.md (API) 읽기
2. rules/types-constants.md 읽기 (admin-web 타입/상수)
```

**개발팀 금지 사항:**
- 스펙 변경 금지 (스펙과 다르면 메인 에이전트에 에스컬레이션)
- 소유권 밖 파일 수정 금지
- Firestore 컬렉션/필드 구조 변경 금지 (스펙에 없는 구조 변경은 메인 에이전트에 에스컬레이션 — 이 프로젝트는 SQL DB 없이 Firestore만 사용)

---

### Phase 3: 검증팀 (p3-qa-lead 1명 teammate + 서브에이전트 4종)

**teammate vs 서브에이전트 원칙**: Phase 3는 p3-qa-lead만 teammate(name 지정, 메인에 직접 보고). 나머지 4개 검증(test/code/perf/sec)은 p3-qa-lead가 내부에서 서브에이전트로 병렬 호출한다. 서브에이전트는 name이 없어 SendMessage 대상이 될 수 없음 — 결과를 호출자인 p3-qa-lead에게 직접 반환.

**구성:**
| 역할 | 유형 | 에이전트 | 검증 항목 |
|------|------|---------|---------|
| **종합자** | teammate | `spec-compliance-reviewer` (`p3-qa-lead`) | 스펙 대조 + 서브에이전트 4종 수렴 + 종합 판정 + 메인 보고 |
| **빌드** | 서브에이전트 | `test-runner` | pytest(Python `app/`) + tsc --noEmit(admin-web) 검증 |
| **품질** | 서브에이전트 | `parallel-reviewer` | 코드 품질, 컨벤션 준수 |
| **성능** | 서브에이전트 | `perf-reviewer` | N+1, 불필요 렌더, 인덱스 미활용 |
| **보안** | 서브에이전트 | `security-auditor` | SQL injection, XSS, 권한 체크 |

**메인 스폰 (p3-qa-lead만 teammate):**
```
Agent(name="p3-qa-lead", subagent_type="spec-compliance-reviewer", ...)
# 나머지 4종은 p3-qa-lead 프롬프트 내에서 서브에이전트로 병렬 호출
```
스폰 직후 메인이 TodoWrite 항목을 `in_progress`로 갱신하고, 정보 계층 Level 2 형식(`◎ p3-qa-lead  검증 중 (서브에이전트 4종 병렬)`)으로 직접 출력한다.

**p3-qa-lead 프롬프트 필수 포함 (서브에이전트 호출 지시):**
```
### 검증 서브에이전트 병렬 호출
아래 4개 검증을 서브에이전트로 동시 호출하라 (team_name 없음, 일반 Agent() 호출):
- Agent(subagent_type="test-runner",       model="sonnet", ...): pytest(Python) + tsc --noEmit(admin-web)
- Agent(subagent_type="parallel-reviewer",                  ...): 코드 품질, 컨벤션 준수
- Agent(subagent_type="perf-reviewer",                      ...): N+1, 불필요 렌더, 인덱스
- Agent(subagent_type="security-auditor",                   ...): SQL injection, XSS, 권한

모든 결과 수렴 후 종합 판정 → [TEAM_JUDGMENT] SendMessage to 메인.
```

**상호작용 프로토콜:**
```
1. 메인이 p3-qa-lead 단독 스폰 (teammate, name 지정)
2. p3-qa-lead가 서브에이전트 4종 병렬 호출 (Agent(), team_name 없음)
3. 메인이 Codex 교차 리뷰 동시 실행 (p3-qa-lead와 병렬):
   → codex exec -m gpt-5.6-sol "변경 파일 목록 + diff 요약 + 리뷰 요청"
   → 결과를 .claude/bridge/codex-result.txt로 수집
4. 서브에이전트 + Codex 결과 수렴:
   - BUILD_RESULT:  PASS/FAIL + 에러 목록
   - REVIEW_RESULT: 이슈 목록 (severity: high/medium/low)
   - PERF_RESULT:   성능 이슈
   - SEC_RESULT:    보안 이슈
   - CODEX_RESULT:  gpt-5.6-sol 교차 리뷰 (다른 모델 관점)
5. p3-qa-lead가 Claude 4종 종합 판정 → [TEAM_JUDGMENT] SendMessage to 메인
6. 메인이 Codex 결과와 합산:
   - 일치 → 최종 PASS
   - Codex만 이슈 발견 → 메인이 직접 확인 후 반영 여부 결정
   - 상충 → 사용자에게 양쪽 제시
   - Codex 미설치/타임아웃 → Claude 결과만으로 판정 (fail-graceful)
```

**Ralph Loop (Phase 3 실패 복구 규칙):**
```
MAX_ITERATIONS=5 (같은 검증 항목 최대 재시도)

- 1회 FAIL: p3-qa-lead가 [FIX_REQUEST] to 메인 → 메인이 해당 개발 워커 재스폰 → 수정 후 메인 경유 재검증 요청
- 2회 동일 FAIL: 근본 원인 분석 브리핑 필수
  → p3-qa-lead가 원인 분석 요약 포함한 [FIX_REQUEST] 발행
- 3회 동일 오류: 자동 일시정지 → [RALPH_ESCALATION] SendMessage to 메인
  → 메인이 개입하여 방향 결정 (재시도 / 설계 변경 / 예외 처리)
- 5회 초과: 강제 에스컬레이션, 메인이 직접 수정
```

**메인 에이전트 출력 예시:**
```
━━━ Phase 3/4 | QA (p3-qa-lead + 서브에이전트 4종 + Codex) ━━━━━━
구성: p3-qa-lead(종합, teammate) + 서브에이전트[tsc, code, perf, sec] + Codex(gpt-5.6-sol)
    ↳ [VERIFY_RESULT] tsc   | tsc PASS
    ↳ [VERIFY_RESULT] code  | 이슈 1건 (severity: low)
    ↳ [VERIFY_RESULT] perf  | PASS
    ↳ [VERIFY_RESULT] sec   | PASS
    ↳ [VERIFY_RESULT] codex | 이슈 2건 (1건 Claude와 상충)
  ◎ p3-qa-lead  종합 판정: PASS (Claude 4/4)
  ◎ Codex       교차 리뷰: 상충 1건 → 사용자 판단 대기
✅ [PHASE_GATE] Phase 3→4 | QA 통과 ✅ | 메인 최종 검증 ✅
```

**Phase 3→4 전환 게이트 (메인 에이전트 — 최종 검증 필수):**
1. p3-qa-lead 종합 판정 수신 ([TEAM_JUDGMENT])
2. **메인이 critical 이슈로 지적된 파일을 직접 Read** (Sonnet이 놓친 것 Opus가 재확인)
3. **스펙 ACCEPTANCE_CRITERIA vs 구현 최종 대조** (메인이 직접)
4. 문제 발견 → 메인이 해당 개발 워커를 재스폰하여 교정 요청 (Phase 2/3 재진입)
5. 문제 없음 → Phase 4 진입
    ↳ [VERIFY_RESULT] perf | PASS
    ↳ [VERIFY_RESULT] sec  | PASS
  ◎ p3-qa-lead  종합 판정: PASS 4/4
✅ [PHASE_GATE] Phase 3→4 | QA 통과 ✅
```

**FAIL 시 복구 프로토콜:**
```
Phase 3 FAIL:
1. 리뷰어가 이슈를 메인에 보고
2. 메인(Opus 1M)이 전체 컨텍스트를 활용하여 직접 수정
   (워커 재스폰 금지 — 빈 컨텍스트 시작이라 품질 저하 + 토큰 낭비)
3. 수정 후 test-runner 재실행으로 회귀 확인
4. 최대 3회 반복 — 3회 동일 실패 시 사용자 에스컬레이션
```

**메인 에이전트 FAIL 출력:**
```
    ↳ ⚠ [FIX_REQUEST] p3-qa-lead → 메인 | 빌드 에러 2건 → p2-dev-ui 재스폰 (1/5회)
```

**검증팀 금지 사항:**
- 직접 코드 수정 금지 (리포트만)
- 스펙 변경 금지
- 리뷰 결과를 사용자에게 직접 보고 금지 (p3-qa-lead 경유)

---

### Phase 4: 정리 (메인 에이전트 직접 수행)

```
━━━ Phase 4/4 | 정리 ━━━━━━━━━━━━━━━━━━━━━━━━━━
  ◎ 아카이브 완료. 잔여 teammate 정리 완료.
커밋 제안 → [y/N]
```

```
1. 잔여 teammate 정리:
   - 완료 보고 후에도 종료되지 않은 teammate가 있으면 TaskStop({task_id: "그 name"})으로 종료
   - 일반적으로 p3-qa-lead만 잔존 (Phase 1/2 워커는 완료 시 이미 셧다운)

2. 산출물 아카이브:
   - .claude/plans/{feature}-spec.md → .claude/plans/archive/ 로 이동

3. TodoWrite 정리:
   - 전체 Phase 항목을 completed로 마감

4. 완료 보고:
   - 변경 파일 목록
   - 검증 결과 요약
   - 커밋 제안 (사용자 확인 후)
```

---

## 산출물 생명주기

```
생성:    Phase 1에서 .claude/plans/{feature}-spec.md 작성
사용:    Phase 2에서 개발팀이 참조
검증:    Phase 3에서 p3-qa-lead가 스펙 대조
아카이브: Phase 4에서 .claude/plans/archive/로 이동
삭제:    수동 (사용자 판단) 또는 30일 후 자동 제안
```

**누적 방지:**
- 완료된 feature의 plans 파일은 Phase 4에서 반드시 아카이브
- `.claude/plans/`에는 **진행 중인 feature 파일만** 존재

---

## 전체 실행 흐름

```
[사용자] "3팀 돌려 {작업 설명}"
    ↓
[메인] TodoWrite로 Phase 태스크 + 서브태스크 등록
    ↓
━━━ Phase 1/4 | 기획팀 (flat, 2명) ━━━
    ├─ p1-plan-arch (기획종합): 스펙 초안 → .claude/plans/ 저장
    └─ p1-plan-ux (UX검증): UX 리뷰 → 메인 보고, 메인 relay
    ↓ (최대 2라운드)
    ↓ [plan_approval_request] p1-plan-arch → 메인 → approve
✅ [PHASE_GATE] 스펙 파일 확인 + 메인 approve → Phase 2 unblock
    ↓
━━━ Phase 2/4 | 개발팀 (flat, 1~3명) ━━━
    ├─ p2-dev-ui (UI구현): TSX 구현 (스펙 참조)
    └─ p2-dev-api (API구현): API 구현 (필요 시, 병렬)
    ↓ (API 계약 교환은 메인 relay, Ralph Loop 적용)
✅ [PHASE_GATE] 개발 완료 → Phase 3 unblock
    ↓
━━━ Phase 3/4 | QA (p3-qa-lead 단독 teammate) ━━━
    └─ p3-qa-lead (종합): 스펙 대조 + 서브에이전트 4종 병렬 호출 + 종합 판정
       ├─ 서브에이전트: test-runner (pytest + tsc 빌드)
       ├─ 서브에이전트: parallel-reviewer (코드 품질)
       ├─ 서브에이전트: perf-reviewer (성능)
       └─ 서브에이전트: security-auditor (보안)
    ↓
    ├─ PASS → Phase 4
    └─ FAIL → ⚠ [FIX_REQUEST] to 메인 → 개발 워커 재스폰 → 재검증 (Ralph Loop, MAX 5회)
    ↓
━━━ Phase 4/4 | 정리 ━━━
    ├─ 산출물 아카이브
    ├─ 잔여 teammate 정리 (TaskStop)
    └─ 완료 보고 + 커밋 제안
```

## MECE 역할 매트릭스

| 활동 | 기획팀 | 개발팀 | 검증팀(p3-qa-lead) | 메인 |
|------|:---:|:---:|:---:|:---:|
| 코드 분석 (읽기) | O | O | O | O |
| 스펙 작성 | O | X | X | X |
| UX 검증 | O | X | X | X |
| 코드 수정 | X | O | X | (공유 파일만) |
| API 구현 | X | O | X | X |
| 빌드 검증 | X | X | O (서브에이전트) | X |
| 스펙 대조 | X | X | O | X |
| 코드 품질 리뷰 | X | X | O (서브에이전트) | X |
| Phase 전환 판단 | X | X | X | O |
| Plan Approval 판정 | X | X | X | O |
| 산출물 관리 | X | X | X | O |
| 팀 생성/해산 | X | X | X | O |

## 팀 구성 판단 (agent-spawn.md v2 연동)

```
Trivial (1-2파일 × 1-5줄):  /team-build 호출 안 됨 — 메인 직접 처리
Standard (Phase 0 조사 후):  조사 결과 독립 스트림 수에 따라 팀 규모 결정
Orchestra (사용자 명시):     규모 무관, 무조건 풀 팀 오케스트라
```

**teammate당 작업 수 비율 (팀 규모 가이드라인):**
```
기준: 5~6 tasks/teammate
  10개 작업 → 2명
  15개 작업 → 3명
  20개 작업 → 4명 (종합자 1명 + 실행 3명)
  25개+ 작업 → 5명 (종합자 1명 + 실행 4명, worktree 격리 권장)

적용 시점: Phase 0 조사에서 총 작업 수 파악 후 팀 규모 확정
```

상세 판정 기준: `.claude/rules/agent-spawn.md` 참조

---

## TeammateIdle 훅 (자동화 옵션)

Phase 3 검증 완료 시 메인이 자동으로 알림을 받으려면 settings.json에 TeammateIdle 훅을 설정할 수 있다.

```json
// .claude/settings.json 예시
{
  "hooks": {
    "TeammateIdle": [
      {
        "matcher": "p3-qa-lead",
        "hooks": [
          {
            "type": "command",
            "command": "echo '[TeammateIdle] QA 종합 완료: $TEAMMATE_NAME'"
          }
        ]
      }
    ]
  }
}
```

**현재 기본값: 수동** — p3-qa-lead가 [TEAM_JUDGMENT] SendMessage로 메인에 보고.
TeammateIdle 훅 설정 시 p3-qa-lead 완료를 메인이 자동으로 감지하여 Phase 4 진입을 즉시 트리거할 수 있다.
