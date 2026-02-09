FROM python:3.11-slim

# Install systemd/journalctl for reading journal logs
RUN apt-get update && apt-get install -y --no-install-recommends \
    systemd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OLLAMA_URL=http://wopr-ollama:11434
ENV AI_ENGINE_DB=/data/ai_engine.db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
