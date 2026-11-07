"""ASGI entry point for the local dashboard."""

from polaris.web.api import create_app

app = create_app()
