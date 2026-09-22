"""Local HTTP API. Importing this package does not import pywebview."""

from manga_tagger.api.app import create_app, enqueue_startup_scan, serve

__all__ = ["create_app", "enqueue_startup_scan", "serve"]
