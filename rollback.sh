#!/bin/bash
# ─────────────────────────────────────────────────────
# Token Watcher v2 롤백 스크립트
#
# 문제 발생 시 이전 리비전(Bedrock 직접 호출 전용)으로 즉시 롤백
#
# [사용법]
#   chmod +x rollback.sh && ./rollback.sh
#
# [롤백 대상]
#   gmail-notifier-00095-ccn (Token Watcher 제거, Bedrock 직접만 사용)
# ─────────────────────────────────────────────────────

set -e

PROJECT_ID="${GCP_PROJECT_ID:-gmail-notifier-480807}"
REGION="${GCP_REGION:-asia-northeast3}"
SERVICE_NAME="gmail-notifier"
ROLLBACK_REVISION="gmail-notifier-00095-ccn"

echo "========================================="
echo "Gmail Notifier - ROLLBACK"
echo "========================================="
echo "Rolling back to: ${ROLLBACK_REVISION}"
echo "(Bedrock 직접 호출 전용, Token Watcher 없음)"
echo ""

gcloud run services update-traffic ${SERVICE_NAME} \
    --to-revisions=${ROLLBACK_REVISION}=100 \
    --region=${REGION} \
    --project=${PROJECT_ID}

echo ""
echo "========================================="
echo "Rollback Complete!"
echo "Active revision: ${ROLLBACK_REVISION}"
echo "========================================="
