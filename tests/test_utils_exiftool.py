from dji_metadata_embedder.utils.exiftool import (
    EXIFTOOL_BASELINE,
    decode_floor,
    describe_decode_capability,
    exiftool_exe,
    version_key,
)


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


def test_version_key_orders_numerically():
    # "13.5" is older than "13.39" — numeric, not lexicographic.
    assert version_key("13.5") < version_key("13.39")
    assert version_key("12.76") < version_key("13.05")
    assert version_key("13.59") > version_key("13.52")
    assert version_key("garbage") == (0, 0)


def test_decode_floor_baseline_for_unknown_schema():
    assert decode_floor(None) == EXIFTOOL_BASELINE
    assert decode_floor("djmd") == EXIFTOOL_BASELINE
    assert decode_floor("dvtm_SomeFutureModel.proto") == EXIFTOOL_BASELINE


def test_decode_floor_matches_known_schemas():
    # probe() returns e.g. "dvtm_Air3s.proto;model_name:FC9113;..."
    assert decode_floor("dvtm_Air3s.proto;model_name:FC9113") == "13.39"
    assert decode_floor("dvtm_Mini5Pro.proto") == "13.52"
    assert decode_floor("dvtm_NEO.proto") == "13.35"


def test_describe_decode_capability_unavailable_below_baseline():
    text = describe_decode_capability("12.76")
    assert text.startswith("UNAVAILABLE")
    assert "12.76" in text and "13.05" in text
    assert "dji-embed doctor --install exiftool" in text


def test_describe_decode_capability_limited_between_floors():
    text = describe_decode_capability("13.20")
    assert text.startswith("LIMITED")
    assert "Air 3S" in text and "13.39" in text
    assert "dji-embed doctor --install exiftool" in text


def test_describe_decode_capability_ok_at_pin():
    text = describe_decode_capability("13.59")
    assert text.startswith("OK")
    assert "covers all supported models" in text
