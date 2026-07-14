---
name: ui-ux-expert
description: UI/UX 평가 및 모바일 반응형 검증. 컴포넌트 코드를 읽고 사용성, 접근성, 일관성, 모바일 텍스트 오버플로, 터치 타겟, 레이아웃 깨짐을 검출. 컴포넌트 작성, 모달, 테이블, 폼, 차트, 반응형, 버튼, KPI 카드, 필터 영역, 텍스트 줄바꿈, 숫자 오버플로 관련 작업 시 자동 참조. Playwright 375px 검증 절차 포함.
user-invocable: true
argument-hint: "[파일경로 또는 페이지경로]"
---

# UI/UX Expert — 권위있는 기준 기반 평가

아래 레퍼런스를 기반으로 평가합니다.

---

## 1. UX 사용성 원칙 (Nielsen Norman + 인지과학)
!`cat "${CLAUDE_SKILL_DIR}/references/ux-heuristics.md" 2>/dev/null`

---

## 2. 접근성 기준 (WCAG 2.2 AA)
!`cat "${CLAUDE_SKILL_DIR}/references/accessibility.md" 2>/dev/null`

---

## 3. 엔터프라이즈 패턴 (Carbon + Ant Design)
!`cat "${CLAUDE_SKILL_DIR}/references/enterprise-patterns.md" 2>/dev/null`

---

## 4. Tailwind + shadcn/ui 모범사례
!`cat "${CLAUDE_SKILL_DIR}/references/tailwind-patterns.md" 2>/dev/null`

---

## 5. 프로젝트 컨벤션 + 빌드 패턴
!`cat "${CLAUDE_SKILL_DIR}/references/project-conventions.md" 2>/dev/null`

---

## 6. 레이아웃 패턴 (모달/그리드/테이블 크기 기준)
!`cat "${CLAUDE_SKILL_DIR}/references/layout-patterns.md" 2>/dev/null`

---

## 7. 안티패턴 (금지 패턴 목록)
!`cat "${CLAUDE_SKILL_DIR}/references/anti-patterns.md" 2>/dev/null`

---

## 8. 시각적 계층 (정보 계층/무게 배분/그루핑)
!`cat "${CLAUDE_SKILL_DIR}/references/visual-hierarchy.md" 2>/dev/null`

---

## 9. 사전 전달 체크리스트 (구현 완료 전 48항목 검증)
!`cat "${CLAUDE_SKILL_DIR}/references/pre-delivery-checklist.md" 2>/dev/null`

---

## 10. 모바일 반응형 설계 (브레이크포인트/전환 규칙/터치 인터랙션)
!`cat "${CLAUDE_SKILL_DIR}/references/responsive-design.md" 2>/dev/null`

---

## 11. 신뢰성 있는 정보 출처 (최신 데이터 참조용)
!`cat "${CLAUDE_SKILL_DIR}/references/trusted-sources.md" 2>/dev/null`

---

## 12. Playwright 모바일 검증 절차
!`cat "${CLAUDE_SKILL_DIR}/scripts/verify-mobile.md" 2>/dev/null`

---

## 평가 대상
$ARGUMENTS
