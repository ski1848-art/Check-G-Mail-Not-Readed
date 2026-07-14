---
name: restart-server
description: admin-web 개발 서버 재시작 — 포트 2222 정리 + 캐시 삭제 + npm run dev
user-invocable: true
allowed-tools: Bash
---

# 서버 재시작 (admin-web)

```bash
# 1. 기존 프로세스 종료
lsof -ti:2222 | xargs kill -9 2>/dev/null
pkill -f "next dev" 2>/dev/null

# 2. 대기
sleep 2

# 3. 캐시 삭제
rm -rf admin-web/.next

# 4. 서버 시작
cd admin-web && npm run dev
```

> 포트: 2222 (admin-web/package.json에서 `next dev -p 2222` 지정)

Flask 백엔드 재시작이 필요한 경우:
```bash
# Flask 개발 서버
cd /path/to/project && python -m flask run --port 5000
# 또는
python app/main.py
```
