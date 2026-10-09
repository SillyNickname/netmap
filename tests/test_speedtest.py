"""
NetMap - Speedtest Feature Test Suite
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import asyncio
import time
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from netmap.config import Config
from netmap.db import init_databases, get_hosts_db
from netmap.main import app
from netmap.speedtest_daemon import SpeedtestProtocol


@pytest_asyncio.fixture(autouse=True)
async def setup_speedtest_test_env(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "test_speedtest_netmap.cfg"
    hosts_db_path = tmp_path / "test_hosts.db"
    history_db_path = tmp_path / "test_history.db"

    test_cfg_path.write_text(f"""[server]
host = 127.0.0.1
port = 8080
secret_key = test-speedtest-secret-key
url_prefix = 

[poller]
interval_seconds = 30
ping_threads = 5
ping_timeout = 1
ping_count = 1

[history]
retention_hours = 24

[speedtest]
enabled = true
server_url = 
duration_seconds = 5
visitor_cooldown_hours = 2

[database]
hosts_db = {hosts_db_path}
history_db = {history_db_path}
""")

    test_config = Config(config_path=test_cfg_path)
    monkeypatch.setattr("netmap.config.config", test_config)
    monkeypatch.setattr("netmap.db.config", test_config)
    monkeypatch.setattr("netmap.api.speedtest.config", test_config)

    await init_databases()
    return test_config


@pytest.mark.asyncio
async def test_speedtest_config_and_ping():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Config endpoint
        cfg_res = await client.get("/api/speedtest/config")
        assert cfg_res.status_code == 200
        data = cfg_res.json()
        assert data["enabled"] is True
        assert data["duration_seconds"] == 5
        assert data["can_test"] is True
        assert data["cooldown_remaining_seconds"] == 0
        assert data["visitor_cooldown_hours"] == 2

        # Ping endpoint
        ping_res = await client.get("/api/speedtest/ping")
        assert ping_res.status_code == 200
        pdata = ping_res.json()
        assert pdata["status"] == "ok"
        assert "timestamp" in pdata
        assert ping_res.headers.get("content-encoding") == "identity"


@pytest.mark.asyncio
async def test_speedtest_download_and_upload_streaming():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Download endpoint (request 128KB)
        dl_res = await client.get("/api/speedtest/download?bytes=131072")
        assert dl_res.status_code == 200
        assert dl_res.headers.get("content-encoding") == "identity"
        assert dl_res.headers.get("content-type") == "application/octet-stream"
        assert len(dl_res.content) == 131072

        # Upload endpoint (send 64KB)
        payload = b"X" * 65536
        ul_res = await client.post(
            "/api/speedtest/upload",
            content=payload,
            headers={"Content-Type": "application/octet-stream"}
        )
        assert ul_res.status_code == 200
        udata = ul_res.json()
        assert udata["status"] == "ok"
        assert udata["received_bytes"] == 65536
        assert udata["speed_mbps"] > 0


@pytest.mark.asyncio
async def test_speedtest_visitor_results_and_cooldown():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Visitor posts first test result
        payload = {
            "ping_ms": 12.5,
            "jitter_ms": 1.2,
            "download_max_mbps": 95.4,
            "download_avg_mbps": 88.2,
            "upload_max_mbps": 45.0,
            "upload_avg_mbps": 40.1
        }
        res1 = await client.post(
            "/api/speedtest/results",
            json=payload,
            headers={"X-Forwarded-For": "192.168.10.55"}
        )
        assert res1.status_code == 200
        r1_data = res1.json()
        assert r1_data["status"] == "ok"
        assert r1_data["client_ip"] == "192.168.10.55"
        assert r1_data["role"] == "visitor"

        # 2. Config endpoint now reflects active visitor cooldown for that IP
        cfg_res = await client.get(
            "/api/speedtest/config",
            headers={"X-Forwarded-For": "192.168.10.55"}
        )
        assert cfg_res.status_code == 200
        cfg_data = cfg_res.json()
        assert cfg_data["can_test"] is False
        assert cfg_data["cooldown_remaining_seconds"] > 7000  # ~7200 seconds (2 hours)

        # 3. Visitor attempts second test immediately -> HTTP 429 Too Many Requests
        res2 = await client.post(
            "/api/speedtest/results",
            json=payload,
            headers={"X-Forwarded-For": "192.168.10.55"}
        )
        assert res2.status_code == 429

        # 4. Another distinct IP is NOT subject to the first IP's cooldown
        cfg_res2 = await client.get(
            "/api/speedtest/config",
            headers={"X-Forwarded-For": "192.168.10.56"}
        )
        assert cfg_res2.status_code == 200
        assert cfg_res2.json()["can_test"] is True


@pytest.mark.asyncio
async def test_speedtest_operator_admin_bypass_cooldown_and_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as operator
        login_res = await client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
        assert login_res.status_code == 200

        # 2. Operator posts test result from an IP that was in cooldown
        payload = {
            "ping_ms": 15.0,
            "jitter_ms": 2.0,
            "download_max_mbps": 120.0,
            "download_avg_mbps": 110.0,
            "upload_max_mbps": 50.0,
            "upload_avg_mbps": 48.0
        }
        res_op1 = await client.post(
            "/api/speedtest/results",
            json=payload,
            headers={"X-Forwarded-For": "10.0.0.99"}
        )
        assert res_op1.status_code == 200
        assert res_op1.json()["role"] == "operator"

        # 3. Operator immediately posts another test result from same IP -> succeeds!
        res_op2 = await client.post(
            "/api/speedtest/results",
            json=payload,
            headers={"X-Forwarded-For": "10.0.0.99"}
        )
        assert res_op2.status_code == 200
        assert res_op2.json()["role"] == "operator"

        # 4. Operator can query and search speedtest results
        list_res = await client.get("/api/speedtest/results?search_ip=10.0.0.99")
        assert list_res.status_code == 200
        ldata = list_res.json()
        assert ldata["total"] >= 2
        assert len(ldata["results"]) >= 2
        assert ldata["results"][0]["client_ip"] == "10.0.0.99"


@pytest.mark.asyncio
async def test_speedtest_admin_delete_results():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a result
        payload = {
            "ping_ms": 20.0,
            "jitter_ms": 1.0,
            "download_max_mbps": 50.0,
            "download_avg_mbps": 45.0,
            "upload_max_mbps": 20.0,
            "upload_avg_mbps": 18.0
        }
        res = await client.post(
            "/api/speedtest/results",
            json=payload,
            headers={"X-Forwarded-For": "172.16.0.10"}
        )
        result_id = res.json()["id"]

        # Guest cannot delete -> 401
        del_guest = await client.delete(f"/api/speedtest/results/{result_id}")
        assert del_guest.status_code == 401

        # Login as operator: operator cannot delete (requires admin) -> 403
        await client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
        del_op = await client.delete(f"/api/speedtest/results/{result_id}")
        assert del_op.status_code == 403

        # Login as admin: admin can delete -> 200
        await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        del_admin = await client.delete(f"/api/speedtest/results/{result_id}")
        assert del_admin.status_code == 200
        assert del_admin.json()["deleted_id"] == result_id


@pytest.mark.asyncio
async def test_speedtest_page_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/speedtest")
        assert res.status_code == 200
        assert "NetMap - Teste de Velocidade / Speedtest" in res.text
        assert "speedtest.js" in res.text


@pytest.mark.asyncio
async def test_speedtest_standalone_daemon():
    # Spin up daemon on local test port
    loop = asyncio.get_running_loop()
    server = await loop.create_server(
        lambda: SpeedtestProtocol(),
        "127.0.0.1",
        18081
    )
    async with server:
        async with AsyncClient(base_url="http://127.0.0.1:18081", trust_env=False) as client:
            # 1. Health check
            h_res = await client.get("/health")
            assert h_res.status_code == 200
            assert h_res.json()["service"] == "netmap-speedtest-daemon"

            # 2. Ping check
            p_res = await client.get("/ping")
            assert p_res.status_code == 200
            assert "timestamp" in p_res.json()

            # 3. Download check (64 KB)
            d_res = await client.get("/download?bytes=65536")
            assert d_res.status_code == 200
            assert len(d_res.content) == 65536

            # 4. Upload check (32 KB)
            u_res = await client.post("/upload", content=b"Y" * 32768)
            assert u_res.status_code == 200
            assert u_res.json()["received_bytes"] == 32768
