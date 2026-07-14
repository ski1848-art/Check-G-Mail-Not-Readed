# Anti-Patterns — UI/UX 안티패턴 목록

> 출처: Vercel Web Interface Guidelines, UI/UX Pro Max Skill (161 rules), Nielsen Norman, 프로젝트 실전

## 레이아웃 (AP-L)

| ID | 금지 | 이유 | 대안 |
|----|------|------|------|
| AP-L1 | `max-w-[95vw]` 뷰포트 비율 모달 (데스크톱) | 모니터에 따라 과도하게 넓어짐 | 고정 max-width (1400px 이하). **모바일(md 미만)에서는 허용** |
| AP-L2 | 카드 그리드 높이 불균일 | 시선 분산, 스캔 어려움 | 테이블 행 또는 아코디언 |
| AP-L3 | 1400px에 4열+ 분할 | 각 열 350px 미만 → 절단 | 3열 이하 또는 탭 |
| AP-L4 | 모든 열 고정폭 그리드 | 반응형 깨짐 | 최소 1개 fr/minmax |
| AP-L5 | 내부 스크롤 + 고정 높이 테이블 | 스크롤 중첩, UX 혼란 | 페이지 레벨 스크롤 |
| AP-L6 | 가로 스크롤 | 콘텐츠 숨김 [Pro Max #5] | 열 축소 또는 반응형 |
| AP-L7 | border/rounded 컨테이너에서 자식이 경계를 넘는 것 | 시각적 결함, 레이아웃 붕괴 | 자식에 `flex-wrap`/`flex-1 min-w-0`, 컨테이너에 `overflow-hidden`은 최후 수단 (콘텐츠 잘림 주의) |
| AP-L8 | 고정 너비 입력(w-[160px] 등)을 모바일에서 그대로 사용 | 부모 너비 초과 | `w-full lg:w-[160px]` + 부모 `flex-1 min-w-0` |

## 시각 디자인 (AP-V)

| ID | 금지 | 이유 | 대안 |
|----|------|------|------|
| AP-V1 | 색상 배지 남용 (항목마다 다른 배경) | 시각적 소음 [Nielsen #8 미학] | 도트(●) + 텍스트 |
| AP-V2 | 모든 영역 동일 시각적 무게 | 중요도 구별 불가 | 크기/배경/테두리로 차등 |
| AP-V3 | `ring-2 ring-*-300` 글로우 | 촌스러움 | `border-color` 변경 |
| AP-V4 | `shadow-xl` 이상 | 인라인 요소에 과도 | `shadow-sm` 최대 |
| AP-V5 | gradient 버튼 (헤더 외) | 프로젝트 컨벤션 위반 | `bg-indigo-600` |
| AP-V6 | `rounded-full` 배지 | 프로젝트 배지 규칙 위반 | `rounded` (4px) |
| AP-V7 | Emoji 아이콘 (업무 UI) | 비전문적 인상 [Pro Max #4] | SVG 아이콘 |
| AP-V8 | neon/형광 색상 + dark mode | ERP에 부적합 [Pro Max #4] | muted 색상 |

## 인터랙션 (AP-I)

| ID | 금지 | 이유 | 대안 |
|----|------|------|------|
| AP-I1 | `<div onClick>` | 키보드 접근성 위반 [WCAG 2.1.1] | `<button>` |
| AP-I2 | native `<select>` | 스타일링 제한 | `useDropdown` 훅 |
| AP-I3 | `alert()`/`confirm()` | 브라우저 네이티브 UI | 커스텀 모달/토스트 |
| AP-I4 | hover-only 기능 | 터치 디바이스 접근 불가 [Pro Max #2] | 항상 표시 또는 클릭 |
| AP-I5 | 중요 기능 숨김 (접기 뒤) | 기능 존재 모름 [Nielsen #6 인식] | 항상 표시 |
| AP-I6 | 150ms 미만/300ms 초과 트랜지션 | 부자연스러움 [Pro Max #7] | 150-300ms |

## 데이터 표시 (AP-D)

| ID | 금지 | 이유 | 대안 |
|----|------|------|------|
| AP-D1 | 동일 데이터 2곳+ 표시 | 동기화 문제, 인지 부하 | 단일 소스 |
| AP-D2 | truncate without title | 정보 손실 | `title` 속성 추가 |
| AP-D3 | 빈 상태 미처리 | 오류로 오인 | 안내 메시지 |
| AP-D4 | 숫자 인라인 포맷 | 일관성 깨짐 | `formatAmount()` |
| AP-D5 | 대비 4.5:1 미만 텍스트 | 가독성 저하 [WCAG 1.4.3] | 대비 확보 |

## ERP 특화 (AP-E)

| ID | 금지 | 이유 | 대안 |
|----|------|------|------|
| AP-E1 | 데스크톱에서 카드뷰 강제 | 정보 밀도 저하 | 데스크톱=테이블, 모바일=카드뷰 조건부 허용 (`responsive-design.md`) |
| AP-E2 | 과도한 장식 (gradient/animation) | 업무 집중 분산 | 미니멀 UI |
| AP-E3 | 설정 변경 즉시 저장 (확인 없이) | 실수 복구 어려움 | 명시적 저장 버튼 |
| AP-E4 | 44px 미만 터치 타겟 | 클릭 오류 [Pro Max #2] | 최소 44x44px |

## 모바일 (AP-M)

| ID | 금지 | 이유 | 대안 |
|----|------|------|------|
| AP-M1 | 모바일에서 `grid-cols-2`+ 폼 강제 | 입력 필드 극도로 좁아짐 | `grid-cols-1 md:grid-cols-2` |
| AP-M2 | 모바일에서 고정 px 모달 너비 | 뷰포트 초과 → 가로 스크롤 | `w-full max-w-[95vw] md:max-w-[1200px]` |
| AP-M3 | hover 전용 기능 (모바일 대체 없음) | 터치 디바이스 접근 불가 | tap/click 대체 필수 |
| AP-M4 | 터치 타겟 간격 8px 미만 | Fat Finger 오작동 [NNGroup] | `gap-2` 이상 |
| AP-M5 | `user-scalable=no` 뷰포트 설정 | 핀치 줌 차단 → WCAG 위반 | 줌 허용 유지 |
| AP-M6 | 모바일에서 데스크톱 테이블 그대로 축소 | 7~8px 글씨, 터치 불가 | 카드뷰/컬럼 숨김/sticky column |
| AP-M7 | 짧은 라벨(총 입금 등) `whitespace-nowrap` 없이 flex 배치 | 글자별 줄바꿈("총\n입\n금") | `whitespace-nowrap` 필수 |
| AP-M8 | 13자리+ 숫자를 고정 너비 컨테이너에 삽입 | 숫자 오버플로/잘림 | `truncate` 또는 반응형 폰트 `text-xs md:text-sm` |
| AP-M9 | 모바일 flex 아이템에 `min-w-0` 없이 텍스트 배치 | flex 자식이 부모 넘침 | flex 자식에 `min-w-0` 기본 적용 |
| AP-M10 | 데이터 라벨(금액)을 모바일 차트에 표시 | 라벨 겹침으로 읽을 수 없음 | `isMobile ? undefined : labelRenderer` |
| AP-M11 | 모바일 수정 후 placeholder 데이터로만 검증 | 실 데이터에서 깨짐 미탐지 | 실제 운영 데이터(최대 길이)로 검증 필수 |
