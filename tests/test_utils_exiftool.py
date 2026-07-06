from dji_metadata_embedder.utils.exiftool import exiftool_exe


def test_defaults_to_path_exiftool(monkeypatch):
    monkeypatch.delenv("DJIEMBED_EXIFTOOL_PATH", raising=False)
    assert exiftool_exe() == "exiftool"


def test_env_override_used_when_it_exists(monkeypatch, tmp_path):
    exe = tmp_path / "exiftool.exe"
    exe.write_text("stub")
    monkeypatch.setenv("DJIEMBED_EXIFTOOL_PATH", str(exe))
    assert exiftool_exe() == str(exe)


def test_env_override_ignored_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("DJIEMBED_EXIFTOOL_PATH", str(tmp_path / "nope"))
    assert exiftool_exe() == "exiftool"


def test_mp4_telemetry_and_photomap_share_the_resolver():
    # The two ExifTool call sites resolve through the one public helper.
    from dji_metadata_embedder import mp4_telemetry
    from dji_metadata_embedder.geo import photomap

    assert mp4_telemetry._exiftool_exe is exiftool_exe
    assert photomap.exiftool_exe is exiftool_exe
