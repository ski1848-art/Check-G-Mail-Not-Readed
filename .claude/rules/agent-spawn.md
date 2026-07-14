# 에이전트 스폰 규칙

## 모델/성능 정책 (절대 규칙)

### 팀 구조
- **Claude Code 팀 구조는 flat** — 메인이 전원 스폰. 4명 이상 시 종합 담당 1명 지정 가능 (프롬프트 역할 지정, 시스템 계층 아님)
- 프롬프트로 역할(종합자/구현자/검증자) 지정하여 협업

### 셧다운 정책 (토큰 최적화)
- **작업 완료 → 보고 → 즉시 셧다운** (idle 과금 방지)
- 교차 공유는 **메인이 중계** — 워커 완료 보고 수신 후 필요한 정보를 다른 워커에 전달
- idle teammate는 토큰을 계속 소비함 (공식 문서: "Active teammates continue consuming tokens even if idle")

### teammate / subagent 분류 (Anthropic 권장: 동시 teammate 3~5개)

**teammate** (오케스트라 시 name 지정 스폰 + SendMessage, 실시간 협업):
```
code-architect           ← 기획/설계
api-worker               ← 백엔드 구현 (Flask + Next.js API Routes)
ui-worker                ← 프론트엔드 구현 (admin-web)
spec-compliance-reviewer ← QA 리드 (subagent 4종 오케스트레이션)
```

**subagent** (결과만 반환, teammate 또는 메인이 호출):
```
test-runner        ← pytest(Python) + tsc(admin-web) 검증
security-auditor   ← 보안 감사 (Slack 서명, 키 노출, 인증)
perf-reviewer      ← Gmail/LLM/Firestore 호출 효율 분석
parallel-reviewer  ← 코드 품질/컨벤션 리뷰
root-cause-analyst ← 버그 근본 원인 (코드 + 외부 시스템 추적)
doc-syncer         ← 문서 동기화
ui-designer, ui-ux-expert, harness-audit
```

**외부 (Codex)**: 교차 리뷰, 반증 찾기, UI 리뷰 — `codex exec` 직접 호출 (Bash)

### 모델 선택 (작업 성격별 — 토큰 효율 우선)

**판정 기준: 작업 복잡도 + 추론 요구 수준** (특정 모델 버전명을 규칙에 하드코딩하지 않는다 — 모델 교체 시 규칙이 낡는 것 방지)

```
Opus급 필수 (복잡 추론):
  아키텍처 설계, 복잡 버그 디버깅, 다파일 의존성 분석, 보안 감사
  → code-architect, root-cause-analyst, security-auditor, spec-compliance-reviewer

Sonnet급 적합 (구현/실행):
  파일 생성, UI 구현, API 구현, 테스트, 리뷰, 문서
  → ui-worker, api-worker, test-runner, parallel-reviewer,
    perf-reviewer, ui-designer, harness-audit, doc-syncer

서브에이전트 전용 (Sonnet, 팀 외부):
  → Explore, Plan, ui-ux-expert
```

- **사용자가 명시적으로 모델 지정 시** → 사용자 지시 우선
- **서브에이전트(팀 외부)** = Sonnet 기본
- **1M 컨텍스트**: 서브에이전트에 1M 지정 불가 (`model: "opus"`는 표준 Opus 매핑). 완화: 파일 경로만 전달, 에이전트가 직접 Read

### effort 전파 정책
- **frontmatter `effort` 필드가 SSOT** — ENV `CLAUDE_CODE_EFFORT_LEVEL`은 `ENV_SCRUB=1`에 의해 서브에이전트에 전달 안 됨
- Opus급 에이전트 frontmatter: `effort: max` 필수
- Sonnet급 에이전트: frontmatter effort 기본값 사용 (별도 명시 불필요)

### Codex 외부 리뷰어

**역할**: 모든 코드 수정의 교차 리뷰어. Claude와 다른 계열 모델이라 진짜 교차검증.
**호출**: `codex exec -m gpt-5.6-sol "프롬프트"` (Bash 직접 호출, stdout 수신)
> 모델/추론 기본값은 `~/.codex/config.toml` (현재 `gpt-5.6-sol`, reasoning `high`). `-m` 생략 시 이 기본값 적용. 버전 변경 시 config와 함께 갱신할 것.

**특화 영역** (우선 배정): 프론트엔드/UI 리뷰, CLI/스크립트 리뷰, 고난도 버그 교차 디버깅, 아키텍처 second opinion
**교차 디버깅**: Claude 실패 시 Codex 동시 투입 → 다른 접근법 합산. 양쪽 실패 → 사용자 에스컬레이션.
**Fail-graceful**: Codex 미설치/타임아웃 시 Claude 단독 모드

### 메인 = 플레잉 코치 (코딩 + 종합)

메인은 가장 컨텍스트가 넓으므로 **직접 코딩 + 종합 판단 모두 수행**:
- **메인**: 모든 도구 사용 가능 — 코드 구현, 리뷰, 교차검증, 팀 관리 겸임
- **워커(teammate)**: 실행 도구 위주
- 메인이 직접 구현하는 것이 퀄리티 높은 경우 워커에 위임하지 않음
- 병렬화가 필요한 독립 스트림만 워커에 분배

### 재귀 방지 워터마크 (Anthropic 패턴)

에이전트가 다른 에이전트를 스폰할 때:
- 프롬프트에 `[SPAWNED_BY:{parent_name}]` 워터마크 삽입
- 이 워터마크가 감지된 에이전트는 **추가 에이전트 스폰 금지** (재귀 방지)
- 원칙: 메인만 에이전트를 스폰 (flat 구조 유지)
- 예외: spec-compliance-reviewer(p3-qa-lead)는 QA 서브에이전트 4종을 내부 호출 가능 (team-build Phase 3)

---

## 프롬프트 필수 요건
- **50-100단어 핵심 프롬프트** — CLAUDE.md + rules/ 자동 로딩되므로 중복 기술 금지
- **포함 필수**: 파일 소유권 + IOV 3요소 + 완료 보고 형식
- **포함 금지**: 프로젝트 전반 설명, CLAUDE.md에 이미 있는 규칙, 코딩 컨벤션 (자동 로딩)

### IOV 3요소 필수 포함 (CLAUDE.md "목적 중심 완료 프레임워크" 연동)
에이전트 프롬프트에 반드시 포함:
```
## 목적 (WHY)
[이 작업을 하는 근본 이유 — 사용자 의도]

## 기대 결과 (OUTCOME)
GIVEN: [사전 조건] / WHEN: [작업 완료 후] / THEN: [기대되는 관찰 가능한 결과]

## 검증 방법 (VERIFY)
[에이전트가 직접 확인할 수 있는 검증 단계]
```

### 완료 보고 필수 포함
기존 BLUF + 상태코드 + 확신도에 추가:
- **OUTCOME**: `MET` / `PARTIAL` / `NOT_MET`
- **VERIFY_EVIDENCE**: 검증 수행 결과 (실행 출력, API 응답, 스크린샷 등)
- `NOT_MET` 시 완료 보고 금지 — 미달성 사유 + 추가 필요 작업 명시

---

## 핵심 원칙: 조사 우선 → 의도 기반 분류

### 판정 흐름

```
[사용자 요청]
    │
    ├─ Trivial? → Yes → 메인 직접 처리 (조사·팀 없음)
    │
    ├─ 사용자가 "팀/사업부/오케스트라" 명시? → Yes → 무조건 오케스트라
    │
    └─ 그 외 → Phase 0 조사 → 결과에 따라:
        ├─ 독립 스트림 1개, 5파일 이하 → 메인 직접 또는 teammate 1명
        ├─ 독립 스트림 2개 → teammate 2명 (팀 내, 교차검증)
        └─ 독립 스트림 3+개 → 오케스트라 (/team-build)
```

**충돌 시 우선순위:** 사용자 명시 > scout 제안 > 메인 판단 (CLAUDE.md "사용자 권한" 원칙)

---

## 작업 분류 기준 (3단계)

### Tier 1: Trivial — 메인 직접 처리

아래 조건을 **모두** 충족하는 경우만 Trivial:
- 변경 대상: **1-2파일** / 변경 규모: 파일당 **1-5줄**
- **새로운 비즈니스 로직 없음** (1-2줄 안전 체크/검증 추가는 Trivial로 간주)
- API 변경 없음, 데이터 구조 변경 없음

**Trivial이 아닌 것 (금지 목록):**
- 조건문/루프/함수 추가
- 타입 정의 변경이 여러 소비자에 전파
- API 엔드포인트 수정
- Firestore 컬렉션 구조/쿼리 변경
- 3개 이상 파일에 걸치는 수정

리뷰 체인: `test-runner` → `parallel-reviewer` (축소 버전, 백그라운드)

### Tier 2: Standard — 조사 후 결정

Trivial이 아닌 모든 작업의 기본 단계.

**Phase 0 조사 (필수):**
1. Explore 에이전트 스폰 (`model="sonnet"`)
2. 조사 보고: 파일 목록 + 의존성 + 독립 스트림 식별 + 판정 제안
3. 메인이 검토 → 방식 확정 → 1줄 브리핑 후 진행

**"독립 스트림"의 정의:**
- 파일 소유권이 겹치지 않는 작업 단위
- 공유 파일(타입, 유틸)은 메인 에이전트 소유 → 스트림에 포함하지 않음

### Tier 3: Orchestra — 오케스트라 (팀 모드)

**트리거 (OR 조건):**
1. 사용자가 "팀", "사업부", "team-build", "오케스트라" 명시
2. 조사 결과 독립 스트림 3+개
3. Feature 스펙이 필요한 신규 기능

**필수 요소:** 팀 스폰(name 지정 teammate) + SendMessage 교차검증. 예외 없음.

---

## Agent() 직접 호출 vs teammate 스폰 판정

### subagent(Agent() 직접) — 비용 1.5-2x
**조건: 파일 소유권 겹침 없음 + peer 통신 불필요**

| 허용 | 예시 |
|------|------|
| 독립 파일 생성/수정 | 서로 다른 파일을 각자 작성 (run_in_background=true) |
| Trivial 축소 리뷰 | test-runner, parallel-reviewer |
| doc-syncer 단독 | 문서 동기화 |
| Phase 0 scout | Explore 에이전트 |
| 리뷰어 트리거 체인 | perf/parallel/security (백그라운드) |

### teammate(name 지정 스폰) — 비용 3-4x
**조건: 파일 소유권 겹침 OR 실시간 peer 통신 필요 OR 사용자 명시**

| 필요 | 예시 |
|------|------|
| 공유 파일 동시 수정 | 백엔드→API→UI 의존 체인 |
| 실시간 협업 | 설계→구현 피드백 루프 |
| 사용자 "팀/오케스트라" 명시 | 사용자 지시 우선 |

**핵심**: 독립 파일 생성은 subagent로 충분. teammate는 통신이 필요할 때만.

---

## 병렬 디스패치 조건

병렬 전 3가지 확인: **독립 파일 세트, 공유 상태 없음, 실패 격리** → 모두 Yes면 병렬.
이 조건은 Phase 0 조사에서 확인. 조사 없이 병렬 판단 금지.

---

## 교차검증 규칙

- **모든 teammate 간 소통 = SendMessage** (파일 기반 인수인계 금지)
- fire-and-forget(개별 Agent() → 결과만 수신) **금지** — 구현 작업은 팀 내 실행
- teammate 2명 이상이면 반드시 상호 결과 교환
- **자기 검증 금지 원칙:**
  - teammate가 한 작업 → 메인이 Phase 게이트에서 직접 검증
  - **메인이 직접 한 작업 → 별도 에이전트 스폰하여 교차검증 필수** (자기 코드 자기 리뷰 금지)

### 워커 간 결과 공유 프로토콜 (메인 중계 방식)

**원칙**: 워커는 메인에만 보고 → 메인이 의존 워커에 중계 → 워커는 보고 후 즉시 셧다운.
(워커 간 직접 SendMessage는 양쪽 턴 소비 → 메인이 중계하면 한쪽만 소비)

**메인의 의무:**
1. 워커 A 완료 보고 수신 → A 즉시 셧다운
2. 의존 관계 있는 워커 B가 아직 작업 중이면 → `[TAG] from A: {핵심 1-3줄}` SendMessage
3. B도 완료 → 즉시 셧다운

**subagent 방식일 때**: 교차 공유 불필요 — 각 subagent 결과가 메인에 요약 반환되고, 메인이 통합 검증.

**교환 태그:**

| 조합 | 태그 |
|------|------|
| api-worker → ui-worker | [API_CONTRACT] |
| 리뷰어 간 | [REVIEW_FINDING] |

---

## 리뷰어 트리거 체인 (코드 수정 시)

### 체인 순서
1. `test-runner` → 2. `spec-compliance-reviewer` (Feature) → 3. `perf-reviewer` + `parallel-reviewer` + `security-auditor` + **`codex:REVIEW`** 동시 → 4. `doc-syncer`
- `codex:REVIEW`는 perf/parallel/security와 **동시 실행** (병렬, Codex 활성 시만)
- Codex 코드는 Claude `parallel-reviewer`가 리뷰 (역방향)

### 배치 실행 원칙
- **같은 트리거 내 순차 수정**: 전체 수정 완료 후 **1회만** 실행
  - 예: 리뷰 결과 Critical→High→Medium 순차 처리 = 1트리거 → 마지막 1회
- **별개 트리거 수정**: 각 트리거 완료 시마다 실행

### team-build Phase 3 중복 방지
`/team-build` Phase 3(QA팀)이 실행되면 CLAUDE.md "코드 수정 완료" 자동 트리거 체인을 **생략**한다.
Phase 3 QA팀이 동일 역할(test-runner, parallel-reviewer, perf-reviewer, security-auditor)을 수행하므로 중복 방지.
doc-syncer만 Phase 4에서 별도 실행.

### Phase 3 Codex 교차 리뷰 (자동)
Phase 3에서 p3-qa-lead와 **병렬로** 메인이 Codex 교차 리뷰 실행:
```
codex exec -m gpt-5.6-sol "변경 파일: {파일목록}. diff 요약: {요약}. 보안/품질/성능 관점 리뷰."
```
결과를 [TEAM_JUDGMENT]에 합산:
```
[TEAM_JUDGMENT] 필수 필드:
  claude_result: PASS/FAIL (서브에이전트 4종 종합)
  codex_result: PASS/FAIL/SKIPPED (Codex 교차 리뷰)
  codex_findings: {건수}
  codex_conflicts: {Claude와 상충하는 판단 — 있으면 상세}
```
Codex 미설치/타임아웃 시 `codex_result: SKIPPED`.

---

## 에이전트 보고 표준
- **BLUF 필수** + 상태코드(DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT) + 확신도 0-100% + 증거
- 상세 포맷: `~/.claude/reporting-framework.md` 참조

## TodoWrite 필수 포함 항목
작업 시작 시 마지막 항목: `test-runner 검증`, `parallel-reviewer + perf-reviewer + security-auditor`, `doc-syncer`
(team-build Phase 3 사용 시 위 항목 대신 "Phase 3 QA 완료 대기"로 대체)

## 전수 처리 (EPV 패턴)
- "전부/모두/빠짐없이" 감지 시 자동 적용. 상세: `/full-sweep`
