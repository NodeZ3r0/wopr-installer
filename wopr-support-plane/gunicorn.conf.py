"""Gunicorn configuration for WOPR Support Gateway."""

import os
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8443")
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
