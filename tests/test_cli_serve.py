from click.testing import CliRunner

from dji_metadata_embedder import cli as cli_mod
from dji_metadata_embedder.cli import main


def test_serve_missing_page_is_clean_error(tmp_path):
    res = CliRunner().invoke(main, ["serve", str(tmp_path)])
    assert res.exit_code != 0
    assert "photomap.html not found" in res.output
    assert "--page" in res.output


def test_serve_defaults(tmp_path, monkeypatch):
    (tmp_path / "photomap.html").write_text("<p>map</p>", encoding="utf-8")
    seen: dict = {}

    def fake_serve(directory, page, **kwargs):
        seen["page"] = page
        seen.update(kwargs)

    monkeypatch.setattr(cli_mod, "serve_directory", fake_serve)
    res = CliRunner().invoke(main, ["serve", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert seen["page"] == "photomap.html"
    assert seen["open_browser"] is True
    assert seen["bare_url"] is False
    assert seen["stop_on_stdin_eof"] is False


def test_serve_wrapper_flags_pass_through(tmp_path, monkeypatch):
    (tmp_path / "flightmap.html").write_text("<p>map</p>", encoding="utf-8")
    seen: dict = {}

    def fake_serve(directory, page, **kwargs):
        seen["page"] = page
        seen.update(kwargs)

    monkeypatch.setattr(cli_mod, "serve_directory", fake_serve)
    res = CliRunner().invoke(main, [
        "serve", str(tmp_path), "--page", "flightmap.html",
        "--no-browser", "--url-only", "--exit-with-stdin",
    ])
    assert res.exit_code == 0, res.output
    assert seen["page"] == "flightmap.html"
    assert seen["open_browser"] is False
    assert seen["bare_url"] is True
    assert seen["stop_on_stdin_eof"] is True
