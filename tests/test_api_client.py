import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api_client import api_client

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_policy_info_endpoint():
    response = client.get("/api/policy/info")
    assert response.status_code == 200
    data = response.json()
    assert data["policy_reference"] == "SRV-POL-001"
    assert data["total_chunks_indexed"] > 0

def test_auth_login_endpoint():
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data

def test_chat_policy_endpoint():
    response = client.post("/api/chat", json={
        "message": "What is the maximum price allowed for creating a service?"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "500,000" in data["response"] or "500000" in data["response"]

def test_chat_unauthorized_update_endpoint():
    response = client.post("/api/chat", json={
        "message": "Update my phone number to 01712345678.",
        "user_context": {"can_update_profile": False}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "permission_denied"
    assert data.get("details", {}).get("api_called") is False

