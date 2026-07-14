# Playwright 모바일 검증 절차

모바일 UI 수정 후 반드시 이 절차를 실행하여 검증한다.

## 1. 모바일 뷰포트 검증

```
mcp__playwright__browser_resize(375, 812)
mcp__playwright__browser_navigate(대상 URL)
mcp__playwright__browser_take_screenshot(fullPage=true, filename="mobile-verify.png")
```

## 2. 텍스트 오버플로 자동 탐지

```javascript
// browser_evaluate로 실행
() => {
  const issues = [];
  document.querySelectorAll('*').forEach(el => {
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      const text = el.textContent?.trim().slice(0, 50);
      if (text && text.length > 0) {
        issues.push({
          tag: el.tagName,
          class: el.className?.toString().slice(0, 80),
          text: text,
          scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth,
          overflow: el.scrollWidth - el.clientWidth
        });
      }
    }
  });
  return issues.filter(i => i.overflow > 5).slice(0, 20);
}
```

결과가 빈 배열이 아니면 오버플로 문제 있음 → 수정 필요.

## 3. PC 레이아웃 보호 검증

```
mcp__playwright__browser_resize(1920, 1080)
mcp__playwright__browser_take_screenshot(filename="desktop-verify.png")
```

모바일 수정 전 PC 스크린샷과 비교하여 레이아웃 변경 없음 확인.

## 4. 체크 항목

- [ ] 모바일: 가로 스크롤 없음
- [ ] 모바일: 텍스트 글자별 줄바꿈 없음
- [ ] 모바일: 숫자 컨테이너 밖 오버플로 없음
- [ ] 모바일: 차트 라벨 겹침 없음
- [ ] PC: 레이아웃 변경 없음
- [ ] PC: 숨긴 컬럼이 정상 표시됨
- [ ] PC: 필터 접기 버튼 안 보임
