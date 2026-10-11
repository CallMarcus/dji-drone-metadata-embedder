import json
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

import pytest
from click.testing import CliRunner

from dji_metadata_embedder import cli as cli_mod
from dji_metadata_embedder.cli import _timeline_output, main
from dji_metadata_embedder.geo import timeline as tl
from dji_metadata_embedder.geo.clipprobe import ClipFacts
from tests._series import series, write_srt


def _facts(path):
    return ClipFacts(
        path=path,
        rate=Fraction(30000, 1001),
        frames=600,
        width=3840,
        height=2160,
        has_audio=False,
        created_utc=None,
        tc_start=None,
        schema=None,
    )


@pytest.fixture
def footage(tmp_path, monkeypatch):
    folder = tmp_path / "Alps"
    folder.mkdir()
    (folder / "DJI_0001.MP4").write_bytes(b"")
    write_srt(folder / "DJI_0001.SRT", series(20, with_dt=True))
    monkeypatch.setattr(tl, "exiftool_available", lambda: True)
    monkeypatch.setattr(tl, "probe_clip", _facts)
    return folder


def _events(res):
    return [json.loads(line) for line in res.stdout.splitlines() if line]


def test_writes_a_timeline_next_to_the_clips(footage):
    res = CliRunner().invoke(main, ["timeline", str(footage)])
    assert res.exit_code == 0, res.output
    root = ET.fromstring((footage / "Alps.fcpxml").read_bytes())
    assert len(list(root.iter("asset-clip"))) == 1
    assert any(m.get("value").startswith("Steady") for m in root.iter("marker"))
    assert "Timeline written" in res.output


def test_jsonl_contract(footage):
    res = CliRunner().invoke(main, ["timeline", str(footage), "--progress", "jsonl"])
    assert res.exit_code == 0, res.output
    events = _events(res)
    assert events[0]["event"] == "start" and events[-1]["event"] == "result"
    summary = events[-1]["summary"]
    assert set(summary) == {
        "clips",
        "placed",
        "omitted",
        "markers",
        "gimbal",
        "slowmo_clips",
    }
    assert summary["placed"] == 1 and summary["markers"]["steady"] == 1
    assert events[-1]["outputs"] == [str((footage / "Alps.fcpxml").resolve())]


def test_refuses_to_overwrite_a_foreign_timeline(footage):
    foreign = footage / "Alps.fcpxml"
    foreign.write_text(
        '<?xml version="1.0"?><fcpxml version="1.10"/>', encoding="utf-8"
    )
    res = CliRunner().invoke(main, ["timeline", str(footage)])
    assert res.exit_code == 2 and "was not written by dji-embed" in res.output
    assert foreign.read_text(encoding="utf-8").endswith('<fcpxml version="1.10"/>')


def test_replaces_its_own_timeline(footage):
    runner = CliRunner()
    assert runner.invoke(main, ["timeline", str(footage)]).exit_code == 0
    assert runner.invoke(main, ["timeline", str(footage)]).exit_code == 0


def test_output_must_be_fcpxml(footage, tmp_path):
    res = CliRunner().invoke(
        main, ["timeline", str(footage), "-o", str(tmp_path / "t.xml")]
    )
    assert res.exit_code == 2


def test_upper_case_suffix_is_accepted(footage, tmp_path):
    res = CliRunner().invoke(
        main, ["timeline", str(footage), "-o", str(tmp_path / "T.FCPXML")]
    )
    assert res.exit_code == 0, res.output


def test_output_directory_gets_the_default_name(footage, tmp_path):
    outdir = tmp_path / "out"
    outdir.mkdir()
    assert (
        CliRunner()
        .invoke(main, ["timeline", str(footage), "-o", str(outdir)])
        .exit_code
        == 0
    )
    assert (outdir / "Alps.fcpxml").is_file()


def test_a_single_file_is_rejected(footage):
    assert (
        CliRunner().invoke(main, ["timeline", str(footage / "DJI_0001.MP4")]).exit_code
        == 2
    )


def test_unknown_moment_kind_is_rejected(footage):
    res = CliRunner().invoke(
        main, ["timeline", str(footage), "--moments", "steady,orbit"]
    )
    assert res.exit_code == 2 and "orbit" in res.output


def test_moments_filter(footage):
    res = CliRunner().invoke(
        main, ["timeline", str(footage), "--moments", "rise", "--progress", "jsonl"]
    )
    assert _events(res)[-1]["summary"]["markers"]["steady"] == 0


def test_empty_folder_exits_1(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "exiftool_available", lambda: True)
    res = CliRunner().invoke(main, ["timeline", str(tmp_path)])
    assert res.exit_code == 1 and ".LRF" in res.output


def test_drive_root_gets_a_default_name():
    assert _timeline_output(Path(Path.cwd().anchor), None).name == "timeline.fcpxml"


def test_unwritable_output_is_a_clean_error(footage, monkeypatch):  # Review Focus 5
    def boom(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(cli_mod, "write_fcpxml", boom)
    res = CliRunner().invoke(main, ["timeline", str(footage)])
    assert res.exit_code == 1 and "Could not write" in res.output
    res = CliRunner().invoke(main, ["timeline", str(footage), "--progress", "jsonl"])
    assert res.exit_code == 1 and _events(res)[-1]["event"] == "error"
