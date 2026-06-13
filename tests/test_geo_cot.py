import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pytest

from dji_metadata_embedder.geo.track import Track, TrackPoint
from dji_metadata_embedder.geo.cot import track_to_cot

_BASE = datetime(2024, 7, 2, 22, 31, 0)


def _pt(lat, lon, alt, sec):
    return TrackPoint(
        lat=lat, lon=lon, alt=alt, timestamp="", utc=_BASE + timedelta(seconds=sec)
    )


def _moving_track(n=4, step_sec=0.6):
    # Each point ~0.001 deg north of the previous -> due-north heading.
    pts = [_pt(59.30 + i * 0.001, 18.20, 100.0, i * step_sec) for i in range(n)]
    return Track(name="DJI_0157", points=pts)


def _parse(xml_text):
    return ET.fromstring(xml_text)


def _pli_events(root, cot_type="a-n-A"):
    return [e for e in root if e.get("type") == cot_type]


def _route_events(root):
    return [e for e in root if e.get("type") == "b-m-r"]


def test_output_is_well_formed_events_root():
    root = _parse(track_to_cot(_moving_track()))
    assert root.tag == "events"


def test_interval_downsamples_pli_events():
    track = _moving_track(n=4, step_sec=0.6)  # utc at 0,0.6,1.2,1.8
    # interval 0 keeps every point; interval 1.0 keeps first, 1.2, and last.
    assert len(_pli_events(_parse(track_to_cot(track, interval=0.0)))) == 4
    assert len(_pli_events(_parse(track_to_cot(track, interval=1.0)))) == 3


def test_pli_event_has_utc_time_point_and_stale():
    ev = _pli_events(_parse(track_to_cot(_moving_track())))[0]
    assert ev.get("time") == "2024-07-02T22:31:00Z"
    assert ev.get("start") == ev.get("time")
    assert ev.get("stale") > ev.get("time")  # lexical compare OK for Z-times
    pt = ev.find("point")
    assert pt.get("lat") == "59.3"
    assert pt.get("hae") == "100.0"
    assert pt.get("ce") == "9999999.0"


def test_default_and_override_cot_type():
    assert _pli_events(_parse(track_to_cot(_moving_track())))  # default a-n-A present
    root = _parse(track_to_cot(_moving_track(), cot_type="a-f-A-M-H-Q"))
    assert _pli_events(root, cot_type="a-f-A-M-H-Q")
    assert not _pli_events(root, cot_type="a-n-A")


def test_course_and_speed_derived_for_moving_track():
    # Two points 0.001 deg north, 1s apart -> ~111 m/s due north.
    track = Track(name="t", points=[_pt(0.0, 0.0, 50.0, 0), _pt(0.001, 0.0, 50.0, 1)])
    ev = _pli_events(_parse(track_to_cot(track, interval=0.0)))[0]
    trk = ev.find("./detail/track")
    assert trk is not None
    assert trk.get("course") == "0.0"
    assert abs(float(trk.get("speed")) - 111.2) < 1.0


def test_last_point_omits_track_detail():
    track = Track(name="t", points=[_pt(0.0, 0.0, 50.0, 0), _pt(0.001, 0.0, 50.0, 1)])
    events = _pli_events(_parse(track_to_cot(track, interval=0.0)))
    assert events[-1].find("./detail/track") is None


def test_route_event_links_match_sampled_points():
    root = _parse(track_to_cot(_moving_track(n=3), interval=0.0))
    routes = _route_events(root)
    assert len(routes) == 1
    assert len(routes[0].findall("./detail/link")) == 3


def test_empty_track_yields_no_events():
    root = _parse(track_to_cot(Track(name="t", points=[])))
    assert len(root) == 0


def test_single_point_has_no_route():
    track = Track(name="t", points=[_pt(0.0, 0.0, 50.0, 0)])
    root = _parse(track_to_cot(track))
    assert len(_pli_events(root)) == 1
    assert _route_events(root) == []


def test_track_to_cot_requires_utc():
    # build_track always sets utc; a hand-built point without it must raise a
    # clear error rather than fail cryptically deep in serialization.
    track = Track(name="t", points=[TrackPoint(lat=0.0, lon=0.0, alt=0.0, timestamp="")])
    with pytest.raises(ValueError, match="utc"):
        track_to_cot(track)
