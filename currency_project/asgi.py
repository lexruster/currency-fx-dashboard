"""
ASGI entrypoint – mounts both Django and FastAPI on a single server.

Routes:
  /api/*  → FastAPI  (health, summary)
  /*      → Django   (dashboard)
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "currency_project.settings")
django.setup()

from django.core.asgi import get_asgi_application  # noqa: E402

from fastapi_app.main import app as fastapi_app  # noqa: E402

django_app = get_asgi_application()


async def application(scope, receive, send):
    """Root ASGI application that dispatches by path prefix."""
    if scope["type"] in ("http", "websocket"):
        path: str = scope.get("path", "/")
        if path.startswith("/api"):
            # Strip /api prefix so FastAPI sees /health, /summary
            scope = dict(scope, path=path[4:] or "/", root_path=scope.get("root_path", "") + "/api")
            await fastapi_app(scope, receive, send)
            return
    await django_app(scope, receive, send)
