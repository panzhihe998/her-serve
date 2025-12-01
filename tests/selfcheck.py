from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_selfcheck():
    res = client.get("/selfcheck")
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "ok"

    checks = data["checks"]

    # 检查几个关键项目
    assert "root" in checks
    assert "openai_key_exists" in checks
    assert "firestore" in checks
    assert "model_name_valid" in checks
