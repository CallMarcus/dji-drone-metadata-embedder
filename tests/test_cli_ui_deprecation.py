"""The legacy Flask web UI is deprecated in favour of the desktop app and
``photomap --serve`` (decided 2026-07; removal in a future minor release)."""

from click.testing import CliRunner

from dji_metadata_embedder.cli import main


def test_ui_help_is_marked_deprecated_with_replacements():
    res = CliRunner().invoke(main, ["ui", "--help"])
    assert res.exit_code == 0
    assert "DEPRECATED" in res.output
    # The help names both replacements so users know where to go.
    assert "desktop app" in res.output
    assert "photomap" in res.output


def test_main_command_listing_flags_ui_as_deprecated():
    res = CliRunner().invoke(main, ["--help"])
    assert res.exit_code == 0
    # Both the hand-written overview and click's generated listing carry the
    # deprecation (the generated label may wrap onto its own line).
    assert "(deprecated)" in res.output
    assert "(DEPRECATED)" in res.output
