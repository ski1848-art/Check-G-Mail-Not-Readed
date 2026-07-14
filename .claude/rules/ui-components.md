---
paths:
  - "admin-web/components/**/*.tsx"
  - "admin-web/app/**/page.tsx"
---

# UI 컴포넌트 규칙 (admin-web)

## 핵심 규칙 요약
- 모달: ESC 닫기 + 외부 클릭 닫기 + body scroll lock + z-50
- 테이블: 페이지 레벨 스크롤 (내부 스크롤/고정 높이 금지), `<table>` 시맨틱 마크업
- 버튼: Primary=`bg-blue-600`, Secondary=`border-gray-300`, Danger=`bg-red-600`
- 브랜드 색상: blue 계열 (실제 admin-web 기준 — `.cursorrules-ui`와 일치)
- 금지: `ring-2 ring-*-300` 글로우, gradient 버튼, `shadow-xl` 이상
- `<div onClick>` 금지 → `<button>` 사용

## shadcn/ui 컴포넌트 (신규 UI 작업 시 우선 사용)
설치된 경우 `admin-web/components/ui/` 확인 후 재사용
- **Dialog** — 모달 (ESC, 외부 클릭, 포커스 트랩 내장)
- **Table** — 테이블
- **Select** — 셀렉트/드롭다운

**규칙: 신규 UI 작업 시 직접 구현 전에 기존 컴포넌트 먼저 확인 → 있으면 그거 쓰기.**

## UI 검증 의무 (코드만으로 완료 선언 금지)
UI 컴포넌트 신규/대규모 수정 시 (개발 서버는 포트 2222):
1. **Playwright 스냅샷** — MCP playwright(`browser_navigate` → `http://localhost:2222/...` → `browser_snapshot`/`browser_take_screenshot`)로 실제 화면 확인 (별도 e2e 테스트 스위트 없음)
2. **모바일 확인** — `browser_resize(375, 812)` 후 재캡처로 반응형 깨짐 확인
3. **인터랙션 테스트** — 모달 ESC, 접기/펼치기, 폼 제출 등 상태 전환 검증
4. tsc 통과만으로 UI 완료 선언 **금지** — 브라우저 실행 결과로 판정
