"""Gunicorn configuration for WOPR SSH CA Service."""

bind = "127.0.0.1:9444"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
