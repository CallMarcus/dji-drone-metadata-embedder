"""djmd TimeStamp is the real recording clock (slow-motion clips): it must
reach TelemetrySample.real_s. Coordinates are synthetic."""

from dji_metadata_embedder import mp4_telemetry as mt


def _doc(sample_time, timestamp=None):
    doc = {
        "SampleTime": sample_time,
        "GPSLatitude": 10.0,
        "GPSLongitude": 20.0,
        "AbsoluteAltitude": 100.0,
    }
    if timestamp is not None:
        doc["TimeStamp"] = timestamp
    return doc


def test_djmd_timestamp_maps_to_real_s():
    data = [
        {
            "SourceFile": "x.MP4",
            "Doc1": _doc(0.0, 44.187883),
            "Doc2": _doc(0.0333667, 44.19205),
        }
    ]
    samples, saw = mt._samples_from_exiftool(data)
    assert saw
    assert [s.real_s for s in samples] == [44.187883, 44.19205]


def test_missing_timestamp_leaves_real_s_none():
    data = [{"SourceFile": "x.MP4", "Doc1": _doc(0.0), "Doc2": _doc(0.0333667)}]
    samples, _ = mt._samples_from_exiftool(data)
    assert [s.real_s for s in samples] == [None, None]
