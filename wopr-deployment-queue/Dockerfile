FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN mkdir -p /opt/wopr-deployment-queue/pending \
             /opt/wopr-deployment-queue/approved \
             /opt/wopr-deployment-queue/deployed \
             /opt/wopr-deployment-queue/failed

CMD ["python3", "queue-manager.py"]
