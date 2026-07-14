---
name: harness-evolve
description: 하네스 평가 + 고도화 통합 — 현재 설정 7축 평가 후, 공식 업데이트/커뮤니티 트렌드 기반 업그레이드 제안. "하네스 고도화", "하네스평가", "환경평가", "설정점검"으로 실행.
user-invocable: true
disable-model-invocation: false
---

# 하네스 평가 + 고도화

현재 하네스를 평가하고, 외부 최신 정보와 비교하여 업그레이드를 제안한다.
사용자 승인 시 바로 적용.

## 트리거
- `/harness-evolve`, "하네스 고도화", "하네스평가", "환경평가", "설정점검", "하네스 업데이트", "MECE 검열", "중복 검사", "계층 검토"

## 평가 기준 로드
!`cat "${CLAUDE_SKILL_DIR}/references/best-practices.md" 2>/dev/null | head -400`

## 프로세스

### Phase 1: 현재 하네스 평가

#### Step 1: 파일 수집
아래 파일/폴더를 모두 읽는다:
1. `CLAUDE.md`
2. `.claude/settings.json` + `.claude/settings.local.json`
3. `.claude/agents/*.md`
4. `.claude/skills/*/SKILL.md`
5. `.claude/rules/*.md`
6. `.claudeignore`
7. 프로젝트 메모리 MEMORY.md
8. `.claude/plans/` (존재 시)
9. `~/.config/espanso/match/claude.yml` (Espanso 스니펫 — 프로토콜 문구 최신화 확인)

#### Step 2: 정량 측정 → harness-audit 위임

`harness-audit` 에이전트를 스폰하여 정량 메트릭 + 7축 점수 + 드리프트 감지를 일괄 수행.
결과를 받아 Step 4 리포트에 통합한다. (중복 측정 방지)

#### Step 3: 10축 평가 기준 (harness-audit이 참조)

| 축 | 비중 | 핵심 |
|---|---|---|
| 간결성 & Progressive Disclosure | 5% | CLAUDE.md/MEMORY.md 크기, rules/ 분리율 |
| 보안 게이트 | 15% | exit 2 훅, DDL 차단, MCP RO/RW 분리 |
| 에이전트 설계 | 15% | **프롬프트 5요소 평균**, 모델 배치, 역할 MECE |
| 팀 아키텍처 | 15% | Phase 구조, QA팀, tmux 오케스트라 |
| QA & 평가 품질 | 10% | Playwright 실제 클릭, FAIL 복구 루프 |
| 컨텍스트 엔지니어링 | 10% | 핸드오프, SSOT, path-scoped 로딩 |
| 워크플로우 자동화 | 10% | 트리거 체인, 의도 기반 트리거 MECE |
| Load-Bearing & 진화 | 5% | 가정 테이블, harness-evolve 자체 품질 |
| 가시성 & 관찰성 | 10% | 정보 계층, Phase 게이트, Agent Monitor |
| 도메인 적합성 | 5% | 도메인 MCP, 특화 에이전트, 도메인 스킬 |

등급: A(92+), A-(88-91), B+(82-87), B(75-81), C(65-74), D(<65)

#### Step 3.5: 에이전트 프롬프트 품질 감사 (축 3 세부)

harness-audit이 각 에이전트 프롬프트를 **5요소 25점 만점**으로 채점:

| 요소 | 5점 기준 |
|------|---------|
| 체크리스트 | `- [ ]` 10개+ 체크박스, 3개+ 카테고리 |
| 캘리브레이션 | FAIL/PASS/WARN 코드 스니펫 비교 3개+ |
| 도구 활용 | 구체적 명령어 + 의사결정 트리 |
| 출력 형식 | BLUF + 상태코드 + 판정 테이블 + 리스크 |
| 팀 프로토콜 | 팀 모드 감지 + 합의 교환 + 에스컬레이션 |

**목표**: 전체 에이전트 평균 20점(A등급) 이상, D등급(0-9) 0개.
프롬프트 품질 D등급 에이전트 발견 시 → Phase 2 제안에 "프롬프트 개선" 자동 포함.

#### Step 4: 평가 리포트 출력
```markdown
# 하네스 평가 리포트
## 종합 점수: {점수}/100 ({등급})
| 축 | 비중 | 점수 | 등급 | 핵심 이슈 |
...
## 감점 사유 상세
...
```

---

### Phase 2: 외부 변화 수집 + 고도화 제안

#### Step 5: 외부 소스 수집 (병렬)

> `/research` 스킬의 검색 도구 및 교차 검증 원칙을 적용한다:
> DuckDuckGo MCP (search + fetch_content) + WebSearch 병행, 복수 소스 교차 검증, 페이지 본문 추출 활용.

**5-1. 공식 소스 (병렬 WebFetch + DuckDuckGo fetch_content)**

| 소스 | URL | 수집 대상 |
|------|-----|----------|
| Claude Code 공식 | `code.claude.com/docs/en/changelog` | 새 기능, 설정 변경, 마이그레이션 |
| Claude Code 공식 | `code.claude.com/docs/en/best-practices` | 권장사항, 안티패턴 |
| Claude Code 공식 | `code.claude.com/docs/en/hooks-guide` | hook 패턴, 이벤트 |
| Anthropic Research | `anthropic.com/research` | 에이전트 설계, 프롬프트 엔지니어링 |
| OpenAI Codex/Agents | `platform.openai.com/docs` | 에이전트 패턴, tool use, 오케스트레이션 |
| Google Gemini CLI | `ai.google.dev` | CLI 에이전트 설정, 컨텍스트 관리 |
| xAI Grok | `docs.x.ai` | 에이전트 아키텍처, 실시간 정보 통합 |

> 각 소스에서 **에이전트 설정/오케스트레이션/하네스 관련 패턴만** 추출.
> 모델 성능 비교나 가격은 수집 대상이 아님.

**5-2. 커뮤니티 동적 탐색 (1k★ 이상만)**

매번 고정 레포가 아닌, **최신 인기 레포를 실시간 탐색**한다:

1. **복수 검색 쿼리 실행** (DuckDuckGo MCP search + WebSearch 병렬):
   - `"Claude Code" agent harness framework {현재년도} github`
   - `"Claude Code" OR "Codex" OR "Gemini CLI" agent skills hooks best practices site:github.com`
   - `AI coding agent orchestration configuration {현재년도} stars`
   - `agentic coding workflow automation best practices {현재년도}`
2. **Stars 상위 5~10개 레포 식별** — GitHub API(`curl -s api.github.com/repos/{owner}/{repo}`)로 실제 Stars 확인
3. **각 레포 핵심 파일 읽기** (WebFetch 병렬):
   - README.md / CLAUDE.md (아키텍처 개요)
   - `.claude/` 디렉토리 구조 (에이전트/스킬/훅 패턴)
4. **패턴 추출**: 우리 하네스에 없는 새로운 기법/구조 식별
5. **채택 평가**: `references/best-practices.md` §12.2 기준 (실익 30%, 적합성 25%, 검증도 20%, 도입비용 15%, 중복여부 10%)으로 점수화
6. **4.0점 이상만 제안에 포함** (3.0-3.9은 트레이드오프 설명 후 사용자 판단)

#### Step 6: 차이 분석 + 제안 (최대 3개)

Phase 1 감점 사유 + Phase 2 외부 변화를 종합하여 제안 생성.

각 제안 형식:
```
### 제안 N: {제목}
- **유형**: 외부 패턴 도입 | 프롬프트 품질 개선 | 드리프트 수정 | 구조 개선
- **출처**: {공식 docs URL 또는 프로젝트명 + 별점 또는 "내부 감사"}
- **현재**: {현재 하네스 상태}
- **제안**: {변경 내용}
- **근거**: {1~2줄}
- **영향 파일**: {목록}
- **위험도**: 낮음/중간/높음
```

**프롬프트 품질 개선 제안 자동 트리거**: Step 3.5에서 D등급(0-9) 에이전트가 발견되면 해당 에이전트의 5요소 부족 사항을 제안에 자동 포함. 개선 시 perf-reviewer(25/25)를 골든 템플릿으로 참조.

#### Step 7: 사용자 승인 + 적용

AskUserQuestion으로 수락/거부 확인:
- 수락 → 파일 수정
- 거부 → memory에 기록 (재제안 방지)
- 제안 없으면 → "현재 하네스 최신 상태입니다." 한 줄 출력

#### Step 8: 이력 기록

memory에 고도화 이력 기록 (날짜, 적용/거부 내역, 출처)

---

### Phase 2.5: MECE 검열 (계층 구조 중복 제거)

Phase 2 고도화 제안 전/후에 반드시 실행. 독립 실행도 가능 ("MECE 검열", "중복 검사").

#### Step M1: 계층 파일 전수 수집

아래 파일을 모두 읽어 내용을 수집한다:
1. `CLAUDE.md` (root) + 모든 하위 `**/CLAUDE.md`
2. `.claude/rules/*.md`
3. `.claude/skills/*/references/*.md` (주요 스킬만)
4. `docs/UI-UX 기준.md`, `components/patterns/*.md`
5. `.agent/rules/*.md` (존재 시)
6. 프로젝트 메모리 (`~/.claude/projects/*/memory/MEMORY.md` + 하위 파일)
7. `~/.config/espanso/match/claude.yml` (Espanso 스니펫)

#### Step M2: MECE 위반 탐지

수집된 파일을 교차 비교하여 다음을 탐지:

| 위반 유형 | 설명 | 심각도 |
|----------|------|--------|
| **동일 중복** | 같은 내용이 2곳 이상에 복사됨 | 高 — 한쪽 제거, 링크로 대체 |
| **유사 중복** | 같은 개념을 다른 표현으로 기술 | 中 — 마스터 1곳 지정, 나머지 삭제 |
| **상충** | 서로 모순된 규칙 | 高 — 즉시 해소 |
| **고립** | 참조되지 않는 파일, 역할 불명 | 低 — 계층에 편입 또는 삭제 |
| **누락** | 규칙이 어디에도 없음 (CE 미충족) | 中 — 적절한 계층에 추가 |

#### Step M3: MECE 정리 원칙

1. **단일 진실 원천(SSOT)**: 각 규칙은 정확히 1곳에만 상세 기술
2. **상위 = 개요 + 링크, 하위 = 상세**: root CLAUDE.md는 1줄 요약 + `rules/` 링크, rules/는 상세 구현
3. **계층 역할 분담**:
   - `CLAUDE.md` root: 절대 금지 + 개요 + 에이전트/트리거 체인
   - `.claude/rules/`: 도메인별 구현 규칙 (path 기반 자동 로드)
   - `components/CLAUDE.md`: 빌드 패턴 인덱스 + UI 고유 규칙 (배지, 시각화 프로세스)
   - `docs/UI-UX 기준.md`: UI 마스터 (이론 + 전체 규칙)
   - `.claude/skills/*/references/`: 스킬 전용 평가 기준
   - `memory/`: 피드백·프로젝트 컨텍스트 (규칙이 아닌 "왜"만)
4. **공용 컴포넌트 규칙은 props로 분리**: 여러 계층에서 참조하는 규칙은 마스터에만 두고 나머지는 링크

#### Step M4: 정리 리포트 + 적용

```markdown
## MECE 검열 결과
| # | 위반 유형 | 파일A | 파일B | 내용 | 조치 |
|---|---------|-------|-------|------|------|
| 1 | 동일 중복 | ... | ... | ... | 파일A에서 삭제, 링크 추가 |
...
```

AskUserQuestion으로 정리 승인 → Edit 도구로 수정.

---

### Phase 3: 자동 감사 + 자기참조적 개선 루프

Phase 1~2 완료 후, 또는 독립 실행 가능.

#### Step 9: harness-audit 에이전트 실행

`harness-audit` 에이전트를 스폰하여 정량 감사를 수행한다.

스폰 프롬프트에 포함할 내용:
- 프로젝트: Hotseller ERP (Next.js 15 + Supabase)
- 스코프: CLAUDE.md, .claude/ 전체, rules/, .claudeignore, MEMORY.md
- 이전 감사 점수가 memory에 있으면 비교 요청
- 출력: 정량 메트릭 + 7축 점수 + 드리프트 감지 + 개선 제안

#### Step 9.5: Load-Bearing Test 점검

하네스의 각 구성 요소가 어떤 "모델 한계 가정"에 기반하는지 재검토한다.
(Anthropic 원칙: "모든 하네스 컴포넌트는 모델 한계 가정을 인코딩. 모델 진화 시 재검토 필수")

점검 대상:
| 컴포넌트 | 가정 | 검증 방법 |
|---------|------|---------|
| exit 2 훅 | Claude가 훅 차단을 우회하지 않음 | 최근 차단 로그 확인 |
| permissionMode: plan | 에이전트가 plan 모드를 지킴 | 최근 에이전트 실행 이력 |
| 2라운드 기획 제한 | 2라운드 내 합의 도달 가능 | 팀빌드 이력에서 초과 비율 |
| Phase 직렬 구조 | 기획→개발→검증 순서 필수 | Opus 4.6에서 병합 가능성 |
| 5명 QA 병렬 | 동시 5명이 충돌 없이 동작 | 최근 팀빌드 QA 결과 |

가정이 더 이상 유효하지 않거나 모델 업데이트로 동작이 달라졌으면:
→ AskUserQuestion으로 사용자에게 알리고, 해당 컴포넌트 재설계 제안

#### Step 10: Before/After 비교

Phase 2에서 적용한 변경이 있으면:
1. 변경 전 점수 (Step 9 또는 memory에서)
2. 변경 후 harness-audit 재실행
3. Before/After 비교표 출력:

```markdown
## Before/After 비교
| 축 | 변경 전 | 변경 후 | 변화 |
|---|---------|---------|------|
| 간결성 | N | N | ±N |
...
| **종합** | **N/100** | **N/100** | **±N** |
```

#### Step 11: 드리프트 자동 수정 제안

harness-audit에서 발견된 드리프트 중 자동 수정 가능한 건에 대해:
1. 수정 대상 파일 + 위반 내용 목록
2. AskUserQuestion으로 일괄 수정 승인 요청
3. 승인 시 Edit 도구로 수정

#### Step 12: 감사 결과 memory 기록

```markdown
# harness-audit 결과 ({날짜})
- 종합: {점수}/100 ({등급})
- 드리프트: {N}건 (High:{N}, Medium:{N}, Low:{N})
- 개선 적용: {N}건 / 거부: {N}건
```

## 규칙
- **자동 적용 금지** — 반드시 사용자 수락 후
- **최대 3개 제안** — 과부하 방지 (Phase 2)
- **거부 재제안 금지** — memory 확인
- **1k★ 미만 무시** — 검증 안 된 패턴 배제
- **고정 레포 목록 금지** — 매 실행 시 최신 검색으로 동적 탐색. 같은 레포만 반복 참조하지 않는다
- **개별 패턴 선별 채택** — 프레임워크 통째 도입 금지, 우리 하네스에 맞는 개별 패턴만 추출
- **채택 평가 필수** — `references/best-practices.md` §12.2 기준 4.0+ 만 제안, 3.0-3.9은 트레이드오프 설명
- **공식 > 커뮤니티** — 충돌 시 공식 우선
- **Phase 3 독립 실행 가능** — "하네스 감사", "드리프트 체크"로 Phase 3만 실행
- **드리프트 수정도 승인 필수** — 자동 수정 금지
- **Espanso 스니펫 최신화** — CLAUDE.md의 프로토콜/워크플로우가 변경되면 `~/.config/espanso/match/claude.yml`의 스니펫 문구도 동기화 제안. 현재 스니펫: `!ㄱㅅ`/`!rt`(브리핑 프로토콜), `!ㄱㄱ`/`!rr`(개발 프로토콜)
