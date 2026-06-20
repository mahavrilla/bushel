from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_preflight_allows_vite_origin():
    """A browser preflight from the Vite dev server origin must be allowed."""
    resp = client.options(
        "/recipes/import",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_actual_request_carries_cors_header():
    resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
