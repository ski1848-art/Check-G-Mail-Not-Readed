# Responsive Design — 모바일 반응형 검증 가이드

> PC 기본 규칙: `docs/UI-UX 기준.md` / 모바일 상세: `docs/모바일 최적화.md`

---

## 브레이크포인트

| 토큰 | Tailwind | 범위 | 디바이스 |
|------|----------|------|---------|
| xs | (기본) | ~639px | 모바일 |
| sm | `sm:` | 640~767px | 모바일 대형 |
| md | `md:` | 768~1023px | 태블릿 |
| lg | `lg:` | 1024~1279px | 데스크톱 |
| xl | `xl:` | 1280px~ | 데스크톱 대형 |

---

## 모바일 텍스트 오버플로 방지 (필수 검증)

### 라벨 줄바꿈 방지

짧은 라벨(2-4자 한글: "총 입금", "순 수익" 등)이 flex 아이템 안에서 글자별 줄바꿈되는 것을 방지.

```tsx
// ❌ flex 공간 부족 시 "총\n입\n금" 으로 깨짐
<span className="text-gray-500">총 입금</span>

// ✅ 줄바꿈 방지
<span className="text-gray-500 whitespace-nowrap">총 입금</span>
```

**적용 대상**: KPI 라벨, 통계 제목, 배지 텍스트, 차트 범례, 테이블 헤더

### 숫자/금액 오버플로 방지

13자리 원화(₩61,359,513,175) 등이 컨테이너를 넘지 않도록.

```tsx
// ❌ 고정 너비 안에서 오버플로
<div className="w-32"><span className="font-bold">₩61,359,513,175</span></div>

// ✅ 방법 1: truncate + title (정보 보존)
<div className="w-32"><span className="font-bold truncate block" title="₩61,359,513,175">₩61,359,513,175</span></div>

// ✅ 방법 2: 반응형 폰트 축소
<span className="font-bold text-xs md:text-sm tabular-nums">₩61,359,513,175</span>

// ✅ 방법 3: 모바일에서 축약 표시
{isMobile ? formatCompact(amount) : formatAmount(amount)}
// 613.6억 vs ₩61,359,513,175
```

### flex 자식 shrink 방지

```tsx
// ❌ flex 자식이 내용 때문에 부모를 넘김
<div className="flex gap-1">
  <span>총 입금</span>
  <span className="font-bold">₩61,359,513,175</span>
</div>

// ✅ min-w-0 + truncate
<div className="flex gap-1 items-center">
  <span className="whitespace-nowrap flex-shrink-0">총 입금</span>
  <span className="font-bold min-w-0 truncate">₩61,359,513,175</span>
</div>
```

### KPI 카드 모바일 전환

```tsx
// ❌ 모바일에서 3개 KPI가 가로로 쌓여 글자 깨짐
<div className="flex items-center gap-4">
  <div>총 입금 ₩61B</div>
  <div>총 출금 ₩59B</div>
  <div>순 수익 ₩1.4B</div>
</div>

// ✅ 모바일 세로, PC 가로
<div className="flex flex-col md:flex-row items-start md:items-center gap-1 md:gap-4">
  <div className="flex items-center gap-1">
    <span className="whitespace-nowrap text-gray-500">총 입금</span>
    <span className="font-bold text-blue-600 tabular-nums">₩61,359,513,175</span>
  </div>
  ...
</div>
```

---

## 실제 데이터 검증 의무

모바일 검증 시 placeholder("test", "12,345")가 아닌 **실제 운영 데이터**로 검증 필수.

| 데이터 유형 | 최대 길이 예시 | 테스트 필수 |
|-----------|-------------|:---------:|
| 원화 금액 | ₩61,359,513,175 (13자리) | 필수 |
| 거래처명 | "네이버파이낸셜주식회사" (10자) | 필수 |
| 계좌번호 | 0290834650XXXX (14자리) | 필수 |
| 이메일 | example@longestdomain.co.kr | 권장 |

---

## 컴포넌트 모바일 전환 규칙

### 모달 → 바텀시트/풀스크린

| PC | 모바일 (md 미만) |
|---|---|
| Center Modal (≤640px) | 바텀시트 |
| Center Modal (>640px) | 풀스크린 |
| Tooltip | 탭→인라인 확장 |
| Dropdown Menu (3+) | ActionSheet |

### 테이블 → 모바일 패턴

| 패턴 | 적용 조건 |
|------|---------|
| 우선순위 컬럼 숨김 | 6열+, `hidden md:table-cell` |
| 카드뷰 전환 | 상세 정보 중요, `md:hidden` 카드 + `hidden md:block` 테이블 |
| Sticky Column | 5열 이하, 좌측 1-2열 sticky |

### 카드뷰 3라인 레이아웃 (ERP 표준)

거래 내역 등 데이터 테이블의 모바일 카드뷰 표준 구조:

```
┌──────────────────────────────────────┐
│ □ 메모(제목)  예금주(서브)      금액  │  ← 1라인
│   날짜시간  계좌별칭         입출금   │  ← 2라인
│   결제대상  거래분류  대상분류  상태   │  ← 3라인
└──────────────────────────────────────┘
```

**규칙:**
- **1라인**: 메모(`tx.memo || tx.description_original`)가 제목, 예금주는 서브(있을 때만), 금액 우측 정렬
- **2라인**: 날짜시간 + 계좌별칭 배지 + 입출금 배지
- **3라인**: 결제대상 + 거래분류 + 대상분류 — 데이터 없으면 `-`(회색), 상태 배지 항상 우측
- **3라인은 데이터 유무와 무관하게 항상 3개 슬롯 표시** — 조건부 숨김 금지
- 카드 패딩: `px-3 py-2`, 2~3라인 좌측 `ml-5` (체크박스 정렬)
- 결제대상 `max-w-[140px]`, 거래분류 `max-w-[100px]` truncate
- attribution_type 한글 매핑: revenue=매출, expense=비용, investment=투자, financial=재무, customer=고객

### 필터 → 접기/칩

| PC | 모바일 |
|---|---|
| 상단 필터 바 | 접기/펼치기 (`hidden lg:flex` + 토글) |
| 확장 필터 | 바텀시트 |
| 고정 너비 | `w-full lg:w-XX` |

---

## 터치 인터랙션

- **최소 터치 타겟**: 44x44px (Apple HIG, WCAG)
- **최소 간격**: 8px
- **hover 대체**: 반드시 tap/click 대안 필요
- **금지**: `user-scalable=no`, 차트 scroll hijacking

---

## Playwright 검증 절차

모바일 UI 수정 후 반드시 실행:

```
1. browser_resize(375, 812) → 모바일 뷰포트
2. browser_navigate(대상 URL)
3. browser_take_screenshot(fullPage) → 모바일 스크린샷
4. browser_evaluate → document.querySelectorAll로 overflow 체크:
   el.scrollWidth > el.clientWidth (가로 오버플로)
5. browser_resize(1920, 1080) → PC 뷰포트
6. browser_take_screenshot → PC 스크린샷
7. PC 레이아웃 변경 없음 확인
```
