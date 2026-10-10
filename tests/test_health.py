from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None, environment="test")), base_url="http://127.0.0.1:8000") as test_client:
        yield test_client


def test_live_without_models_or_database(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive", "project_id": "GOV-CS-028", "phase": 12}
    UUID(response.headers["x-request-id"])


def test_ready_reports_only_current_dependencies(client):
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["required_dependencies"]["postgresql"] == "unavailable_or_migrations_missing"
    assert response.json()["optional_services"] == {"chroma": "separate_index_service", "ollama": "separate_local_rag_worker"}


def test_request_ids_are_unique_and_client_input_is_not_trusted(client):
    first = client.get("/health/live", headers={"X-Request-ID": "untrusted"})
    second = client.get("/health/live")
    assert first.headers["x-request-id"] != "untrusted"
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert first.headers["cache-control"] == "no-store"


def test_not_found_has_consistent_error_and_request_id(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert response.json()["error"]["code"] == "http_error"


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173"])
def test_allowed_browser_origin(client, origin):
    response = client.get("/health/ready", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_unapproved_origin_gets_no_permission(client):
    response = client.get("/health/ready", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight(client):
    response = client.options("/health/ready", headers={
        "Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    denied = client.options("/health/ready", headers={
        "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET",
    })
    assert denied.status_code == 400


@pytest.mark.parametrize("origins", [["*"], ["https://example.com"], [], ["http://localhost:5173/path"]])
def test_invalid_cors_configuration_rejected(origins):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=origins)


def test_invalid_environment_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")


def test_error_paths_do_not_leak_input_or_internal_details():
    app = create_app(Settings(_env_file=None, environment="test"))

    @app.get("/test/validate")
    async def validate(value: int):
        return {"value": value}

    @app.get("/test/fail")
    async def fail():
        raise RuntimeError("private-internal-detail")

    @app.get("/test/http")
    async def http():
        raise HTTPException(status_code=429, detail="Try later", headers={"Retry-After": "1"})

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        invalid = client.get("/test/validate?value=private-input")
        assert invalid.status_code == 422
        assert "private-input" not in invalid.text
        failed = client.get("/test/fail", headers={"Origin": "http://127.0.0.1:5173"})
        assert failed.status_code == 500
        assert "private-internal-detail" not in failed.text
        assert failed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        assert failed.json()["error"]["request_id"] == failed.headers["x-request-id"]
        limited = client.get("/test/http")
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "1"
