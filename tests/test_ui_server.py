"""Smoke tests for the dji-embed web UI server."""

from __future__ import annotations

from pathlib import Path

import pytest

flask = pytest.importorskip("flask")

from dji_metadata_embedder.ui.server import create_app  # noqa: E402

TOKEN = "unit-test-token"


@pytest.fixture()
def client():
    app = create_app(TOKEN)
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def _auth(client):
    """Seed the auth cookie so subsequent requests are authenticated."""
    resp = client.get(f"/?t={TOKEN}")
    assert resp.status_code == 200
    return resp


def test_home_requires_token(client):
    resp = client.get("/")
    assert resp.status_code == 403


def test_home_with_token_sets_cookie_and_renders(client):
    resp = _auth(client)
    assert "djiembed_token" in resp.headers.get("Set-Cookie", "")
    assert b"djiembed-token" in resp.data


def test_security_headers_present(client):
    resp = _auth(client)
    assert "Content-Security-Policy" in resp.headers
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def test_public_routes_bypass_token(client):
    healthz = client.get("/healthz")
    assert healthz.status_code == 200
    assert healthz.get_json() == {"ok": True}

    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert b"serviceWorker" in sw.data or b"addEventListener" in sw.data

    manifest = client.get("/static/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.get_json()["name"] == "dji-embed"


def test_api_rejects_unauth_requests(client):
    resp = client.get("/api/doctor")
    assert resp.status_code == 403


def test_api_accepts_header_token(client):
    resp = client.get("/api/doctor", headers={"X-DJIEmbed-Token": TOKEN})
    assert resp.status_code == 200
    body = resp.get_json()
    assert {"app_version", "system", "tools", "dependencies_ok", "missing"} <= body.keys()


def test_api_accepts_cookie_after_seeded(client):
    _auth(client)
    resp = client.get("/api/doctor")
    assert resp.status_code == 200


def test_api_embed_requires_directory(client):
    _auth(client)
    resp = client.post("/api/jobs/embed", json={})
    assert resp.status_code == 400
    assert "directory" in resp.get_json()["error"].lower()


def test_api_embed_rejects_non_directory(client, tmp_path):
    _auth(client)
    bogus = tmp_path / "does-not-exist"
    resp = client.post("/api/jobs/embed", json={"directory": str(bogus)})
    assert resp.status_code == 400


def test_api_validate_rejects_non_directory(client, tmp_path):
    _auth(client)
    resp = client.post("/api/validate", json={"directory": str(tmp_path / "nope")})
    assert resp.status_code == 400


def test_api_validate_empty_directory(client, tmp_path):
    _auth(client)
    resp = client.post("/api/validate", json={"directory": str(tmp_path)})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_files"] == 0
    assert body["valid_pairs"] == 0


def test_api_convert_requires_known_format(client, tmp_path):
    _auth(client)
    srt = tmp_path / "tiny.SRT"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    resp = client.post(
        "/api/convert", json={"srt": str(srt), "format": "bogus"}
    )
    assert resp.status_code == 400


def test_api_check_missing_path(client):
    _auth(client)
    resp = client.post("/api/check", json={"path": "/definitely/not/here"})
    assert resp.status_code == 400


def test_job_not_found(client):
    _auth(client)
    resp = client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404
    resp = client.post("/api/jobs/nonexistent/cancel")
    assert resp.status_code == 404


SAMPLES = Path(__file__).resolve().parents[1] / "samples"
AIR3 = SAMPLES / "air3" / "clip.SRT"


def test_api_geojson_returns_feature_collection(client):
    _auth(client)
    resp = client.post("/api/geojson", json={"srt": str(AIR3)})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "FeatureCollection"
    assert any(
        f["geometry"] and f["geometry"]["type"] == "LineString" for f in body["features"]
    )


def test_api_geojson_requires_srt(client):
    _auth(client)
    resp = client.post("/api/geojson", json={})
    assert resp.status_code == 400


def test_api_geojson_rejects_missing_file(client):
    _auth(client)
    resp = client.post("/api/geojson", json={"srt": "/definitely/not/here.SRT"})
    assert resp.status_code == 400


def test_api_geojson_redact_drop_null_geometry(client):
    _auth(client)
    resp = client.post("/api/geojson", json={"srt": str(AIR3), "redact": "drop"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["features"]) == 1
    assert body["features"][0]["geometry"] is None


def test_api_geojson_redact_fuzz_coarsens(client):
    _auth(client)
    resp = client.post("/api/geojson", json={"srt": str(AIR3), "redact": "fuzz"})
    body = resp.get_json()
    line = next(
        f for f in body["features"]
        if f["geometry"] and f["geometry"]["type"] == "LineString"
    )
    lon, lat = line["geometry"]["coordinates"][0][:2]
    assert lat == round(lat, 3) and lon == round(lon, 3)


def test_api_geojson_rejects_unauth(client):
    resp = client.post("/api/geojson", json={"srt": str(AIR3)})
    assert resp.status_code == 403


def test_csp_allows_osm_tiles(client):
    resp = _auth(client)
    assert "tile.openstreetmap.org" in resp.headers["Content-Security-Policy"]
