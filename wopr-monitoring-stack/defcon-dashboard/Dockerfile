# WOPR DEFCON ONE Dashboard
# Custom monitoring frontend with CRT terminal aesthetic

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 wopr && chown -R wopr:wopr /app
USER wopr

EXPOSE 8088

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8088"]
