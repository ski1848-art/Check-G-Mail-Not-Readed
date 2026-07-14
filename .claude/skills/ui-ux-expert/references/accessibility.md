# WCAG 2.2 접근성 가이드 (ERP 웹앱 기준)

> Level A + AA 기준, ERP 관리 시스템에 관련 있는 항목만 필터링.
>
> **캘리브레이션 (2026-03-11):**
> - 내부 ERP 시스템이므로 스크린 리더 전용 ARIA 속성(`sr-only`, `aria-live`, `role="alert"` 등)은 **낮은 우선순위**
> - **시맨틱 HTML** + **키보드 네비게이션**에 집중
> - 필수: `<button>`, `<label>`, `<table>/<thead>/<th>`, 포커스 링, 색상 대비
> - 선택: `aria-label`, `aria-describedby`, `role` 속성 (시간 여유 시 적용)

---

## 1. 지각 가능 (Perceivable)

사용자가 정보와 UI 컴포넌트를 인지할 수 있어야 한다.

### 1.1.1 Non-text Content (Level A)

**기준:** 모든 비텍스트 콘텐츠에 텍스트 대안을 제공해야 한다.

**ERP 적용:**
- 아이콘 버튼에 `aria-label` 필수 (편집, 삭제, 다운로드 등)
- 차트/그래프에 데이터 테이블 대안 제공
- 장식용 이미지는 `alt=""` 또는 `aria-hidden="true"`

**Tailwind/HTML:**
```html
<!-- 아이콘 버튼 -->
<button aria-label="삭제" class="p-2 hover:bg-red-50 rounded">
  <TrashIcon class="w-5 h-5" aria-hidden="true" />
</button>

<!-- 장식용 아이콘 -->
<span class="text-green-500" aria-hidden="true">●</span> 승인완료
```

**흔한 위반:** 아이콘만 있는 버튼에 `aria-label` 누락, 상태 표시 색상 원에 텍스트 없음

### 1.3.1 Info and Relationships (Level A)

**기준:** 시각적으로 전달되는 정보/구조/관계가 프로그래밍적으로 결정 가능해야 한다.

**ERP 적용:**
- 테이블은 `<table>`, `<thead>`, `<th scope="col">` 시맨틱 마크업 사용
- 폼 필드와 라벨 `<label htmlFor>` 연결
- 섹션 구분에 적절한 헤딩 레벨 (`h1` > `h2` > `h3`)
- 필수 필드 표시는 시각 + `aria-required="true"`

**Tailwind/HTML:**
```html
<label htmlFor="amount" class="block text-sm font-medium text-gray-700">
  금액 <span class="text-red-500" aria-label="필수">*</span>
</label>
<input id="amount" aria-required="true" class="mt-1 block w-full rounded-md border-gray-300" />
```

**흔한 위반:** `<div>` 기반 커스텀 테이블, `<label>` 없는 입력 필드

### 1.3.5 Identify Input Purpose (Level AA)

**기준:** 폼 입력의 목적을 프로그래밍적으로 식별할 수 있어야 한다.

**ERP 적용:**
- 이름, 이메일, 전화번호 필드에 `autocomplete` 속성 추가
- `autocomplete="name"`, `autocomplete="email"`, `autocomplete="tel"`

### 1.4.1 Use of Color (Level A)

**기준:** 색상만으로 정보를 전달하면 안 된다. 텍스트, 패턴, 아이콘을 병행해야 한다.

**ERP 적용:**
- 상태 표시: 색상 + 텍스트 라벨 병기 (초록 원 + "승인", 빨강 원 + "반려")
- 에러 필드: 빨간 테두리 + 에러 메시지 텍스트
- 차트: 색상 + 패턴/마커 형태로 구분

**Tailwind/HTML:**
```html
<!-- Good: 색상 + 텍스트 -->
<span class="inline-flex items-center gap-1.5 text-sm">
  <span class="w-2 h-2 rounded-full bg-green-500" aria-hidden="true"></span>
  승인완료
</span>

<!-- Bad: 색상만 -->
<span class="w-2 h-2 rounded-full bg-green-500"></span>
```

**흔한 위반:** 빨강/초록으로만 구분하는 성공/실패 상태 (색각 이상자 고려 없음)

### 1.4.3 Contrast (Minimum) (Level AA)

**기준:** 일반 텍스트 4.5:1, 큰 텍스트(18pt+/14pt bold+) 3:1 대비율.

**ERP 적용:**
- 본문: `text-gray-900` on `bg-white` (21:1) — 충분
- 보조 텍스트: `text-gray-600` on `bg-white` (5.7:1) — 충분
- 주의: `text-gray-400` on `bg-white` (3.9:1) — **미달, placeholder에만 사용**
- 주의: `text-gray-300` on `bg-white` (2.6:1) — **위반, 사용 금지**

**Tailwind 안전 팔레트 (bg-white 기준):**

| 용도 | 클래스 | 대비율 | 적합성 |
|------|--------|--------|--------|
| 본문 텍스트 | `text-gray-900` | 21:1 | AA 통과 |
| 부제/라벨 | `text-gray-700` | 9.2:1 | AA 통과 |
| 보조 텍스트 | `text-gray-600` | 5.7:1 | AA 통과 |
| 비활성/힌트 | `text-gray-500` | 4.6:1 | AA 통과 (경계) |
| Placeholder | `text-gray-400` | 3.9:1 | AA 미달 (placeholder만) |
| 링크 | `text-blue-600` | 5.2:1 | AA 통과 |
| 에러 | `text-red-600` | 4.6:1 | AA 통과 |
| 성공 | `text-green-700` | 5.1:1 | AA 통과 |

**흔한 위반:** `text-gray-400`을 일반 텍스트에 사용, 연한 배경에 연한 텍스트

### 1.4.4 Resize Text (Level AA)

**기준:** 텍스트를 200%까지 확대해도 기능 손실이나 가로 스크롤이 발생하면 안 된다.

**ERP 적용:**
- 고정 `px` 대신 `rem` 기반 사이즈 사용 (Tailwind 기본)
- 테이블 셀에 `min-width` 대신 `min-w-0` + `truncate` 패턴
- 레이아웃은 `flex-wrap` 또는 `grid` 기반으로 리플로우 허용

### 1.4.10 Reflow (Level AA)

**기준:** 320px 너비에서 가로 스크롤 없이 콘텐츠가 리플로우되어야 한다 (데이터 테이블 제외).

**ERP 적용:**
- 모바일 뷰에서 카드 형태로 전환 (`hidden md:table` / `md:hidden`)
- 사이드바는 모바일에서 오버레이 또는 숨김 처리

### 1.4.11 Non-text Contrast (Level AA)

**기준:** UI 컴포넌트와 그래픽 요소는 인접 색상과 3:1 이상 대비.

**ERP 적용:**
- 입력 필드 테두리: `border-gray-300` on `bg-white` (1.9:1) — **위반 가능**
- 개선: `border-gray-400` (2.8:1) 또는 `border-gray-500` (3.9:1)
- 체크박스, 라디오, 토글 등 컨트롤의 테두리/배경 대비 확인

### 1.4.13 Content on Hover or Focus (Level AA)

**기준:** 호버/포커스로 나타나는 콘텐츠는 해제 가능, 호버 가능, 지속적이어야 한다.

**ERP 적용:**
- 툴팁: ESC로 닫기 가능, 마우스가 툴팁 위로 이동해도 유지
- 드롭다운 메뉴: 포커스가 메뉴 안에 있는 동안 유지

---

## 2. 조작 가능 (Operable)

UI 컴포넌트와 네비게이션을 조작할 수 있어야 한다.

### 2.1.1 Keyboard (Level A)

**기준:** 모든 기능이 키보드로 조작 가능해야 한다.

**ERP 적용:**
- 모든 인터랙티브 요소에 Tab으로 접근 가능
- 커스텀 컴포넌트(드롭다운, 모달, 탭)에 키보드 핸들러 구현
- `<div onClick>` 대신 `<button>` 또는 `role="button" tabIndex={0} onKeyDown`

**Tailwind/HTML:**
```html
<!-- Bad: 키보드 접근 불가 -->
<div onClick={handleClick} class="cursor-pointer">삭제</div>

<!-- Good: 키보드 접근 가능 -->
<button onClick={handleClick} class="cursor-pointer">삭제</button>
```

**흔한 위반:** `<div>` 클릭 핸들러, 커스텀 드롭다운에 키보드 지원 없음

### 2.1.2 No Keyboard Trap (Level A)

**기준:** 키보드 포커스가 특정 컴포넌트에 갇히면 안 된다.

**ERP 적용:**
- 모달: 포커스 트랩은 허용하되, ESC로 탈출 가능해야 함
- 날짜 선택기: Tab으로 빠져나갈 수 있어야 함

### 2.4.1 Bypass Blocks (Level A)

**기준:** 반복되는 콘텐츠 블록을 건너뛸 수 있는 메커니즘 제공.

**ERP 적용:**
- "본문으로 건너뛰기" 링크 (첫 Tab에 나타남)
- 랜드마크 역할: `<nav>`, `<main>`, `<aside>`

**Tailwind/HTML:**
```html
<a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg">
  본문으로 건너뛰기
</a>
```

### 2.4.3 Focus Order (Level A)

**기준:** 포커스 순서가 의미와 조작에 맞는 논리적 순서를 따라야 한다.

**ERP 적용:**
- DOM 순서 = 시각적 순서 (CSS로 재배치 시 주의)
- 모달 열림 시 포커스를 모달 내부로 이동
- 모달 닫힘 시 포커스를 트리거 요소로 복귀

**흔한 위반:** `tabIndex` 양수값 사용, CSS `order`로 시각 순서 변경 후 DOM 미반영

### 2.4.7 Focus Visible (Level AA)

**기준:** 키보드 포커스 시 가시적인 인디케이터가 표시되어야 한다.

**ERP 적용:**
- 모든 인터랙티브 요소에 포커스 링 표시
- `outline: none` 단독 사용 금지 — 대체 포커스 스타일 필수

**Tailwind:**
```html
<!-- 포커스 링 기본 패턴 -->
<button class="focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:outline-none">
  저장
</button>

<!-- 입력 필드 -->
<input class="focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
```

**흔한 위반:** 글로벌 `outline: none` without 대체 스타일, `focus:` 대신 마우스만 고려

---

## 3. 이해 가능 (Understandable)

정보와 UI 조작이 이해 가능해야 한다.

### 3.1.1 Language of Page (Level A)

**기준:** 페이지의 기본 언어가 프로그래밍적으로 결정 가능해야 한다.

**ERP 적용:**
```html
<html lang="ko">
```

### 3.2.1 On Focus (Level A)

**기준:** 포커스를 받는 것만으로 예상치 못한 맥락 변경이 발생하면 안 된다.

**ERP 적용:**
- 탭 전환은 클릭/Enter로만, 포커스만으로 전환 금지
- 드롭다운 포커스만으로 페이지 이동 금지

### 3.2.2 On Input (Level A)

**기준:** 입력값 변경만으로 예상치 못한 맥락 변경이 발생하면 안 된다.

**ERP 적용:**
- 필터 드롭다운 변경 시 자동 제출 허용 (이것은 예상 가능한 동작)
- 하지만 라디오 버튼 선택으로 갑자기 다른 페이지로 이동은 금지

### 3.3.1 Error Identification (Level A)

**기준:** 에러가 감지되면 텍스트로 식별하고 설명해야 한다.

**ERP 적용:**
- 각 에러 필드 아래에 구체적인 에러 메시지
- 폼 상단에 에러 요약 + 해당 필드로 링크

**Tailwind/HTML:**
```html
<div>
  <label htmlFor="salary" class="block text-sm font-medium text-gray-700">기본급</label>
  <input id="salary" aria-invalid="true" aria-describedby="salary-error"
    class="mt-1 block w-full rounded-md border-red-500 focus:ring-red-500" />
  <p id="salary-error" role="alert" class="mt-1 text-sm text-red-600">
    기본급은 0보다 커야 합니다.
  </p>
</div>
```

### 3.3.2 Labels or Instructions (Level A)

**기준:** 폼 컨트롤에 라벨 또는 입력 안내를 제공해야 한다.

**ERP 적용:**
- 모든 입력 필드에 `<label>` 연결
- 특수 형식 입력에 placeholder + 도움말 텍스트 (예: "YYYY-MM-DD")
- 필수 필드 시각적 표시 + `aria-required`

**흔한 위반:** placeholder만 있고 label 없는 필드, 아이콘만 있는 검색 입력

### 3.3.3 Error Suggestion (Level A)

**기준:** 에러 발생 시 가능한 수정 제안을 제공해야 한다.

**ERP 적용:**
- "날짜 형식이 올바르지 않습니다" 대신 "날짜 형식이 올바르지 않습니다 (예: 2026-03-11)"
- 유사한 값 제안 (계정과목 검색 시 유사 항목 표시)

### 3.3.4 Error Prevention - Legal, Financial, Data (Level A)

**기준:** 법적/재무적/데이터 관련 제출은 검토, 확인, 또는 되돌리기가 가능해야 한다.

**ERP 적용:**
- 전표 확정 전 미리보기 단계
- 급여 일괄 처리 전 확인 다이얼로그 + 요약 표시
- 삭제 동작 후 일정 기간 복구 가능 (소프트 딜리트)

---

## 4. 견고함 (Robust)

다양한 사용자 에이전트(브라우저, 보조 기술)에서 해석 가능해야 한다.

### 4.1.2 Name, Role, Value (Level A)

**기준:** 모든 UI 컴포넌트의 이름, 역할, 값이 프로그래밍적으로 결정 가능해야 한다.

**ERP 적용:**
- 커스텀 컴포넌트에 적절한 ARIA 역할 부여
- 토글 스위치: `role="switch"` + `aria-checked`
- 탭: `role="tablist"`, `role="tab"`, `role="tabpanel"`
- 모달: `role="dialog"` + `aria-labelledby` + `aria-modal="true"`

**Tailwind/HTML:**
```html
<!-- 커스텀 토글 -->
<button role="switch" aria-checked={enabled} aria-label="알림 활성화"
  class={`relative inline-flex h-6 w-11 rounded-full transition-colors
    ${enabled ? 'bg-blue-600' : 'bg-gray-200'}`}>
  <span class={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition
    ${enabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
</button>

<!-- 탭 -->
<div role="tablist" aria-label="재무 관리">
  <button role="tab" aria-selected={activeTab === 'journal'} aria-controls="panel-journal">
    전표
  </button>
</div>
<div role="tabpanel" id="panel-journal" aria-labelledby="tab-journal">
  ...
</div>
```

**흔한 위반:** `<div>`로 만든 커스텀 컴포넌트에 ARIA 없음, `aria-selected` 미갱신

---

## Quick Reference: Tailwind 접근성 유틸리티

| 유틸리티 | 용도 | 사용처 |
|---------|------|--------|
| `sr-only` | 시각적으로 숨기되 스크린 리더에서 읽힘 | 아이콘 라벨, 추가 설명 |
| `not-sr-only` | `sr-only` 해제 | 포커스 시 표시할 skip 링크 |
| `focus-visible:ring-2` | 키보드 포커스 시만 링 표시 | 모든 인터랙티브 요소 |
| `focus:outline-none` | 기본 아웃라인 제거 | `focus-visible:ring`과 함께만 사용 |
| `aria-hidden="true"` | 보조 기술에서 숨김 | 장식 아이콘, 중복 텍스트 |
| `aria-label` | 접근 가능한 이름 | 텍스트 없는 버튼 |
| `aria-describedby` | 추가 설명 연결 | 에러 메시지, 도움말 |
| `aria-live="polite"` | 동적 콘텐츠 변경 알림 | 토스트, 검색 결과 수 |
| `aria-live="assertive"` | 즉시 알림 | 에러 알림 |
| `role="alert"` | 경고 역할 (`aria-live="assertive"` 내포) | 에러 메시지 |
| `role="status"` | 상태 역할 (`aria-live="polite"` 내포) | 성공 메시지, 로딩 |

---

## ERP 접근성 구현 체크리스트

### [필수] 키보드 네비게이션
- [ ] 모든 인터랙티브 요소 Tab 접근 가능
- [ ] 모달에 포커스 트랩 + ESC 닫기
- [ ] 드롭다운에 화살표 키 네비게이션
- [ ] 테이블 행 Enter로 상세 보기
- [ ] `<div onClick>` 대신 `<button>` 사용

### [필수] 시맨틱 마크업
- [ ] 테이블: `<table>`, `<thead>`, `<th scope>`
- [ ] 네비게이션: `<nav>`, `<main>`, `<aside>`
- [ ] 헤딩 레벨 순서 유지 (h1 > h2 > h3)
- [ ] 버튼은 `<button>`, 링크는 `<a>`
- [ ] 모든 입력에 `<label>` 연결

### [필수] 색상 & 대비
- [ ] 본문 텍스트 4.5:1 이상 대비
- [ ] 색상 외 추가 시각 단서 (아이콘, 텍스트)
- [ ] UI 컴포넌트 테두리 3:1 이상 대비
- [ ] `text-gray-400` 이하는 placeholder에만 사용

### [필수] alert/confirm 교체
- [ ] `window.alert()` → 토스트 컴포넌트로 교체
- [ ] `window.confirm()` → 커스텀 확인 다이얼로그로 교체
- [ ] 토스트: 성공(green)/실패(red)/경고(yellow)/정보(blue) 4종
- [ ] 확인 다이얼로그: 제목, 설명, 확인/취소 버튼, ESC 닫기

### [선택] ARIA 속성 (낮은 우선순위)
- [ ] 아이콘 버튼에 `aria-label`
- [ ] 필수 필드 `aria-required="true"`
- [ ] 에러 필드 `aria-invalid="true"` + `aria-describedby`
- [ ] 토스트/알림에 `aria-live` 설정
- [ ] Skip navigation 링크
