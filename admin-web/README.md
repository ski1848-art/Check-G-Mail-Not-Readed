# Gmail Notifier Admin Web

Gmail Important Mail Notifier를 위한 관리자 콘솔입니다. Slack 사용자 등록, Gmail 계정 매핑, 알림 활성화 상태를 GUI를 통해 관리할 수 있습니다.

## 기술 스택

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **Auth**: NextAuth.js (Google Provider)
- **Database**: Google Cloud Firestore
- **Deployment**: Google Cloud Run

## 주요 기능

- **사용자 관리**: Slack User ID별로 수신할 Gmail 계정들을 관리 (CRUD)
- **실시간 적용**: 수정된 규칙은 Notifier 서비스에서 60초 내에 자동으로 반영 (TTL 캐시)
- **변경 이력**: 모든 규칙 수정 사항을 Audit Log로 기록하여 추적 가능
- **보안**: 특정 도메인 또는 허용된 관리자 이메일만 접근 가능

## 환경변수 설정 (.env.local)

```env
NEXTAUTH_URL=http://localhost:2222
NEXTAUTH_SECRET=your-secret-key

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# 접근 권한 설정
ALLOWED_EMAIL_DOMAIN=company.com
ADMIN_EMAILS=admin1@company.com,admin2@company.com

# Firestore 설정
FIRESTORE_PROJECT_ID=your-project-id
# 로컬 개발 시: GOOGLE_APPLICATION_CREDENTIALS 환경변수가 설정되어 있어야 함
# Cloud Run 배포 시: GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64 사용 권장
GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64=...
```

## 로컬 실행 방법

```bash
cd admin-web
npm install
npm run dev
```

## 배포 방법 (Cloud Run)

1. `GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64`를 포함한 환경변수를 설정합니다.
2. `gcloud runs deploy`를 통해 배포합니다.
   - 포트: 2222
   - 메모리: 512Mi 이상 권장
