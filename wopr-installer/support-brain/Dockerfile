# WOPR Support Brain - Docker Configuration
# Central AI service for beacon management and issue resolution

FROM python:3.11-slim

# Set labels
LABEL maintainer="WOPR Team"
LABEL description="WOPR Support Brain - Central AI orchestrator for beacon management"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY models.py .
COPY wopr_support_brain.py .

# Create data directory for SQLite database
RUN mkdir -p /data

# Set default environment variables
ENV PORT=8080
ENV DB_PATH=/data/support_brain.db
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434
ENV MAX_AUTO_FIXES_PER_HOUR=10
ENV HEARTBEAT_TIMEOUT=300
ENV CRITICAL_THRESHOLD=600
ENV NTFY_SERVER=https://ntfy.sh
ENV NTFY_TOPIC=wopr-support
ENV EMAIL_ENABLED=false
ENV DEBUG=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE 8080

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash wopr && \
    chown -R wopr:wopr /app /data

USER wopr

# Run the application
CMD ["python", "-m", "uvicorn", "wopr_support_brain:app", "--host", "0.0.0.0", "--port", "8080"]
