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
