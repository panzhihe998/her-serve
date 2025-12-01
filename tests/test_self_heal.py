# tests/test_self_heal.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_self_heal_basic():
    res = client.get("/self_heal")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "ok"
    assert "actions" in data
    assert isinstance(data["actions"], list)
