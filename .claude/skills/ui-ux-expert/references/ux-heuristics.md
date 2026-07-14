# UX Heuristics & 인지과학 기반 설계 원칙

> 에이전트 참조용 레퍼런스. ERP/관리 시스템 맥락에 맞게 정리.

---

## Part 1: Nielsen의 10 Usability Heuristics

### 1. Visibility of System Status

**정의:** 시스템은 적절한 피드백을 합리적인 시간 내에 제공하여, 사용자에게 현재 상태를 항상 알려야 한다.

**ERP 적용 예시:**
- 데이터 저장/삭제 시 토스트 알림으로 성공/실패 즉시 표시
- 대량 데이터 처리(급여 계산, 일괄 전표 생성) 시 프로그레스 바 표시
- 테이블 필터/정렬 적용 시 활성 필터 뱃지로 현재 조건 명시

**위반 패턴:**
- 버튼 클릭 후 아무 반응 없이 수 초간 대기 (로딩 인디케이터 없음)
- 폼 제출 후 성공/실패 여부를 알 수 없는 상태

**Tailwind 체크포인트:**
- [ ] `animate-spin` — 로딩 스피너
- [ ] `transition-colors duration-200` — 버튼 상태 전환
- [ ] `disabled:opacity-50 disabled:cursor-not-allowed` — 비활성 상태 표시

### 2. Match Between the System and the Real World

**정의:** 시스템은 내부 전문 용어가 아닌 사용자에게 익숙한 단어, 구문, 개념을 사용해야 한다.

**ERP 적용 예시:**
- 회계 용어는 업무 담당자가 사용하는 표현 그대로 (차변/대변, 매입/매출)
- 날짜 형식은 한국 표준(YYYY-MM-DD) 사용, 미국식 MM/DD 지양
- 상태값은 코드가 아닌 한글 라벨 표시 ("APPROVED" 대신 "승인완료")

**위반 패턴:**
- DB 컬럼명이나 API 에러 코드가 그대로 노출
- 영문 약어만 표시 (e.g., "PO", "SO" without 한글 병기)

**Tailwind 체크포인트:**
- [ ] 한글 폰트 `font-sans` 기본 적용, 가독성 우선
- [ ] `text-sm` 이상 사용 (한글은 영문보다 큰 사이즈 필요)

### 3. User Control and Freedom

**정의:** 사용자는 실수를 하므로, 원치 않는 동작에서 빠져나올 수 있는 "비상구"가 필요하다.

**ERP 적용 예시:**
- 전표/지출 결의 삭제 전 확인 다이얼로그 + 되돌리기(Undo) 옵션
- 모달/패널에서 ESC 키 또는 바깥 클릭으로 닫기
- 다단계 폼(급여 설정, 채용 프로세스)에서 이전 단계로 돌아가기

**위반 패턴:**
- 확인 없이 즉시 삭제되는 위험 액션
- 뒤로가기 버튼 없이 처음부터 다시 시작해야 하는 플로우

**Tailwind 체크포인트:**
- [ ] 모달 `backdrop`에 클릭 이벤트 바인딩
- [ ] 위험 버튼 `bg-red-600 hover:bg-red-700` + 확인 단계 분리

### 4. Consistency and Standards

**정의:** 서로 다른 단어, 상황, 동작이 같은 의미인지 사용자가 고민할 필요가 없어야 한다.

**ERP 적용 예시:**
- 모든 테이블에 동일한 정렬/필터/페이지네이션 패턴 적용
- "저장" 버튼은 항상 오른쪽 하단, 동일한 스타일
- 날짜 선택기, 금액 입력 등 공통 컴포넌트 재사용

**위반 패턴:**
- 페이지마다 다른 위치에 있는 액션 버튼
- 같은 데이터를 다른 형식으로 표시 (한 곳은 "1,000,000", 다른 곳은 "1000000")

**Tailwind 체크포인트:**
- [ ] 디자인 토큰 일관성: `text-gray-900`, `bg-white`, `border-gray-200`
- [ ] 버튼 variant 통일: primary(`bg-blue-600`), danger(`bg-red-600`), ghost(`bg-transparent`)

### 5. Error Prevention

**정의:** 좋은 에러 메시지도 중요하지만, 최선의 설계는 문제 발생 자체를 예방한다.

**ERP 적용 예시:**
- 금액 입력 시 자동 쉼표 포맷팅으로 자릿수 실수 방지
- 날짜 범위 선택 시 종료일이 시작일보다 앞서면 자동 보정
- 중복 전표 생성 시 경고 메시지 표시

**위반 패턴:**
- 잘못된 입력을 제출 후에야 알려주는 방식 (실시간 유효성 검사 없음)
- 되돌릴 수 없는 동작에 확인 단계가 없음

**Tailwind 체크포인트:**
- [ ] 인라인 유효성 검사 `text-red-600 text-sm mt-1`
- [ ] 비활성 제출 버튼 `disabled:opacity-50` (유효하지 않을 때)

### 6. Recognition Rather than Recall

**정의:** 요소, 동작, 옵션을 보이게 만들어 사용자의 기억 부담을 최소화해야 한다.

**ERP 적용 예시:**
- 최근 검색어/자주 사용하는 계정과목 상단 표시
- 폼 필드에 placeholder와 도움말 텍스트 제공
- 테이블 컬럼 헤더에 툴팁으로 데이터 설명

**위반 패턴:**
- 코드만 표시하고 이름을 보여주지 않는 드롭다운 (계정코드 "1101" without "보통예금")
- 이전 화면의 맥락 없이 다음 단계 진행

**Tailwind 체크포인트:**
- [ ] 툴팁 `group relative` + `group-hover:block hidden` 패턴
- [ ] placeholder `placeholder:text-gray-400`

### 7. Flexibility and Efficiency of Use

**정의:** 숙련 사용자를 위한 단축키는 초보에게 보이지 않으면서, 양쪽 모두에게 효율적이어야 한다.

**ERP 적용 예시:**
- 테이블에서 키보드 단축키(Enter: 저장, Esc: 취소) 지원
- 자주 사용하는 필터 조합 저장/불러오기
- 대량 작업용 일괄 선택/처리 기능 (체크박스 + 일괄 액션)

**위반 패턴:**
- 모든 동작에 마우스 클릭만 가능 (키보드 단축키 없음)
- 반복 작업에 매번 같은 설정을 처음부터 입력

**Tailwind 체크포인트:**
- [ ] 포커스 링 `focus:ring-2 focus:ring-blue-500 focus:ring-offset-2`
- [ ] `kbd` 요소 스타일 `px-1.5 py-0.5 bg-gray-100 rounded text-xs font-mono`

### 8. Aesthetic and Minimalist Design

**정의:** 인터페이스에 불필요하거나 드물게 필요한 정보를 포함하지 않아야 한다.

**ERP 적용 예시:**
- 대시보드에 핵심 KPI만 표시, 상세는 드릴다운으로 제공
- 테이블 컬럼은 업무에 필수적인 것만 기본 표시, 나머지는 토글
- 빈 상태(empty state)에 명확한 안내 메시지

**위반 패턴:**
- 한 화면에 20개 이상 컬럼이 있는 테이블
- 사용 빈도가 낮은 기능이 주요 동선에 노출

**Tailwind 체크포인트:**
- [ ] 여백 활용 `space-y-4`, `gap-4` — 정보 밀도 조절
- [ ] `hidden lg:block` — 반응형으로 보조 정보 숨김

### 9. Help Users Recognize, Diagnose, and Recover from Errors

**정의:** 에러 메시지는 평문으로 표현하고, 문제를 정확히 지적하며, 해결 방법을 제안해야 한다.

**ERP 적용 예시:**
- "서버 오류" 대신 "급여 계산 중 홍길동 사원의 기본급이 미설정입니다"
- 에러 발생 필드로 자동 스크롤 + 하이라이트
- 실패한 API 요청에 재시도 버튼 제공

**위반 패턴:**
- "Error 500" 또는 "Something went wrong" 같은 일반 메시지
- 어떤 필드에서 에러가 발생했는지 표시하지 않음

**Tailwind 체크포인트:**
- [ ] 에러 필드 `border-red-500 focus:ring-red-500`
- [ ] 에러 메시지 `text-red-600 text-sm flex items-center gap-1`
- [ ] 에러 배너 `bg-red-50 border-l-4 border-red-500 p-4`

### 10. Help and Documentation

**정의:** 시스템은 추가 설명 없이도 사용 가능해야 하지만, 필요 시 문서를 제공해야 한다.

**ERP 적용 예시:**
- 복잡한 기능(전표 생성, 급여 정산) 옆에 "?" 아이콘으로 인라인 도움말
- 처음 사용하는 기능에 온보딩 투어/가이드
- 검색 가능한 도움말 섹션

**위반 패턴:**
- 도움말이 전혀 없는 복잡한 설정 화면
- 외부 매뉴얼만 존재하고 인앱 가이드가 없음

**Tailwind 체크포인트:**
- [ ] 도움말 아이콘 `text-gray-400 hover:text-gray-600 cursor-help`
- [ ] 인라인 팁 `bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm`

---

## Part 2: Peter Morville의 UX Honeycomb

7가지 사용자 경험 요소로, 유용성(Usability)을 넘어 전체 UX를 평가한다.

| 요소 | 정의 | ERP 적용 핵심 |
|------|------|-------------|
| **Useful** | 실제 사용자 문제를 해결하는가 | 업무 프로세스 자동화, 수동 작업 제거 |
| **Usable** | 직관적이고 학습 비용이 낮은가 | 일관된 테이블/폼 패턴, 명확한 레이블 |
| **Desirable** | 시각적으로 매력적이고 감정적 만족을 주는가 | 깔끔한 레이아웃, 적절한 애니메이션 |
| **Findable** | 원하는 기능/정보를 쉽게 찾을 수 있는가 | 사이드바 구조화, 검색, 브레드크럼 |
| **Accessible** | 다양한 능력/환경의 사용자가 사용 가능한가 | 키보드 네비게이션, 색상 대비, ARIA |
| **Credible** | 신뢰할 수 있고 투명한가 | 정확한 수치 표시, 감사 로그, 변경 이력 |
| **Valuable** | 시간 절약, 업무 효율 등 실질적 가치를 제공하는가 | ROI 가시화, 리포트 자동 생성 |

### ERP 시스템 Honeycomb 체크리스트

- [ ] **Useful**: 이 기능이 없으면 사용자가 수동으로 해야 할 작업이 있는가?
- [ ] **Usable**: 신규 직원이 5분 내에 기본 조작을 익힐 수 있는가?
- [ ] **Desirable**: 시각적 일관성이 유지되고, 불필요한 시각 노이즈가 없는가?
- [ ] **Findable**: 3클릭 이내에 원하는 메뉴에 도달 가능한가?
- [ ] **Accessible**: 키보드만으로 모든 핵심 기능을 수행할 수 있는가?
- [ ] **Credible**: 금액, 날짜 등 중요 데이터가 정확히 표시되는가?
- [ ] **Valuable**: 이 기능이 월간 몇 시간의 업무 시간을 절약하는가?

---

## Part 3: 인지과학 기반 UX 법칙

### Fitts's Law (피츠의 법칙)

**정의:** 타겟까지의 이동 시간은 타겟까지의 거리에 비례하고, 타겟의 크기에 반비례한다.

**공식:** `T = a + b * log2(D/W + 1)` (D=거리, W=너비)

**ERP 적용:**
- 주요 액션 버튼은 충분히 크게 (`h-10 px-6` 이상)
- 자주 사용하는 버튼은 현재 작업 영역 가까이 배치
- 테이블 행 액션은 행 내부 또는 호버 시 인접 표시
- 모달의 확인/취소 버튼은 하단 우측에 밀접 배치

**위반 패턴:**
- 작은 아이콘 버튼만 있는 액션 영역 (`w-4 h-4`)
- 화면 반대편에 위치한 "저장"과 "취소" 버튼

```html
<!-- Good: 충분한 크기와 인접 배치 -->
<div class="flex justify-end gap-2">
  <button class="h-10 px-6 rounded-lg">취소</button>
  <button class="h-10 px-6 rounded-lg bg-blue-600 text-white">저장</button>
</div>
```

### Hick's Law (힉의 법칙)

**정의:** 의사결정에 걸리는 시간은 선택지의 수와 복잡도에 비례하여 증가한다.

**공식:** `T = b * log2(n + 1)` (n=선택지 수)

**ERP 적용:**
- 드롭다운 선택지가 10개 초과 시 검색 기능 추가
- 복잡한 설정은 카테고리별 그룹핑
- 단계별 위자드로 한 번에 하나의 결정만 요구
- 대시보드 액션은 3~5개 이내로 제한

**위반 패턴:**
- 50개 이상 항목이 있는 플랫 드롭다운
- 한 화면에 10개 이상의 CTA 버튼

### Miller's Law (밀러의 법칙)

**정의:** 일반인의 작업 기억(working memory)은 평균 7(+-2)개 항목을 처리한다.

**ERP 적용:**
- 네비게이션 최상위 메뉴는 5~9개 이내
- 테이블 기본 표시 컬럼은 7개 이내, 나머지는 확장/설정으로
- 대시보드 핵심 지표는 4~6개로 제한
- 스텝 인디케이터는 3~5단계 이내

**위반 패턴:**
- 15개 이상 메뉴가 나열된 사이드바 (그룹핑 없음)
- 한 폼에 20개 이상 입력 필드가 스크롤 없이 나열

### Jakob's Law (야콥의 법칙)

**정의:** 사용자는 대부분의 시간을 다른 사이트에서 보내므로, 이미 익숙한 패턴대로 동작하기를 기대한다.

**ERP 적용:**
- 좌측 사이드바 네비게이션 (업계 표준)
- 테이블 정렬은 컬럼 헤더 클릭 (화살표 아이콘)
- 검색은 상단 또는 테이블 위 (`Ctrl/Cmd + K` 단축키)
- 삭제는 빨간색, 확인은 파란색 (색상 관례)

### Doherty Threshold (도허티 임계값)

**정의:** 시스템 응답이 400ms 이내일 때 생산성이 급격히 향상된다.

**ERP 적용:**
- API 응답 지연 시 스켈레톤 UI로 체감 속도 개선
- 테이블 필터링은 클라이언트 사이드 우선 (소규모 데이터)
- 디바운스된 검색 (`300ms` delay)으로 서버 부하 감소
- 낙관적 업데이트(optimistic update)로 즉시 반영

```html
<!-- 스켈레톤 UI 예시 -->
<div class="animate-pulse space-y-3">
  <div class="h-4 bg-gray-200 rounded w-3/4"></div>
  <div class="h-4 bg-gray-200 rounded w-1/2"></div>
  <div class="h-4 bg-gray-200 rounded w-5/6"></div>
</div>
```

---

## Quick Reference: 설계 결정 시 참조 매트릭스

| 설계 결정 | 참조 원칙 |
|----------|---------|
| 버튼 크기/위치 | Fitts's Law |
| 선택지 개수 | Hick's Law, Miller's Law |
| 메뉴 구조 | Miller's Law, Jakob's Law |
| 로딩/피드백 | Visibility of System Status, Doherty Threshold |
| 에러 처리 | Error Prevention, Help Recognize Errors |
| 용어/라벨 | Match Real World, Recognition > Recall |
| 일관성 | Consistency & Standards, Jakob's Law |
| 위험 동작 | User Control & Freedom, Error Prevention |
| 정보 밀도 | Aesthetic & Minimalist, Miller's Law |
| 접근성 | UX Honeycomb (Accessible), Flexibility |
