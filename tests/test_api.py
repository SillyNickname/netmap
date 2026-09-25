import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from netmap.config import Config
from netmap.db import init_databases, get_hosts_db
from netmap.main import app

@pytest_asyncio.fixture(autouse=True)
async def setup_api_test_env(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "test_api_netmap.cfg"
    hosts_db_path = str(tmp_path / "test_api_hosts.db")
    history_db_path = str(tmp_path / "test_api_history.db")

    with open(test_cfg_path, "w") as f:
        f.write(f"""[server]
host = 127.0.0.1
port = 8888
secret_key = test-secret

[poller]
interval_seconds = 10
ping_threads = 5
ping_timeout = 1
ping_count = 1

[history]
retention_hours = 24

[database]
hosts_db = {hosts_db_path}
history_db = {history_db_path}
""")

    test_config = Config(config_path=test_cfg_path)
    monkeypatch.setattr("netmap.config.config", test_config)
    monkeypatch.setattr("netmap.db.config", test_config)
    monkeypatch.setattr("netmap.ping_engine.config", test_config)
    monkeypatch.setattr("netmap.api.admin.config", test_config)

    await init_databases()
    return test_config

@pytest.mark.asyncio
async def test_public_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check system status
        res = await client.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        assert "total_hosts" in data
        assert "is_polling" in data

        # Check tree
        res = await client.get("/api/tree")
        assert res.status_code == 200
        tree_data = res.json()
        assert "locations" in tree_data

@pytest.mark.asyncio
async def test_auth_and_force_poll_permissions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Guest user cannot force poll
        res = await client.post("/api/poll/force")
        assert res.status_code == 401

        # 2. Login as operator
        login_res = await client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
        assert login_res.status_code == 200
        assert login_res.json()["success"] is True

        # 3. Operator can force poll
        res_poll = await client.post("/api/poll/force")
        assert res_poll.status_code == 200
        assert res_poll.json()["success"] is True

        # 4. Operator cannot access admin endpoints
        res_admin = await client.get("/api/admin/settings")
        assert res_admin.status_code == 403

        # 5. Logout
        res_logout = await client.post("/api/auth/logout")
        assert res_logout.status_code == 200

        # 6. Login as admin
        login_admin = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert login_admin.status_code == 200

        # 7. Admin can access settings
        res_settings = await client.get("/api/admin/settings")
        assert res_settings.status_code == 200
        assert res_settings.json()["ping_threads"] == 5

        # 8. Admin can create a host
        create_host_res = await client.post("/api/admin/hosts", json={
            "name": "Router-1",
            "ip_address": "127.0.0.1",
            "location": "Main Datacenter",
            "description": "Core router"
        })
        assert create_host_res.status_code == 200
        host_id = create_host_res.json()["id"]

        # 9. Fetch timeline for created host
        res_timeline = await client.get(f"/api/hosts/{host_id}/timeline")
        assert res_timeline.status_code == 200
        assert res_timeline.json()["host"]["name"] == "Router-1"
