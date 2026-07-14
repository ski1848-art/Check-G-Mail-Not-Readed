# Tailwind CSS & shadcn/ui Patterns Reference

> shadcn/ui 컴포넌트 합성 패턴 + Tailwind CSS 엔터프라이즈 모범사례
> ERP 대시보드/관리 시스템 최적화 가이드

---

## 1. shadcn/ui 컴포넌트 패턴

### 1.1 Compound Components 패턴

핵심: Root 컴포넌트가 Context로 상태 관리, 자식이 Context를 소비하여 자동 반응.

```tsx
// 사용 예
<Table.Root data={data} columns={columns}>
  <Table.Toolbar />
  <Table.Header />
  <Table.Body />
  <Table.Pagination />
</Table.Root>
```

**성능:** 자주 변경되는 상태(sorting, selected)와 정적 설정(columns, density)의 Context를 분리.

### 1.2 cn() 유틸리티

`clsx` + `tailwind-merge` 조합으로 클래스 충돌 해결:

```tsx
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

// Variant 패턴
const buttonVariants = {
  variant: {
    default: 'bg-blue-600 text-white hover:bg-blue-700',
    destructive: 'bg-red-600 text-white hover:bg-red-700',
    outline: 'border border-gray-300 bg-white hover:bg-gray-50',
    ghost: 'hover:bg-gray-100',
    link: 'text-blue-600 underline-offset-4 hover:underline',
  },
  size: {
    sm: 'h-8 px-3 text-xs',
    default: 'h-9 px-4 text-sm',
    lg: 'h-10 px-6 text-base',
    icon: 'h-9 w-9',
  },
};
```

**안티패턴:** `className={\`text-${color}-600\`}` — 동적 클래스 문자열 금지 (Tailwind가 감지 못함). 대신 완전한 클래스명 매핑 사용.

### 1.3 주요 컴포넌트 패턴

#### Button
- 그룹: `<div class="flex items-center gap-3">취소(outline) + 저장(default)</div>`
- 로딩: `<Loader2 class="mr-2 h-4 w-4 animate-spin" /> 저장 중...`
- 아이콘: `variant="ghost" size="icon"` + `aria-label` 필수

#### Dialog (모달)
- 크기: `sm:max-w-[480px]`
- 구조: DialogHeader → 폼 필드 (`space-y-4 py-4`) → DialogFooter
- Footer 순서: 취소(outline) → 저장(default) (우측이 Primary)
- 금지: 모달 안에 모달 중첩, 스크롤이 필요한 긴 모달

#### Table
- 금액/숫자: `text-right font-mono tabular-nums`
- 날짜: `text-sm text-gray-500`
- 긴 텍스트는 truncate 처리

#### Form (react-hook-form + zod)
- 숫자 입력: `type="text" inputMode="numeric"` + `formatInputValue` / `parseFormattedNumber`

#### Select / Tabs / Toast
- Select: `SelectTrigger` → `SelectContent` → `SelectGroup` + `SelectItem`
- Tabs: `border-b-2 data-[state=active]:border-blue-600`
- Toast: `toast.success()` / `toast.error()` (sonner), 되돌리기 action 포함 가능

### 1.4 접근성 (Radix UI 기반)

shadcn/ui는 Radix UI 기반으로 키보드/ARIA 자동 처리:
- Dialog: Escape 닫기, 포커스 트랩, aria-labelledby
- Select: 화살표 키 탐색, Enter 선택
- Tabs: 좌우 화살표 탐색, role="tablist"

추가 필수:
- 아이콘 버튼: `aria-label` + `<span class="sr-only">`
- 로딩: `role="status" aria-live="polite"`

---

## 2. Tailwind CSS 모범사례

### 2.1 레이아웃: flex vs grid

| 상황 | 선택 | 클래스 |
|------|------|--------|
| 1차원 배치 | Flex | `flex items-center gap-3` |
| 2차원 그리드 | Grid | `grid grid-cols-3 gap-4` |
| 수직 스택 | Flex | `flex flex-col gap-4` |
| 폼 2열 | Grid | `grid grid-cols-1 md:grid-cols-2 gap-4` |
| 좌-우 정렬 | Flex | `flex items-center justify-between` |
| 카드 그리드 | Grid | `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6` |
| 사이드바+콘텐츠 | Grid | `grid grid-cols-[240px_1fr]` |

### 2.2 간격 시스템

**gap 권장**, space는 수직 스택에서만 제한적 사용.

**안티패턴:** 자식에 개별 margin (`mr-3`) → 부모에 `gap-3` 사용.

| 토큰 | 값 | 용도 |
|------|-----|------|
| `gap-1` | 4px | 아이콘-텍스트 |
| `gap-2` | 8px | 인라인 필터 |
| `gap-3` | 12px | 버튼 그룹 |
| `gap-4` | 16px | 폼 필드, 카드 내부 |
| `gap-6` | 24px | 카드 그리드 |
| `gap-8` | 32px | 페이지 섹션 |

### 2.3 반응형 (Mobile-First)

기본 = 모바일, `md:` (768px)이 주요 breakpoint.

| Breakpoint | 용도 |
|-----------|------|
| 기본 | 모바일 — 사이드바 숨김, 단일 컬럼 |
| `md:` | 태블릿 — 사이드바 표시, 2컬럼 폼 |
| `lg:` | 데스크탑 — 풀 테이블, 3컬럼 |
| `xl:` | 와이드 — 여유 여백, 넓은 패널 |

```html
<!-- 반응형 그리드 -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
<!-- 반응형 정렬 -->
<div class="flex flex-col md:flex-row md:items-center gap-4">
<!-- 반응형 텍스트 -->
<span class="hidden lg:inline">거래일자</span>
<span class="lg:hidden">일자</span>
```

### 2.4 시맨틱 색상

**ERP 상태 색상 매핑:**

| 상태 | 배경 | 텍스트 | 용도 |
|------|------|-------|------|
| 성공/승인 | `bg-green-50` | `text-green-700` | 승인 완료, 입금 |
| 경고/대기 | `bg-yellow-50` | `text-yellow-700` | 승인 대기 |
| 에러/반려 | `bg-red-50` | `text-red-700` | 반려, 출금 |
| 정보 | `bg-blue-50` | `text-blue-700` | 매칭 완료 |
| 비활성 | `bg-gray-50` | `text-gray-500` | 취소 |

**상태 배지:** `inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border`

**안티패턴:** `bg-[#1a73e8]` 하드코딩 금지 → `bg-blue-600` 또는 `bg-primary` 사용.

### 2.5 성능 최적화

- `@apply` 사용 제한 — 글로벌 리셋, 서드파티 오버라이드에서만 허용. 컴포넌트 스타일은 React 컴포넌트로 추출.
- 중복/상충 방지: `p-4 px-6` → `px-6 py-4`, `flex flex-row` → `flex`
- `tailwind.config.js` content 경로 정확히 지정 (node_modules 포함 금지)
- 동적 클래스는 `safelist`로 등록

---

## 3. ERP 대시보드 실전 패턴

### 3.1 통계 카드 (KPI)

```html
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
  <div class="bg-white rounded-lg border p-4">
    <div class="flex items-center justify-between">
      <span class="text-sm text-gray-500">총 매출</span>
      <TrendingUp class="w-4 h-4 text-green-500" />
    </div>
    <p class="text-2xl font-bold mt-2">₩12,345,678</p>
    <p class="text-xs text-green-600 mt-1">+12.5% 전월 대비</p>
  </div>
</div>
```

### 3.2 액션 드롭다운 (행별)

`MoreHorizontal` 아이콘 → `DropdownMenuContent align="end"` → 상세/수정 + 구분선 + 삭제(`text-red-600`)

### 3.3 사이드 패널 (Drawer)

- 오버레이: `fixed inset-0 bg-black/20 z-40`
- 패널: `fixed right-0 top-0 h-full w-[480px] bg-white border-l shadow-xl z-50`
- sticky 헤더/푸터, 스크롤 가능 콘텐츠

### 3.4 검색 + 필터 통합

`bg-white rounded-lg border` 래퍼 안에:
1. 필터 영역 `p-4 border-b`: 기간 + 상태 Select + 검색 Input + 조회/초기화 버튼
2. 테이블 본체
3. 페이지네이션 `p-4 border-t`

---

## 4. 패턴 선택 가이드

| 상황 | 패턴 | 핵심 |
|------|------|------|
| 목록 + 필터 + 페이지네이션 | Pro Table | `bg-white rounded-lg border` 래퍼 |
| 생성/수정 | Dialog or Page | `sm:max-w-[480px]` 모달 |
| 상세 보기 | Side Panel | `fixed right-0 w-[480px]` |
| 상태 표시 | Badge | `text-xs rounded-full border` |
| 일괄 작업 | Batch Action Bar | `bg-blue-50 border-b` |
| 행별 액션 | Dropdown Menu | `MoreHorizontal` 트리거 |
| 뷰 전환 | Tabs | `border-b-2` 활성 표시 |
| 알림 | Toast (sonner) | `toast.success/error()` |
| 숫자 입력 | Formatted Input | `type="text" inputMode="numeric"` |

### 클래스 조합 치트시트

```
페이지 래퍼:     min-h-screen bg-gray-50
카드 컨테이너:   bg-white rounded-lg border
페이지 제목:     text-xl font-bold text-gray-900
보조 텍스트:     text-sm text-gray-500
필터 영역:       p-4 border-b
테이블 행 호버:  hover:bg-gray-50 transition-colors
금액 표시:       text-right font-mono tabular-nums
상태 배지:       inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border
포커스 링:       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500
비활성 상태:     disabled:pointer-events-none disabled:opacity-50
트랜지션:        transition-colors duration-150
```
