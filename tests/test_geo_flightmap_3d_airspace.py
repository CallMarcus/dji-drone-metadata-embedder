"""3D map embedding of the --airspace overlay (#424) — template level."""
from datetime import datetime, timedelta

from dji_metadata_embedder.geo.flightmap3d_html import flights_to_3d_html
from dji_metadata_embedder.geo.track import Track, TrackPoint


def _flight() -> Track:
    t0 = datetime(2026, 6, 15, 12, 0, 0)
    return Track(name="DJI_0001", points=[
        TrackPoint(lat=10.0, lon=20.0 + i * 0.0006, alt=100.0 + i,
                   timestamp=f"00:00:{i:02d},000",
                   utc=t0 + timedelta(seconds=i * 10.0))
        for i in range(5)
    ])


def test_3d_html_embeds_airspace_when_given():
    html = flights_to_3d_html(
        [_flight()], "t",
        airspace_json={"zones": [], "notes": [], "covered": True},
    )
    assert 'id="airspace-data"' in html
    assert "airspaceFeatures" in html


def test_3d_html_omits_airspace_by_default():
    html = flights_to_3d_html([_flight()], "t")
    assert 'id="airspace-data"' not in html
    # Not "airspace-volume": the gaze click-arbitration guard names the layer
    # ids in every 3D map's JS (and no-ops when the layers don't exist);
    # airspaceFeatures is defined only by the embedded airspace module.
    assert "airspaceFeatures" not in html


def test_airspace_data_block_escapes_script_breakout():
    html = flights_to_3d_html(
        [_flight()], "t",
        airspace_json={"zones": [], "notes": ["</script><b>x</b>"],
                       "covered": False},
    )
    assert "</script><b>x</b>" not in html
