---
name: playwright-verify
description: UI 수정 후 Playwright 자동 검증 워크플로우. 스크린샷 + 인터랙션 + 반응형 3 breakpoint.
argument-hint: "[페이지 경로] (예: /admin/finance)"
user-invocable: true
---

# Playwright UI 검증

## 사용 시점
- UI 컴포넌트 신규/대규모 수정 완료 후
- tsc 통과만으로 UI 완료 선언하려 할 때 **이 스킬로 검증**

## 실행 절차

### 1. 서버 실행 확인
```bash
lsof -ti:2222 || echo "서버 미실행 — npm run dev 필요"
```

### 2. 3 breakpoint 스크린샷
```bash
# MCP playwright 사용
mcp__playwright__browser_navigate: { url: "http://localhost:2222$ARGUMENTS" }
mcp__playwright__browser_take_screenshot: { type: "png", filename: "desktop.png" }

# 모바일
mcp__playwright__browser_resize: { width: 375, height: 812 }
mcp__playwright__browser_take_screenshot: { type: "png", filename: "mobile.png" }

# 태블릿
mcp__playwright__browser_resize: { width: 768, height: 1024 }
mcp__playwright__browser_take_screenshot: { type: "png", filename: "tablet.png" }
```

### 3. 인터랙션 검증 (해당 시)
- 모달: 열기 → ESC 닫기 → 외부 클릭 닫기
- 아코디언: 클릭 열기 → 다시 클릭 닫기
- 폼: 입력 → 제출 → 에러 표시
- 셀렉트: 클릭 열기 → 옵션 선택

### 4. 접근성 스냅샷
```
mcp__playwright__browser_snapshot 으로 DOM 구조 확인
→ role="dialog", role="button", aria-label 존재 여부
```

### 5. 판정
- 3 breakpoint 모두 레이아웃 정상 → PASS
- 인터랙션 정상 동작 → PASS
- 하나라도 깨짐 → FAIL + 수정 후 재검증
