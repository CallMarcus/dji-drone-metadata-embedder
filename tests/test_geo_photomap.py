import json as jsonlib
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from dji_metadata_embedder.geo.photomap import (
    PhotoPoint,
    PhotomapError,
    camera_summary,
    format_exposure,
    photos_to_geojson,
    photos_to_kml,
    points_from_exiftool_json,
    scan_photos,
    write_photos_geojson,
    write_photos_kml,
)

# Shape verified against a real `exiftool -json -n -b` run.
CANNED = [
    {
        "SourceFile": "photos/church2.jpg",
        "GPSLatitude": 60.173047,
        "GPSLongitude": 24.92515,
        "GPSAltitude": 88.1,
        "DateTimeOriginal": "2026:06:15 13:05:10",
        "Model": "FC8482",
        "ISO": 100,
        "ExposureTime": 0.0005,
        "FNumber": 1.7,
        "ThumbnailImage": "base64:/9j/THUMB2",
    },
    {
        "SourceFile": "photos/church1.jpg",
        "GPSLatitude": 60.170278,
        "GPSLongitude": 24.952222,
        "GPSAltitude": 95.3,
        "DateTimeOriginal": "2026:06:15 12:30:45",
        "Model": "FC8482",
        "ISO": 100,
        "ExposureTime": 0.001,
        "FNumber": 1.7,
        # no ThumbnailImage -> pin without preview
    },
    {"SourceFile": "photos/no_gps.jpg", "DateTimeOriginal": "2026:06:15 12:31:00"},
    {"SourceFile": "photos/zero_fix.jpg", "GPSLatitude": 0.0, "GPSLongitude": 0.0},
]


def test_parses_gps_photos_and_skips_the_rest():
    points, skipped = points_from_exiftool_json(CANNED)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]  # sorted
    assert skipped == ["no_gps.jpg", "zero_fix.jpg"]  # sorted
    p = points[0]
    assert p.lat == 60.170278 and p.lon == 24.952222 and p.alt == 95.3
    assert p.timestamp == "2026-06-15 12:30:45"  # EXIF colons -> display dashes
    assert p.model == "FC8482" and p.iso == 100
    assert p.exposure == 0.001 and p.fnum == 1.7


# DJI restarts file numbering per card/session, so a recursive per-location
# archive scan collides on basenames unless names carry their subdirectory.
_RECURSIVE = [
    {"SourceFile": "/scan/root/north/DJI_0001.JPG", "GPSLatitude": 1.0, "GPSLongitude": 2.0},
    {"SourceFile": "/scan/root/south/DJI_0001.JPG", "GPSLatitude": 3.0, "GPSLongitude": 4.0},
]


def test_recursive_root_yields_relative_display_names():
    points, _ = points_from_exiftool_json(_RECURSIVE, root=Path("/scan/root"))
    assert [p.name for p in points] == ["north/DJI_0001.JPG", "south/DJI_0001.JPG"]


def test_no_root_yields_basenames():
    points, _ = points_from_exiftool_json(_RECURSIVE)
    assert [p.name for p in points] == ["DJI_0001.JPG", "DJI_0001.JPG"]


def test_relative_name_falls_back_to_basename_when_outside_root():
    # SourceFile not under the given root (unexpected) -> safe basename.
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "/elsewhere/x.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0}],
        root=Path("/scan/root"),
    )
    assert points[0].name == "x.jpg"


def test_relative_name_normalises_backslash_separators():
    # ExifTool echoes the directory arg's separators; a Windows root uses "\".
    points, _ = points_from_exiftool_json(
        [{"SourceFile": r"C:\scan\root/sub/DJI_0001.JPG",
          "GPSLatitude": 1.0, "GPSLongitude": 2.0}],
        root=Path(r"C:\scan\root"),
    )
    assert points[0].name == "sub/DJI_0001.JPG"


def test_scan_photos_recursive_uses_relative_names(monkeypatch, tmp_path):
    src = [{"SourceFile": f"{tmp_path}/a/DJI_0001.JPG",
            "GPSLatitude": 1.0, "GPSLongitude": 2.0}]
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _Proc(stdout=jsonlib.dumps(src))
    )
    points, _ = scan_photos(tmp_path, recursive=True)
    assert points[0].name == "a/DJI_0001.JPG"


def test_thumbnail_base64_prefix_is_stripped():
    points, _ = points_from_exiftool_json(CANNED)
    by_name = {p.name: p for p in points}
    assert by_name["church2.jpg"].thumbnail_b64 == "/9j/THUMB2"
    assert by_name["church1.jpg"].thumbnail_b64 is None


def test_dng_previewimage_used_when_no_thumbnail():
    # DJI DNGs expose their preview as PreviewImage, not EXIF:ThumbnailImage.
    points, _ = points_from_exiftool_json([{
        "SourceFile": "a.dng", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
        "PreviewImage": "base64:/9j/PREVIEW",
    }])
    assert points[0].thumbnail_b64 == "/9j/PREVIEW"


def test_thumbnail_preferred_over_preview():
    # The small EXIF thumbnail wins over the (potentially large) preview.
    points, _ = points_from_exiftool_json([{
        "SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
        "ThumbnailImage": "base64:/9j/THUMB",
        "PreviewImage": "base64:/9j/PREVIEW",
    }])
    assert points[0].thumbnail_b64 == "/9j/THUMB"


def test_oversized_preview_is_dropped_to_protect_budget():
    from dji_metadata_embedder.geo import photomap as pm
    big = "A" * (pm._MAX_PREVIEW_B64_CHARS + 4)  # valid base64, over the cap
    points, _ = points_from_exiftool_json([{
        "SourceFile": "a.dng", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
        "PreviewImage": "base64:" + big,
    }])
    assert points[0].thumbnail_b64 is None


def test_scan_photos_requests_preview_tag(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _Proc(stdout="[]")

    monkeypatch.setattr(subprocess, "run", fake_run)
    scan_photos(tmp_path)
    assert "-PreviewImage" in seen["args"]


def test_non_base64_thumbnail_is_dropped():
    points, _ = points_from_exiftool_json(
        [{
            "SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
            "ThumbnailImage": 'base64:]]><img src="x">',
        }]
    )
    assert points[0].thumbnail_b64 is None


def test_missing_altitude_is_none():
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0}]
    )
    assert points[0].alt is None  # distinct from a real 0 m fix
    assert points[0].timestamp is None


def test_real_zero_altitude_is_preserved_distinct_from_missing():
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "z.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
          "GPSAltitude": 0.0}]
    )
    assert points[0].alt == 0.0


def test_unparseable_numeric_fields_become_none():
    points, _ = points_from_exiftool_json(
        [{
            "SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
            "ISO": "100, 100", "ExposureTime": "n/a", "FNumber": None,
        }]
    )
    assert points[0].iso is None
    assert points[0].exposure is None
    assert points[0].fnum is None


def test_format_exposure():
    assert format_exposure(0.001) == "1/1000 s"
    assert format_exposure(0.0005) == "1/2000 s"
    assert format_exposure(2.5) == "2.5 s"
    assert format_exposure(None) is None
    assert format_exposure(0) is None
    assert format_exposure(0.7) == "0.7 s"
    assert format_exposure(0.5) == "1/2 s"
    assert format_exposure(0.6) == "0.6 s"


def test_missing_sourcefile_falls_back_to_question_mark():
    points, _ = points_from_exiftool_json([{"GPSLatitude": 1.0, "GPSLongitude": 2.0}])
    assert points[0].name == "?"


def test_camera_summary_joins_available_parts():
    p = PhotoPoint(lat=0, lon=0, alt=0, name="a.jpg", model="FC8482",
                   iso=100, exposure=0.001, fnum=1.7)
    assert camera_summary(p) == "FC8482 · ISO 100 · 1/1000 s · f/1.7"
    bare = PhotoPoint(lat=0, lon=0, alt=0, name="a.jpg")
    assert camera_summary(bare) == ""


class _Proc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_scan_photos_builds_command_and_parses(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        import json as _json
        return _Proc(stdout=_json.dumps(CANNED))

    monkeypatch.setattr(subprocess, "run", fake_run)
    points, skipped = scan_photos(tmp_path)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]
    assert skipped == ["no_gps.jpg", "zero_fix.jpg"]
    args = seen["args"]
    assert args[1:4] == ["-json", "-n", "-b"]
    assert "-r" not in args
    assert "-Composite:GPSLatitude" in args
    assert "-EXIF:ThumbnailImage" in args
    for ext in ("jpg", "jpeg", "dng"):
        i = args.index(ext)
        assert args[i - 1] == "-ext"
    assert args[-1] == str(tmp_path)
    assert seen["kwargs"].get("encoding") == "utf-8"


def test_scan_photos_recursive_adds_r(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _Proc(stdout="[]")

    monkeypatch.setattr(subprocess, "run", fake_run)
    scan_photos(tmp_path, recursive=True)
    assert "-r" in seen["args"]


def test_scan_photos_empty_stdout_means_no_photos(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout=""))
    assert scan_photos(tmp_path) == ([], [])


def test_scan_photos_missing_exiftool_raises_hint(monkeypatch, tmp_path):
    def raise_fnf(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    with pytest.raises(PhotomapError, match="doctor"):
        scan_photos(tmp_path)


def test_scan_photos_hard_failure_raises_stderr(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _Proc(stdout="", stderr="boom", returncode=1),
    )
    with pytest.raises(PhotomapError, match="boom"):
        scan_photos(tmp_path)


def test_scan_photos_bad_json_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout="{nope"))
    with pytest.raises(PhotomapError, match="JSON"):
        scan_photos(tmp_path)


def test_scan_photos_partial_failure_still_parses(monkeypatch, tmp_path):
    import json as _json
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: _Proc(
            stdout=_json.dumps(CANNED), stderr="Error: bad.jpg", returncode=1
        ),
    )
    points, skipped = scan_photos(tmp_path)
    assert [p.name for p in points] == ["church1.jpg", "church2.jpg"]


def test_scan_photos_non_list_json_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(stdout="{}"))
    with pytest.raises(PhotomapError, match="shape"):
        scan_photos(tmp_path)


def _two_points() -> list[PhotoPoint]:
    points, _ = points_from_exiftool_json(CANNED)
    return points


def test_geojson_structure_and_no_thumbnails_by_default():
    data = photos_to_geojson(_two_points())
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    f = data["features"][0]
    assert f["geometry"]["type"] == "Point"
    assert f["geometry"]["coordinates"] == [24.952222, 60.170278, 95.3]  # lon,lat,alt
    assert f["properties"]["name"] == "church1.jpg"
    assert f["properties"]["timestamp"] == "2026-06-15 12:30:45"
    assert f["properties"]["camera"] == "FC8482 · ISO 100 · 1/1000 s · f/1.7"
    assert "thumb" not in f["properties"]
    assert "thumb" not in data["features"][1]["properties"]


def test_geojson_include_thumbnails_opt_in():
    data = photos_to_geojson(_two_points(), include_thumbnails=True)
    by_name = {f["properties"]["name"]: f for f in data["features"]}
    assert by_name["church2.jpg"]["properties"]["thumb"] == "/9j/THUMB2"
    assert "thumb" not in by_name["church1.jpg"]["properties"]  # none available


def test_geojson_empty_points():
    assert photos_to_geojson([]) == {"type": "FeatureCollection", "features": []}


# One photo with EXIF altitude, one without — exercises the alt: float | None split.
_MIXED_ALT = [
    PhotoPoint(lat=1.0, lon=2.0, alt=100.0, name="has_alt.jpg"),
    PhotoPoint(lat=3.0, lon=4.0, alt=None, name="no_alt.jpg"),
]


def test_geojson_omits_altitude_when_missing():
    by_name = {
        f["properties"]["name"]: f for f in photos_to_geojson(_MIXED_ALT)["features"]
    }
    has = by_name["has_alt.jpg"]
    assert has["geometry"]["coordinates"] == [2.0, 1.0, 100.0]
    assert has["properties"]["alt"] == 100.0
    missing = by_name["no_alt.jpg"]
    assert missing["geometry"]["coordinates"] == [4.0, 3.0]  # 2D — no altitude
    assert "alt" not in missing["properties"]


def test_kml_clamps_to_ground_when_altitude_missing():
    root = ET.fromstring(photos_to_kml(_MIXED_ALT, title="t"))
    pms = {
        pm.find(f"{_KML_NS}name").text: pm
        for pm in root.iter(f"{_KML_NS}Placemark")
    }
    has = pms["has_alt.jpg"].find(f"{_KML_NS}Point")
    assert has.find(f"{_KML_NS}altitudeMode").text == "absolute"
    assert has.find(f"{_KML_NS}coordinates").text == "2.0,1.0,100.0"
    missing = pms["no_alt.jpg"].find(f"{_KML_NS}Point")
    assert missing.find(f"{_KML_NS}altitudeMode").text == "clampToGround"
    # altitude is ignored under clampToGround; emit a placeholder 0
    assert missing.find(f"{_KML_NS}coordinates").text == "4.0,3.0,0"


def test_write_photos_geojson(tmp_path):
    out = tmp_path / "photomap.geojson"
    result = write_photos_geojson(_two_points(), out)
    assert result == out
    data = jsonlib.loads(out.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"


_KML_NS = "{http://www.opengis.net/kml/2.2}"


def test_kml_is_wellformed_with_placemark_per_photo():
    kml = photos_to_kml(_two_points(), title="Churches & chapels")
    root = ET.fromstring(kml)  # raises on malformed XML
    doc = root.find(f"{_KML_NS}Document")
    assert doc.find(f"{_KML_NS}name").text == "Churches & chapels"
    placemarks = doc.findall(f"{_KML_NS}Placemark")
    assert [pm.find(f"{_KML_NS}name").text for pm in placemarks] == [
        "church1.jpg", "church2.jpg",
    ]
    coords = placemarks[0].find(f"{_KML_NS}Point/{_KML_NS}coordinates").text
    assert coords == "24.952222,60.170278,95.3"


def test_kml_description_embeds_thumbnail_data_uri():
    kml = photos_to_kml(_two_points(), title="t")
    assert 'data:image/jpeg;base64,/9j/THUMB2' in kml
    root = ET.fromstring(kml)
    descs = [
        pm.find(f"{_KML_NS}description").text
        for pm in root.iter(f"{_KML_NS}Placemark")
    ]
    # church1 has no thumbnail: metadata only, no img tag
    assert "<img" not in descs[0] and "2026-06-15 12:30:45" in descs[0]
    assert "<img" in descs[1]


def test_kml_empty_points():
    root = ET.fromstring(photos_to_kml([], title="empty"))
    assert not list(root.iter(f"{_KML_NS}Placemark"))


def test_write_photos_kml(tmp_path):
    out = tmp_path / "photomap.kml"
    result = write_photos_kml(_two_points(), out, title="t")
    assert result == out
    assert "<kml" in out.read_text(encoding="utf-8")


def test_photomap_install_hint_names_the_doctor_command():
    from dji_metadata_embedder.geo.photomap import _EXIFTOOL_INSTALL_HINT

    assert "dji-embed doctor --install exiftool" in _EXIFTOOL_INSTALL_HINT


# ---------------------------------------------------------------------------
# Original-photo links (#253): the `link` property is opt-in via link_base.
# link_base=None (the default) must leave every output byte-identical, so the
# shareable GeoJSON/HTML never gains fragile file references by accident.


def test_geojson_no_link_property_by_default():
    for f in photos_to_geojson(_two_points())["features"]:
        assert "link" not in f["properties"]


def test_geojson_link_base_empty_links_to_relative_name():
    data = photos_to_geojson(_two_points(), link_base="")
    by_name = {f["properties"]["name"]: f for f in data["features"]}
    assert by_name["church1.jpg"]["properties"]["link"] == "church1.jpg"


def test_geojson_link_preserves_subdirectories_from_recursive_scans():
    pts = [PhotoPoint(lat=1.0, lon=2.0, alt=None, name="card1/DJI_0001.JPG")]
    data = photos_to_geojson(pts, link_base="")
    assert data["features"][0]["properties"]["link"] == "card1/DJI_0001.JPG"


def test_geojson_link_base_relative_folder_prefixes_href():
    pts = [PhotoPoint(lat=1.0, lon=2.0, alt=None, name="a.jpg")]
    # Trailing slash and Windows separators are normalised before joining.
    for base in ("photos/", "photos", "..\\DCIM"):
        data = photos_to_geojson(pts, link_base=base)
        link = data["features"][0]["properties"]["link"]
        assert link == base.replace("\\", "/").rstrip("/") + "/a.jpg"


def test_geojson_link_base_absolute_url():
    pts = [PhotoPoint(lat=1.0, lon=2.0, alt=None, name="a.jpg")]
    data = photos_to_geojson(pts, link_base="https://example.com/photos/")
    assert (
        data["features"][0]["properties"]["link"]
        == "https://example.com/photos/a.jpg"
    )


def test_geojson_link_percent_encodes_name_but_keeps_separators():
    pts = [PhotoPoint(lat=1.0, lon=2.0, alt=None, name='sub dir/a#b"c.jpg')]
    data = photos_to_geojson(pts, link_base="")
    # Each path segment is percent-encoded (space, #, ") but "/" survives so
    # relative subdirectory links still resolve.
    assert data["features"][0]["properties"]["link"] == "sub%20dir/a%23b%22c.jpg"


# ---------------------------------------------------------------------------
# GPano detection (#271): equirectangular panoramas are flagged for a later
# 360 viewer. Detection is opt-in metadata only — it never affects GPS/skip
# logic above.


def test_gpano_equirectangular_sets_is_pano():
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "p.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
          "ProjectionType": "equirectangular"}]
    )
    assert points[0].is_pano is True


def test_gpano_is_case_insensitive():
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "p.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
          "ProjectionType": "Equirectangular"}]
    )
    assert points[0].is_pano is True


def test_missing_or_other_projection_is_not_pano():
    points, _ = points_from_exiftool_json(
        [
            {"SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0},
            {"SourceFile": "b.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
             "ProjectionType": "cylindrical"},
            {"SourceFile": "c.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
             "ProjectionType": 7},
        ]
    )
    assert [p.is_pano for p in points] == [False, False, False]


def test_scan_requests_gpano_projection_tag(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _Proc(stdout="[]")

    monkeypatch.setattr(subprocess, "run", fake_run)
    scan_photos(tmp_path)
    assert "-XMP-GPano:ProjectionType" in seen["args"]


_PANO_POINT = PhotoPoint(lat=1.0, lon=2.0, alt=None, name="pano.jpg", is_pano=True)
_FLAT_POINT = PhotoPoint(lat=1.0, lon=2.0, alt=None, name="flat.jpg")


def test_geojson_pano_property_without_link_base():
    # #283: the pano flag is type metadata, not viewer plumbing — emitted even
    # without links so maps (and GIS consumers) can tell panoramas apart.
    data = photos_to_geojson([_PANO_POINT, _FLAT_POINT])
    by_name = {f["properties"]["name"]: f["properties"] for f in data["features"]}
    assert by_name["pano.jpg"]["pano"] is True
    assert "pano" not in by_name["flat.jpg"]
    assert all("link" not in f["properties"] for f in data["features"])


def test_geojson_pano_property_with_link_base_only_on_panos():
    data = photos_to_geojson([_PANO_POINT, _FLAT_POINT], link_base="")
    by_name = {f["properties"]["name"]: f["properties"] for f in data["features"]}
    assert by_name["pano.jpg"]["pano"] is True
    assert "pano" not in by_name["flat.jpg"]


# ---------------------------------------------------------------------------
# Pano initial view (#309): GPano InitialView* tags are compass-frame; the
# viewer wants yaw relative to the image center (whose heading is
# PoseHeadingDegrees). Attribution (#310): Artist/Copyright become one line.


def _pano_entry(**extra) -> dict:
    e = {"SourceFile": "p.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
         "ProjectionType": "equirectangular"}
    e.update(extra)
    return e


def test_scan_requests_view_and_authorship_tags(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _Proc(stdout="[]")

    monkeypatch.setattr(subprocess, "run", fake_run)
    scan_photos(tmp_path)
    for tag in (
        "-XMP-GPano:PoseHeadingDegrees",
        "-XMP-GPano:InitialViewHeadingDegrees",
        "-XMP-GPano:InitialViewPitchDegrees",
        "-XMP-GPano:InitialHorizontalFOVDegrees",
        "-EXIF:Artist",
        "-EXIF:Copyright",
        "-XMP-dc:Creator",
        "-XMP-dc:Rights",
    ):
        assert tag in seen["args"]


def test_initial_view_heading_maps_to_yaw_relative_to_pose():
    points, _ = points_from_exiftool_json(
        [_pano_entry(InitialViewHeadingDegrees=200.0, PoseHeadingDegrees=180.0)]
    )
    assert points[0].pano_yaw == 20.0


def test_initial_view_yaw_wraps_to_signed_half_turn():
    # 350° vs pose 20° is 30° to the *left*, not 330° to the right.
    points, _ = points_from_exiftool_json(
        [_pano_entry(InitialViewHeadingDegrees=350.0, PoseHeadingDegrees=20.0)]
    )
    assert points[0].pano_yaw == -30.0


def test_initial_view_without_pose_assumes_center_is_north():
    points, _ = points_from_exiftool_json(
        [_pano_entry(InitialViewHeadingDegrees=270.0)]
    )
    assert points[0].pano_yaw == -90.0


def test_initial_view_pitch_clamped_and_fov_sanity_checked():
    points, _ = points_from_exiftool_json([
        _pano_entry(InitialViewPitchDegrees=120.0),
        _pano_entry(SourceFile="q.jpg", InitialHorizontalFOVDegrees=500.0),
        _pano_entry(SourceFile="r.jpg", InitialHorizontalFOVDegrees=90.0),
    ])
    by_name = {p.name: p for p in points}
    assert by_name["p.jpg"].pano_pitch == 90.0
    assert by_name["q.jpg"].pano_hfov is None  # nonsense value dropped
    assert by_name["r.jpg"].pano_hfov == 90.0


def test_view_tags_ignored_on_non_panos():
    points, _ = points_from_exiftool_json(
        [{"SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0,
          "InitialViewHeadingDegrees": 90.0}]
    )
    assert points[0].pano_yaw is None


def test_pano_without_view_tags_has_no_view():
    points, _ = points_from_exiftool_json([_pano_entry()])
    p = points[0]
    assert (p.pano_yaw, p.pano_pitch, p.pano_hfov) == (None, None, None)


def _credit_of(**tags) -> str | None:
    entry = {"SourceFile": "a.jpg", "GPSLatitude": 1.0, "GPSLongitude": 2.0}
    entry.update(tags)
    points, _ = points_from_exiftool_json([entry])
    return points[0].credit


def test_credit_copyright_containing_artist_is_not_repeated():
    assert _credit_of(Artist="Jane Doe",
                      Copyright="© 2026 Jane Doe") == "© 2026 Jane Doe"


def test_credit_joins_distinct_copyright_and_artist():
    assert _credit_of(Artist="Jane Doe",
                      Copyright="All rights reserved") == \
        "All rights reserved · Jane Doe"


def test_credit_single_tags_pass_through():
    assert _credit_of(Artist="Jane Doe") == "Jane Doe"
    assert _credit_of(Copyright="© 2026") == "© 2026"
    assert _credit_of() is None


def test_credit_falls_back_to_xmp_dublin_core():
    # ExifTool returns XMP-dc:Creator as a list.
    assert _credit_of(Creator=["Jane", "Joe"], Rights="© 2026") == \
        "© 2026 · Jane, Joe"


def test_geojson_carries_view_and_credit_props():
    pts = [
        PhotoPoint(lat=1.0, lon=2.0, alt=None, name="pano.jpg", is_pano=True,
                   pano_yaw=-30.0, pano_pitch=10.0, pano_hfov=90.0,
                   credit="© 2026 Jane"),
        PhotoPoint(lat=3.0, lon=4.0, alt=None, name="flat.jpg",
                   credit="© 2026 Jane"),
    ]
    by_name = {
        f["properties"]["name"]: f["properties"]
        for f in photos_to_geojson(pts)["features"]
    }
    pano = by_name["pano.jpg"]
    assert (pano["yaw"], pano["pitch"], pano["hfov"]) == (-30.0, 10.0, 90.0)
    assert pano["credit"] == "© 2026 Jane"
    flat = by_name["flat.jpg"]
    assert flat["credit"] == "© 2026 Jane"
    assert "yaw" not in flat and "pitch" not in flat and "hfov" not in flat


def test_geojson_omits_view_props_when_unset():
    props = photos_to_geojson([_PANO_POINT])["features"][0]["properties"]
    assert props["pano"] is True
    for key in ("yaw", "pitch", "hfov", "credit"):
        assert key not in props


def test_kml_description_includes_credit():
    pts = [PhotoPoint(lat=1.0, lon=2.0, alt=None, name="a.jpg",
                      credit="© 2026 <Jane>")]
    kml = photos_to_kml(pts, title="t")
    root = ET.fromstring(kml)  # escaped credit keeps the XML well-formed
    desc = next(root.iter(f"{_KML_NS}Placemark")).find(f"{_KML_NS}description")
    # Balloons render CDATA as HTML, so the angle brackets must arrive escaped.
    assert "© 2026 &lt;Jane&gt;" in desc.text


def test_redact_photo_points_fuzz_rounds_to_3_decimals():
    from dji_metadata_embedder.geo.photomap import redact_photo_points

    pts = [PhotoPoint(lat=60.170278, lon=24.952222, alt=95.3, name="a.jpg")]
    out = redact_photo_points(pts, "fuzz")
    assert (out[0].lat, out[0].lon) == (60.170, 24.952)
    assert out[0].alt == 95.3 and out[0].name == "a.jpg"
    assert pts[0].lat == 60.170278  # input not mutated


def test_redact_photo_points_none_is_identity():
    from dji_metadata_embedder.geo.photomap import redact_photo_points

    pts = [PhotoPoint(lat=60.170278, lon=24.952222, alt=None, name="a.jpg")]
    assert redact_photo_points(pts, "none") == pts
