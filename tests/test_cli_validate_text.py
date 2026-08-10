"""Text-format ``validate`` report stays legacy-console safe (#477).

On Windows consoles using a legacy code page (cp1252, cp437), any emoji in
the report raised UnicodeEncodeError, which the command's broad exception
handler rebranded as "Validation failed" — hiding the very issue lines the
user ran the command for. The report must therefore stay ASCII-encodable.
"""

from click.testing import CliRunner

from dji_metadata_embedder.cli import ExitCode, main


def _mock_validate_directory(monkeypatch, canned):
    from dji_metadata_embedder.core import validator

    monkeypatch.setattr(
        validator, "validate_directory", lambda directory, drift_threshold: canned
    )


CANNED_WITH_ISSUES = {
    "total_files": 3,
    "valid_pairs": 1,
    "issues": [
        "No SRT file found for DJI_0002.mp4",
        "Drift above threshold in DJI_0001.mp4",
    ],
    "warnings": [],
    "file_analyses": [],
}


def test_validate_text_report_lists_issues(monkeypatch, tmp_path):
    _mock_validate_directory(monkeypatch, CANNED_WITH_ISSUES)
    res = CliRunner().invoke(main, ["validate", str(tmp_path)])
    assert res.exit_code == ExitCode.VALIDATION_ERROR
    assert "Issues found: 2" in res.output
    for issue in CANNED_WITH_ISSUES["issues"]:
        assert f"[!] {issue}" in res.output
    # The failure mode of #477: the handler ate the report entirely.
    assert "Validation failed" not in res.output


def test_validate_text_report_encodes_on_legacy_code_pages(monkeypatch, tmp_path):
    _mock_validate_directory(monkeypatch, CANNED_WITH_ISSUES)
    res = CliRunner().invoke(main, ["validate", str(tmp_path)])
    for codec in ("cp1252", "cp437"):
        res.output.encode(codec)  # raises UnicodeEncodeError on regression
