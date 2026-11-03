"""Production entry point: serve the Django app with Waitress.

    .venv\\Scripts\\python serve.py

Settings come from .env (see .env.example).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from waitress import serve

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from core.wsgi import application  # noqa: E402  (needs the env loaded first)

if __name__ == "__main__":
    host = os.environ.get("WAITRESS_HOST", "127.0.0.1")
    proxy = {}
    if host == "127.0.0.1":
        # Behind IIS: trust its X-Forwarded-* headers so Django sees the real scheme, host and client IP.
        proxy = dict(
            trusted_proxy="127.0.0.1",
            trusted_proxy_headers={"x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"},
            clear_untrusted_proxy_headers=True,
        )
    serve(
        application,
        host=host,
        port=int(os.environ.get("WAITRESS_PORT", "8000")),
        threads=int(os.environ.get("WAITRESS_THREADS", "8")),
        # Windows select() handles at most ~512 sockets; above that Waitress crashes.
        connection_limit=min(int(os.environ.get("WAITRESS_CONNECTION_LIMIT", "400")), 500),
        channel_timeout=int(os.environ.get("WAITRESS_CHANNEL_TIMEOUT", "30")),
        ident="faculty-evaluation",
        **proxy,
    )
