---
name: deploy
description: Cloud Run 배포 — tsc 검증 → git 커밋 → 푸시 → deploy.sh 실행
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
---

# 배포 프로세스 (Cloud Run)

## 실행 순서

### 1. admin-web TypeScript 검증
```bash
cd admin-web && npx tsc --noEmit
```
- 실패 시 **즉시 중단** — 타입 오류 수정 후 재시도

### 2. Python 테스트 (있는 경우)
```bash
python -m pytest tests/ -v --tb=short
```
- 실패 시 **즉시 중단**

### 3. Git 커밋 (변경사항 있을 때만)
```bash
git status
git add <변경된 파일>
git commit -m "feat/fix/chore: 변경 내용"
```

### 4. Git 푸시
```bash
git push origin main
```
- 충돌 발생 시 **즉시 중단** — 사용자에게 보고

### 5. Cloud Run 배포
```bash
./deploy.sh
```
- `GCP_PROJECT_ID`, `SLACK_BOT_TOKEN` 등 필수 환경변수 `.env`에 설정 필요
- 배포 후 Service URL 확인 및 Slack Interactive URL 업데이트 필요 여부 확인

## 배포 후 확인
```bash
# 서비스 상태 확인
gcloud run services describe gmail-notifier --region=asia-northeast3

# 로그 확인
gcloud run services logs read gmail-notifier --region=asia-northeast3 --limit=50
```

## 주의사항
- service-account-key.json 커밋 절대 금지
- .env 파일 커밋 절대 금지
- Secret Manager에 시크릿 등록 → deploy.sh가 자동 처리
