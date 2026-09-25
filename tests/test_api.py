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

@pytest.mark.asyncio
async def test_grouping_consolidation_and_degraded_state():
    from netmap.ping_engine import ping_engine, PingResult

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as admin
        await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        # Create group
        grp_res = await client.post("/api/admin/groups", json={
            "name": "Web-Cluster",
            "aggregation_mode": "any",
            "description": "High availability web frontend"
        })
        assert grp_res.status_code == 200

        # Create 2 member hosts under the same location and parent
        h1_res = await client.post("/api/admin/hosts", json={
            "name": "web-node-01",
            "ip_address": "192.168.1.10",
            "location": "Datacenter Alpha",
            "grouping": "Web-Cluster"
        })
        assert h1_res.status_code == 200
        h1_id = h1_res.json()["id"]

        h2_res = await client.post("/api/admin/hosts", json={
            "name": "web-node-02",
            "ip_address": "192.168.1.11",
            "location": "Datacenter Alpha",
            "grouping": "Web-Cluster"
        })
        assert h2_res.status_code == 200
        h2_id = h2_res.json()["id"]

        # Simulate: Node 1 is UP, Node 2 is DOWN (Timed out)
        ping_engine.latest_host_status[h1_id] = PingResult(
            host_id=h1_id,
            is_up=True,
            rtt_ms=12.5
        )
        ping_engine.latest_host_status[h2_id] = PingResult(
            host_id=h2_id,
            is_up=False,
            rtt_ms=None,
            error_msg="Timeout"
        )

        # 1. Verify /api/tree: Hosts replaced by Grouping name and marked as partially up (is_degraded = True)
        tree_res = await client.get("/api/tree")
        assert tree_res.status_code == 200
        tree = tree_res.json()
        loc = next(l for l in tree["locations"] if l["name"] == "Datacenter Alpha")
        assert len(loc["roots"]) == 1
        group_node = loc["roots"][0]

        # Replaced with grouping name!
        assert group_node["is_group"] is True
        assert group_node["name"] == "Web-Cluster"
        assert group_node["grouping"] == "Web-Cluster"
        assert group_node["hosts_total"] == 2
        assert group_node["hosts_up"] == 1
        # Partially up logic: not all hosts are responsive -> is_degraded is True (Yellow box)
        assert group_node["is_degraded"] is True
        assert group_node["is_up"] is True
        assert group_node["rtt_ms"] == 12.5

        # 2. Verify /api/groups/Web-Cluster/timeline
        grp_timeline_res = await client.get("/api/groups/Web-Cluster/timeline")
        assert grp_timeline_res.status_code == 200
        grp_data = grp_timeline_res.json()["group"]
        assert grp_data["name"] == "Web-Cluster"
        assert grp_data["is_degraded"] is True
        assert grp_data["hosts_up"] == 1
        assert grp_data["hosts_total"] == 2
        assert len(grp_data["members"]) == 2
        m1 = next(m for m in grp_data["members"] if m["id"] == h1_id)
        m2 = next(m for m in grp_data["members"] if m["id"] == h2_id)
        assert m1["is_up"] is True
        assert m1["rtt_ms"] == 12.5
        assert m2["is_up"] is False
        assert m2["rtt_ms"] is None

        # 3. Test when both are responsive -> is_degraded is False
        ping_engine.latest_host_status[h2_id] = PingResult(
            host_id=h2_id,
            is_up=True,
            rtt_ms=15.0
        )
        tree_res2 = await client.get("/api/tree")
        group_node2 = tree_res2.json()["locations"][0]["roots"][0]
        assert group_node2["is_degraded"] is False
        assert group_node2["is_up"] is True
        assert group_node2["hosts_up"] == 2

        # 4. Test when both are down -> is_degraded is False, is_up is False
        ping_engine.latest_host_status[h1_id] = PingResult(
            host_id=h1_id,
            is_up=False,
            rtt_ms=None
        )
        ping_engine.latest_host_status[h2_id] = PingResult(
            host_id=h2_id,
            is_up=False,
            rtt_ms=None
        )
        tree_res3 = await client.get("/api/tree")
        group_node3 = tree_res3.json()["locations"][0]["roots"][0]
        assert group_node3["is_degraded"] is False
        assert group_node3["is_up"] is False
        assert group_node3["hosts_up"] == 0

