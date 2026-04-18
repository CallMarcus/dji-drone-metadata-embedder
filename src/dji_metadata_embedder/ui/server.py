"""Flask application and local HTTP runner for the dji-embed UI."""

from __future__ import annotations

import json
import logging
import secrets
import socket
import sys
import webbrowser
from pathlib import Path
from typing import Any, Callable

try:
    from flask import Flask, Response, abort, g, jsonify, render_template, request, stream_with_context
except ImportError:  # pragma: no cover - exercised at runtime via CLI
    Flask = None  # type: ignore[assignment]

from .. import __version__


logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent
_COOKIE_NAME = "djiembed_token"
_PUBLIC_PREFIXES = ("/static/",)
_PUBLIC_PATHS = frozenset({"/healthz", "/sw.js"})
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

    @app.route("/sw.js")
    def _service_worker():
        # Served from root so its scope covers the whole origin.
        return app.send_static_file("sw.js")

    @app.route("/")
    def _home():
        return render_template("index.html", token=token)

    @app.route("/api/doctor")
    def _api_doctor():
        from ..utilities import check_dependencies, get_tool_versions
        from ..utils import system_info

        try:
            sys_info = system_info.get_system_summary()
        except Exception as exc:  # defensive - system_info shells out
            sys_info = {"error": str(exc)}
        versions = get_tool_versions()
        deps_ok, missing = check_dependencies()
        return jsonify(
            {
                "app_version": __version__,
                "system": sys_info,
                "tools": versions,
                "dependencies_ok": deps_ok,
                "missing": missing,
            }
        )

    @app.route("/api/recent-folders")
    def _api_recent_folders():
        from . import state

        return jsonify({"folders": state.get_recent_folders()})

    @app.route("/api/check", methods=["POST"])
    def _api_check():
        from ..metadata_check import check_metadata

        body = request.get_json(silent=True) or {}
        path = (body.get("path") or "").strip()
        if not path:
            return jsonify({"error": "path is required"}), 400
        target = Path(path).expanduser()
        if not target.exists():
            return jsonify({"error": f"Not found: {path}"}), 400
        result = check_metadata(target)
        return jsonify({"path": str(target), "metadata": result})

    @app.route("/api/convert", methods=["POST"])
    def _api_convert():
        from ..telemetry_converter import (
            extract_telemetry_to_csv,
            extract_telemetry_to_gpx,
        )

        body = request.get_json(silent=True) or {}
        srt = (body.get("srt") or "").strip()
        fmt = (body.get("format") or "").strip().lower()
        if not srt:
            return jsonify({"error": "srt is required"}), 400
        if fmt not in {"gpx", "csv"}:
            return jsonify({"error": "format must be 'gpx' or 'csv'"}), 400
        srt_path = Path(srt).expanduser()
        if not srt_path.is_file():
            return jsonify({"error": f"SRT file not found: {srt}"}), 400

        output = (body.get("output") or "").strip()
        output_path = Path(output).expanduser() if output else None
        try:
            if fmt == "gpx":
                result = extract_telemetry_to_gpx(srt_path, output_path)
            else:
                result = extract_telemetry_to_csv(srt_path, output_path)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify({"output": str(result), "format": fmt})

    @app.route("/api/validate", methods=["POST"])
    def _api_validate():
        from ..core.validator import validate_directory

        body = request.get_json(silent=True) or {}
        directory = (body.get("directory") or "").strip()
        if not directory:
            return jsonify({"error": "directory is required"}), 400
        target = Path(directory).expanduser()
        if not target.is_dir():
            return jsonify({"error": f"Not a directory: {directory}"}), 400
        try:
            threshold = float(body.get("drift_threshold", 1.0))
        except (TypeError, ValueError):
            return jsonify({"error": "drift_threshold must be a number"}), 400

        from . import state
        state.add_recent_folder(str(target))
        result = validate_directory(target, drift_threshold=threshold)
        return jsonify(result)

    @app.route("/api/jobs/embed", methods=["POST"])
    def _api_start_embed():
        from . import state
        from .jobs import registry, run_subprocess_job

        body = request.get_json(silent=True) or {}
        directory = (body.get("directory") or "").strip()
        if not directory:
            return jsonify({"error": "directory is required"}), 400
        target = Path(directory).expanduser()
        if not target.is_dir():
            return jsonify({"error": f"Not a directory: {directory}"}), 400

        cmd: list[str] = [
            sys.executable,
            "-m",
            "dji_metadata_embedder",
            "embed",
            str(target),
        ]
        if body.get("overwrite"):
            cmd.append("--overwrite")
        elif body.get("output"):
            cmd += ["-o", str(body["output"])]
        if body.get("exiftool"):
            cmd.append("--exiftool")
        if body.get("dat_auto"):
            cmd.append("--dat-auto")
        dat = (body.get("dat") or "").strip()
        if dat:
            cmd += ["--dat", dat]
        redact = (body.get("redact") or "none").strip().lower()
        if redact in {"drop", "fuzz"}:
            cmd += ["--redact", redact]
        if body.get("verbose"):
            cmd.append("-v")

        state.add_recent_folder(str(target))
        job = registry().create("embed")
        run_subprocess_job(job, cmd)
        return jsonify({"job_id": job.id})

    @app.route("/api/jobs/<job_id>")
    def _api_job_status(job_id: str):
        from .jobs import registry

        job = registry().get(job_id)
        if job is None:
            abort(404)
        return jsonify(job.to_json())

    @app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
    def _api_job_cancel(job_id: str):
        from .jobs import registry

        job = registry().get(job_id)
        if job is None:
            abort(404)
        job.request_cancel()
        return jsonify(job.to_json())

    @app.route("/api/jobs/<job_id>/events")
    def _api_job_events(job_id: str):
        from .jobs import registry

        job = registry().get(job_id)
        if job is None:
            abort(404)
        start = int(request.args.get("from", 0))

        def _stream():
            yield "retry: 2000\n\n"
            for event in job.subscribe(start=start):
                yield f"data: {json.dumps(event)}\n\n"

        return Response(
            stream_with_context(_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

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
