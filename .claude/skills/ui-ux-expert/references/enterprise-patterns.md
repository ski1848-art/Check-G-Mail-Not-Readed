# Enterprise UI Patterns Reference

> IBM Carbon Design System + Ant Design 기반 엔터프라이즈 패턴 정리
> ERP 관리 시스템에 최적화된 적용 가이드

---

## 1. 데이터 테이블 패턴

### 1.1 밀도 옵션 (Density)

| 밀도 | 행 높이 | 패딩 | 용도 |
|------|---------|------|------|
| Compact | 32px (2rem) | 0.5rem | 대량 데이터 스캔 (거래 내역, 로그) |
| Default | 48px (3rem) | 1rem | 일반 CRUD 테이블 |
| Tall | 64px (4rem) | 1rem | 복합 콘텐츠 (아바타+텍스트, 다중 라인) |

**ERP 적용:** 거래 내역/은행 트랜잭션 → Compact, 직원/주문 → Default, 상품 상세 → Tall

```html
<!-- Compact --> <tr class="h-8 text-sm"><td class="px-2 py-1">...</td></tr>
<!-- Default --> <tr class="h-12"><td class="px-4 py-3">...</td></tr>
<!-- Tall -->    <tr class="h-16"><td class="px-4 py-4">...</td></tr>
```

### 1.2 정렬 (Sorting)

- 3-state 순환: 없음 → 오름차순 → 내림차순 → 없음
- 한 번에 하나의 컬럼만 정렬
- 숫자/날짜/금액 컬럼은 기본 정렬 제공
- 정렬 중인 컬럼 헤더 배경: `bg-gray-100`
- 상태 배지, 액션 버튼 컬럼에는 정렬 적용 금지

### 1.3 필터링 (Filtering)

- 필터는 테이블 위에 배치
- 상단 고정 필터: 날짜 범위, 상태, 검색어
- 확장 필터: 부서, 카테고리, 금액 범위
- 적용된 필터를 태그(칩)로 표시, 개별/전체 해제 가능
- 필터 변경 시 즉시 반영 (Apply 버튼 없이)

```html
<!-- 필터 바 -->
<div class="flex flex-wrap items-center gap-3 p-4 bg-gray-50 border-b">
  <input type="date" class="border rounded px-3 py-1.5 text-sm" />
  <select class="border rounded px-3 py-1.5 text-sm">...</select>
  <input type="text" placeholder="검색..." class="flex-1 min-w-[200px] border rounded px-3 py-1.5 text-sm" />
  <button class="text-sm text-gray-500 hover:text-gray-700">초기화</button>
</div>

<!-- 적용된 필터 태그 -->
<span class="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full">
  상태: 승인대기 <button>&times;</button>
</span>
```

### 1.4 페이지네이션

- 테이블 하단 우측 배치
- 페이지당 개수 선택: 10, 20, 50, 100
- 총 건수 표시 필수: "전체 1,234건 중 1-20건"
- 기본 20건, 거래내역은 50건

### 1.5 행 선택 & 일괄 작업

- 체크박스는 첫 번째 컬럼 (Carbon 표준), 너비 32px
- 헤더 체크박스: 현재 페이지 전체 선택/해제
- 선택 행 배경: `bg-blue-50`, 호버: `bg-blue-100`
- 선택 시 상단에 일괄 액션 바: 선택 건수 + 일괄 승인/삭제 버튼

---

## 2. 폼 패턴

### 2.1 레이블 배치

| 배치 | 용도 |
|------|------|
| Top-aligned (기본) | 생성/수정 폼 (세로 스캔 효율) |
| Inline | 검색/필터 영역 (가로 공간 활용) |

- 레이블과 입력 필드 사이 간격: `mb-1`
- 필수 필드: 레이블 옆 빨간 별표 `<span class="text-red-500">*</span>`

### 2.2 유효성 검증 메시지

- 인라인 검증: 필드 아래에 에러 메시지
- 에러 상태: `border-red-500 bg-red-50` + 아이콘 + 메시지
- 성공 상태: `border-green-500` + 확인 메시지
- 폼 제출 시 첫 번째 에러 필드로 스크롤

### 2.3 폼 그룹핑 & 레이아웃

- 관련 필드를 `<fieldset>` + `<legend>`로 섹션화
- 섹션 간 `<hr class="border-gray-200" />` 구분

| 레이아웃 | 용도 | 필드 수 |
|---------|------|---------|
| Vertical | 기본 생성/수정 폼 | 5개 이상 |
| Horizontal | 설정, 프로필 편집 | 3-8개 |
| Inline | 검색/필터 바 | 2-4개 |
| Step-by-step | 복잡한 생성 프로세스 | 10개 이상 |

---

## 3. 네비게이션 패턴

### 3.1 사이드바

- 고정(fixed) + 스크롤 가능 콘텐츠, 너비 `w-60`
- 1단계: 아이콘 + 텍스트, 2단계: 들여쓰기 + 텍스트만
- 활성 메뉴: `text-blue-600 bg-blue-50 border-l-2 border-blue-600`
- 비활성: `text-gray-700 hover:bg-gray-50 border-l-2 border-transparent`
- 아이템 높이: `h-10` (40px, Ant Design 표준)

### 3.2 브레드크럼

- 3단계 이상 깊이에서 표시
- 현재 페이지는 텍스트만 (링크 아님): `text-gray-900 font-medium`
- 구분자: `/`

### 3.3 탭 네비게이션

- 같은 맥락의 다른 뷰 전환에 사용, 2~7개
- 활성 탭: `font-medium text-blue-600 border-b-2 border-blue-600`
- 탭 전환 시 URL 파라미터 반영 (뒤로가기 지원)
- 배지로 건수 표시: `bg-red-100 text-red-700 text-xs rounded-full`

---

## 4. 피드백 패턴

### 4.1 로딩 상태

| 유형 | 용도 |
|------|------|
| 스켈레톤 | 초기 데이터 로드 (레이아웃 유지): `animate-pulse bg-gray-200 rounded` |
| 스피너 오버레이 | 데이터 갱신 (기존 데이터 위): `absolute inset-0 bg-white/60 z-10` |
| 프로그레스 바 | 파일 업로드, 대량 처리 |

### 4.2 빈 상태 (Empty State)

- 아이콘 + 메시지 + 액션 버튼 조합: `flex flex-col items-center py-16`
- 검색 결과 없음 vs 데이터 없음 구분 (다른 아이콘/메시지)

### 4.3 에러 & 성공 알림

- 인라인 에러: `p-4 bg-red-50 border border-red-200 rounded-md` + 재시도 버튼
- 성공 토스트: 우측 하단, 3~5초 자동 닫힘, 되돌리기(Undo) 포함 가능
- 성공=녹색, 경고=노란색, 에러=빨간색

---

## 5. Pro Layout 패턴 (Ant Design Pro)

### 5.1 표준 레이아웃 구조

```
SIDEBAR (w-60, fixed) | HEADER (검색, 알림, 프로필)
                      | BREADCRUMB
                      | PAGE TITLE + [액션 버튼들]
                      | FILTERS
                      | CONTENT (테이블/카드/폼)
                      | PAGINATION
```

### 5.2 페이지 헤더

```html
<div class="flex items-center justify-between mb-6">
  <div>
    <h1 class="text-xl font-bold text-gray-900">페이지 제목</h1>
    <p class="text-sm text-gray-500 mt-1">설명 텍스트</p>
  </div>
  <div class="flex items-center gap-3">
    <button class="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50">내보내기</button>
    <button class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700">새 등록</button>
  </div>
</div>
```

### 5.3 Pro Table 통합

검색 + 필터 + 테이블 + 페이지네이션을 `bg-white rounded-lg border` 래퍼로 통합:
- 검색/필터 영역: `p-4 border-b`
- 테이블 툴바: `px-4 py-2 border-b bg-gray-50` (총 건수 + 밀도/컬럼 설정)
- 테이블 본체: `overflow-x-auto`
- 페이지네이션: `px-4 py-3 border-t`

---

## 6. ERP 적용 체크리스트

| 패턴 | 적용 기준 | 핵심 클래스 |
|------|----------|------------|
| Compact 테이블 | 거래 내역, 로그 | `h-8 text-sm px-2 py-1` |
| Default 테이블 | 일반 CRUD | `h-12 px-4 py-3` |
| Top-aligned 폼 | 생성/수정 | `block text-sm font-medium mb-1` |
| 필터 바 | 목록 페이지 상단 | `flex flex-wrap gap-3 p-4 bg-gray-50 border-b` |
| 필터 태그 | 적용된 필터 표시 | `inline-flex px-2 py-0.5 bg-blue-50 text-xs rounded-full` |
| 스켈레톤 | 초기 로드 | `animate-pulse bg-gray-200 rounded` |
| 빈 상태 | 데이터 없음 | `flex flex-col items-center py-16` |
| 에러 인라인 | API 실패 | `p-4 bg-red-50 border border-red-200 rounded-md` |
| 성공 토스트 | 저장/삭제 완료 | `fixed bottom-4 right-4 shadow-lg` |
| 페이지 헤더 | 모든 페이지 | `flex items-center justify-between mb-6` |

---

## 7. 모바일 반응형 패턴

> 상세 규칙: `responsive-design.md` 참조. 여기는 엔터프라이즈 적용 요약만.

### 7.1 모바일 테이블 전환

| 전략 | 적용 기준 | 구현 |
|------|---------|------|
| Sticky Column | 5열 이하, 빠른 적용 | 좌측 1~2열 `sticky left-0 bg-white z-10` |
| 컬럼 숨김 | 6열+, 핵심 열 명확 | `hidden md:table-cell` |
| 카드뷰 | UX 우선, 상세 정보 중요 | `md:hidden` 카드 + `hidden md:table` |

**ERP 적용:** 거래내역 → 카드뷰 (거래처+금액+상태), 로그 → sticky column, 설정 → 컬럼 숨김

### 7.2 모바일 모달 전환

| 데스크톱 모달 크기 | 모바일 전환 |
|-----------------|-----------|
| ≤640px (단순 확인) | 바텀시트 |
| 641~900px (표준 폼) | 바텀시트 또는 풀스크린 |
| 901px+ (대형 데이터) | 풀스크린 |

### 7.3 모바일 폼

- 모든 폼 그리드: `grid-cols-1 md:grid-cols-2` (모바일 1열 필수)
- 레이블: Top-aligned만 (inline 금지)
- 입력 높이: `min-h-[44px]` (터치 타겟)
- 숫자 키패드: `inputMode="numeric"`

### 7.4 모바일 필터

- 3개 이하: 칩(chip) 가로 스크롤
- 4개 이상: 바텀시트로 이동, "필터" 버튼으로 트리거
- 검색창: `w-full` (고정 너비 금지)

### 7.5 모바일 네비게이션

- 사이드바 → 햄버거 드로어 또는 하단 탭 바 (주요 3~5개)
- 브레드크럼 → 뒤로가기 화살표 + 현재 제목
- 탭 7개+ → 가로 스크롤 탭

### 7.6 ERP 모바일 적용 체크리스트

| 패턴 | 적용 기준 | 핵심 클래스 |
|------|----------|------------|
| 모달 너비 반응형 | 모든 모달 | `w-full max-w-[95vw] md:max-w-[1200px]` |
| 폼 그리드 반응형 | 모든 폼 | `grid grid-cols-1 md:grid-cols-2 gap-3` |
| 테이블 카드뷰 | 거래 내역 등 | `md:hidden` 카드 + `hidden md:table` |
| 터치 타겟 | 모든 인터랙티브 | `min-h-[44px] min-w-[44px]` |
| 검색창 반응형 | 필터 영역 | `w-full md:w-56` |
| 버튼 패딩 반응형 | 모바일 버튼 | `px-4 py-2 md:px-3 md:py-1.5` |
