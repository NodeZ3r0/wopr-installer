"""Gunicorn configuration for WOPR Support Gateway."""

bind = "127.0.0.1:8443"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
