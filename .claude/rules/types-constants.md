---
paths:
  - "admin-web/lib/**/*.ts"
  - "admin-web/types/**/*.ts"
---

# 타입/상수 규칙 (admin-web TypeScript)

- 새 타입 추가 시 기존 패턴 따르기
- 하드코딩 금지 → `admin-web/lib/utils.ts` 또는 별도 constants 파일에서 import
- 상수 배열은 `as const` 사용
- Firebase/Firestore 관련 타입은 `admin-web/lib/` 하위에 정의
