import subprocess
from click.testing import CliRunner

from dji_metadata_embedder.cli import main
from dji_metadata_embedder import __version__
import dji_metadata_embedder.utilities as utils


def test_version_shows_tool_versions(monkeypatch):
    def fake_run(cmd, capture_output, text, check, shell=False):
        if cmd[0] == "ffmpeg":
            return subprocess.CompletedProcess(
                cmd, 0, stdout="ffmpeg version 6.1\n", stderr=""
            )
        if cmd[0] == "exiftool":
            return subprocess.CompletedProcess(cmd, 0, stdout="12.34\n", stderr="")
        raise FileNotFoundError

    monkeypatch.setattr(utils.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    output = result.output.strip().splitlines()
    assert output[0] == f"dji-embed {__version__}"
    assert "ffmpeg version 6.1" in output[1]
    assert "exiftool 12.34" in output[2]
