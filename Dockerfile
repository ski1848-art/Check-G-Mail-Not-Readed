# ─────────────────────────────────────────────────────
# Gmail Important Mail Notifier - Docker 이미지
#
# [빌드] docker build -t gmail-notifier .
# [실행] docker run -p 8080:8080 --env-file .env gmail-notifier
#
# [구조]
#   Python 3.11 slim → pip install → app/ + config/ 복사
#   gunicorn으로 Flask 앱 실행 (워커 1, 스레드 8)
#
# [Cloud Run 배포 시]
#   - 인증: 메타데이터 서버 자동 인증 (서비스 계정 키 불필요)
#   - 포트: PORT 환경변수 (기본 8080)
#   - 시크릿: GOOGLE_APPLICATION_CREDENTIALS는 Secret Manager에서 주입
# ─────────────────────────────────────────────────────

# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY config/ ./config/

# Create empty state file with valid JSON
RUN echo '{"processed": {}, "last_fetched": null}' > state.json

# non-root 사용자로 실행 (보안)
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --ingroup appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Cloud Run uses PORT env var)
ENV PORT=8080
EXPOSE 8080

# Cloud Run provides credentials via metadata server, no need for key file
# Use gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app.main:app

