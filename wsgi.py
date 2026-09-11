"""Production WSGI entry point for Gunicorn."""
from app import app

__all__ = ["app"]
