# Trusted Sources — 신뢰성 있는 정보 출처 레지스트리

> 사용자 요청 시 이 목록의 소스에서 최신 데이터를 WebFetch/WebSearch로 가져와 참조.

## Tier 1: 공식 (Official)

| 소스 | URL | 용도 | 갱신 주기 |
|------|-----|------|----------|
| **Vercel Web Interface Guidelines** | https://vercel.com/design/guidelines | 100+ UI/UX 규칙, 접근성, 성능 | 수시 |
| **Vercel Agent Skills (GitHub)** | https://github.com/vercel-labs/agent-skills | 공식 스킬 코드, SKILL.md 패턴 | 수시 |
| **Anthropic Skills (GitHub)** | https://github.com/anthropics/skills | 공식 Claude 스킬, 문서 스킬 | 수시 |
| **Anthropic Claude Code Docs** | https://code.claude.com/docs/en/skills | 스킬/에이전트 작성 가이드 | 수시 |
| **Anthropic Skill Building Guide (PDF)** | https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf | 33페이지 공식 가이드, 5가지 디자인 패턴 | 2026.03 |
| **Google ADK Skill Design Patterns** | https://x.com/GoogleCloudTech/status/2033953579824758855 | 5가지 에이전트 스킬 패턴 (Tool Wrapper, Generator, Reviewer, Inversion) | 2026.03 |
| **Google A2UI (Agent-to-UI)** | https://github.com/google/A2UI | 에이전트 기반 UI 생성 스펙 | 2026 |
| **WCAG 2.2** | https://www.w3.org/TR/WCAG22/ | 접근성 표준 | 안정 |
| **Nielsen Norman Group** | https://www.nngroup.com/ | UX 연구, 사용성 원칙 | 수시 |

## Tier 2: 검증된 커뮤니티 (Verified Community)

| 소스 | URL | 용도 | Stars/신뢰도 |
|------|-----|------|-------------|
| **UI/UX Pro Max Skill** | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 161 규칙 엔진, 99 UX 가이드라인 | 높음 |
| **Interface Design Skill** | https://github.com/Dammyjay93/interface-design | 디자인 일관성 강제 시스템 | 높음 |
| **shadcn/ui** | https://ui.shadcn.com/ | Radix + Tailwind 컴포넌트 패턴 | 70k+ stars |
| **IBM Carbon Design** | https://carbondesignsystem.com/ | 엔터프라이즈 UI 패턴 | 공식 |
| **Ant Design** | https://ant.design/ | 백오피스/관리 시스템 패턴 | 90k+ stars |
| **Material Design 3** | https://m3.material.io/ | 색상/타이포/간격 원칙 | Google 공식 |

## Tier 3: 리서치/블로그 (Research)

| 소스 | URL | 용도 |
|------|-----|------|
| **Firecrawl Best Skills** | https://www.firecrawl.dev/blog/best-claude-code-skills | 스킬 비교/리뷰 |
| **Snyk Top Skills** | https://snyk.io/articles/top-claude-skills-ui-ux-engineers/ | UI/UX 스킬 Top 8 |
| **UX Planet** | https://uxplanet.org/ | 디자인 트렌드, 스킬 활용 |
| **IndieHackers Skills Review** | https://www.indiehackers.com/ | 200개 스킬 실사용 리뷰 |
| **Reddit r/ClaudeAI** | https://reddit.com/r/ClaudeAI | 커뮤니티 피드백, 신규 스킬 |
| **Vadim Blog (UX Team)** | https://vadim.blog/ | 에이전트 팀 UX 작업 사례 |

## 사용 방법

에이전트가 UI/UX 관련 최신 정보가 필요할 때:
1. Tier 1 공식 소스를 우선 WebFetch
2. 부족하면 Tier 2 커뮤니티 소스 WebSearch
3. 트렌드/사례는 Tier 3 리서치 참조

## Google ADK 5가지 에이전트 스킬 디자인 패턴

> 출처: [GoogleCloudTech](https://x.com/GoogleCloudTech/status/2033953579824758855)

### 1. Tool Wrapper
에이전트에게 특정 라이브러리의 컨텍스트를 온디맨드로 제공. 시스템 프롬프트에 API 규칙을 하드코딩하는 대신 스킬로 패키징.

### 2. Generator
일관된 출력을 위한 템플릿 기반 프로세스. `assets/`에 출력 템플릿, `references/`에 스타일 가이드 배치. 에이전트가 템플릿 로드 → 가이드 읽기 → 변수 질문 → 문서 생성.

### 3. Reviewer
**무엇을 검사할지**와 **어떻게 검사할지**를 분리. 체크리스트를 교체하면 완전히 다른 전문 감사가 됨. (Python 스타일 → OWASP 보안 체크리스트)

→ **우리의 pre-delivery-checklist.md가 이 패턴**

### 4. Inversion
사용자 주도 → 에이전트 주도로 뒤집기. 에이전트가 인터뷰어 역할을 하여 요구사항을 체계적으로 수집.

### 5. (암시) Orchestrator
여러 스킬을 조합하여 복잡한 워크플로우를 자동화. 분석→설계→구현→검증 파이프라인.

→ **우리의 ui-designer 4단계 워크플로우가 이 패턴**
