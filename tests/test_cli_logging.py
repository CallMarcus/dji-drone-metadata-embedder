"""Logs go to stderr unconditionally (issue #282).

stdout is reserved for real command output — summaries, exported data,
``--progress jsonl`` events — so ``dji-embed <cmd> > file`` never captures
log lines. These tests must run the CLI in a real subprocess: under pytest
the logging plugin already owns the root logger (setup_logging's basicConfig
no-ops) and the conftest rich stub defaults to stderr anyway, so an
in-process test would pass vacuously either way.
"""

import subprocess
import sys

_SRT = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    '<font size="28">FrameCnt: 1, DiffTime: 1000ms\n'
    "2026-06-15 12:00:00.000\n"
    "[latitude: 34.0] [longitude: -84.0] "
    "[rel_alt: 1.000 abs_alt: 100.0]</font>\n"
)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", "from dji_metadata_embedder.cli import main; main()", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_info_logs_go_to_stderr_without_progress(tmp_path):
    (tmp_path / "DJI_0001.SRT").write_text(_SRT, encoding="utf-8")
    proc = _run_cli("flightmap", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    # The RichHandler INFO line ("HTML flight map created: ...") must not
    # interleave with stdout output.
    assert "flight map created" not in proc.stdout.lower()
    assert "flight map created" in proc.stderr.lower()


def test_warning_logs_go_to_stderr_without_progress(tmp_path):
    import os

    # An SRT with absolute datetimes plus a rewritten mtime triggers the
    # aggregated timezone logger.warning in scan_flights (same recipe as the
    # jsonl purity test).
    path = tmp_path / "DJI_0001.SRT"
    path.write_text(_SRT, encoding="utf-8")
    os.utime(path, (946684800.0, 946684800.0))
    proc = _run_cli("flightmap", str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "Timezone auto-detection" not in proc.stdout
    assert "Timezone auto-detection" in proc.stderr
