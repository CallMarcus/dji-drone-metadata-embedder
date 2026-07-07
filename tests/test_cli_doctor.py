"""Doctor output and --install smoke tests (all external calls mocked)."""

import logging

from dji_metadata_embedder import embedder


def test_run_doctor_reports_exiftool_version_and_capability(monkeypatch, caplog):
    monkeypatch.setattr(
        "dji_metadata_embedder.utilities.check_dependencies",
        lambda: (True, []),
    )
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_version", lambda: "12.76"
    )
    monkeypatch.setattr(
        "dji_metadata_embedder.utils.exiftool.exiftool_source", lambda: "PATH"
    )
    with caplog.at_level(logging.INFO):
        embedder.run_doctor()
    text = caplog.text
    assert "12.76" in text
    assert "timed-metadata decode" in text
    assert "UNAVAILABLE" in text
    assert "dji-embed doctor --install exiftool" in text


def test_run_doctor_missing_exiftool_still_reports(monkeypatch, caplog):
    monkeypatch.setattr(
        "dji_metadata_embedder.utilities.check_dependencies",
        lambda: (False, ["exiftool"]),
    )
    with caplog.at_level(logging.INFO):
        embedder.run_doctor()
    assert "exiftool: MISSING" in caplog.text
