"""Thin re-export for gunicorn compatibility (ExecStart references app:app)."""

from api.main import app  # noqa: F401
