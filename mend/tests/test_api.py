"""API integration tests for MEND FastAPI application."""

from fastapi.testclient import TestClient
from mend.api.main import app

client = TestClient(app)


def test_api_status():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert "target_repository" in data
    assert "gemma_runtime" in data
    assert data["target_repository"]["name"] == "LinkWatch"


def test_api_scan():
    resp = client.get("/api/scan")
    assert resp.status_code == 200
    data = resp.json()
    assert "dependencies" in data
    assert "pyproject.toml" in data["manifests_found"]
    assert "jinja2" in data["dependencies"]


def test_api_rules():
    resp = client.get("/api/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    rule_ids = [f["rule_id"] for f in data]
    assert "RULE-COMPAT-001" in rule_ids


def test_api_capsule_generation():
    resp = client.post("/api/capsule/generate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["$schema_version"] == "1.0.0"
    assert "CAPSULE-LINKWATCH" in data["capsule_id"]
    assert "summary_metrics" in data


def test_api_capsule_download():
    resp = client.get("/api/capsule/download")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]


def test_api_capsule_html_report():
    resp = client.get("/api/capsule/report")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "MEND Dependency Exit Capsule" in resp.text


def test_api_recommend_unknown_package():
    resp = client.post("/api/recommend", json={"package_name": "non_existent_pkg_12345"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_recommend_timeout_handling():
    # An impossible 0.0001s timeout should immediately trigger clean 504 Timeout handling
    resp = client.post("/api/recommend", json={"package_name": "appdirs", "timeout_seconds": 0.0001})
    assert resp.status_code in [504, 503]
    assert "timed out" in resp.json()["detail"].lower() or "reach ollama" in resp.json()["detail"].lower()


def test_api_scan_diff():
    resp = client.get("/api/scan/diff")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_drift" in data
    assert "source_sha256_current" in data
    assert "total_dependencies_current" in data
    assert data["total_dependencies_current"] >= 20


def test_api_ledger():
    resp = client.get("/api/ledger")
    assert resp.status_code == 200
    data = resp.json()
    assert "stage_distribution" in data
    assert "ledger_sha256" in data
    assert "entries" in data
    assert len(data["entries"]) >= 20
    stages = [e["stage"] for e in data["entries"]]
    assert "OBSERVED" in stages


def test_api_integrity():
    resp = client.get("/api/integrity")
    assert resp.status_code == 200
    data = resp.json()
    assert "source_snapshot_sha256" in data
    assert len(data["source_snapshot_sha256"]) == 64
    assert "candidate_runner_safety" in data
    assert "disclaimer" in data


def test_api_repositories_list():
    resp = client.get("/api/repositories")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_repo_id" in data
    assert data["active_repo_id"] == "linkwatch"
    assert "repositories" in data
    repos = data["repositories"]
    assert any(r["id"] == "linkwatch" and r["is_official"] for r in repos)


def test_api_repositories_select_invalid():
    resp = client.post("/api/repositories/select", json={"repo_id": "non_existent_repo_id"})
    assert resp.status_code == 404


def test_api_repositories_add_invalid_url():
    resp = client.post("/api/repositories/add", json={"url": "not-a-valid-github-url"})
    assert resp.status_code == 400
    assert "Invalid GitHub URL" in resp.json()["detail"]


def test_api_recommendations_list():
    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


