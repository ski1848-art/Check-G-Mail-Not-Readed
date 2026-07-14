# Pre-Delivery Checklist — 구현 완료 전 자가 검증

> 출처: Vercel Web Interface Guidelines (100+ rules), Pro Max Pre-Delivery, WCAG 2.2

UI 컴포넌트 구현 후 코드 전달 전 반드시 검증.

## 1. 레이아웃 (6항목)

- [ ] 모달 max-width 적정 (480~1400px)
- [ ] 그리드에 유동폭(1fr/minmax) 열 1개 이상
- [ ] 테이블 행 높이 균일
- [ ] 가변 콘텐츠가 아코디언으로 분리됨
- [ ] 주요 영역이 전체 너비의 50% 이상
- [ ] 빈 공간 50% 초과 열 없음

## 2. 시각적 계층 (5항목)

- [ ] L1(구조)/L2(카테고리)/L3(아이템) 구분 명확
- [ ] 섹션 헤더 존재 (bg-gray-50 + font-semibold)
- [ ] 선택/미선택 시각 차이 명확
- [ ] 비활성 영역 opacity-50 + pointer-events-none
- [ ] 가장 중요한 정보가 좌측 상단

## 3. 접근성 (Vercel Guidelines 기반, 8항목)

- [ ] 시맨틱 HTML (button, label, table, nav)
- [ ] 키보드 전체 접근 가능
- [ ] 포커스 순서 논리적
- [ ] 포커스 링 visible (outline 또는 ring)
- [ ] 색상 대비 4.5:1 이상 (텍스트)
- [ ] 터치 타겟 44x44px 이상
- [ ] prefers-reduced-motion 존중 (애니메이션 있을 때)
- [ ] 모든 img에 alt, 장식용은 alt=""

## 4. 프로젝트 컨벤션 (8항목)

- [ ] Compact/Standard 모드 올바르게 적용
- [ ] 버튼 표준 클래스 (bg-indigo-600 등)
- [ ] native select 미사용 → useDropdown
- [ ] gradient 버튼 미사용 (헤더 외)
- [ ] rounded-full 미사용 → rounded (배지)
- [ ] ring 글로우 미사용
- [ ] formatAmount() 등 숫자 포맷 유틸 사용
- [ ] div onClick 미사용 → button

## 5. 인터랙션 (6항목)

- [ ] ESC로 모달/드롭다운 닫힘
- [ ] 외부 클릭으로 모달 닫힘
- [ ] 체크박스 클릭 영역 충분 (label 감싸기)
- [ ] alert()/confirm() 미사용
- [ ] 트랜지션 150-300ms
- [ ] hover-only 기능 없음

## 6. 데이터 표시 (5항목)

- [ ] 빈 상태 안내 메시지
- [ ] truncate에 title 속성
- [ ] 중복 정보 표시 없음
- [ ] 날짜 KST 기준
- [ ] 로딩 상태 UI 존재

## 7. 성능 (Pro Max 기반, 5항목)

- [ ] 100건+ 목록: 페이지네이션 또는 가상 스크롤
- [ ] useCallback 의존성에 배열/객체 없음
- [ ] .map()/.filter() useMemo 캐싱
- [ ] 조건부 컴포넌트 dynamic import
- [ ] 이미지 lazy loading + WebP/AVIF

## 8. 안티패턴 최종 확인 (5항목)

- [ ] AP-L1~L6 레이아웃 안티패턴 없음
- [ ] AP-V1~V8 시각 안티패턴 없음
- [ ] AP-I1~I6 인터랙션 안티패턴 없음
- [ ] AP-D1~D5 데이터 안티패턴 없음
- [ ] AP-E1~E4 ERP 특화 안티패턴 없음
- [ ] AP-M1~M11 모바일 안티패턴 없음

## 9. 반응형/모바일 검증 (8항목)

- [ ] 모달 너비 반응형: `w-full max-w-[95vw] md:max-w-[Npx]`
- [ ] 폼 그리드 반응형: `grid-cols-1 md:grid-cols-2`
- [ ] 테이블 모바일 대응: 카드뷰/컬럼 숨김/sticky column 중 하나
- [ ] 터치 타겟 44x44px 이상 (모든 인터랙티브 요소)
- [ ] 터치 간격 8px 이상 (`gap-2`)
- [ ] 검색/필터 `w-full md:w-56` 반응형
- [ ] hover 전용 기능 없음 (tap 대체 존재)
- [ ] 모바일 폰트 text-sm(14px) 이상
- [ ] 375px에서 모든 라벨 텍스트 줄바꿈 없이 한 줄 표시 (whitespace-nowrap)
- [ ] 375px에서 숫자/금액 컨테이너 밖 오버플로 없음 (truncate/반응형 폰트)
- [ ] flex 자식이 부모를 넘기지 않음 (min-w-0 확인)
- [ ] KPI/통계 카드가 375px에서 정상 레이아웃 (flex-col 전환)
- [ ] 차트 데이터 라벨 모바일에서 겹치지 않음 (isMobile 숨김)
- [ ] 실제 운영 데이터(최대 길이 금액/거래처명)로 Playwright 검증 완료
- [ ] border/rounded 컨테이너의 자식이 경계를 넘지 않음 (AP-L7)
- [ ] 버튼/칩 그룹에 flex-wrap 또는 overflow-x-auto 적용
