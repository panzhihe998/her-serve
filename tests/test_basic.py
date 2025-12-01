# tests/test_basic.py

from fastapi.testclient import TestClient
from app.main import app

# TestClient 是 FastAPI 自带的测试客户端，用来在代码里“假装发 HTTP 请求”
client = TestClient(app)


def test_health():
    """
    验证 /health 接口是否正常工作。
    这是我们的最基础“心跳测试（health check）”。
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # 要求返回 {"status": "ok"}
    assert data.get("status") == "ok"


def test_root():
    """
    验证根路径 / 是否存在，并且返回 JSON。
    不要求内容很复杂，只要能正常返回 200 就行。
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    # 确认字段里有 message 这个 key
    assert "message" in data
