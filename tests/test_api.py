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

@pytest.mark.asyncio
async def test_group_sparkline_one_square_per_round_using_average():
    from netmap.db import get_history_db
    import time

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        # Create group and 2 hosts
        await client.post("/api/admin/groups", json={"name": "Cluster-App", "aggregation_mode": "any"})
        h1 = (await client.post("/api/admin/hosts", json={"name": "app-1", "ip_address": "10.0.0.1", "location": "DC-Main", "grouping": "Cluster-App"})).json()["id"]
        h2 = (await client.post("/api/admin/hosts", json={"name": "app-2", "ip_address": "10.0.0.2", "location": "DC-Main", "grouping": "Cluster-App"})).json()["id"]

        now = int(time.time())
        # Round 1: Both hosts UP (timestamps differ by 1s: now - 300, now - 299)
        # Round 2: 1 host UP, 1 host DOWN (timestamps differ by 2s: now - 200, now - 198) -> Average = 0.5 (Yellow)
        # Round 3: Both hosts DOWN (timestamps: now - 100, now - 100) -> Average = 0.0 (Red)
        history_entries = [
            (h1, now - 300, 1, 2.5, None),
            (h2, now - 299, 1, 3.0, None),
            (h1, now - 200, 1, 2.0, None),
            (h2, now - 198, 0, None, "Timeout"),
            (h1, now - 100, 0, None, "Timeout"),
            (h2, now - 100, 0, None, "Timeout"),
        ]
        async with get_history_db() as db:
            await db.executemany(
                "INSERT INTO ping_history (host_id, timestamp, is_up, rtt_ms, error_msg) VALUES (?, ?, ?, ?, ?)",
                history_entries
            )
            await db.commit()

        tree_res = await client.get("/api/tree")
        assert tree_res.status_code == 200
        tree = tree_res.json()
        loc = next(l for l in tree["locations"] if l["name"] == "DC-Main")
        grp = loc["roots"][0]

        # Verify: Exactly 3 squares for the 3 polling rounds (NOT 6 squares!)
        sparkline = grp["sparkline_30m"]
        assert len(sparkline) == 3, f"Expected exactly 3 squares (1 per round), got {len(sparkline)}"

        # Round 1: Both UP -> Green square
        assert sparkline[0]["up"] is True
        assert sparkline[0]["degraded"] is False
        assert sparkline[0]["hosts_up"] == 2
        assert sparkline[0]["hosts_total"] == 2

        # Round 2: 1 UP, 1 DOWN -> Yellow square (degraded, average = 0.5)
        assert sparkline[1]["up"] is True
        assert sparkline[1]["degraded"] is True
        assert sparkline[1]["avg"] == 0.5
        assert sparkline[1]["hosts_up"] == 1
        assert sparkline[1]["hosts_total"] == 2

        # Round 3: Both DOWN -> Red square (down, average = 0.0)
        assert sparkline[2]["up"] is False
        assert sparkline[2]["degraded"] is False
        assert sparkline[2]["avg"] == 0.0
        assert sparkline[2]["hosts_up"] == 0
        assert sparkline[2]["hosts_total"] == 2

@pytest.mark.asyncio
async def test_reverse_proxy_subpath_support():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Standalone root rendering
        root_res = await client.get("/")
        assert root_res.status_code == 200
        assert 'window.NETMAP_BASE = "";' in root_res.text
        assert 'href="/static/css/netmap.css' in root_res.text

        # 2. Behind proxy with X-Forwarded-Prefix: /netmap (stripped path)
        proxied_res = await client.get("/", headers={"X-Forwarded-Prefix": "/netmap"})
        assert proxied_res.status_code == 200
        assert 'window.NETMAP_BASE = "/netmap";' in proxied_res.text
        assert 'href="/netmap/static/css/netmap.css' in proxied_res.text
        assert 'src="/netmap/static/js/app.js' in proxied_res.text
        assert 'href="/netmap/" class="brand"' in proxied_res.text

        # 3. Behind proxy with X-Forwarded-Prefix: /netmap (stripped static asset requests from Nginx)
        static_app_js = await client.get("/static/js/app.js", headers={"X-Forwarded-Prefix": "/netmap"})
        assert static_app_js.status_code == 200
        assert "NETMAP_BASE" in static_app_js.text

        static_i18n_js = await client.get("/static/js/i18n.js", headers={"X-Forwarded-Prefix": "/netmap"})
        assert static_i18n_js.status_code == 200

        # Unstripped static asset requests
        static_unstripped = await client.get("/netmap/static/js/app.js", headers={"X-Forwarded-Prefix": "/netmap"})
        assert static_unstripped.status_code == 200

        # 4. Behind proxy with X-Forwarded-Prefix: /netmap (unstripped subpath)
        subpath_api = await client.get("/netmap/api/status", headers={"X-Forwarded-Prefix": "/netmap"})
        assert subpath_api.status_code == 200
        assert "total_hosts" in subpath_api.json()

        # 5. Trailing slash redirect for exact prefix
        redir_res = await client.get("/netmap", headers={"X-Forwarded-Prefix": "/netmap"}, follow_redirects=False)
        assert redir_res.status_code == 307
        assert redir_res.headers.get("location") == "/netmap/"

        # 5. Admin page under subpath
        admin_res = await client.get("/netmap/admin", headers={"X-Forwarded-Prefix": "/netmap"})
        assert admin_res.status_code == 200
        assert 'window.NETMAP_BASE = "/netmap";' in admin_res.text
        assert 'href="/netmap/api/admin/csv/template"' in admin_res.text
        assert 'href="/netmap/api/admin/csv/export"' in admin_res.text

        # 6. Session cookie scoped to subpath
        login_res = await client.post(
            "/netmap/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            headers={"X-Forwarded-Prefix": "/netmap", "X-Forwarded-Proto": "https"}
        )
        assert login_res.status_code == 200
        cookie_header = login_res.headers.get("set-cookie", "")
        assert "Path=/netmap" in cookie_header
        assert "Secure" in cookie_header

@pytest.mark.asyncio
async def test_admin_sorting_and_location_filtering():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert login_res.status_code == 200

        await client.post("/api/admin/hosts", json={"name": "Host-Z", "ip_address": "10.0.1.20", "location": "Site-B"})
        await client.post("/api/admin/hosts", json={"name": "Host-A", "ip_address": "10.0.1.2", "location": "Site-A", "grouping": "Grp-1"})
        await client.post("/api/admin/hosts", json={"name": "Host-M", "ip_address": "10.0.1.10", "location": "Site-C", "grouping": "Grp-2"})

        res_name_asc = await client.get("/api/admin/hosts?sort=name&dir=asc")
        assert res_name_asc.status_code == 200
        names_asc = [h["name"] for h in res_name_asc.json()["hosts"]]
        assert names_asc == ["Host-A", "Host-M", "Host-Z"]

        res_name_desc = await client.get("/api/admin/hosts?sort=name&dir=desc")
        assert res_name_desc.status_code == 200
        names_desc = [h["name"] for h in res_name_desc.json()["hosts"]]
        assert names_desc == ["Host-Z", "Host-M", "Host-A"]

        res_loc_asc = await client.get("/api/admin/hosts?sort=location&dir=asc")
        assert res_loc_asc.status_code == 200
        locs_asc = [h["location"] for h in res_loc_asc.json()["hosts"]]
        assert locs_asc == ["Site-A", "Site-B", "Site-C"]

        res_grp = await client.get("/api/admin/hosts?sort=grouping&dir=asc")
        assert res_grp.status_code == 200

        res_grp_name = await client.get("/api/admin/groups?sort=name&dir=desc")
        assert res_grp_name.status_code == 200

        res_tree_loc = await client.get("/api/tree?location_filter=Site-A")
        assert res_tree_loc.status_code == 200
        tree_locs = res_tree_loc.json()["locations"]
        assert len(tree_locs) == 1
        assert tree_locs[0]["name"] == "Site-A"

        res_index = await client.get("/?location=Site-A")
        assert res_index.status_code == 200
        assert "location-tabs" in res_index.text

@pytest.mark.asyncio
async def test_location_warning_levels_and_timeline_pagination():
    import time
    from netmap.ping_engine import ping_engine, PingResult
    from netmap.db import get_history_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        # Create hosts in Location-Yellow (2 hosts) and Location-Red (4 hosts)
        y1_res = await client.post("/api/admin/hosts", json={"name": "Y1", "ip_address": "10.1.1.1", "location": "Loc-Yellow"})
        y2_res = await client.post("/api/admin/hosts", json={"name": "Y2", "ip_address": "10.1.1.2", "location": "Loc-Yellow"})
        y1_id = y1_res.json()["id"]
        y2_id = y2_res.json()["id"]

        r1_res = await client.post("/api/admin/hosts", json={"name": "R1", "ip_address": "10.2.1.1", "location": "Loc-Red"})
        r2_res = await client.post("/api/admin/hosts", json={"name": "R2", "ip_address": "10.2.1.2", "location": "Loc-Red"})
        r3_res = await client.post("/api/admin/hosts", json={"name": "R3", "ip_address": "10.2.1.3", "location": "Loc-Red"})
        r4_res = await client.post("/api/admin/hosts", json={"name": "R4", "ip_address": "10.2.1.4", "location": "Loc-Red"})
        r1_id = r1_res.json()["id"]
        r2_id = r2_res.json()["id"]
        r3_id = r3_res.json()["id"]
        r4_id = r4_res.json()["id"]

        now = int(time.time())

        # Set status: Loc-Yellow 1/2 down (50%) -> alert_level == "yellow"
        ping_engine.latest_host_status[y1_id] = PingResult(host_id=y1_id, is_up=True, rtt_ms=10.0, timestamp=now)
        ping_engine.latest_host_status[y2_id] = PingResult(host_id=y2_id, is_up=False, rtt_ms=None, error_msg="Timeout", timestamp=now)

        # Set status: Loc-Red 3/4 down (75%) -> alert_level == "red"
        ping_engine.latest_host_status[r1_id] = PingResult(host_id=r1_id, is_up=True, rtt_ms=15.0, timestamp=now)
        ping_engine.latest_host_status[r2_id] = PingResult(host_id=r2_id, is_up=False, rtt_ms=None, error_msg="Timeout", timestamp=now)
        ping_engine.latest_host_status[r3_id] = PingResult(host_id=r3_id, is_up=False, rtt_ms=None, error_msg="Timeout", timestamp=now)
        ping_engine.latest_host_status[r4_id] = PingResult(host_id=r4_id, is_up=False, rtt_ms=None, error_msg="Timeout", timestamp=now)

        # Fetch /api/tree and verify alert levels
        tree_res = await client.get("/api/tree")
        assert tree_res.status_code == 200
        tree_data = tree_res.json()
        loc_map = {l["name"]: l for l in tree_data["locations"]}

        assert loc_map["Loc-Yellow"]["alert_level"] == "yellow"
        assert loc_map["Loc-Yellow"]["device_total"] == 2
        assert loc_map["Loc-Yellow"]["device_down"] == 1
        assert loc_map["Loc-Yellow"]["device_down_pct"] == 50.0

        assert loc_map["Loc-Red"]["alert_level"] == "red"
        assert loc_map["Loc-Red"]["device_total"] == 4
        assert loc_map["Loc-Red"]["device_down"] == 3
        assert loc_map["Loc-Red"]["device_down_pct"] == 75.0

        # Insert historical polls into ping_history across multiple days
        past_72h = now - (72 * 3600)
        past_48h = now - (48 * 3600)
        past_24h = now - (24 * 3600)

        async with get_history_db() as db:
            await db.execute("INSERT INTO ping_history (host_id, timestamp, is_up, rtt_ms, error_msg) VALUES (?, ?, ?, ?, ?)",
                            (y1_id, past_72h, 1, 12.0, None))
            await db.execute("INSERT INTO ping_history (host_id, timestamp, is_up, rtt_ms, error_msg) VALUES (?, ?, ?, ?, ?)",
                            (y1_id, past_48h, 1, 14.0, None))
            await db.execute("INSERT INTO ping_history (host_id, timestamp, is_up, rtt_ms, error_msg) VALUES (?, ?, ?, ?, ?)",
                            (y1_id, past_24h, 0, None, "Timeout"))
            await db.execute("INSERT INTO ping_history (host_id, timestamp, is_up, rtt_ms, error_msg) VALUES (?, ?, ?, ?, ?)",
                            (y1_id, now - 60, 1, 11.5, None))
            await db.commit()

        # Query latest 48h (default)
        t_res1 = await client.get(f"/api/hosts/{y1_id}/timeline")
        assert t_res1.status_code == 200
        tl1 = t_res1.json()["timeline"]
        assert tl1["period_hours"] == 48
        assert tl1["has_earlier"] is True
        assert tl1["has_later"] is False
        assert tl1["earliest_time"] == past_72h

        # Query past block using end_time
        t_res2 = await client.get(f"/api/hosts/{y1_id}/timeline?hours=48&end_time={past_24h}")
        assert t_res2.status_code == 200
        tl2 = t_res2.json()["timeline"]
        assert tl2["period_hours"] == 48
        assert tl2["end_time"] == past_24h
        assert tl2["has_later"] is True

@pytest.mark.asyncio
async def test_index_page_collapse_controls():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text
        assert "btn-collapse-all" in html
        assert "btn-expand-all" in html
        assert "collapseAllLocations" in html
        assert "expandAllLocations" in html



