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

# Expose port (Cloud Run uses PORT env var)
ENV PORT=8080
EXPOSE 8080

# Cloud Run provides credentials via metadata server, no need for key file
# Use gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app.main:app

