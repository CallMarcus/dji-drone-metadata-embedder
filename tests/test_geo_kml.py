from pathlib import Path
from xml.etree import ElementTree as ET

from dji_metadata_embedder.geo.kml import convert_to_kml, track_to_kml
from dji_metadata_embedder.geo.track import build_track

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
CLIP = SAMPLES / "air3S" / "clip.SRT"


def test_track_to_kml_is_well_formed_and_has_linestring():
    kml = track_to_kml(build_track(CLIP))
    # Parses as XML (well-formed).
    root = ET.fromstring(kml)
    ns = "{http://www.opengis.net/kml/2.2}"
    coords = root.find(f".//{ns}LineString/{ns}coordinates")
    assert coords is not None
    # KML coordinates are lon,lat,alt tuples.
    first = coords.text.split()[0]
    assert first == "-84.17616,34.270373,302.208"


def test_convert_to_kml_writes_file(tmp_path):
    out = tmp_path / "clip.kml"
    result = convert_to_kml(CLIP, out)
    assert result == out
    assert "<kml" in out.read_text()


def test_kml_includes_footprint_folder():
    from pathlib import Path
    from dji_metadata_embedder.geo.track import build_track
    from dji_metadata_embedder.geo.footprint import build_footprints
    from dji_metadata_embedder.geo.kml import track_to_kml

    samples = Path(__file__).resolve().parents[1] / "samples"
    track = build_track(samples / "air3" / "clip.SRT")
    fps = build_footprints(track, interval=0.0)
    kml = track_to_kml(track, footprints=fps)
    assert "<Folder>" in kml
    assert "Camera footprints" in kml
    assert "clampToGround" in kml


def test_kml_without_footprints_has_no_folder():
    from pathlib import Path
    from dji_metadata_embedder.geo.track import build_track
    from dji_metadata_embedder.geo.kml import track_to_kml

    samples = Path(__file__).resolve().parents[1] / "samples"
    track = build_track(samples / "air3" / "clip.SRT")
    assert "<Folder>" not in track_to_kml(track)
