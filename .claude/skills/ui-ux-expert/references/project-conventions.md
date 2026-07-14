# 프로젝트 컨벤션 (평가 기준)

> 상세 규칙은 마스터 문서를 직접 참조할 것.

## 참조 문서
- **컴포넌트 규칙**: `.claude/rules/ui-components.md` — 모달(ESC/외부클릭/scroll lock), 테이블(페이지 레벨 스크롤), 버튼 색상, shadcn/ui 재사용 규칙
- **디자인 시스템 마스터**: `.cursorrules-ui` — 색상 팔레트, 타이포그래피, 간격, 아이콘, 레이아웃 패턴, 반응형, 한국어 라벨 규칙 전체
- **재사용 컴포넌트**: `admin-web/components/ui/` — 신규 UI 작업 전 먼저 확인 후 있으면 재사용 (예: `slider.tsx`, `toast.tsx`)

## 캘리브레이션 (프로젝트 고유 조정)
- **ARIA**: 낮은 우선순위 (내부 관리자 도구, 외부 고객 대면 아님) — `sr-only`, `aria-live`, `role="alert"` 등 생략 가능. 시맨틱 HTML + 키보드 접근성에 집중.
- **모바일 반응형**: md(768px) 미만에서 카드뷰/바텀시트 적극 활용. 테이블보다 카드뷰가 적합하면 카드뷰 우선. 상세 → `responsive-design.md`
- **색상**: 브랜드 Primary는 `blue-600` (`.cursorrules-ui` §3 기준, `admin-web/app/globals.css`의 `.btn-primary`도 동일). 신규 컴포넌트는 blue 계열로 통일
- **alert/confirm**: 교체 필수 → 커스텀 다이얼로그 사용
- **Skip navigation**: 내부 관리자 도구 특성상 불필요

## 평가 적용 범위
1인 개인 프로젝트로 별도 담당 분리 없음 — admin-web 전체 페이지가 평가 대상:
- `/` — 대시보드 (`admin-web/app/page.tsx`)
- `/events` — 이메일 이벤트 목록 (`admin-web/app/events/page.tsx`)
- `/users`, `/users/new`, `/users/[slackUserId]` — 라우팅 대상 사용자 목록/추가/상세
- `/settings` — 시스템 설정 (AI 판별 민감도, 도메인/키워드 필터 등)
- `/audit` — 감사 로그
- `/login` — 로그인
- 공통 컴포넌트: `admin-web/app/components/Navigation.tsx`, `admin-web/components/`
