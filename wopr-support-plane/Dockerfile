FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ ./api/
COPY gunicorn.conf.py .

# Environment configuration
# WOPR_MODE: "lighthouse" (admin dashboard) or "beacon" (support client only)
ENV WOPR_MODE=beacon
ENV GUNICORN_BIND=0.0.0.0:8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "api.main:app"]
