"""Flask application and local HTTP runner for the dji-embed UI."""

from __future__ import annotations

import logging
import secrets
import socket
import webbrowser
from pathlib import Path
from typing import Any, Callable

try:
    from flask import Flask, abort, g, render_template, request
except ImportError:  # pragma: no cover - exercised at runtime via CLI
    Flask = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent
_COOKIE_NAME = "djiembed_token"
_PUBLIC_PREFIXES = ("/static/",)
_PUBLIC_PATHS = frozenset({"/healthz"})
_FLASK_INSTALL_HINT = (
    "Flask is not installed. Install the UI extra:\n"
    "    pip install 'dji-drone-metadata-embedder[ui]'"
)


def _require_flask() -> None:
    if Flask is None:
        raise RuntimeError(_FLASK_INSTALL_HINT)


def _is_public(path: str) -> bool:
    return path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _token_matches(candidate: str, expected: str) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate, expected)


def create_app(token: str) -> "Flask":
    """Build the Flask app. ``token`` gates every non-public route."""
    _require_flask()
    app = Flask(
        __name__,
        template_folder=str(_PACKAGE_DIR / "templates"),
        static_folder=str(_PACKAGE_DIR / "static"),
        static_url_path="/static",
    )
    app.config["DJIEMBED_TOKEN"] = token

    @app.before_request
    def _enforce_token() -> Any:
        if _is_public(request.path):
            return None
        query = request.args.get("t", "")
        header = request.headers.get("X-DJIEmbed-Token", "")
        cookie = request.cookies.get(_COOKIE_NAME, "")
        if any(_token_matches(c, token) for c in (query, header, cookie)):
            g.needs_cookie = not _token_matches(cookie, token)
            return None
        abort(403)

    @app.after_request
    def _security_headers(response):
        if getattr(g, "needs_cookie", False):
            response.set_cookie(
                _COOKIE_NAME,
                token,
                httponly=True,
                samesite="Strict",
                secure=False,
            )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @app.route("/healthz")
    def _healthz():
        return {"ok": True}

    @app.route("/")
    def _home():
        return render_template("index.html", token=token)

    return app


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_server(
    host: str = "127.0.0.1",
    port: int | None = None,
    open_browser: bool = True,
    token: str | None = None,
    opener: Callable[[str], bool] | None = None,
) -> None:
    """Start the UI server and block until interrupted."""
    _require_flask()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        logger.warning(
            "UI bound to %s; only 127.0.0.1/localhost are intended for use.", host
        )
    token = token or secrets.token_urlsafe(32)
    port = port or _pick_free_port()
    url = f"http://{host}:{port}/?t={token}"
    app = create_app(token)
    print(f"dji-embed UI ready at {url}")
    print("Local use only — do not expose this server to a network.")
    if open_browser:
        try:
            (opener or webbrowser.open)(url)
        except Exception as exc:  # pragma: no cover - browser launch is best-effort
            logger.warning("Could not open browser automatically: %s", exc)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
