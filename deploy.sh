#!/bin/bash
# Gmail Important Mail Notifier - Cloud Run Deployment Script

set -e

# Load .env file if it exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-asia-northeast3}"
SERVICE_NAME="gmail-notifier"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "========================================="
echo "Gmail Notifier - Cloud Run Deployment"
echo "========================================="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Check if required env vars are set
if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo "Error: SLACK_BOT_TOKEN is not set"
    exit 1
fi

if [ -z "$SLACK_SIGNING_SECRET" ]; then
    echo "Warning: SLACK_SIGNING_SECRET is not set"
    echo "You must set this after deployment for Slack interactive messages to work"
    SLACK_SIGNING_SECRET="CONFIGURE_AFTER_DEPLOYMENT"
fi

if [ -z "$LLM_API_KEY" ]; then
    echo "Error: LLM_API_KEY is not set"
    exit 1
fi

if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Error: GOOGLE_APPLICATION_CREDENTIALS file not found"
    exit 1
fi

# Build the container image
echo "Building container image..."
gcloud builds submit --tag ${IMAGE_NAME} --project ${PROJECT_ID}

# Create/Update Secret in Secret Manager for service account key
echo "Uploading service account key to Secret Manager..."
gcloud secrets create gmail-notifier-sa-key \
    --data-file="${GOOGLE_APPLICATION_CREDENTIALS}" \
    --project ${PROJECT_ID} \
    || gcloud secrets versions add gmail-notifier-sa-key \
    --data-file="${GOOGLE_APPLICATION_CREDENTIALS}" \
    --project ${PROJECT_ID}

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --no-allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 540 \
    --set-env-vars SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN}" \
    --set-env-vars SLACK_SIGNING_SECRET="${SLACK_SIGNING_SECRET}" \
    --set-env-vars LLM_API_KEY="${LLM_API_KEY}" \
    --set-env-vars ADMIN_EMAIL="ski1848@hotseller.co.kr" \
    --set-env-vars ROUTING_SOURCE="firestore" \
    --set-env-vars FIRESTORE_PROJECT_ID="${PROJECT_ID}" \
    --set-env-vars ROUTING_CACHE_TTL_SEC="60" \
    --set-env-vars AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    --set-env-vars AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    --set-env-vars AWS_REGION="${AWS_REGION:-us-east-1}" \
    --set-env-vars BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID}" \
    --set-env-vars LEARNING_ENABLED="true" \
    --set-secrets GOOGLE_APPLICATION_CREDENTIALS=gmail-notifier-sa-key:latest \
    --service-account="gmail-notifier-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "Service URL: ${SERVICE_URL}"
echo ""

# Add policy binding to allow /slack/interactive endpoint public access
echo "Configuring /slack/interactive endpoint for public access..."

# Try conditional policy first (Cloud Run doesn't fully support path-based conditions, so this will likely fail)
if gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --member="principalSet://goog/public:all" \
    --role="roles/run.invoker" \
    --condition='resource.name.startsWith("projects/_/locations/'"${REGION}"'/services/'"${SERVICE_NAME}"'/routes/slack")' 2>/dev/null; then
    echo "✅ Conditional IAM policy applied successfully"
else
    echo "⚠️ Conditional IAM policy failed (expected). Adding service-level public access..."
    # Fallback: Make entire service public (Slack signature verification ensures security)
    gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
        --region=${REGION} \
        --project=${PROJECT_ID} \
        --member="allUsers" \
        --role="roles/run.invoker"
    echo "✅ Service-level public access configured"
    echo "   Note: Slack signature verification in code ensures security"
fi

echo ""
echo "Next steps:"
echo "1. Set Slack Interactive URL:"
echo "   ${SERVICE_URL}/slack/interactive"
echo ""
echo "2. Create Cloud Scheduler job:"
echo "   gcloud scheduler jobs create http ${SERVICE_NAME}-job \\"
echo "     --location=${REGION} \\"
echo "     --schedule='*/5 * * * *' \\"
echo "     --uri=${SERVICE_URL}/run-batch \\"
echo "     --http-method=POST \\"
echo "     --oidc-service-account-email=<YOUR_SA_EMAIL>"
echo ""
echo "3. Test the endpoint:"
echo "   curl -X POST ${SERVICE_URL}/run-batch \\"
echo "     -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\""
echo "========================================="


