#!/bin/bash
# ─────────────────────────────────────────────────────
# Gmail Notifier Admin Web - Cloud Run 배포 스크립트
#
# [사전 조건]
#   .env에 아래 항목 추가 필요:
#     NEXTAUTH_SECRET=<랜덤 문자열, openssl rand -hex 32>
#     GOOGLE_CLIENT_ID=<Google OAuth 클라이언트 ID>
#     GOOGLE_CLIENT_SECRET=<Google OAuth 클라이언트 시크릿>
#     ALLOWED_EMAIL_DOMAIN=hotseller.co.kr
#     ADMIN_EMAILS=ski1848@hotseller.co.kr
# ─────────────────────────────────────────────────────

set -e

if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-asia-northeast3}"
SERVICE_NAME="gmail-notifier-admin"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
BACKEND_URL="https://gmail-notifier-5q5uol4lda-du.a.run.app"

echo "========================================="
echo "Gmail Notifier Admin Web - Cloud Run 배포"
echo "========================================="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# 필수 값 체크
if [ -z "$NEXTAUTH_SECRET" ]; then
    echo "Error: NEXTAUTH_SECRET 미설정. 아래 명령으로 생성 후 .env에 추가:"
    echo "  openssl rand -hex 32"
    exit 1
fi

if [ -z "$GOOGLE_CLIENT_ID" ] || [ -z "$GOOGLE_CLIENT_SECRET" ]; then
    echo "Error: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET 미설정"
    echo "  GCP Console > API 및 서비스 > OAuth 2.0 클라이언트에서 발급"
    exit 1
fi

# 이미지 빌드 (admin-web 디렉터리 기준)
echo "Building admin-web image..."
gcloud builds submit ./admin-web --tag ${IMAGE_NAME} --project ${PROJECT_ID}

# Cloud Run 배포
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --set-env-vars NEXTAUTH_SECRET="${NEXTAUTH_SECRET}" \
    --set-env-vars GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID}" \
    --set-env-vars GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET}" \
    --set-env-vars FIRESTORE_PROJECT_ID="${PROJECT_ID}" \
    --set-env-vars ALLOWED_EMAIL_DOMAIN="${ALLOWED_EMAIL_DOMAIN:-hotseller.co.kr}" \
    --set-env-vars ADMIN_EMAILS="${ADMIN_EMAILS:-ski1848@hotseller.co.kr}" \
    --set-env-vars FLASK_SERVICE_URL="${BACKEND_URL}" \
    --set-env-vars GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64="${GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64}"

# 배포된 URL 확인
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo ""
echo "========================================="
echo "배포 완료!"
echo "Admin Web URL: ${SERVICE_URL}"
echo ""
echo "⚠️  NEXTAUTH_URL을 실제 URL로 업데이트 후 재배포 필요:"
echo "  .env에 추가: NEXTAUTH_URL=${SERVICE_URL}"
echo "  그 다음: ./deploy-admin.sh"
echo ""
echo "⚠️  Google OAuth 리디렉션 URI 추가 필요:"
echo "  ${SERVICE_URL}/api/auth/callback/google"
echo "========================================="
